

from __future__ import annotations

import hashlib
import json
import logging
import re
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from bot.cascade.tier1_factcheck import check_tier1
from bot.cascade.tier2_wikidata import check_tier2
from bot.cascade.tier3_ai_search import check_tier3, synthesize_verdict_from_evidence
from bot.cascade.verdict import Verdict
from bot.db import crud
from bot.config import Settings

logger = logging.getLogger(__name__)




def normalize_claim(text: str) -> str:
  
    text = text.strip().lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w\s]", "", text)
    return text


def hash_claim(normalized_text: str) -> str:

    return hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()


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
        logger.info("Cache hit for claim hash %s", claim_hash[:12])
        authoritative = {"true", "false", "misleading"}
        if cached.tier == "fact_check_db" and cached.verdict_label.lower() in authoritative:

            if settings.Factchecker:
                try:
                    live_tier1 = await check_tier1(
                        claim_text,
                        api_key=settings.Factchecker,
                        similarity_threshold=settings.Teir1_Threshold,
                    )
                except Exception as exc:
                    logger.error("Tier 1 revalidation failed: %s", exc)
                    live_tier1 = cached  

                if live_tier1 is None:
                    logger.info("Cached Tier 1 verdict did not revalidate; continuing to Tier 2")
                elif live_tier1.label.lower() != cached.verdict_label.lower():
                    logger.info(
                        "Cached Tier 1 verdict label changed from %s to %s; using live result",
                        cached.verdict_label,
                        live_tier1.label,
                    )
                    await crud.save_verdict_to_cache(
                        session, claim_hash, normalized,
                        live_tier1.label, live_tier1.explanation,
                        live_tier1.sources, live_tier1.tier,
                    )
                    return live_tier1
                else:
                    return Verdict(
                        label=cached.verdict_label,
                        explanation=cached.explanation,
                        sources=json.loads(cached.sources) if cached.sources else [],
                        tier=cached.tier, 
                        confidence=None,
                    )
            else:
                return Verdict(
                    label=cached.verdict_label,
                    explanation=cached.explanation,
                    sources=json.loads(cached.sources) if cached.sources else [],
                    tier=cached.tier,  
                    confidence=None,
                )

        if cached.tier in {"wikidata", "wikipedia"} and cached.verdict_label.lower() == "unverifiable":
            logger.info("Cached Tier 2/Wikipedia unverifiable verdict is stale; continuing the cascade")
        elif cached.tier != "fact_check_db":
            return Verdict(
                label=cached.verdict_label,
                explanation=cached.explanation,
                sources=json.loads(cached.sources) if cached.sources else [],
                tier=cached.tier,  
                confidence=None,
            )
        logger.info("Cached Tier 1 verdict is non-authoritative; continuing the cascade")

    logger.info("Tier 1: Checking Google Fact Check Tools...")
    tier1_result: Optional[Verdict] = None
    try:
        tier1_result = await check_tier1(
            claim_text,
            api_key=settings.Factchecker,
            similarity_threshold=settings.Teir1_Threshold,
        )
    except Exception as exc:
        logger.error("Tier 1 failed (falling through to Tier 2): %s", exc)

    authoritative = {"true", "false", "misleading"}
    if tier1_result is not None and tier1_result.label.lower() in authoritative:
        logger.info("Tier 1 provided authoritative fact-check data; using AI to interpret it.")
        ai_result = await synthesize_verdict_from_evidence(
            claim_text,
            [tier1_result.explanation] + tier1_result.sources,
            settings.HCAI,
            source_tier="fact_check_db",
        )
        if ai_result is not None:
            await crud.save_verdict_to_cache(
                session, claim_hash, normalized,
                ai_result.label, ai_result.explanation,
                ai_result.sources, ai_result.tier,
            )
            return ai_result


        await crud.save_verdict_to_cache(
            session, claim_hash, normalized,
            tier1_result.label, tier1_result.explanation,
            tier1_result.sources, tier1_result.tier,
        )
        return tier1_result
    else:
        logger.info("Tier 1 returned no authoritative data; continuing to Tier 2")


    logger.info("Tier 2: Checking Wikidata structured lookup...")
    tier2_result: Optional[Verdict] = None
    try:
        tier2_result = await check_tier2(claim_text)
    except Exception as exc:
        logger.error("Tier 2 failed (falling through to Tier 3): %s", exc)

    if tier2_result is not None:
        if tier2_result.label.lower() == "unverifiable":

            logger.info("Tier 2 produced only an unverifiable fallback; treating as no-data and continuing to Tier 3.")
            tier2_result = None
        else:
            logger.info("Tier 2 provided data; using AI to interpret it.")
            ai_result = await synthesize_verdict_from_evidence(
                claim_text,
                [tier2_result.explanation] + tier2_result.sources,
                settings.HCAI,
                source_tier=tier2_result.tier,
            )
            if ai_result is not None:

                if ai_result.label.lower() == "unverifiable" and tier2_result.tier in {"wikipedia", "wikidata"}:
                    logger.info(
                        "AI synthesized 'Unverifiable' from Wikipedia evidence; continuing to Tier 3 for web search."
                    )

                    tier2_result = None
                else:
                    await crud.save_verdict_to_cache(
                        session, claim_hash, normalized,
                        ai_result.label, ai_result.explanation,
                        ai_result.sources, ai_result.tier,
                    )
                    return ai_result


            if tier2_result is not None:
                await crud.save_verdict_to_cache(
                    session, claim_hash, normalized,
                    tier2_result.label, tier2_result.explanation,
                    tier2_result.sources, tier2_result.tier,
                )
                return tier2_result

  
    remaining = await crud.get_remaining_tier3_budget(
        session, guild_id, default_limit=settings.Teir3_Limit
    )
    if remaining <= 0:
        logger.info("Tier 3 budget exhausted for guild %s", guild_id)

        return make_budget_exceeded_verdict()


    logger.info("Tier 3: Running web search + AI synthesis...")
    tier3_result: Optional[Verdict] = None
    try:
        tier3_result = await check_tier3(
            claim_text,
            HCAI=settings.HCAI,
            Search=settings.Search,
        )
    except Exception as exc:
        logger.error("Tier 3 failed: %s", exc)

    if tier3_result is None:

        logger.error("Tier 3 unavailable — not charging budget or caching.")
        return Verdict(
            label="Unverifiable",
            explanation="Fact-check unavailable: the web-search service is not configured.",
            sources=[],
            tier="ai_search",
            confidence=0.0,
        )


    await crud.decrement_tier3_budget(session, guild_id)

    await crud.save_verdict_to_cache(
        session, claim_hash, normalized,
        tier3_result.label, tier3_result.explanation,
        tier3_result.sources, tier3_result.tier,
    )

    return tier3_result
