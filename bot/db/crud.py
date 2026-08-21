

from __future__ import annotations

import datetime
import json
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import (
    CachedVerdict,
    FlaggedMessage,
    GuildTier3Budget,
    TrackedChannel,
)




async def is_channel_tracked(session: AsyncSession, guild_id: str, channel_id: str) -> bool:
   
    stmt = select(TrackedChannel).where(
        TrackedChannel.guild_id == guild_id,
        TrackedChannel.channel_id == channel_id,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None


async def set_channel_tracking(
    session: AsyncSession,
    guild_id: str,
    channel_id: str,
    added_by: str,
) -> None:

    existing = await is_channel_tracked(session, guild_id, channel_id)
    if existing:
        return
    row = TrackedChannel(
        guild_id=guild_id,
        channel_id=channel_id,
        added_by=added_by,
    )
    session.add(row)
    await session.commit()


async def remove_channel_tracking(
    session: AsyncSession,
    guild_id: str,
    channel_id: str,
) -> bool:

    stmt = select(TrackedChannel).where(
        TrackedChannel.guild_id == guild_id,
        TrackedChannel.channel_id == channel_id,
    )
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        return False
    await session.delete(row)
    await session.commit()
    return True




async def mark_message_flagged(
    session: AsyncSession,
    message_id: str,
    channel_id: str,
    guild_id: str,
) -> None:
 
    stmt = select(FlaggedMessage).where(FlaggedMessage.message_id == message_id)
    result = await session.execute(stmt)
    if result.scalar_one_or_none() is not None:
        return  # already flagged
    row = FlaggedMessage(
        message_id=message_id,
        channel_id=channel_id,
        guild_id=guild_id,
    )
    session.add(row)
    await session.commit()


async def is_message_flagged(session: AsyncSession, message_id: str) -> bool:

    stmt = select(FlaggedMessage).where(FlaggedMessage.message_id == message_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None




async def get_cached_verdict(
    session: AsyncSession, claim_hash: str, Cache_Expiry: int = 7
) -> Optional[CachedVerdict]:

    stmt = select(CachedVerdict).where(CachedVerdict.claim_hash == claim_hash)
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        return None
    age = datetime.datetime.now(datetime.timezone.utc) - row.created_at.replace(
        tzinfo=datetime.timezone.utc
    )
    if age.days >= Cache_Expiry:
        await session.delete(row)
        await session.commit()
        return None
    return row


async def save_verdict_to_cache(
    session: AsyncSession,
    claim_hash: str,
    claim_text_normalized: str,
    verdict_label: str,
    explanation: str,
    sources: list[str],
    tier: str,
) -> None:

    stmt = select(CachedVerdict).where(CachedVerdict.claim_hash == claim_hash)
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing is not None:
        existing.verdict_label = verdict_label
        existing.explanation = explanation
        existing.sources = json.dumps(sources)
        existing.tier = tier
        existing.created_at = datetime.datetime.now(datetime.timezone.utc)
    else:
        row = CachedVerdict(
            claim_hash=claim_hash,
            claim_text_normalized=claim_text_normalized,
            verdict_label=verdict_label,
            explanation=explanation,
            sources=json.dumps(sources),
            tier=tier,
        )
        session.add(row)
    await session.commit()




async def get_remaining_tier3_budget(
    session: AsyncSession, guild_id: str, default_limit: int = 20
) -> int:
    
    today = datetime.date.today()
    stmt = select(GuildTier3Budget).where(GuildTier3Budget.guild_id == guild_id)
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        row = GuildTier3Budget(
            guild_id=guild_id,
            calls_used_today=0,
            budget_date=today,
            daily_limit=default_limit,
        )
        session.add(row)
        await session.commit()
        return default_limit
    if row.budget_date != today:
        row.calls_used_today = 0
        row.budget_date = today
        await session.commit()
    return max(0, row.daily_limit - row.calls_used_today)


async def decrement_tier3_budget(session: AsyncSession, guild_id: str) -> None:

    today = datetime.date.today()
    stmt = select(GuildTier3Budget).where(GuildTier3Budget.guild_id == guild_id)
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        row = GuildTier3Budget(
            guild_id=guild_id,
            calls_used_today=1,
            budget_date=today,
        )
        session.add(row)
    else:
        if row.budget_date != today:
            row.calls_used_today = 1
            row.budget_date = today
        else:
            row.calls_used_today += 1
    await session.commit()
