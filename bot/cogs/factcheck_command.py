

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
)
from bot.db import session as db_session
from bot.detection.classifier import ClaimDetector

logger = logging.getLogger(__name__)


class FactCheckCommandCog(commands.Cog):


    def __init__(self, bot: commands.Bot, detector: ClaimDetector, settings: Settings):
        self.bot = bot
        self.detector = detector
        self.settings = settings

    @app_commands.command(name="factcheck", description="Fact-check a specific claim")
    @app_commands.describe(claim="The factual claim you want to verify")
    @app_commands.checks.cooldown(1, 15.0, key=lambda i: i.user.id)
    async def factcheck(self, interaction: discord.Interaction, claim: str) -> None:

        claim = claim.strip()
        if len(claim) < 5:
            await interaction.response.send_message(
                "Please provide a fuller claim to fact-check (at least 5 characters).",
                ephemeral=True,
            )
            return

        if len(claim) > 500:
            claim = claim[:500]


        checking_embed = discord.Embed(
            title="🔍 Checking...",
            description=f"Fact-checking: {claim[:200]}{'...' if len(claim) > 200 else ''}",
            color=discord.Colour.blue(),
        )

        await interaction.response.send_message(embed=checking_embed)


        try:
            checking_msg = await interaction.original_response()
        except discord.NotFound:
            logger.error("Could not fetch original response message")
            return

  
        guild_id = str(interaction.guild_id) if interaction.guild_id else "0"
        try:
            async with db_session.async_session_factory() as session:
                verdict = await run_cascade(claim, guild_id, session, self.settings)

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
            logger.error("Cascade failed for /factcheck: %s", exc, exc_info=True)
            try:
                await checking_msg.edit(embed=format_error())
            except discord.HTTPException:
                pass

    @factcheck.error
    async def factcheck_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
   
        if isinstance(error, app_commands.CommandOnCooldown):
            await interaction.response.send_message(
                f"Please wait {error.retry_after:.0f}s before using this command again.",
                ephemeral=True,
            )
        elif isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "You don't have permission to use this command.",
                ephemeral=True,
            )
        else:
            logger.error("/factcheck error: %s", error)
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "Something went wrong. Please try again.",
                    ephemeral=True,
                )
