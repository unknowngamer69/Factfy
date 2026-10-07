from __future__ import annotations

import re
from dataclasses import dataclass

import discord

from bot.ocr import extract_text_from_image

MAX_EXTRACTED_TEXT = 2000


@dataclass(frozen=True)
class MessageTextResult:
    text: str
    image_seen: bool
    ocr_failed: bool


def strip_bot_mention(text: str, bot_id: int) -> str:
    return re.sub(rf"<@!?{bot_id}>", "", text, count=1).strip()


async def extract_message_text(
    message: discord.Message,
    *,
    ocr_threshold: float,
    base_text: str | None = None,
) -> MessageTextResult:
    parts: list[str] = []
    text = (message.content if base_text is None else base_text).strip()
    if text:
        parts.append(text)

    image_seen = False
    ocr_failed = False

    for attachment in message.attachments:
        content_type = (attachment.content_type or "").lower()
        is_image = content_type.startswith("image/")
        if not is_image:
            is_image = bool(
                re.search(r"\.(png|jpe?g|webp|bmp|gif)$", attachment.filename or "", re.I)
            )
        if not is_image:
            continue

        image_seen = True
        result = await extract_text_from_image(attachment.url)
        if result is None or result.confidence < ocr_threshold or not result.text.strip():
            ocr_failed = True
            continue

        parts.append(result.text.strip())

    combined = "\n".join(dict.fromkeys(part for part in parts if part))
    if len(combined) > MAX_EXTRACTED_TEXT:
        combined = combined[:MAX_EXTRACTED_TEXT].rsplit(" ", 1)[0] + "..."

    return MessageTextResult(text=combined, image_seen=image_seen, ocr_failed=ocr_failed)
