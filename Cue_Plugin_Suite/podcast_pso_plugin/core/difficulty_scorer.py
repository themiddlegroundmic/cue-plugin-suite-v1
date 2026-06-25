"""
difficulty_scorer.py
====================
Calculates two scores for each keyword and episode:

1. DIFFICULTY SCORE (0–100) — how hard it is to rank for a keyword.
   Formula mirrors Ausha's methodology using free data:
     competitor_count × episode_depth_weight × recency_weight

2. PSO SCORE (0–100) — how well an episode is currently optimized.
   Factors: title quality, description quality, tag quality, safety flags,
   boilerplate position, chapter presence.

Priority assignment:
   P0 — show-level global fix (description, author tag)
   P1 — top 20 highest-opportunity episodes
   P2 — next 50 episodes
   P3 — archive backfill
"""

import math
from datetime import datetime, timezone
from typing import Dict, List, Optional

from .feed_parser import Episode, Show


# ── Difficulty calculation weights ───────────────────────────────────────────

def calculate_difficulty(
    competitor_count: int,
    avg_episode_count: float,
    avg_recency_days: float,
) -> int:
    """
    Difficulty score (0–100).
    Higher = harder to rank.

    competitor_count:   number of shows in top 10 for this keyword
    avg_episode_count:  average episode count of top 10 competitors
    avg_recency_days:   average days since last episode for top 10 competitors
    """
    # Base: competitor saturation (0–40 points)
    saturation = min(40, competitor_count * 4)

    # Depth: established shows with large catalogs are harder to beat (0–35 points)
    depth = min(35, (avg_episode_count / 10) * 3.5)

    # Recency: active shows are harder to beat (0–25 points)
    # Lower recency_days = more active = harder
    if avg_recency_days <= 7:
        recency = 25
    elif avg_recency_days <= 30:
        recency = 20
    elif avg_recency_days <= 90:
        recency = 12
    elif avg_recency_days <= 365:
        recency = 5
    else:
        recency = 0

    raw = saturation + depth + recency
    return min(100, max(0, int(raw)))


def difficulty_label(score: int) -> str:
    if score >= 70:
        return "Hard"
    elif score >= 40:
        return "Medium"
    else:
        return "Easy"


# ── PSO Score calculation ────────────────────────────────────────────────────

BOILERPLATE_SIGNALS = [
    "send us", "fan mail", "buymeacoffee", "buy me a coffee",
    "brio", "trimmer", "sponsor", "support the show",
    "follow us on", "subscribe to", "leave a review",
]

DEAD_TAGS = {
    "podcast", "podcasting", "podcasts", "episode", "episodes",
    "show", "shows", "host", "hosts", "guest", "guests",
    "interview", "interviews", "audio", "listen", "subscribe",
}


def score_episode(episode: Episode) -> int:
    """
    Calculate PSO score (0–100) for a single episode.
    Returns integer score.
    """
    score = 100

    # ── Title checks (max deduction: 30) ────────────────────────────────────
    title = episode.title or ""
    if len(title) > 80:
        score -= 10  # Too long for Apple Podcasts display
    if len(title) < 20:
        score -= 15  # Too vague / short
    vague_starters = ["ep", "episode", "episode #", "#", "s0", "s1", "s2",
                       "part", "bonus", "special", "update", "news"]
    if any(title.lower().startswith(v) for v in vague_starters):
        score -= 10
    if not any(c.isalpha() for c in title):
        score -= 20

    # ── Description checks (max deduction: 35) ───────────────────────────────
    desc = episode.description or ""
    first_150 = desc[:150].lower()

    if not desc:
        score -= 35
    else:
        # Boilerplate at top
        if any(sig in first_150 for sig in BOILERPLATE_SIGNALS):
            score -= 20
        # Description too short
        if len(desc.split()) < 50:
            score -= 10
        # No chapters / timestamps
        if "(00:00)" not in desc and "00:00" not in desc:
            score -= 5

    # ── Tag checks (max deduction: 20) ──────────────────────────────────────
    tags = episode.tags or []
    if not tags:
        score -= 20
    else:
        dead_count = sum(1 for t in tags if t.lower() in DEAD_TAGS)
        if dead_count >= len(tags) * 0.5:
            score -= 15  # More than half the tags are dead
        elif dead_count > 0:
            score -= 5
        if len(tags) < 3:
            score -= 5

    # ── Safety flags (max deduction: 15) ────────────────────────────────────
    if episode.safety_flags:
        score -= min(15, len(episode.safety_flags) * 5)

    return max(0, min(100, score))


def assign_priority(score: int, safety_flags: List[str],
                    has_boilerplate: bool) -> str:
    """Assign P1/P2/P3 priority based on score and flags."""
    if safety_flags or (has_boilerplate and score < 60):
        return "P1"
    if score < 55:
        return "P1"
    if score < 75:
        return "P2"
    return "P3"


class DifficultyScorer:
    """
    Scores all episodes in a show and assigns priorities.

    Usage:
        scorer = DifficultyScorer()
        scored_show = scorer.score_show(show)
    """

    def score_show(self, show: Show) -> Show:
        """Score all episodes and assign priorities. Mutates episode objects."""
        all_scores = []

        for episode in show.episodes:
            pso = score_episode(episode)
            episode.pso_score = pso

            first_150 = (episode.description or "")[:150].lower()
            has_boilerplate = any(sig in first_150 for sig in BOILERPLATE_SIGNALS)
            episode.priority = assign_priority(
                pso, episode.safety_flags, has_boilerplate
            )
            all_scores.append(pso)

        # Re-rank: top 20 lowest scores → P1, next 50 → P2, rest → P3
        sorted_episodes = sorted(show.episodes, key=lambda e: e.pso_score)
        for i, ep in enumerate(sorted_episodes):
            if i < 20:
                ep.priority = "P1"
            elif i < 70:
                ep.priority = "P2"
            else:
                ep.priority = "P3"

        return show

    def score_keyword_difficulty(
        self,
        competitors: List[Dict],
    ) -> Dict:
        """
        Calculate difficulty score for a keyword given its competitor list.
        competitors: list from AppleDetector.get_competitors()
        """
        if not competitors:
            return {"score": 0, "label": "Easy", "competitor_count": 0}

        count = len(competitors)
        avg_episodes = sum(c.get("episode_count", 0) for c in competitors) / count

        # Estimate recency from episode count as proxy (no pub_date in iTunes API)
        # More episodes generally = more active show
        avg_recency_days = max(7, 365 - (avg_episodes * 1.5))

        score = calculate_difficulty(count, avg_episodes, avg_recency_days)
        return {
            "score": score,
            "label": difficulty_label(score),
            "competitor_count": count,
            "avg_episode_count": round(avg_episodes, 1),
        }
