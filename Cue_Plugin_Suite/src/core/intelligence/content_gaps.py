from __future__ import annotations

from typing import Any, Dict, List

from .competitors import extract_keywords
from src.core.types.models import CueKeyword, CueShow


class ContentGapDetector:
    def detect(
        self,
        show: CueShow | None,
        competitors: List[Dict[str, Any]],
        keywords: List[CueKeyword],
        related_queries: List[str],
        youtube_terms: List[str] | None = None,
    ) -> List[Dict[str, Any]]:
        user_text = ""
        if show:
            user_text = " ".join([show.title, show.description] + [e.title + " " + e.description for e in show.episodes[:8]])
        user_keywords = set(extract_keywords(user_text, limit=80))
        competitor_terms = set()
        for competitor in competitors:
            competitor_terms.update(extract_keywords(f"{competitor.get('showTitle', '')} {competitor.get('description', '')}", limit=30))

        youtube_terms = youtube_terms or []
        gaps: List[Dict[str, Any]] = []
        missing_competitor_terms = sorted(term for term in competitor_terms if term not in user_keywords)[:6]
        if missing_competitor_terms:
            topic = " ".join(missing_competitor_terms[:3])
            gaps.append({
                "gap_topic": topic,
                "reason": "Competitors use terms the current metadata does not emphasize.",
                "supporting_signals": ["Apple/Spotify competitor keywords"],
                "suggested_angle": f"Create a focused segment or title angle around {topic}.",
                "confidence": 68,
            })

        for query in related_queries[:5]:
            normalized = query.lower()
            if normalized and normalized not in user_text.lower():
                gaps.append({
                    "gap_topic": query,
                    "reason": "Related search interest exists but is not clearly covered in the show or recent episode metadata.",
                    "supporting_signals": ["Google Trends related query"],
                    "suggested_angle": f"Explain {query} in a practical creator or listener context.",
                    "confidence": 72,
                })

        explicit = [k.value for k in keywords if not k.presentInUserContent][:5]
        if explicit:
            gaps.append({
                "gap_topic": explicit[0],
                "reason": "Candidate PSO keywords are missing from the current metadata.",
                "supporting_signals": ["Keyword coverage comparison"],
                "suggested_angle": f"Use {explicit[0]} naturally in the title, opening description, or chapter names.",
                "confidence": 64,
            })

        for term in youtube_terms[:5]:
            if term.lower() not in user_text.lower():
                gaps.append({
                    "gap_topic": term,
                    "reason": "YouTube result titles or descriptions emphasize this topic more than the current RSS metadata.",
                    "supporting_signals": ["YouTube Data API result metadata"],
                    "suggested_angle": f"Test a cross-platform angle focused on {term}.",
                    "confidence": 70,
                })

        if not gaps:
            gaps.append({
                "gap_topic": "No major v1 content gap",
                "reason": "Available public signals did not reveal a clear missing keyword or angle.",
                "supporting_signals": [],
                "suggested_angle": "Continue monitoring as more platform signals are collected.",
                "confidence": 55,
            })
        return gaps
