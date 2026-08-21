from __future__ import annotations

import logging

import discord
from discord.ext import commands

from bot.config import Settings
from bot.cascade.runner import run_cascade, is_budget_exceeded
from bot.cascade.verdict import (
    Verdict,
    format_as_embed,
    format_error,
    format_not_a_claim,
    format_ocr_failed,
)
from bot.db import crud
from bot.db import session as db_session
from bot.detection.classifier import ClaimDetector
from bot.ocr import extract_text_from_image

logger = logging.getLogger(__name__)


MAGNIFYING_GLASS = "\U0001F50D"


class Events(commands.Cog):


    def __init__(
        self,
        bot: commands.Bot,
        detector: ClaimDetector,
        settings: Settings,
    ):
        self.bot = bot
        self.detector = detector
        self.settings = settings

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
  
       
        if message.author.bot or message.guild is None:
            return

        
        if self.bot.user in message.mentions:
            mention_str = f"<@{self.bot.user.id}>"
            claim_text = message.content.replace(mention_str, "", 1).strip()
            if not claim_text:
                return
            await self._handle_mention_factcheck(message, claim_text)
            return

      
        async with db_session.async_session_factory() as session:
            tracked = await crud.is_channel_tracked(
                session, str(message.guild.id), str(message.channel.id)
            )
        if not tracked:
            return

        
        result = self.detector.is_claim(
            message.content, threshold=self.settings.Claim_Dectection_Threshold
        )

        if result.is_claim:
            logger.info(
                "Claim detected (confidence %.2f, signals: %s) in #%s",
                result.confidence,
                result.matched_signals,
                getattr(message.channel, "name", message.channel.id),
            )
           
            try:
                await message.add_reaction(MAGNIFYING_GLASS)
            except discord.HTTPException as exc:
                logger.error("Failed to add reaction: %s", exc)
                return

            
            async with db_session.async_session_factory() as session:
                await crud.mark_message_flagged(
                    session,
                    str(message.id),
                    str(message.channel.id),
                    str(message.guild.id),
                )

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:

      
        if str(payload.emoji) != MAGNIFYING_GLASS:
            return

    
        if payload.user_id == self.bot.user.id:
            return

   
        async with db_session.async_session_factory() as session:
            flagged = await crud.is_message_flagged(session, str(payload.message_id))
        if not flagged:
            return

      
        channel = self.bot.get_channel(payload.channel_id)
        if channel is None:
            return

        try:
            message = await channel.fetch_message(payload.message_id)
        except discord.NotFound:
            logger.warning("Flagged message %s not found", payload.message_id)
            return

       
        guild = message.guild
        if guild is None:
            return

      
        claim_text = ""

        if message.attachments:
            for attachment in message.attachments:
                if attachment.content_type and attachment.content_type.startswith("image/"):
                    
                    ocr_result = await extract_text_from_image(attachment.url)
                    if ocr_result is None:
                       
                        await self._send_reply(message, format_ocr_failed())
                        return
                    if ocr_result.confidence < self.settings.OCR_Threshold:
                      
                        await self._send_reply(message, format_ocr_failed())
                        return
                    claim_text = ocr_result.text
                    break

      
        if not claim_text:
            claim_text = message.content

        if not claim_text or len(claim_text.strip()) < 5:
            await self._send_reply(message, format_not_a_claim())
            return

        
        checking_embed = discord.Embed(
            title="🔍 Checking...",
            description=f"Fact-checking: {claim_text[:200]}{'...' if len(claim_text) > 200 else ''}",
            color=discord.Colour.blue(),
        )

        try:
            checking_msg = await message.reply(embed=checking_embed, mention_author=False)
        except discord.HTTPException as exc:
            logger.error("Failed to send checking message: %s", exc)
            return

       
        try:
            async with db_session.async_session_factory() as session:
                verdict = await run_cascade(
                    claim_text, str(guild.id), session, self.settings
                )

            
            if is_budget_exceeded(verdict):
               
                try:
                    await checking_msg.edit(
                        content=(
                            "Daily AI fact-check limit reached for this server — "
                            "try again tomorrow, or use `/factcheck` once results reset."
                        ),
                        embed=None,
                    )
                except discord.HTTPException:
                    pass
            else:
                embed = format_as_embed(verdict)
                await checking_msg.edit(embed=embed)

        except Exception as exc:
            logger.error("Cascade failed: %s", exc, exc_info=True)
            try:
                await checking_msg.edit(embed=format_error())
            except discord.HTTPException:
                pass

    async def _send_reply(self, message: discord.Message, embed: discord.Embed) -> None:

        try:
            await message.reply(embed=embed, mention_author=False)
        except discord.HTTPException as exc:
            logger.error("Failed to send reply: %s", exc)

    async def _handle_mention_factcheck(
        self, message: discord.Message, claim_text: str
    ) -> None:

        guild = message.guild
        if guild is None:
            return

        if not claim_text or len(claim_text.strip()) < 5:
            await self._send_reply(message, format_not_a_claim())
            return

        checking_embed = discord.Embed(
            title="🔍 Checking...",
            description=f"Fact-checking: {claim_text[:200]}{'...' if len(claim_text) > 200 else ''}",
            color=discord.Colour.blue(),
        )

        try:
            checking_msg = await message.reply(embed=checking_embed, mention_author=False)
        except discord.HTTPException as exc:
            logger.error("Failed to send checking message: %s", exc)
            return

        try:
            async with db_session.async_session_factory() as session:
                verdict = await run_cascade(
                    claim_text, str(guild.id), session, self.settings
                )

            if is_budget_exceeded(verdict):
                try:
                    await checking_msg.edit(
                        content=(
                            "Daily AI fact-check limit reached for this server — "
                            "try again tomorrow, or use `/factcheck` once results reset."
                        ),
                        embed=None,
                    )
                except discord.HTTPException:
                    pass
            else:
                embed = format_as_embed(verdict)
                await checking_msg.edit(embed=embed)

        except Exception as exc:
            logger.error("Mention fact-check cascade failed: %s", exc, exc_info=True)
            try:
                await checking_msg.edit(embed=format_error())
            except discord.HTTPException:
                pass


async def setup(bot: commands.Bot) -> None:
  
    pass
