"""
core/keyword_classifier.py
==========================
YouTube keyword term classification engine.

Classifies each keyword into one of five categories based on
where the signal was detected. Classification order (priority):
  1. DETECTED   — appears in YouTube autocomplete results
  2. COMPETITOR — extracted from top-ranking competitor video titles/tags
  3. LOCAL      — contains a geographic identifier for the niche
  4. GUEST      — names a person, organization, or entity
  5. DEAD       — generic term with no search specificity

Classification follows the same methodology as the Podcast PSO plugin
but calibrated for YouTube's search behavior.
"""

from typing import List, Dict, Optional
from dataclasses import dataclass

# Dead keywords — generic terms that appear in many videos but drive no
# incremental discovery. YouTube's algorithm ignores these in ranking.
DEAD_KEYWORDS = {
    "video", "videos", "youtube", "channel", "subscribe", "watch",
    "new", "latest", "today", "now", "update", "news", "clip",
    "episode", "ep", "show", "podcast", "interview", "guest",
    "reaction", "react", "reacts", "commentary", "explained",
    "full", "official", "original", "live", "stream", "streaming",
    "highlights", "recap", "review", "analysis", "breakdown",
    "2024", "2025", "2026", "january", "february", "march",
    "april", "may", "june", "july", "august", "september",
    "october", "november", "december",
}

# Geographic identifiers for Michigan political commentary niche
MICHIGAN_GEO_TERMS = {
    "michigan", "detroit", "lansing", "grand rapids", "flint",
    "ann arbor", "warren", "sterling heights", "troy", "livonia",
    "westland", "dearborn", "clinton township", "canton", "shelby",
    "macomb", "oakland", "wayne county", "kent county", "washtenaw",
    "upper peninsula", "lower peninsula", "downriver", "metro detroit",
    "pure michigan", "mitten state",
}

# Political entity terms relevant to the niche
POLITICAL_ENTITY_TERMS = {
    "gretchen whitmer", "whitmer", "tudor dixon", "dana nessel",
    "jocelyn benson", "gary peters", "debbie stabenow", "elissa slotkin",
    "mike rogers", "john james", "michigan legislature", "michigan senate",
    "michigan house", "michigan supreme court", "michigan dnr",
    "michigan dot", "michigan egle", "michigan sos", "michigan ag",
}


@dataclass
class ClassifiedKeyword:
    """A keyword with its classification and source evidence."""
    keyword: str
    classification: str          # DETECTED / COMPETITOR / LOCAL / GUEST / DEAD
    source: str                  # Where the signal came from
    autocomplete_position: Optional[int] = None
    competitor_frequency: int = 0
    confidence: str = "HIGH"     # HIGH / MEDIUM / LOW

    def __str__(self) -> str:
        pos = f" (autocomplete #{self.autocomplete_position})" if self.autocomplete_position else ""
        freq = f" (competitor freq: {self.competitor_frequency})" if self.competitor_frequency else ""
        return f"[{self.classification}] {self.keyword}{pos}{freq} — {self.source}"


class YouTubeKeywordClassifier:
    """
    Classifies YouTube keywords by detection source.
    Detected terms take priority over all other classifications.
    """

    def __init__(
        self,
        geo_terms: Optional[set] = None,
        entity_terms: Optional[set] = None,
        dead_terms: Optional[set] = None,
    ):
        self.geo_terms = geo_terms or MICHIGAN_GEO_TERMS
        self.entity_terms = entity_terms or POLITICAL_ENTITY_TERMS
        self.dead_terms = dead_terms or DEAD_KEYWORDS

    def classify(
        self,
        keyword: str,
        autocomplete_suggestions: Optional[List[str]] = None,
        competitor_terms: Optional[Dict[str, int]] = None,
    ) -> ClassifiedKeyword:
        """
        Classify a single keyword.

        Priority order:
        1. DETECTED — in autocomplete results
        2. COMPETITOR — in competitor title/tag data
        3. LOCAL — geographic identifier
        4. GUEST — named entity
        5. DEAD — generic term
        """
        kw_lower = keyword.lower().strip()

        # 1. Check autocomplete (highest priority)
        if autocomplete_suggestions:
            for i, suggestion in enumerate(autocomplete_suggestions):
                if kw_lower in suggestion.lower() or suggestion.lower() in kw_lower:
                    return ClassifiedKeyword(
                        keyword=keyword,
                        classification="DETECTED",
                        source=f"YouTube autocomplete position {i + 1}",
                        autocomplete_position=i + 1,
                        confidence="HIGH",
                    )

        # 2. Check competitor terms
        if competitor_terms:
            freq = competitor_terms.get(kw_lower, 0)
            if freq >= 2:
                return ClassifiedKeyword(
                    keyword=keyword,
                    classification="COMPETITOR",
                    source=f"Competitor video titles/tags (frequency: {freq})",
                    competitor_frequency=freq,
                    confidence="HIGH" if freq >= 5 else "MEDIUM",
                )

        # 3. Check geographic terms
        for geo in self.geo_terms:
            if geo in kw_lower:
                return ClassifiedKeyword(
                    keyword=keyword,
                    classification="LOCAL",
                    source=f"Geographic identifier: '{geo}'",
                    confidence="HIGH",
                )

        # 4. Check entity terms
        for entity in self.entity_terms:
            if entity in kw_lower:
                return ClassifiedKeyword(
                    keyword=keyword,
                    classification="GUEST",
                    source=f"Named entity: '{entity}'",
                    confidence="HIGH",
                )

        # 5. Check dead terms
        words = set(kw_lower.split())
        dead_overlap = words & self.dead_terms
        if dead_overlap or kw_lower in self.dead_terms:
            return ClassifiedKeyword(
                keyword=keyword,
                classification="DEAD",
                source=f"Generic term with no search specificity: {dead_overlap or {kw_lower}}",
                confidence="HIGH",
            )

        # Default: unclassified but not dead
        return ClassifiedKeyword(
            keyword=keyword,
            classification="COMPETITOR",
            source="No autocomplete signal — treated as competitor/factual term",
            confidence="LOW",
        )

    def classify_batch(
        self,
        keywords: List[str],
        autocomplete_map: Optional[Dict[str, List[str]]] = None,
        competitor_terms: Optional[Dict[str, int]] = None,
    ) -> List[ClassifiedKeyword]:
        """
        Classify a list of keywords.

        Args:
            keywords: List of terms to classify.
            autocomplete_map: Dict mapping seed keywords to their autocomplete suggestions.
            competitor_terms: Dict mapping competitor terms to their frequency.

        Returns:
            List of ClassifiedKeyword objects.
        """
        results = []
        # Flatten autocomplete map into a single suggestion list
        all_suggestions = []
        if autocomplete_map:
            for suggestions in autocomplete_map.values():
                all_suggestions.extend(suggestions)

        for kw in keywords:
            classified = self.classify(
                kw,
                autocomplete_suggestions=all_suggestions or None,
                competitor_terms=competitor_terms,
            )
            results.append(classified)

        return results

    def filter_dead(self, keywords: List[ClassifiedKeyword]) -> List[ClassifiedKeyword]:
        """Return only non-dead keywords."""
        return [k for k in keywords if k.classification != "DEAD"]

    def sort_by_priority(self, keywords: List[ClassifiedKeyword]) -> List[ClassifiedKeyword]:
        """
        Sort keywords in PSO tag order:
        DETECTED → COMPETITOR → LOCAL → GUEST → DEAD
        """
        priority = {"DETECTED": 0, "COMPETITOR": 1, "LOCAL": 2, "GUEST": 3, "DEAD": 4}
        return sorted(keywords, key=lambda k: priority.get(k.classification, 5))
