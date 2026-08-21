

from __future__ import annotations

import datetime

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class TrackedChannel(Base):


    __tablename__ = "tracked_channels"

    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(String, nullable=False, index=True)
    channel_id = Column(String, nullable=False)
    added_by = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("guild_id", "channel_id", name="uq_guild_channel"),
    )


class FlaggedMessage(Base):


    __tablename__ = "flagged_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(String, nullable=False, unique=True, index=True)
    channel_id = Column(String, nullable=False)
    guild_id = Column(String, nullable=False)
    flagged_at = Column(DateTime, nullable=False, server_default=func.now())


class CachedVerdict(Base):


    __tablename__ = "cached_verdicts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    claim_hash = Column(String, nullable=False, unique=True, index=True)
    claim_text_normalized = Column(String, nullable=False)
    verdict_label = Column(String, nullable=False)  
    explanation = Column(String, nullable=False)
    sources = Column(String, nullable=False)  
    tier = Column(String, nullable=False)  
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class GuildTier3Budget(Base):


    __tablename__ = "guild_tier3_budgets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(String, nullable=False, unique=True, index=True)
    calls_used_today = Column(Integer, nullable=False, default=0)
    budget_date = Column(Date, nullable=False)
    daily_limit = Column(Integer, nullable=False, default=20)
