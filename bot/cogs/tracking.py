

from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from bot.config import Settings
from bot.db import crud
from bot.db import session as db_session

logger = logging.getLogger(__name__)


class TrackingCog(commands.Cog):


    def __init__(self, bot: commands.Bot, settings: Settings):
        self.bot = bot
        self.settings = settings

    @app_commands.command(name="track-channel", description="Add or remove a channel from fact-check tracking")
    @app_commands.describe(
        action="Whether to add or remove the channel",
        channel="The channel to track or untrack (defaults to current channel)",
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(name="add", value="add"),
            app_commands.Choice(name="remove", value="remove"),
        ]
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def track_channel(
        self,
        interaction: discord.Interaction,
        action: str,
        channel: discord.TextChannel | None = None,
    ) -> None:
    
        target_channel = channel or interaction.channel
        if target_channel is None:
            await interaction.response.send_message(
                "Please specify a channel.", ephemeral=True
            )
            return

        guild_id = str(interaction.guild_id) if interaction.guild_id else ""
        channel_id = str(target_channel.id)
        user_id = str(interaction.user.id)

        async with db_session.async_session_factory() as session:
            if action == "add":
                await crud.set_channel_tracking(session, guild_id, channel_id, user_id)
                embed = discord.Embed(
                    title="Channel Tracking Enabled",
                    description=f"Now tracking <#{channel_id}> for fact-check detection.",
                    color=discord.Colour.green(),
                )
            else:
                removed = await crud.remove_channel_tracking(session, guild_id, channel_id)
                if removed:
                    embed = discord.Embed(
                        title="Channel Tracking Removed",
                        description=f"<#{channel_id}> is no longer tracked for fact-check detection.",
                        color=discord.Colour.orange(),
                    )
                else:
                    embed = discord.Embed(
                        title="Not Tracked",
                        description=f"<#{channel_id}> was not being tracked.",
                        color=discord.Colour.light_grey(),
                    )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @track_channel.error
    async def track_channel_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
     
        if isinstance(error, app_commands.MissingPermissions):
            embed = discord.Embed(
                title="Permission Denied",
                description="You need the **Manage Server** permission to use this command.",
                color=discord.Colour.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            logger.error("track_channel error: %s", error)
            embed = discord.Embed(
                title="Error",
                description="Something went wrong. Please try again.",
                color=discord.Colour.red(),
            )
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=embed, ephemeral=True)
