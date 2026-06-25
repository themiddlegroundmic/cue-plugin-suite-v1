"""
core/autocomplete.py
====================
YouTube autocomplete keyword suggestions.

Uses the YouTube suggest endpoint (same endpoint the YouTube search bar
uses when you start typing) to pull demand-ordered keyword completions.
This endpoint is public, requires no API key, and costs 0 quota units.

The order of suggestions reflects YouTube's internal demand weighting —
suggestions that appear first are searched more frequently.
"""

import logging
import urllib.parse
from typing import List, Dict, Optional

import requests

logger = logging.getLogger(__name__)

# YouTube's internal autocomplete endpoint — same one the search bar uses
YOUTUBE_SUGGEST_URL = "https://suggestqueries.google.com/complete/search"


def get_autocomplete_suggestions(
    seed_keyword: str,
    language: str = "en",
    region: str = "US",
    max_results: int = 10,
) -> List[str]:
    """
    Fetch YouTube autocomplete suggestions for a seed keyword.

    Args:
        seed_keyword: The base keyword to expand.
        language: BCP-47 language code.
        region: ISO 3166-1 alpha-2 country code.
        max_results: Maximum number of suggestions to return.

    Returns:
        List of suggested keyword strings in demand order (highest first).
    """
    params = {
        "client": "youtube",
        "ds": "yt",
        "q": seed_keyword,
        "hl": language,
        "gl": region,
        "output": "toolbar",
    }

    try:
        resp = requests.get(
            YOUTUBE_SUGGEST_URL,
            params=params,
            timeout=8,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.warning(f"YouTube autocomplete request failed for '{seed_keyword}': {e}")
        return []

    # Parse the XML-style response
    suggestions = []
    try:
        import xml.etree.ElementTree as ET
        root = ET.fromstring(resp.text)
        for suggestion in root.findall(".//suggestion"):
            data = suggestion.get("data", "")
            if data and data.lower() != seed_keyword.lower():
                suggestions.append(data)
                if len(suggestions) >= max_results:
                    break
    except Exception as e:
        logger.warning(f"Could not parse autocomplete response for '{seed_keyword}': {e}")
        return []

    return suggestions


def expand_keyword_set(
    seed_keywords: List[str],
    prefixes: Optional[List[str]] = None,
    suffixes: Optional[List[str]] = None,
    language: str = "en",
    region: str = "US",
) -> Dict[str, List[str]]:
    """
    Expand a list of seed keywords using autocomplete, optionally with
    prefix/suffix modifiers to surface long-tail variations.

    Args:
        seed_keywords: Base keywords to expand.
        prefixes: Optional list of prefixes to prepend (e.g. ["how", "why", "best"]).
        suffixes: Optional list of suffixes to append (e.g. ["2024", "explained", "today"]).
        language: BCP-47 language code.
        region: ISO 3166-1 alpha-2 country code.

    Returns:
        Dict mapping each seed keyword to its list of autocomplete suggestions.
    """
    results: Dict[str, List[str]] = {}

    queries_to_run = list(seed_keywords)

    if prefixes:
        for seed in seed_keywords:
            for prefix in prefixes:
                queries_to_run.append(f"{prefix} {seed}")

    if suffixes:
        for seed in seed_keywords:
            for suffix in suffixes:
                queries_to_run.append(f"{seed} {suffix}")

    for query in queries_to_run:
        suggestions = get_autocomplete_suggestions(query, language=language, region=region)
        if suggestions:
            results[query] = suggestions

    return results


def classify_autocomplete_signal(
    keyword: str,
    suggestions: List[str],
) -> Dict[str, object]:
    """
    Determine if a keyword appears in autocomplete and at what position.

    Args:
        keyword: The keyword to check.
        suggestions: List of autocomplete suggestions for a seed term.

    Returns:
        Dict with 'detected' (bool), 'position' (int or None), 'signal_strength' (str).
    """
    keyword_lower = keyword.lower().strip()
    for i, suggestion in enumerate(suggestions):
        if keyword_lower in suggestion.lower():
            position = i + 1
            if position <= 3:
                strength = "STRONG"
            elif position <= 6:
                strength = "MODERATE"
            else:
                strength = "WEAK"
            return {
                "detected": True,
                "position": position,
                "signal_strength": strength,
                "matched_suggestion": suggestion,
            }

    return {
        "detected": False,
        "position": None,
        "signal_strength": "NONE",
        "matched_suggestion": None,
    }
