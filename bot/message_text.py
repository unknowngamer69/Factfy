from __future__ import annotations

import re
from dataclasses import dataclass

import discord

from bot.ocr import extract_text_from_image

MAX_EXTRACTED_TEXT = 2000
RECENT_CONTEXT_LIMIT = 8

_GENERIC_FACTCHECK_PROMPTS = {
    "is this true",
    "is this true?",
    "is this false",
    "is this real",
    "is this real?",
    "is this correct",
    "is this correct?",
    "fact check this",
    "fact-check this",
    "factcheck this",
    "check this",
    "verify this",
    "verify this claim",
    "is this accurate",
    "is this accurate?",
    "true",
    "true?",
    "real",
    "real?",
}


@dataclass(frozen=True)
class MessageTextResult:
    text: str
    image_seen: bool
    ocr_failed: bool


def strip_bot_mention(text: str, bot_id: int) -> str:
    return re.sub(rf"<@!?{bot_id}>", "", text, count=1).strip()


def _is_generic_factcheck_prompt(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", text.strip().lower())
    normalized = re.sub(r"[.!]+$", "", normalized).strip()
    return normalized in _GENERIC_FACTCHECK_PROMPTS


def _is_image_attachment(attachment: discord.Attachment) -> bool:
    content_type = (attachment.content_type or "").lower()
    if content_type.startswith("image/"):
        return True
    return bool(
        re.search(
            r"\.(png|jpe?g|webp|bmp|gif)$",
            attachment.filename or "",
            re.I,
        )
    )


async def _extract_single_message(
    message: discord.Message,
    *,
    ocr_threshold: float,
) -> tuple[list[str], bool, bool]:
    parts: list[str] = []
    text = (message.content or "").strip()
    if text:
        parts.append(text)

    image_seen = False
    ocr_failed = False

    for attachment in message.attachments:
        if not _is_image_attachment(attachment):
            continue

        image_seen = True
        result = await extract_text_from_image(attachment.url)
        if result is None or result.confidence < ocr_threshold or not result.text.strip():
            ocr_failed = True
            continue

        parts.append(result.text.strip())

    return parts, image_seen, ocr_failed


async def _get_context_message(message: discord.Message) -> discord.Message | None:
    """Find the message the user is asking Factfy to verify.

    Priority:
    1. An explicit Discord reply/reference.
    2. For generic prompts such as "is this true?", the user's most recent
       substantive message in the same channel, limited to a few messages back.
    """
    reference = message.reference
    if reference and reference.message_id:
        resolved = reference.resolved
        if isinstance(resolved, discord.Message):
            return resolved

        try:
            channel = message.channel
            if hasattr(channel, "fetch_message"):
                return await channel.fetch_message(reference.message_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass

    if not _is_generic_factcheck_prompt(message.content):
        return None

    try:
        async for previous in message.channel.history(
            limit=RECENT_CONTEXT_LIMIT,
            before=message,
        ):
            if previous.author.bot:
                continue
            if previous.author.id != message.author.id:
                continue
            if previous.content.strip() or any(
                _is_image_attachment(attachment)
                for attachment in previous.attachments
            ):
                return previous
    except (discord.Forbidden, discord.HTTPException):
        return None

    return None


async def extract_message_text(
    message: discord.Message,
    *,
    ocr_threshold: float,
    base_text: str | None = None,
    include_context: bool = True,
) -> MessageTextResult:
    parts: list[str] = []
    text = (message.content if base_text is None else base_text).strip()
    if text:
        parts.append(text)

    image_seen = False
    ocr_failed = False

    current_parts, current_image_seen, current_ocr_failed = await _extract_single_message(
        message,
        ocr_threshold=ocr_threshold,
    )
    if base_text is not None:
        current_parts = [
            part for part in current_parts if part != message.content.strip()
        ]
    parts.extend(current_parts)
    image_seen = image_seen or current_image_seen
    ocr_failed = ocr_failed or current_ocr_failed

    if include_context and not current_image_seen:
        context_message = await _get_context_message(message)
        if context_message is not None and context_message.id != message.id:
            context_parts, context_image_seen, context_ocr_failed = await _extract_single_message(
                context_message,
                ocr_threshold=ocr_threshold,
            )
            if context_parts:
                # Put the referenced/recent claim before "is this true?" so the
                # detector and fact-checker receive the actual claim first.
                parts = context_parts + parts
            image_seen = image_seen or context_image_seen
            ocr_failed = ocr_failed or context_ocr_failed

    combined = "\n".join(dict.fromkeys(part for part in parts if part))
    if len(combined) > MAX_EXTRACTED_TEXT:
        combined = combined[:MAX_EXTRACTED_TEXT].rsplit(" ", 1)[0] + "..."

    return MessageTextResult(
        text=combined,
        image_seen=image_seen,
        ocr_failed=ocr_failed,
    )
