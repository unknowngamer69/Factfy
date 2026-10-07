from __future__ import annotations

import hashlib
import json
import logging
import re

from sqlalchemy.ext.asyncio import AsyncSession

from bot.cascade.tier1_factcheck import check_tier1
from bot.cascade.tier2_wikidata import check_tier2
from bot.cascade.tier3_ai_search import check_tier3, synthesize_verdict_from_evidence
from bot.cascade.verdict import Verdict
from bot.config import Settings
from bot.db import crud

logger = logging.getLogger(__name__)


def normalize_claim(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"\s+", " ", text)
    return re.sub(r"[^\w\s]", "", text)


def is_budget_exceeded(verdict: Verdict) -> bool:
    return verdict.budget_exceeded


def make_budget_exceeded_verdict() -> Verdict:
    return Verdict(
        label="Unverifiable",
        explanation="Daily AI fact-check limit reached for this server.",
        sources=[],
        tier="ai_search",
        confidence=0.0,
        budget_exceeded=True,
    )


def _cached_verdict(row) -> Verdict:
    return Verdict(
        label=row.verdict_label,
        explanation=row.explanation,
        sources=json.loads(row.sources) if row.sources else [],
        tier=row.tier,
        confidence=None,
    )


async def run_cascade(
    claim_text: str,
    guild_id: str,
    session: AsyncSession,
    settings: Settings,
) -> Verdict:
    normalized = normalize_claim(claim_text)
    claim_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    cached = await crud.get_cached_verdict(
        session, claim_hash, Cache_Expiry=settings.Cache_Expiry
    )
    if cached is not None:
        authoritative = {"true", "false", "misleading"}
        if cached.tier == "fact_check_db" and cached.verdict_label.lower() in authoritative:
            if settings.Factchecker:
                try:
                    live = await check_tier1(
                        claim_text,
                        api_key=settings.Factchecker,
                        similarity_threshold=settings.Teir1_Threshold,
                    )
                except Exception as exc:
                    logger.error("Tier 1 cache revalidation failed: %s", exc)
                    live = None

                if live is not None and live.label.lower() != cached.verdict_label.lower():
                    await crud.save_verdict_to_cache(
                        session,
                        claim_hash,
                        normalized,
                        live.label,
                        live.explanation,
                        live.sources,
                        live.tier,
                    )
                    return live

            return _cached_verdict(cached)

        if cached.tier in {"knowledge_evidence", "ai_search"}:
            return _cached_verdict(cached)

        logger.info("Ignoring legacy cache entry from tier '%s'.", cached.tier)

    logger.info("Tier 1: checking Google Fact Check Tools")
    try:
        tier1_result = await check_tier1(
            claim_text,
            api_key=settings.Factchecker,
            similarity_threshold=settings.Teir1_Threshold,
        )
    except Exception as exc:
        logger.error("Tier 1 failed: %s", exc)
        tier1_result = None

    authoritative = {"true", "false", "misleading"}
    if tier1_result is not None and tier1_result.label.lower() in authoritative:
        ai_result = await synthesize_verdict_from_evidence(
            claim_text,
            [tier1_result.explanation] + tier1_result.sources,
            settings.HCAI,
            source_tier="fact_check_db",
        )
        result = ai_result or tier1_result
        await crud.save_verdict_to_cache(
            session,
            claim_hash,
            normalized,
            result.label,
            result.explanation,
            result.sources,
            result.tier,
        )
        return result

    logger.info("Tier 2: gathering structured and Wikipedia evidence")
    try:
        tier2_result = await check_tier2(claim_text)
    except Exception as exc:
        logger.error("Tier 2 failed: %s", exc)
        tier2_result = None

    if tier2_result is not None:
        logger.info("Tier 2 provided evidence; using AI to interpret it.")
        ai_result = await synthesize_verdict_from_evidence(
            claim_text,
            tier2_result.evidence + tier2_result.sources,
            settings.HCAI,
            source_tier="knowledge_evidence",
        )
        if ai_result is not None:
            await crud.save_verdict_to_cache(
                session,
                claim_hash,
                normalized,
                ai_result.label,
                ai_result.explanation,
                ai_result.sources,
                ai_result.tier,
            )
            return ai_result

        logger.warning(
            "Tier 2 evidence could not be synthesized; continuing to Tier 3."
        )

    remaining = await crud.get_remaining_tier3_budget(
        session, guild_id, default_limit=settings.Teir3_Limit
    )
    if remaining <= 0:
        return make_budget_exceeded_verdict()

    logger.info("Tier 3: running web search + AI synthesis")
    try:
        tier3_result = await check_tier3(
            claim_text,
            HCAI=settings.HCAI,
            Search=settings.Search,
        )
    except Exception as exc:
        logger.error("Tier 3 failed: %s", exc)
        tier3_result = None

    if tier3_result is None:
        return Verdict(
            label="Unverifiable",
            explanation="Fact-check unavailable: the web-search service is not configured.",
            sources=[],
            tier="ai_search",
            confidence=0.0,
        )

    await crud.decrement_tier3_budget(session, guild_id)
    await crud.save_verdict_to_cache(
        session,
        claim_hash,
        normalized,
        tier3_result.label,
        tier3_result.explanation,
        tier3_result.sources,
        tier3_result.tier,
    )
    return tier3_result
