

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

import discord


@dataclass
class Verdict:


    label: str 
    explanation: str
    sources: list[str] = field(default_factory=list)
    tier: Literal["fact_check_db", "knowledge_evidence", "ai_search"] = "ai_search"
    confidence: float | None = None
    budget_exceeded: bool = False



_LABEL_COLORS: dict[str, discord.Colour] = {
    "True": discord.Colour.green(),
    "False": discord.Colour.red(),
    "Misleading": discord.Colour.gold(),
    "Unverifiable": discord.Colour.light_grey(),
}

_LABEL_EMOJI: dict[str, str] = {
    "True": "✅",
    "False": "❌",
    "Misleading": "⚠️",
    "Unverifiable": "❓",
}

_TIER_LABELS: dict[str, str] = {
    "fact_check_db": "Google Fact Check + AI",
    "knowledge_evidence": "knowledge sources + AI",
    "ai_search": "AI-synthesized search",
}


def is_well_formed_url(url: str) -> bool:

    return bool(re.match(r"^https?://\S+$", url))


def format_as_embed(verdict: Verdict) -> discord.Embed:

    color = _LABEL_COLORS.get(verdict.label, discord.Colour.light_grey())
    emoji = _LABEL_EMOJI.get(verdict.label, "")
    tier_label = _TIER_LABELS.get(verdict.tier, verdict.tier)

    embed = discord.Embed(
        title=f"{emoji} {verdict.label}",
        description=verdict.explanation,
        color=color,
    )


    valid_urls = [u for u in verdict.sources if is_well_formed_url(u)]
    if valid_urls:
        source_text = "\n".join(f"[Source {i + 1}]({url})" for i, url in enumerate(valid_urls, 1))
        embed.add_field(name="Sources", value=source_text, inline=False)
    else:
        embed.add_field(name="Sources", value="No sources available.", inline=False)

    embed.set_footer(text=f"Verified via {tier_label}")

    return embed


def format_not_a_claim() -> discord.Embed:

    return discord.Embed(
        title="Not a factual claim",
        description=(
            "This looks like an opinion or subjective statement rather than "
            "a factual claim that can be verified. Fact-checking is only "
            "available for declarative factual statements."
        ),
        color=discord.Colour.light_grey(),
    )




def format_ocr_failed() -> discord.Embed:

    return discord.Embed(
        title="Unable to read image",
        description=(
            "I couldn't extract clear text from that image. "
            "It may be too blurry, low-resolution, or contain non-text content. "
            "Try typing the claim directly with `/factcheck`."
        ),
        color=discord.Colour.light_grey(),
    )


def format_error() -> discord.Embed:

    return discord.Embed(
        title="Something went wrong",
        description=(
            "Something went wrong while checking that claim — "
            "try again in a moment."
        ),
        color=discord.Colour.red(),
    )
