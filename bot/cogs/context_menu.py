

from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from bot.config import Settings
from bot.cascade.runner import run_cascade, is_budget_exceeded
from bot.cascade.verdict import (
    format_as_embed,
    format_error,
    format_not_a_claim,
    format_ocr_failed,
)
from bot.db import session as db_session
from bot.detection.classifier import ClaimDetector
from bot.message_text import extract_message_text

logger = logging.getLogger(__name__)


async def factcheck_context(interaction: discord.Interaction, message: discord.Message) -> None:

    cog = interaction.client.get_cog("ContextMenuCog")
    if cog is None:
        return
    await cog._run_factcheck(interaction, message)


class ContextMenuCog(commands.Cog):


    def __init__(self, bot: commands.Bot, detector: ClaimDetector, settings: Settings):
        self.bot = bot
        self.detector = detector
        self.settings = settings

    async def cog_load(self) -> None:
        self.bot.tree.add_command(
            app_commands.ContextMenu(
                name="Fact-check this",
                callback=factcheck_context,
            )
        )

    async def cog_unload(self) -> None:
        self.bot.tree.remove_command("Fact-check this", type=discord.AppCommandType.message)

    async def _run_factcheck(self, interaction: discord.Interaction, message: discord.Message) -> None:
        await interaction.response.defer(ephemeral=True)

       
        extracted = await extract_message_text(
            message, ocr_threshold=self.settings.OCR_Threshold
        )
        claim_text = extracted.text.strip()


        if not claim_text or len(claim_text.strip()) < 5:
            await interaction.followup.send(
                embed=format_not_a_claim(),
                ephemeral=True,
            )
            return

    
        if len(claim_text) > 500:
            claim_text = claim_text[:500]

      
        checking_embed = discord.Embed(
            title="🔍 Checking...",
            description=f"Fact-checking: {claim_text[:200]}{'...' if len(claim_text) > 200 else ''}",
            color=discord.Colour.blue(),
        )

        checking_msg = await interaction.followup.send(embed=checking_embed)

  
        guild_id = str(interaction.guild_id) if interaction.guild_id else "0"
        try:
            async with db_session.async_session_factory() as session:
                verdict = await run_cascade(claim_text, guild_id, session, self.settings)

            if is_budget_exceeded(verdict):
              
                await checking_msg.edit(
                    content=(
                        "Daily AI fact-check limit reached for this server — "
                        "try again tomorrow, or use `/factcheck` once results reset."
                    ),
                    embed=None,
                )
            else:
                embed = format_as_embed(verdict)
                await checking_msg.edit(embed=embed)

        except Exception as exc:
            logger.error("Cascade failed for context menu: %s", exc, exc_info=True)
            try:
                await checking_msg.edit(embed=format_error())
            except discord.HTTPException:
                pass
