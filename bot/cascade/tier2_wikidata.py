

from __future__ import annotations

import asyncio
import html
import logging
import re
from typing import Optional

from SPARQLWrapper import SPARQLWrapper, JSON
import httpx
from difflib import SequenceMatcher

from bot.cascade.verdict import Verdict

logger = logging.getLogger(__name__)


_wikidata_semaphore = asyncio.Semaphore(3)

_WIKIDATA_ENDPOINT = "https://query.wikidata.org/sparql"


_BIRTH_PATTERN = re.compile(
    r"(?:who was|who is|the person)?\s*"
    r"(?:what year|what date|when)?\s*"
    r"was\s+(\w[\w\s]+?)\s+born\s*(?:in\s+(\d{4})|on\s+(.+?))?\s*\??$",
    re.IGNORECASE,
)


_DEATH_PATTERN = re.compile(
    r"(\w[\w\s]+?)\s+(?:died|was born and died)\s+(?:in\s+(\d{4})|on\s+(.+?))?\s*\??$",
    re.IGNORECASE,
)

_POPULATION_PATTERN = re.compile(
    r"(?:the\s+)?population\s+(?:of|in)\s+([\w\s]+?)\s+(?:is|was|were)\s+([\d,.\s]+)\s*\??$",
    re.IGNORECASE,
)
_POPULATION_PATTERN_ALT = re.compile(
    r"([\w\s]+?)\s+(?:has|have|had)\s+(?:a\s+)?population\s+(?:of|about|around|approximately)?\s*([\d,.\s]+)\s*\??$",
    re.IGNORECASE,
)


_EVENT_DATE_PATTERN = re.compile(
    r"([\w\s]+?)\s+(?:happened|occurred|started|began|ended)\s+in\s+(\d{4})\s*\??$",
    re.IGNORECASE,
)


_CAPITAL_PATTERN = re.compile(
    r"([\w\s]+?)\s+(?:is|are)\s+the\s+capital\s+(?:of|city\s+of)\s+([\w\s]+?)\s*\??$",
    re.IGNORECASE,
)


def _escape_sparql_literal(value: str) -> str:
   

    value = html.unescape(value)

    value = value.replace("\\", "\\\\")
    value = value.replace('"', '\\"')
    value = value.replace("'", "\\'")
    value = value.strip()

    return value[:200]


def _parse_number(text: str) -> int | float | None:

    text = text.strip().replace(",", "").replace(".", "")
    try:
        return int(text)
    except ValueError:
        return None


async def _query_wikidata(sparql: str) -> dict | None:

    try:
        async with _wikidata_semaphore:
            wrapper = SPARQLWrapper(_WIKIDATA_ENDPOINT)
            wrapper.setQuery(sparql)
            wrapper.setReturnFormat(JSON)

            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, wrapper.query)
            return result.convert()
    except Exception as exc:
        logger.error("Wikidata SPARQL query failed: %s", exc)
        return None


async def _check_birth_date(claim_text: str) -> Optional[Verdict]:
  
    match = _BIRTH_PATTERN.search(claim_text)
    if not match:
        return None

    person_name = _escape_sparql_literal(match.group(1))
    year = match.group(2)

    sparql = f"""
    SELECT ?personLabel ?birthDate WHERE {{
      ?person wdt:P31 wd:Q5 .
      ?person rdfs:label "{person_name}"@en .
      ?person wdt:P569 ?birthDate .
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }} LIMIT 5
    """

    data = await _query_wikidata(sparql)
    if not data:
        return None

    bindings = data.get("results", {}).get("bindings", [])
    if not bindings:
        return None

    row = bindings[0]
    birth_date_str = row.get("birthDate", {}).get("value", "")
    person_label = row.get("personLabel", {}).get("value", person_name)


    year_match = re.search(r"(\d{4})", birth_date_str)
    if not year_match:
        return None

    actual_year = int(year_match.group(1))

    if year:
        claimed_year = _parse_number(year)
        if claimed_year is not None:
            if int(claimed_year) == actual_year:
                return Verdict(
                    label="Unverifiable",
                    explanation=f"{person_label} was indeed born in {actual_year}.",
                    sources=[f"https://www.wikidata.org/wiki/{row.get('person', {}).get('value', '').split('/')[-1]}"],
                    tier="knowledge_evidence",
                    confidence=0.95,
                )
            else:
                return Verdict(
                    label="Unverifiable",
                    explanation=f"{person_label} was born in {actual_year}, not {int(claimed_year)}.",
                    sources=[f"https://www.wikidata.org/wiki/{row.get('person', {}).get('value', '').split('/')[-1]}"],
                    tier="knowledge_evidence",
                    confidence=0.95,
                )


    return Verdict(
        label="Unverifiable",
        explanation=f"{person_label} was born on {birth_date_str[:10]}.",
        sources=[f"https://www.wikidata.org/wiki/{row.get('person', {}).get('value', '').split('/')[-1]}"],
        tier="knowledge_evidence",
        confidence=0.9,
    )


async def _check_death_date(claim_text: str) -> Optional[Verdict]:
  
    match = _DEATH_PATTERN.search(claim_text)
    if not match:
        return None

    person_name = _escape_sparql_literal(match.group(1))
    year = match.group(2)

    sparql = f"""
    SELECT ?personLabel ?deathDate ?person WHERE {{
      ?person wdt:P31 wd:Q5 .
      ?person rdfs:label "{person_name}"@en .
      ?person wdt:P570 ?deathDate .
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }} LIMIT 5
    """

    data = await _query_wikidata(sparql)
    if not data:
        return None

    bindings = data.get("results", {}).get("bindings", [])
    if not bindings:
        return None

    row = bindings[0]
    death_date_str = row.get("deathDate", {}).get("value", "")
    person_label = row.get("personLabel", {}).get("value", person_name)
    person_id = row.get("person", {}).get("value", "").split("/")[-1]

    year_match = re.search(r"(\d{4})", death_date_str)
    if not year_match:
        return None

    actual_year = int(year_match.group(1))

    if year:
        claimed_year = _parse_number(year)
        if claimed_year is not None:
            if int(claimed_year) == actual_year:
                return Verdict(
                    label="Unverifiable",
                    explanation=f"{person_label} died in {actual_year}.",
                    sources=[f"https://www.wikidata.org/wiki/{person_id}"],
                    tier="knowledge_evidence",
                    confidence=0.95,
                )
            else:
                return Verdict(
                    label="Unverifiable",
                    explanation=f"{person_label} died in {actual_year}, not {int(claimed_year)}.",
                    sources=[f"https://www.wikidata.org/wiki/{person_id}"],
                    tier="knowledge_evidence",
                    confidence=0.95,
                )

    return Verdict(
        label="Unverifiable",
        explanation=f"{person_label} died on {death_date_str[:10]}.",
        sources=[f"https://www.wikidata.org/wiki/{person_id}"],
        tier="knowledge_evidence",
        confidence=0.9,
    )


async def _check_population(claim_text: str) -> Optional[Verdict]:

    match = _POPULATION_PATTERN.search(claim_text) or _POPULATION_PATTERN_ALT.search(claim_text)
    if not match:
        return None

    place_name = _escape_sparql_literal(match.group(1))
    claimed_pop = _parse_number(match.group(2))
    if claimed_pop is None:
        return None

    sparql = f"""
    SELECT ?placeLabel ?population ?place WHERE {{
      ?place wdt:P1082 ?population .
      ?place rdfs:label "{place_name}"@en .
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }} ORDER BY DESC(?population) LIMIT 3
    """

    data = await _query_wikidata(sparql)
    if not data:
        return None

    bindings = data.get("results", {}).get("bindings", [])
    if not bindings:
        return None


    best = None
    best_diff = float("inf")
    for row in bindings:
        pop = int(row.get("population", {}).get("value", "0"))
        diff = abs(pop - claimed_pop)
        if diff < best_diff:
            best_diff = diff
            best = row

    if best is None:
        return None

    actual_pop = int(best.get("population", {}).get("value", "0"))
    place_label = best.get("placeLabel", {}).get("value", place_name)
    place_id = best.get("place", {}).get("value", "").split("/")[-1]

    tolerance = actual_pop * 0.1
    if abs(actual_pop - claimed_pop) <= tolerance:
        return Verdict(
            label="Unverifiable",
            explanation=f"The population of {place_label} is approximately {actual_pop:,}.",
            sources=[f"https://www.wikidata.org/wiki/{place_id}"],
            tier="knowledge_evidence",
            confidence=0.85,
        )
    else:
        return Verdict(
            label="Unverifiable",
            explanation=f"The population of {place_label} is approximately {actual_pop:,}, not {claimed_pop:,}.",
            sources=[f"https://www.wikidata.org/wiki/{place_id}"],
            tier="knowledge_evidence",
            confidence=0.85,
        )


async def _check_event_date(claim_text: str) -> Optional[Verdict]:
  
    match = _EVENT_DATE_PATTERN.search(claim_text)
    if not match:
        return None

    event_name = _escape_sparql_literal(match.group(1))
    claimed_year = _parse_number(match.group(2))
    if claimed_year is None:
        return None

    sparql = f"""
    SELECT ?eventLabel ?inception ?event WHERE {{
      ?event wdt:P31/wdt:P279* wd:Q1190554 .
      ?event rdfs:label "{event_name}"@en .
      ?event wdt:P571 ?inception .
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }} LIMIT 5
    """

    data = await _query_wikidata(sparql)
    if not data:
        return None

    bindings = data.get("results", {}).get("bindings", [])
    if not bindings:
        return None

    row = bindings[0]
    inception_str = row.get("inception", {}).get("value", "")
    event_label = row.get("eventLabel", {}).get("value", event_name)
    event_id = row.get("event", {}).get("value", "").split("/")[-1]

    year_match = re.search(r"(\d{4})", inception_str)
    if not year_match:
        return None

    actual_year = int(year_match.group(1))

    if int(claimed_year) == actual_year:
        return Verdict(
            label="Unverifiable",
            explanation=f"{event_label} occurred in {actual_year}.",
            sources=[f"https://www.wikidata.org/wiki/{event_id}"],
            tier="knowledge_evidence",
            confidence=0.9,
        )
    else:
        return Verdict(
            label="Unverifiable",
            explanation=f"{event_label} occurred in {actual_year}, not {int(claimed_year)}.",
            sources=[f"https://www.wikidata.org/wiki/{event_id}"],
            tier="knowledge_evidence",
            confidence=0.9,
        )


async def _check_capital(claim_text: str) -> Optional[Verdict]:
  
    match = _CAPITAL_PATTERN.search(claim_text)
    if not match:
        return None

    city_name = _escape_sparql_literal(match.group(1))
    country_name = _escape_sparql_literal(match.group(2))

    sparql = f"""
    SELECT ?cityLabel ?countryLabel ?city WHERE {{
      ?country wdt:P36 ?city .
      ?city rdfs:label "{city_name}"@en .
      ?country rdfs:label "{country_name}"@en .
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }} LIMIT 5
    """

    data = await _query_wikidata(sparql)
    if not data:
        return None

    bindings = data.get("results", {}).get("bindings", [])
    if not bindings:
        return None

    row = bindings[0]
    city_label = row.get("cityLabel", {}).get("value", city_name)
    country_label = row.get("countryLabel", {}).get("value", country_name)
    city_id = row.get("city", {}).get("value", "").split("/")[-1]

    return Verdict(
        label="Unverifiable",
        explanation=f"{city_label} is indeed the capital of {country_label}.",
        sources=[f"https://www.wikidata.org/wiki/{city_id}"],
        tier="knowledge_evidence",
        confidence=0.9,
    )



_HANDLERS = [
    _check_birth_date,
    _check_death_date,
    _check_population,
    _check_capital,
    _check_event_date,
]


async def check_tier2(claim_text: str) -> Optional[Verdict]:

    pattern_matched = False
    for handler in _HANDLERS:
        result = await handler(claim_text)
        if result is not None:
            logger.info("Tier 2 match found via %s: %s", handler.__name__, result.label)
            return result
        if handler.__name__ == "_check_birth_date" and _BIRTH_PATTERN.search(claim_text):
            pattern_matched = True
        elif handler.__name__ == "_check_death_date" and _DEATH_PATTERN.search(claim_text):
            pattern_matched = True
        elif handler.__name__ == "_check_population" and (_POPULATION_PATTERN.search(claim_text) or _POPULATION_PATTERN_ALT.search(claim_text)):
            pattern_matched = True
        elif handler.__name__ == "_check_capital" and _CAPITAL_PATTERN.search(claim_text):
            pattern_matched = True
        elif handler.__name__ == "_check_event_date" and _EVENT_DATE_PATTERN.search(claim_text):
            pattern_matched = True

    if pattern_matched:
        logger.debug(
            "Tier 2 matched a known pattern but found no structured data for claim; falling back to Wikipedia search"
        )
    else:
        logger.debug("Tier 2: no pattern matched for claim")

  
    try:
        wiki_verdict = await _check_wikipedia_general(claim_text)
        if wiki_verdict is not None:
            logger.info("Tier 2 (Wikipedia) provided a fallback result")
            return wiki_verdict
    except Exception as exc:
        logger.debug("Wikipedia fallback failed: %s", exc)

    return None


def _normalize_search_text(text: str) -> list[str]:
    text = re.sub(r"[^a-z0-9\s]", "", text.lower())
    tokens = [t for t in text.split() if t and t not in {"a", "an", "the", "is", "are", "was", "were", "of", "in", "on", "and", "or", "to", "for", "with", "as", "by", "from", "not", "no", "that", "this", "it", "its", "be", "been", "being", "have", "has", "had"}]
    normalized = []
    for token in tokens:
        if token.endswith("ies") and len(token) > 4:
            normalized.append(token[:-3] + "y")
        elif token.endswith("es") and len(token) > 4 and not token.endswith("ses"):
            normalized.append(token[:-2])
        elif token.endswith("s") and len(token) > 3 and not token.endswith("ss"):
            normalized.append(token[:-1])
        else:
            normalized.append(token)
    return normalized


def _extract_core_search_phrase(text: str) -> str:
    text = re.sub(r"\([^)]*\)", "", text)
    match = re.search(
        r"^(.+?)\s+(?:is|are|was|were|has|have|had|will|would|can|could|should|shall|may|might|must|died|born|located|built|constructed|destroyed|moved|dismantled|opened|closed|started|occurred|happened|founded|published|released|claimed|reported)\b",
        text,
        re.IGNORECASE,
    )
    if match:
        core = match.group(1).strip()
        core = re.sub(r"^(the|a|an)\s+", "", core, flags=re.IGNORECASE)
        core = re.sub(r"\b(structure|building|tower|bridge|road|film|movie|book|document|report|article)$", "", core, flags=re.IGNORECASE).strip()
        return core
    return text.strip()


def _search_relevance_score(claim_text: str, title: str, snippet: str) -> float:
    claim_tokens = set(_normalize_search_text(claim_text))
    title_tokens = set(_normalize_search_text(title))
    snippet_tokens = set(_normalize_search_text(snippet))
    if not claim_tokens:
        return 0.0
    title_overlap = len(claim_tokens & title_tokens) / len(claim_tokens)
    snippet_overlap = len(claim_tokens & snippet_tokens) / len(claim_tokens)
    return max(title_overlap, snippet_overlap)


def _is_numeric_or_date_claim(claim_text: str) -> bool:
    return bool(
        re.search(r"\b(born|died|age|population|in|on)\b", claim_text, re.IGNORECASE)
        and re.search(r"\d{3,4}", claim_text)
    )


async def _search_wikipedia_articles(search_text: str) -> list[tuple[float, str, str]]:
    search_url = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "list": "search",
        "srsearch": search_text,
        "format": "json",
        "srlimit": 5,
        "srprop": "snippet",
    }

    async with _wikidata_semaphore:
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {"User-Agent": "FactfyBot/1.0 (https://github.com/; contact: none)"}
            resp = await client.get(search_url, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()

    results = data.get("query", {}).get("search", [])
    scored_sources: list[tuple[float, str, str]] = []
    claim_tokens = set(_normalize_search_text(search_text))
    for r in results:
        title = r.get("title", "")
        snippet = r.get("snippet", "")
        score = _search_relevance_score(search_text, title, snippet)

        title_tokens = [t for t in re.sub(r"[^a-z0-9\s]", "", title.lower()).split() if t]
        if title_tokens and len(title_tokens) <= 3 and any(t in claim_tokens for t in title_tokens):
            score = min(1.0, score + 0.45)

        if score >= 0.35:
            url = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
            scored_sources.append((score, title, url))

    return scored_sources


async def _fetch_wikipedia_extracts(titles: list[str]) -> dict[str, str]:
    """Fetch readable page extracts so Tier 2 passes actual evidence to the AI."""
    if not titles:
        return {}

    params = {
        "action": "query",
        "prop": "extracts",
        "explaintext": 1,
        "exintro": 0,
        "exchars": 5000,
        "titles": "|".join(titles[:3]),
        "format": "json",
        "redirects": 1,
    }
    headers = {"User-Agent": "FactfyBot/1.0 (https://github.com/unknowngamer69/Factfy; contact: none)"}

    try:
        async with _wikidata_semaphore:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    "https://en.wikipedia.org/w/api.php",
                    params=params,
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Wikipedia extract request failed: %s", exc)
        return {}

    pages = data.get("query", {}).get("pages", {})
    extracts: dict[str, str] = {}
    for page in pages.values():
        title = page.get("title", "")
        extract = re.sub(r"\s+", " ", page.get("extract", "")).strip()
        if title and extract:
            extracts[title] = extract[:5000]
    return extracts


async def _check_wikipedia_general(claim_text: str) -> Optional[Verdict]:

    search_url = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "list": "search",
        "srsearch": claim_text,
        "format": "json",
        "srlimit": 5,
        "srprop": "snippet",
    }

    primary_sources = await _search_wikipedia_articles(claim_text)
    core_phrase = _extract_core_search_phrase(claim_text)
    secondary_sources: list[tuple[float, str, str]] = []
    if core_phrase and core_phrase.lower() != claim_text.strip().lower():
        secondary_sources = await _search_wikipedia_articles(core_phrase)

    scored_sources = primary_sources
    if not scored_sources and secondary_sources:
        scored_sources = secondary_sources
    elif secondary_sources and secondary_sources[0][0] > scored_sources[0][0] + 0.1:
        scored_sources = secondary_sources

    if not scored_sources:
        logger.debug("Wikipedia fallback found no sufficiently relevant articles for claim: %s", claim_text)
        return None

    exact_matches = [item for item in scored_sources if item[1].lower() == claim_text.strip().lower()]
    if exact_matches:
        scored_sources = exact_matches

    scored_sources.sort(key=lambda item: item[0], reverse=True)
    top_sources = scored_sources[:3]
    sources = [url for _, _, url in top_sources]
    titles = [title for _, title, _ in top_sources]

    # Search results only identify candidate pages. Fetch the actual page text so
    # the downstream AI can reason over evidence instead of seeing bare URLs.
    extracts = await _fetch_wikipedia_extracts(titles)
    evidence_parts = []
    for title, url in zip(titles, sources):
        extract = extracts.get(title)
        if extract:
            evidence_parts.append(f"[{title}] {extract} (Source: {url})")

    if not evidence_parts:
        logger.debug("Wikipedia pages were found but no readable extracts were returned")
        return None

    explanation = (
        "Wikipedia evidence retrieved for AI synthesis:\n"
        + "\n".join(evidence_parts)
    )

    return Verdict(
        label="Unverifiable",
        explanation=explanation,
        sources=sources,
        tier="knowledge_evidence",
        confidence=0.5,
    )
