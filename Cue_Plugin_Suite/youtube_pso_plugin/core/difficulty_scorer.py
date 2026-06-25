"""
core/difficulty_scorer.py
=========================
YouTube PSO score (0–100) and keyword difficulty formula.

Difficulty is calculated from three signals:
  1. Competitor channel strength — average subscriber count of top-ranking channels
  2. View velocity — average views on top-ranking videos for this keyword
  3. Autocomplete position — earlier position = higher demand = higher competition

PSO Score (opportunity score) inverts difficulty and weights by demand:
  PSO Score = (Demand × (100 - Difficulty)) / 100
  Higher PSO Score = better opportunity (high demand, low competition)
"""

import math
from typing import List, Optional, Dict
from dataclasses import dataclass

from .search_rank import KeywordRankResult
from .competitor_scraper import CompetitorProfile


@dataclass
class DifficultyResult:
    """Difficulty and PSO score for a single keyword."""
    keyword: str
    difficulty: int          # 0–100 (higher = harder to rank)
    demand_score: int        # 0–100 (proxy from autocomplete position + trends)
    pso_score: int           # 0–100 (opportunity score — higher is better)
    difficulty_label: str    # LOW / MEDIUM / HIGH
    competitor_count: int    # Number of strong channels ranking for this keyword
    avg_competitor_views: int
    your_rank: Optional[int]
    recommendation: str

    @property
    def rank_label(self) -> str:
        if self.your_rank is None:
            return "Not ranking"
        return f"#{self.your_rank}"


class YouTubeDifficultyScorer:
    """
    Calculates difficulty and PSO opportunity scores for YouTube keywords.
    """

    # Subscriber thresholds for difficulty weighting
    LARGE_CHANNEL = 100_000
    MEDIUM_CHANNEL = 10_000
    SMALL_CHANNEL = 1_000

    # View count thresholds
    HIGH_VIEWS = 500_000
    MEDIUM_VIEWS = 50_000
    LOW_VIEWS = 5_000

    def score(
        self,
        rank_result: KeywordRankResult,
        competitor_profiles: Optional[List[CompetitorProfile]] = None,
        autocomplete_position: Optional[int] = None,
        trends_score: Optional[int] = None,
    ) -> DifficultyResult:
        """
        Calculate difficulty and PSO score for a single keyword.

        Args:
            rank_result: Search rank result for this keyword.
            competitor_profiles: Competitor channel profiles (for subscriber data).
            autocomplete_position: Position in YouTube autocomplete (1 = highest demand).
            trends_score: Google Trends interest score 0–100.

        Returns:
            DifficultyResult with difficulty, demand, and PSO score.
        """
        keyword = rank_result.keyword
        top_results = rank_result.top_results[:10]

        # ── Difficulty calculation ────────────────────────────────────────────

        difficulty = 0

        # Factor 1: Competitor channel strength (0–40 points)
        # Build a map of channel_id → subscriber count from profiles
        sub_map: Dict[str, int] = {}
        if competitor_profiles:
            for profile in competitor_profiles:
                sub_map[profile.channel_id] = profile.subscriber_count

        if top_results:
            channel_ids = [r.channel_id for r in top_results[:5]]
            sub_counts = [sub_map.get(ch_id, 0) for ch_id in channel_ids if ch_id in sub_map]

            if sub_counts:
                avg_subs = sum(sub_counts) / len(sub_counts)
                if avg_subs >= self.LARGE_CHANNEL:
                    difficulty += 40
                elif avg_subs >= self.MEDIUM_CHANNEL:
                    difficulty += 25
                elif avg_subs >= self.SMALL_CHANNEL:
                    difficulty += 12
                else:
                    difficulty += 5
            else:
                # No subscriber data — estimate from result count
                difficulty += min(len(top_results) * 2, 20)

        # Factor 2: View velocity on top results (0–35 points)
        view_counts = [r.view_count for r in top_results[:5] if r.view_count > 0]
        if view_counts:
            avg_views = sum(view_counts) / len(view_counts)
            if avg_views >= self.HIGH_VIEWS:
                difficulty += 35
            elif avg_views >= self.MEDIUM_VIEWS:
                difficulty += 20
            elif avg_views >= self.LOW_VIEWS:
                difficulty += 10
            else:
                difficulty += 4

        # Factor 3: Autocomplete position (0–25 points)
        # Earlier position = more popular = more competition
        if autocomplete_position is not None:
            if autocomplete_position <= 2:
                difficulty += 25
            elif autocomplete_position <= 5:
                difficulty += 15
            elif autocomplete_position <= 8:
                difficulty += 8
            else:
                difficulty += 3
        else:
            # Not in autocomplete = lower competition
            difficulty += 0

        difficulty = min(100, difficulty)

        # ── Demand calculation ────────────────────────────────────────────────

        demand = 50  # Default baseline

        if autocomplete_position is not None:
            # Earlier autocomplete position = higher demand
            if autocomplete_position == 1:
                demand = 90
            elif autocomplete_position <= 3:
                demand = 75
            elif autocomplete_position <= 6:
                demand = 60
            else:
                demand = 45
        else:
            demand = 30  # Not in autocomplete = lower demand signal

        if trends_score is not None:
            # Blend autocomplete demand with trends score
            demand = int((demand + trends_score) / 2)

        demand = min(100, max(0, demand))

        # ── PSO Score (opportunity) ───────────────────────────────────────────

        # High demand + low difficulty = high opportunity
        pso_score = int((demand * (100 - difficulty)) / 100)
        pso_score = min(100, max(0, pso_score))

        # ── Labels and recommendation ─────────────────────────────────────────

        if difficulty <= 33:
            difficulty_label = "LOW"
        elif difficulty <= 66:
            difficulty_label = "MEDIUM"
        else:
            difficulty_label = "HIGH"

        if pso_score >= 60:
            recommendation = (
                f"HIGH OPPORTUNITY — Target '{keyword}' in your next 3 videos. "
                "Use in title (first 60 chars), first line of description, and tags."
            )
        elif pso_score >= 35:
            recommendation = (
                f"MODERATE OPPORTUNITY — Include '{keyword}' in description and tags. "
                "Consider as a secondary title keyword."
            )
        else:
            recommendation = (
                f"LOW OPPORTUNITY — '{keyword}' has either low demand or high competition. "
                "Use as a supporting tag only, not in the title."
            )

        return DifficultyResult(
            keyword=keyword,
            difficulty=difficulty,
            demand_score=demand,
            pso_score=pso_score,
            difficulty_label=difficulty_label,
            competitor_count=len(set(r.channel_id for r in top_results)),
            avg_competitor_views=int(sum(r.view_count for r in top_results) / max(len(top_results), 1)),
            your_rank=rank_result.channel_rank,
            recommendation=recommendation,
        )

    def score_batch(
        self,
        rank_results: List[KeywordRankResult],
        competitor_profiles: Optional[List[CompetitorProfile]] = None,
        autocomplete_map: Optional[Dict[str, int]] = None,
        trends_map: Optional[Dict[str, int]] = None,
    ) -> List[DifficultyResult]:
        """
        Score a list of keyword rank results.

        Args:
            rank_results: List of KeywordRankResult objects.
            competitor_profiles: Competitor channel profiles.
            autocomplete_map: Dict mapping keyword → autocomplete position.
            trends_map: Dict mapping keyword → Google Trends score (0–100).

        Returns:
            List of DifficultyResult objects sorted by PSO score descending.
        """
        results = []
        for rr in rank_results:
            ac_pos = autocomplete_map.get(rr.keyword) if autocomplete_map else None
            trends = trends_map.get(rr.keyword) if trends_map else None
            result = self.score(rr, competitor_profiles, ac_pos, trends)
            results.append(result)

        return sorted(results, key=lambda r: r.pso_score, reverse=True)
