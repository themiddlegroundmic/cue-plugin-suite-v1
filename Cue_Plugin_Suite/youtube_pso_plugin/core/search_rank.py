"""
core/search_rank.py
===================
YouTube Data API v3 search rank detection.

Uses the free YouTube Data API v3 Search.list endpoint to determine
where a given channel's videos rank for a set of keywords.

API cost: 100 units per search query (daily quota: 10,000 units free).
At 100 units/query, you get 100 free keyword searches per day.

Credentials: YOUTUBE_API_KEY stored as a platform-level secret in Cue.
Users never configure this directly.
"""

import os
import time
import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field

import requests

logger = logging.getLogger(__name__)

YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"
UNITS_PER_SEARCH = 100  # YouTube Data API v3 cost per Search.list call


@dataclass
class SearchResult:
    """A single video result from a YouTube keyword search."""
    rank: int
    video_id: str
    title: str
    channel_id: str
    channel_title: str
    description: str
    published_at: str
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0


@dataclass
class KeywordRankResult:
    """Rank result for a single keyword."""
    keyword: str
    channel_id: str
    channel_rank: Optional[int]           # None = not in top 50
    top_results: List[SearchResult] = field(default_factory=list)
    units_used: int = UNITS_PER_SEARCH
    error: Optional[str] = None

    @property
    def is_ranking(self) -> bool:
        return self.channel_rank is not None

    @property
    def rank_label(self) -> str:
        if self.channel_rank is None:
            return "Not ranking"
        return f"#{self.channel_rank}"


class YouTubeSearchRank:
    """
    Detects where a YouTube channel ranks for a set of keywords
    using the YouTube Data API v3 Search.list endpoint.

    The results come back in rank order — position 0 in the response
    is the first result a viewer sees when searching that term on YouTube.
    This is the same data source used by professional YouTube SEO tools.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("YOUTUBE_API_KEY", "")
        self._units_used = 0

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    @property
    def units_used(self) -> int:
        return self._units_used

    @property
    def units_remaining(self) -> int:
        return max(0, 10_000 - self._units_used)

    def search_keyword(
        self,
        keyword: str,
        channel_id: str,
        max_results: int = 50,
        region_code: str = "US",
        relevance_language: str = "en",
    ) -> KeywordRankResult:
        """
        Search YouTube for a keyword and find where the given channel ranks.

        Args:
            keyword: The search term to query.
            channel_id: The YouTube channel ID to look for in results.
            max_results: How many results to fetch (max 50 per call).
            region_code: ISO 3166-1 alpha-2 country code.
            relevance_language: BCP-47 language code.

        Returns:
            KeywordRankResult with rank position and top results.
        """
        if not self.is_configured:
            return KeywordRankResult(
                keyword=keyword,
                channel_id=channel_id,
                channel_rank=None,
                error="YOUTUBE_API_KEY not configured. Add it as a platform-level secret.",
            )

        params = {
            "part": "snippet",
            "q": keyword,
            "type": "video",
            "maxResults": min(max_results, 50),
            "regionCode": region_code,
            "relevanceLanguage": relevance_language,
            "key": self.api_key,
        }

        try:
            resp = requests.get(YOUTUBE_SEARCH_URL, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            self._units_used += UNITS_PER_SEARCH
        except requests.RequestException as e:
            logger.error(f"YouTube search API error for '{keyword}': {e}")
            return KeywordRankResult(
                keyword=keyword,
                channel_id=channel_id,
                channel_rank=None,
                error=str(e),
            )

        items = data.get("items", [])
        top_results = []
        channel_rank = None

        for i, item in enumerate(items):
            snippet = item.get("snippet", {})
            vid_id = item.get("id", {}).get("videoId", "")
            ch_id = snippet.get("channelId", "")

            result = SearchResult(
                rank=i + 1,
                video_id=vid_id,
                title=snippet.get("title", ""),
                channel_id=ch_id,
                channel_title=snippet.get("channelTitle", ""),
                description=snippet.get("description", ""),
                published_at=snippet.get("publishedAt", ""),
            )
            top_results.append(result)

            if ch_id == channel_id and channel_rank is None:
                channel_rank = i + 1

        return KeywordRankResult(
            keyword=keyword,
            channel_id=channel_id,
            channel_rank=channel_rank,
            top_results=top_results,
            units_used=UNITS_PER_SEARCH,
        )

    def batch_search(
        self,
        keywords: List[str],
        channel_id: str,
        delay_seconds: float = 0.5,
        **kwargs,
    ) -> List[KeywordRankResult]:
        """
        Run search rank detection for a list of keywords.

        Args:
            keywords: List of search terms to check.
            channel_id: YouTube channel ID to track.
            delay_seconds: Pause between API calls to respect rate limits.

        Returns:
            List of KeywordRankResult objects in keyword order.
        """
        results = []
        for kw in keywords:
            if self.units_remaining < UNITS_PER_SEARCH:
                logger.warning(
                    f"YouTube API quota nearly exhausted ({self._units_used}/10,000 used). "
                    f"Stopping at keyword '{kw}'."
                )
                break
            result = self.search_keyword(kw, channel_id, **kwargs)
            results.append(result)
            if delay_seconds > 0:
                time.sleep(delay_seconds)
        return results

    def enrich_with_stats(self, results: List[KeywordRankResult]) -> List[KeywordRankResult]:
        """
        Enrich top search results with view/like/comment counts
        using the Videos.list endpoint (1 unit per call, batched by 50).
        """
        if not self.is_configured:
            return results

        # Collect all video IDs from top results
        all_video_ids = []
        for r in results:
            for sr in r.top_results[:10]:  # Only enrich top 10 per keyword
                if sr.video_id:
                    all_video_ids.append(sr.video_id)

        if not all_video_ids:
            return results

        # Batch into groups of 50 (API limit)
        stats_map: Dict[str, Dict] = {}
        for i in range(0, len(all_video_ids), 50):
            batch = all_video_ids[i:i + 50]
            params = {
                "part": "statistics",
                "id": ",".join(batch),
                "key": self.api_key,
            }
            try:
                resp = requests.get(YOUTUBE_VIDEOS_URL, params=params, timeout=10)
                resp.raise_for_status()
                data = resp.json()
                self._units_used += 1  # Videos.list costs 1 unit
                for item in data.get("items", []):
                    vid_id = item.get("id", "")
                    stats = item.get("statistics", {})
                    stats_map[vid_id] = {
                        "view_count": int(stats.get("viewCount", 0)),
                        "like_count": int(stats.get("likeCount", 0)),
                        "comment_count": int(stats.get("commentCount", 0)),
                    }
            except requests.RequestException as e:
                logger.warning(f"Could not enrich video stats: {e}")

        # Apply stats back to results
        for r in results:
            for sr in r.top_results:
                if sr.video_id in stats_map:
                    s = stats_map[sr.video_id]
                    sr.view_count = s["view_count"]
                    sr.like_count = s["like_count"]
                    sr.comment_count = s["comment_count"]

        return results

    def quota_status(self) -> Dict[str, Any]:
        return {
            "used": self._units_used,
            "remaining": self.units_remaining,
            "daily_limit": 10_000,
            "cost_per_search": UNITS_PER_SEARCH,
            "searches_remaining": self.units_remaining // UNITS_PER_SEARCH,
        }
