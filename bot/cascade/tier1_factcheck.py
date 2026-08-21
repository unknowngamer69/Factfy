

from __future__ import annotations

import asyncio
import logging
import os
import re
from difflib import SequenceMatcher
from typing import Optional

import httpx

from bot.cascade.verdict import Verdict, is_well_formed_url

logger = logging.getLogger(__name__)


_google_semaphore = asyncio.Semaphore(5)

_GOOGLE_FACT_CHECK_URL = "https://factchecktools.googleapis.com/v1alpha1/claims:search"


def _normalize_text(text: str) -> str:

    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


_STOPWORDS = {
    "a",
    "an",
    "the",
    "is",
    "are",
    "was",
    "were",
    "in",
    "on",
    "of",
    "and",
    "or",
    "to",
    "for",
    "with",
    "as",
    "by",
    "at",
    "from",
    "not",
    "no",
    "that",
    "this",
    "it",
    "its",
    "be",
    "been",
    "being",
    "have",
    "has",
    "had",
    "do",
    "does",
    "did",
}


def _singularize_token(token: str) -> str:
    if token.endswith("ies") and len(token) > 4:
        return token[:-3] + "y"
    if token.endswith("es") and len(token) > 4 and not token.endswith("ses"):
        return token[:-2]
    if token.endswith("s") and len(token) > 3 and not token.endswith("ss"):
        return token[:-1]
    return token


def _tokenize_text(text: str) -> list[str]:
    normalized = _normalize_text(text)
    tokens = []
    for token in normalized.split():
        if token in _STOPWORDS:
            continue
        token = _singularize_token(token)
        if token:
            tokens.append(token)
    return tokens


def _query_overlap(a: str, b: str) -> float:
    a_tokens = set(_tokenize_text(a))
    b_tokens = set(_tokenize_text(b))
    if not a_tokens:
        return 0.0
    return len(a_tokens & b_tokens) / len(a_tokens)


def _text_similarity(a: str, b: str) -> float:

    a_norm = _normalize_text(a)
    b_norm = _normalize_text(b)
    seq = SequenceMatcher(None, a_norm, b_norm).ratio()
    a_tokens = set(_tokenize_text(a))
    b_tokens = set(_tokenize_text(b))
    jaccard = 0.0
    if a_tokens and b_tokens:
        jaccard = len(a_tokens & b_tokens) / len(a_tokens | b_tokens)
    overlap = _query_overlap(a, b)

    weighted = 0.5 * seq + 0.3 * jaccard + 0.2 * overlap
    if jaccard < 0.4 and overlap < 0.4:
        weighted *= 0.8

    return weighted




async def check_tier1(
    claim_text: str,
    api_key: str | None = None,
    similarity_threshold: float = 0.6,
) -> Optional[Verdict]:

    api_key = api_key or os.getenv("Factchecker", "") or os.getenv("GOOGLE_API_KEY", "")
    if not api_key:
        logger.warning(
            "No Google Fact Check API key configured (Factchecker or GOOGLE_API_KEY) — skipping Tier 1"
        )
        return None

    try:
        async with _google_semaphore:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    _GOOGLE_FACT_CHECK_URL,
                    params={"key": api_key, "query": claim_text, "languageCode": "en"},
                )
                resp.raise_for_status()
                data = resp.json()
    except httpx.HTTPStatusError as exc:
        logger.error("Google Fact Check API error (status %s): %s", exc.response.status_code, exc)
        return None
    except httpx.HTTPError as exc:
        logger.error("Google Fact Check API network error: %s", exc)
        return None

    claims = data.get("claims", [])
    if not claims:
        return None

    logger.debug("Google Fact Check returned %d claims", len(claims))

   
    best_match: dict | None = None
    best_similarity = 0.0

    for claim in claims:
        claim_text_api = claim.get("text", "")
        similarity = _text_similarity(claim_text, claim_text_api)

        logger.debug("Candidate fact-check: similarity=%.3f | api_text=%s", similarity, claim_text_api[:160])
        if similarity >= similarity_threshold and similarity > best_similarity:
            best_similarity = similarity
            best_match = claim

    if best_match is None:
        return None


    claim_reviews = best_match.get("claimReview", [])
    if not claim_reviews:
        return None

    review = claim_reviews[0]
    rating = review.get("textualRating", "").strip().lower()
    source_url = review.get("url", "")
    publisher = review.get("publisher", {}).get("name", "Unknown source")


    label_map = {
        "true": "True",
        "mostly true": "True",
        "accurate": "True",
        "correct": "True",
        "false": "False",
        "mostly false": "False",
        "misleading": "Misleading",
        "partly true": "Misleading",
        "half true": "Misleading",
        "outdated": "Misleading",
        "unverifiable": "Unverifiable",
        "no evidence": "Unverifiable",
    }

    verdict_label = "Unverifiable"
    for key, val in label_map.items():
        if key in rating:
            verdict_label = val
            break

    sources = [source_url] if source_url and is_well_formed_url(source_url) else []

    explanation = f"Based on fact-checking by {publisher}."
    review_title = review.get("title", "")
    if review_title:
        explanation = f"{review_title} — {explanation}"

    logger.info("Tier 1 match found (similarity %.2f): %s", best_similarity, verdict_label)

    return Verdict(
        label=verdict_label,
        explanation=explanation,
        sources=sources,
        tier="fact_check_db",
        confidence=best_similarity,
    )
