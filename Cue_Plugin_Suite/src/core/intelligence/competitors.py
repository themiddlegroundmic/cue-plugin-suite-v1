from __future__ import annotations

import re
from collections import Counter
from typing import Any, Dict, List

from src.core.types.models import CueShow


WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9-]{2,}")
STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "your", "you", "are",
    "podcast", "episode", "show", "today", "about", "into", "what", "when",
}


def extract_keywords(text: str, limit: int = 20) -> List[str]:
    counts = Counter(
        w.lower()
        for w in WORD_RE.findall(text or "")
        if w.lower() not in STOPWORDS and len(w) > 2
    )
    return [word for word, _ in counts.most_common(limit)]


class CompetitorAnalyzer:
    def analyze(self, plugin_competitors: List[Dict[str, Any]], user_show: CueShow | None = None) -> List[Dict[str, Any]]:
        user_keywords = set()
        if user_show:
            user_keywords = set(extract_keywords(user_show.title + " " + user_show.description))
        analyzed = []
        for competitor in plugin_competitors:
            title = competitor.get("title") or competitor.get("name") or ""
            description = competitor.get("description") or ""
            keywords = extract_keywords(f"{title} {description}")
            analyzed.append({
                "showTitle": title,
                "description": description,
                "feedUrl": competitor.get("feedUrl") or competitor.get("feed_url") or "",
                "episodeCount": competitor.get("episodeCount") or competitor.get("episode_count"),
                "recentEpisodeTitles": competitor.get("recentEpisodeTitles", []),
                "publishingFrequency": competitor.get("publishingFrequency"),
                "averageDescriptionLength": len(description.split()) if description else 0,
                "keywordOverlap": sorted(set(keywords) & user_keywords),
                "source": competitor.get("source", ""),
                "externalUrl": competitor.get("externalUrl") or competitor.get("external_url") or "",
            })
        return analyzed

