"""
keyword_classifier.py
=====================
Classifies keywords into PSO categories following Ausha's methodology
(but executed locally with no paid tool):

  DETECTED   — found in Apple Podcasts search results for this topic
  COMPETITOR — used by top-ranking competitor shows in their metadata
  FACTUAL    — specific entities: people, places, legislation, events
  LOCAL      — geographic terms (michigan, detroit, lansing, midwest, etc.)
  GUEST      — guest names or organizations mentioned in episode
  DEAD       — generic terms with no search value (podcast, episode, host, etc.)

Tag replacement order (PSO-correct):
  DETECTED → FACTUAL → LOCAL → GUEST → BRAND → (remove DEAD)
"""

import re
from typing import Dict, List, Set, Tuple


# ── Dead tags — remove these, they have zero PSO value ──────────────────────
DEAD_TAGS: Set[str] = {
    "podcast", "podcasting", "podcasts", "episode", "episodes",
    "show", "shows", "host", "hosts", "guest", "guests",
    "interview", "interviews", "audio", "listen", "subscribe",
    "follow", "review", "rating", "itunes", "spotify", "apple",
    "new episode", "weekly", "daily", "monthly", "season", "series",
    "talk", "talking", "discussion", "conversation", "chat",
    "news", "current events", "today", "this week", "latest",
}

# ── Local geographic signals ─────────────────────────────────────────────────
LOCAL_SIGNALS: Set[str] = {
    "michigan", "detroit", "lansing", "grand rapids", "flint",
    "ann arbor", "traverse city", "upper peninsula", "lower peninsula",
    "midwest", "great lakes", "rust belt", "swing state",
    "michigan voters", "michigan politics", "michigan legislature",
    "michigan governor", "michigan senate", "michigan house",
}

# ── Factual entity patterns ──────────────────────────────────────────────────
FACTUAL_PATTERNS = [
    r"\b(act|bill|law|amendment|resolution|executive order)\b",
    r"\b(senate|congress|house|supreme court|court|judge|justice)\b",
    r"\b(president|governor|senator|representative|mayor|commissioner)\b",
    r"\b(election|primary|ballot|vote|voting|redistricting|gerrymandering)\b",
    r"\b(iran|ukraine|russia|china|israel|gaza|nato|un|eu|imf|fed)\b",
    r"\b(nuclear|tariff|tariffs|sanctions|treaty|deal|agreement|accord)\b",
    r"\b(inflation|recession|gdp|unemployment|interest rate|federal reserve)\b",
    r"\b(trump|biden|harris|desantis|whitmer|nessel|benson)\b",
    r"\b(republican|democrat|gop|progressive|conservative|liberal|moderate)\b",
    r"\b(2024|2025|2026|2028)\b",
]

_FACTUAL_RE = re.compile("|".join(FACTUAL_PATTERNS), re.IGNORECASE)


class KeywordClassifier:
    """
    Classifies a set of candidate keywords into PSO categories.

    Usage:
        classifier = KeywordClassifier(
            detected_terms=["michigan politics", "iran nuclear deal"],
            competitor_terms={"michigan redistricting": 12, "political commentary": 8},
            episode_text="Full episode title + description text",
            guest_names=["John Smith", "Jane Doe"],
        )
        classified = classifier.classify()
    """

    def __init__(
        self,
        detected_terms: List[str],
        competitor_terms: Dict[str, int],
        episode_text: str = "",
        guest_names: List[str] = None,
        show_brand: str = "",
    ):
        self.detected = [t.lower().strip() for t in detected_terms]
        self.competitor = {k.lower().strip(): v for k, v in competitor_terms.items()}
        self.episode_text = episode_text.lower()
        self.guest_names = [g.lower().strip() for g in (guest_names or [])]
        self.show_brand = show_brand.lower().strip()

    def classify(self) -> Dict[str, List[str]]:
        """
        Returns a dict with keys: detected, competitor, factual, local, guest, dead.
        Each value is a list of terms in that category.
        """
        result = {
            "detected": [],
            "competitor": [],
            "factual": [],
            "local": [],
            "guest": [],
            "dead": [],
        }

        all_candidates = set(self.detected) | set(self.competitor.keys())

        for term in all_candidates:
            category = self._classify_term(term)
            result[category].append(term)

        # Sort each category by relevance
        result["detected"] = sorted(result["detected"],
                                     key=lambda t: self.detected.index(t)
                                     if t in self.detected else 99)
        result["competitor"] = sorted(result["competitor"],
                                       key=lambda t: self.competitor.get(t, 0),
                                       reverse=True)
        return result

    def _classify_term(self, term: str) -> str:
        """Classify a single term into its PSO category."""
        # Dead first — these are always removed regardless of other signals
        if term in DEAD_TAGS or any(dead in term for dead in DEAD_TAGS
                                     if len(dead) > 6):
            return "dead"

        # Detected via Apple Podcasts search — highest priority after dead/guest
        if term in self.detected:
            return "detected"

        # Guest names
        if any(guest in term or term in guest for guest in self.guest_names):
            return "guest"

        # Local geographic
        if any(local in term or term in local for local in LOCAL_SIGNALS):
            return "local"

        # Factual entities
        if _FACTUAL_RE.search(term):
            return "factual"

        # Competitor metadata
        if term in self.competitor:
            return "competitor"

        # Default: treat as factual if it appears in episode text
        if term in self.episode_text:
            return "factual"

        return "competitor"

    def build_pso_tag_set(self, max_tags: int = 12) -> List[str]:
        """
        Build the PSO-ordered tag replacement set.
        Order: DETECTED → FACTUAL → LOCAL → GUEST → BRAND
        Dead tags are excluded.
        """
        classified = self.classify()
        ordered = (
            classified["detected"][:3] +
            classified["factual"][:3] +
            classified["local"][:2] +
            classified["guest"][:2] +
            ([self.show_brand] if self.show_brand else [])
        )
        # Deduplicate preserving order
        seen = set()
        result = []
        for tag in ordered:
            if tag not in seen and tag not in DEAD_TAGS:
                seen.add(tag)
                result.append(tag)
        return result[:max_tags]

    @staticmethod
    def is_dead_tag(tag: str) -> bool:
        return tag.lower().strip() in DEAD_TAGS
