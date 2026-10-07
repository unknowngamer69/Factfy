

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Optional

import httpx
import os
from pydantic import BaseModel, field_validator

from bot.cascade.verdict import Verdict, is_well_formed_url

logger = logging.getLogger(__name__)


_ai_semaphore = asyncio.Semaphore(3)

_HACKCLUB_AI_URL = "https://ai.hackclub.com/proxy/v1/chat/completions"

_SEARCH_URL = "https://search.hackclub.com/res/v1/web/search"
_EXA_SEARCH_URL = "https://ai.hackclub.com/proxy/v1/exa/search"


MAX_CLAIM_LENGTH = 500


class AISynthesisResponse(BaseModel):


    verdict: str
    explanation: str
    sources: list[str] = []

    @field_validator("verdict")
    @classmethod
    def validate_verdict(cls, v: str) -> str:
        allowed = {"True", "False", "Misleading", "Unverifiable"}
        if v not in allowed:
            return "Unverifiable"
        return v

    @field_validator("sources", mode="before")
    @classmethod
    def validate_sources(cls, v: list[str]) -> list[str]:

        return [url for url in v if re.match(r"^https?://\S+$", str(url))]


def _truncate_claim(text: str) -> str:

    if len(text) <= MAX_CLAIM_LENGTH:
        return text
    return text[:MAX_CLAIM_LENGTH].rsplit(" ", 1)[0] + "..."


async def _hackclub_search(query: str, api_key: str, count: int = 5) -> list[dict]:

    if not api_key:
        logger.warning("No Search configured — skipping web search")
        return []

    try:
        async with _ai_semaphore:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    _SEARCH_URL,
                    params={"q": query[:400], "count": count, "search_lang": "en"},
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                resp.raise_for_status()
                data = resp.json()
    except httpx.HTTPStatusError as exc:
        logger.error("Hack Club Search API error (status %s): %s", exc.response.status_code, exc)
        return []
    except httpx.HTTPError as exc:
        logger.error("Hack Club Search network error: %s", exc)
        return []

  
    results = data.get("web", {}).get("results", [])
    if not results:
        logger.warning("Hack Club Search API returned no results for query: %s", query[:120])
        logger.debug("Hack Club Search response payload: %s", data)
    snippets = []
    for r in results[:count]:
        snippets.append(
            {
                "title": r.get("title", ""),
                "description": r.get("description", ""),
                "url": r.get("url", ""),
            }
        )
    return snippets


async def _hackclub_exa_search(query: str, api_key: str, count: int = 5) -> list[dict]:

    if not api_key:
        logger.warning("No HCAI configured — skipping Exa search")
        return []

    try:
        async with _ai_semaphore:
            async with httpx.AsyncClient(timeout=15.0) as client:
                payload = {
                    "query": query[:400],
                    "numResults": count,
                    "contents": {"text": True, "highlights": True},
                }
                resp = await client.post(
                    _EXA_SEARCH_URL,
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
    except httpx.HTTPStatusError as exc:
        logger.error("Hack Club Exa search API error (status %s): %s", exc.response.status_code, exc)
        return []
    except httpx.HTTPError as exc:
        logger.error("Hack Club Exa search network error: %s", exc)
        return []

  
    results = data.get("results") or data.get("web", {}).get("results") or []
    snippets = []
    for r in results[:count]:
        snippets.append(
            {
                "title": r.get("title", "") if isinstance(r, dict) else "",
                "description": r.get("snippet", r.get("description", "")) if isinstance(r, dict) else "",
                "url": r.get("url", r.get("link", "")) if isinstance(r, dict) else "",
            }
        )
    return snippets


async def _hackclub_ai_synthesis(claim_text: str, snippets: list[dict], api_key: str) -> Optional[AISynthesisResponse]:

    if not api_key:
        logger.warning("No HCAI configured — skipping Tier 3")
        return None

 
    context_parts = []
    for i, s in enumerate(snippets, 1):
        context_parts.append(f"[Source {i}] {s['title']}: {s['description']} (URL: {s['url']})")
    context = "\n".join(context_parts)

    system_prompt = """You are a fact-checking assistant. Given a claim and a set of web search snippets,
determine whether the claim is True, False, Misleading, or Unverifiable.

IMPORTANT RULES:
- You must ONLY cite URLs that were actually provided in the search snippets. Never invent URLs.
- If the snippets don't contain enough information to make a determination, say "Unverifiable".
- Be concise in your explanation (2-3 sentences maximum).
- Return your response as a JSON object with exactly these fields:
  {
    "verdict": "True" or "False" or "Misleading" or "Unverifiable",
    "explanation": "Brief explanation of your verdict",
    "sources": ["URL1", "URL2"]  // only URLs from the snippets above
  }"""

    user_prompt = f"""Claim: {claim_text}

Search snippets:
{context}

Respond with a JSON object only, no other text."""

    try:
        model = os.getenv("HACKCLUB_AI_MODEL", "google/gemini-2.5-flash")
        async with _ai_semaphore:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    _HACKCLUB_AI_URL,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "max_tokens": 4096,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                    },
                )
                resp.raise_for_status()
                data = resp.json()

      
        choices = data.get("choices", [])
        if not choices:
            logger.error("Hack Club AI returned empty choices")
            return None

        response_text = choices[0].get("message", {}).get("content", "")

      
        json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
        if not json_match:
            logger.error("Could not find JSON in Hack Club AI response: %s", response_text[:200])
            return None

        parsed = json.loads(json_match.group())
        return AISynthesisResponse(**parsed)

    except json.JSONDecodeError as exc:
        logger.error("Failed to parse Hack Club AI response JSON: %s", exc)
        return None
    except httpx.HTTPError as exc:
        logger.error("Hack Club AI API error: %s", exc)
        return None
    except Exception as exc:
        logger.error("Unexpected error in Hack Club AI synthesis: %s", exc)
        return None


async def check_tier3(
    claim_text: str,
    HCAI: str = "",
    Search: str = "",
) -> Optional[Verdict]:

    if not Search:

        if HCAI:
            logger.info(
                "Search not set; falling back to HCAI for Exa search"
            )

            Search = ""  
        else:
            logger.error("Tier 3 cannot run: Search is not configured.")
            return None

    truncated = _truncate_claim(claim_text)


    if Search:
        snippets = await _hackclub_search(truncated, Search)
        if not snippets and HCAI:
            logger.info("Tier 3 Brave search returned no snippets; trying Exa fallback.")
            snippets = await _hackclub_exa_search(truncated, HCAI)
    else:

        snippets = await _hackclub_exa_search(truncated, HCAI)

    logger.info("Tier 3 search returned %d snippet(s)", len(snippets))
    if not snippets:
        logger.info("Tier 3 had no search snippets to synthesize from.")
        return Verdict(
            label="Unverifiable",
            explanation="No search results found to verify this claim.",
            sources=[],
            tier="ai_search",
            confidence=0.0,
        )


    synthesis = await _hackclub_ai_synthesis(truncated, snippets, HCAI)
    if synthesis is None:

        source_urls = [s["url"] for s in snippets if s.get("url") and re.match(r"^https?://\S+$", s["url"])]
        return Verdict(
            label="Unverifiable",
            explanation="Unable to synthesize a verdict from available search results.",
            sources=source_urls[:3],
            tier="ai_search",
            confidence=0.0,
        )

    
    source_urls = synthesis.sources[:3]  
    if not source_urls:
        source_urls = [s["url"] for s in snippets[:3] if s.get("url") and re.match(r"^https?://\S+$", s["url"])]

    logger.info("Tier 3 result: %s (from %d snippets)", synthesis.verdict, len(snippets))

    return Verdict(
        label=synthesis.verdict,
        explanation=synthesis.explanation,
        sources=source_urls,
        tier="ai_search",
        confidence=0.7, 
    )


async def synthesize_verdict_from_evidence(
    claim_text: str,
    evidence: list[str],
    HCAI: str = "",
    source_tier: str = "fact_check_db",
) -> Optional[Verdict]:

    if not HCAI:
        logger.warning("No HCAI configured — cannot synthesize evidence-based verdict.")
        return None

    prompt = f"""You are a fact-checking assistant. Given a claim and extracted supporting evidence, answer whether the claim is True, False, Misleading, or Unverifiable.

Claim: {claim_text}

Evidence:
"""
    for item in evidence:
        if item:
            prompt += f"- {item}\n"
    prompt += "\nOnly use the evidence provided above. Do not hallucinate new facts. Respond with a JSON object containing verdict, explanation, and sources."

    try:
        async with _ai_semaphore:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    _HACKCLUB_AI_URL,
                    headers={
                        "Authorization": f"Bearer {HCAI}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": os.getenv("HACKCLUB_AI_MODEL", "google/gemini-2.5-flash"),
                        "max_tokens": 4096,
                        "messages": [
                            {"role": "system", "content": "You are an honest, conservative fact-check assistant."},
                            {"role": "user", "content": prompt},
                        ],
                    },
                )
                resp.raise_for_status()
                data = resp.json()

        choices = data.get("choices", [])
        if not choices:
            logger.error("Hack Club AI returned empty choices for evidence-based synthesis")
            return None

        response_text = choices[0].get("message", {}).get("content", "")
        json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
        if not json_match:
            logger.error("Could not parse JSON from evidence synthesis response: %s", response_text[:200])
            return None

        parsed = json.loads(json_match.group())
        synthesis = AISynthesisResponse(**parsed)

        allowed_sources = {
            item.strip()
            for item in evidence
            if is_well_formed_url(item.strip())
        }
        sources = [
            s for s in synthesis.sources
            if is_well_formed_url(s) and s in allowed_sources
        ]
        if not sources:
            sources = list(allowed_sources)[:3]

        return Verdict(
            label=synthesis.verdict,
            explanation=synthesis.explanation,
            sources=sources,
            tier=source_tier,
            confidence=0.8,
        )
    except Exception as exc:
        logger.error("Evidence-based AI synthesis failed: %s", exc)
        return None
