"""Initial schema

Revision ID: 7ebf53e64664
Revises: 
Create Date: 2026-07-14 20:27:30.079412
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op



revision: str = '7ebf53e64664'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    op.create_table('cached_verdicts',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('claim_hash', sa.String(), nullable=False),
    sa.Column('claim_text_normalized', sa.String(), nullable=False),
    sa.Column('verdict_label', sa.String(), nullable=False),
    sa.Column('explanation', sa.String(), nullable=False),
    sa.Column('sources', sa.String(), nullable=False),
    sa.Column('tier', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_cached_verdicts_claim_hash'), 'cached_verdicts', ['claim_hash'], unique=True)
    op.create_table('flagged_messages',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('message_id', sa.String(), nullable=False),
    sa.Column('channel_id', sa.String(), nullable=False),
    sa.Column('guild_id', sa.String(), nullable=False),
    sa.Column('flagged_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_flagged_messages_message_id'), 'flagged_messages', ['message_id'], unique=True)
    op.create_table('guild_tier3_budgets',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('guild_id', sa.String(), nullable=False),
    sa.Column('calls_used_today', sa.Integer(), nullable=False),
    sa.Column('budget_date', sa.Date(), nullable=False),
    sa.Column('daily_limit', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_guild_tier3_budgets_guild_id'), 'guild_tier3_budgets', ['guild_id'], unique=True)
    op.create_table('tracked_channels',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('guild_id', sa.String(), nullable=False),
    sa.Column('channel_id', sa.String(), nullable=False),
    sa.Column('added_by', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('guild_id', 'channel_id', name='uq_guild_channel')
    )
    op.create_index(op.f('ix_tracked_channels_guild_id'), 'tracked_channels', ['guild_id'], unique=False)
  


def downgrade() -> None:
  
    op.drop_index(op.f('ix_tracked_channels_guild_id'), table_name='tracked_channels')
    op.drop_table('tracked_channels')
    op.drop_index(op.f('ix_guild_tier3_budgets_guild_id'), table_name='guild_tier3_budgets')
    op.drop_table('guild_tier3_budgets')
    op.drop_index(op.f('ix_flagged_messages_message_id'), table_name='flagged_messages')
    op.drop_table('flagged_messages')
    op.drop_index(op.f('ix_cached_verdicts_claim_hash'), table_name='cached_verdicts')
    op.drop_table('cached_verdicts')
  
