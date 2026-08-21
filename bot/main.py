

from __future__ import annotations

import asyncio
import logging
import os
import sys

import discord
from discord.ext import commands
from dotenv import load_dotenv


load_dotenv()

from bot.config import Settings, load_settings
from bot.db.session import init_db, close_db
from bot.detection.classifier import ClaimDetector
from bot.events import Events
from bot.cogs.tracking import TrackingCog
from bot.cogs.factcheck_command import FactCheckCommandCog
from bot.cogs.context_menu import ContextMenuCog



def setup_logging(level: str = "INFO") -> None:
   
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
   
    logging.getLogger("discord").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)




intents = discord.Intents.default()
intents.message_content = True  
intents.reactions = True       

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
)


_detector: ClaimDetector | None = None
_settings: Settings | None = None


@bot.event
async def on_ready() -> None:

    logger = logging.getLogger(__name__)
    logger.info("Logged in as %s (ID: %s)", bot.user, bot.user.id)  
    logger.info("Connected to %d guilds", len(bot.guilds))




def main() -> None:
  
    settings = load_settings()
    setup_logging(settings.Log_lvl)
    logger = logging.getLogger(__name__)

  
    logger.info("Starting Fact-Check Bot with config: %s", settings.secrets_safe_repr())


    logger.info("Loading spaCy en_core_web_sm model...")
    try:
        import spacy
        nlp = spacy.load("en_core_web_sm")
    except OSError as exc:
        logger.error("Failed to load spaCy model: %s", exc)
        logger.error("Run 'python -m spacy download en_core_web_sm' first.")
        sys.exit(1)


    logger.info("Loading trained claim classifier...")
    try:
        detector = ClaimDetector.load(nlp)
    except FileNotFoundError as exc:
        logger.error("Classifier not found: %s", exc)
        logger.error("Run 'python -m bot.detection.train_classifier' first.")
        sys.exit(1)


    logger.info("Initializing database at %s", settings.Database_URL)
    init_db(settings.Database_URL)


    global _detector, _settings
    _detector = detector
    _settings = settings


    logger.info("Connecting to Discord...")
    try:
        bot.run(settings.Bot_Token, log_handler=None)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
     
        loop = asyncio.new_event_loop()
        loop.run_until_complete(close_db())
        loop.close()




_startup_done = False


@bot.event
async def on_ready_load_cogs() -> None:
   
    global _startup_done
    if _startup_done:
        return
    _startup_done = True

    await bot.add_cog(Events(bot, _detector, _settings))  
    await bot.add_cog(TrackingCog(bot, _settings))  
    await bot.add_cog(FactCheckCommandCog(bot, _detector, _settings))  
    await bot.add_cog(ContextMenuCog(bot, _detector, _settings)) 

    logger = logging.getLogger(__name__)
    logger.info("All cogs loaded successfully")

    
    try:
        synced = await bot.tree.sync()
        logger.info("Synced %d slash commands", len(synced))
    except Exception as exc:
        logger.error("Failed to sync commands: %s", exc)


bot.add_listener(on_ready_load_cogs, "on_ready")


if __name__ == "__main__":
    main()
