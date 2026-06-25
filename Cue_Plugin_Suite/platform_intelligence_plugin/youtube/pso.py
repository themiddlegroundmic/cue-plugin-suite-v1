"""
youtube/pso.py
==============
YouTube PSO (Platform Search Optimization) plugin.
Parallel architecture to the podcast PSO plugin.

Data sources (all free):
  - YouTube Data API v3 — search rank, competitor metadata, video stats
  - YouTube autocomplete endpoint — keyword demand signal
  - Google Trends (pytrends) — cross-platform demand signal

Platform credential: YOUTUBE_API_KEY (platform-level, set once by Cue org)
No per-user setup required.

API quota: 10,000 units/day free. Full channel audit uses ~200–400 units.
"""

import os
import time
import json
import requests
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field


# ── Configuration ─────────────────────────────────────────────────────────────

YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")
YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"
YOUTUBE_CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"
YOUTUBE_AUTOCOMPLETE_URL = "https://suggestqueries.google.com/complete/search"

# Units consumed per API call (YouTube Data API v3 quota)
QUOTA_SEARCH = 100      # search.list costs 100 units
QUOTA_VIDEOS = 1        # videos.list costs 1 unit per video
QUOTA_CHANNELS = 1      # channels.list costs 1 unit

REQUEST_DELAY = 0.5     # seconds between API calls


@dataclass
class YouTubeVideo:
    """Metadata for a single YouTube video."""
    video_id: str
    title: str
    description: str
    channel_id: str
    channel_title: str
    published_at: str
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    duration: str = ""
    tags: List[str] = field(default_factory=list)
    chapters: List[Tuple[str, str]] = field(default_factory=list)  # (timestamp, name)
    rank_position: int = 0  # position in search results (1 = top)


@dataclass
class YouTubeKeywordResult:
    """PSO result for a single keyword."""
    keyword: str
    autocomplete_suggestions: List[str] = field(default_factory=list)
    top_videos: List[YouTubeVideo] = field(default_factory=list)
    competitor_channels: List[str] = field(default_factory=list)
    difficulty_score: int = 0       # 0–100 (higher = harder to rank)
    demand_score: int = 0           # 0–100 (higher = more search demand)
    trends_score: int = 0           # 0–100 from Google Trends
    your_rank: Optional[int] = None # Your channel's rank for this keyword (None = not ranking)
    term_classification: str = ""   # DETECTED / COMPETITOR / LOCAL / DEAD


class YouTubePSO:
    """
    YouTube PSO detector and keyword intelligence engine.
    Uses YouTube Data API v3 + autocomplete + Google Trends.
    Platform-level API key — no per-user setup.
    """

    def __init__(self, api_key: str = "", channel_id: str = ""):
        self.api_key = api_key or YOUTUBE_API_KEY
        self.channel_id = channel_id  # The show's YouTube channel ID
        self._quota_used = 0

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def get_autocomplete_suggestions(self, keyword: str) -> List[str]:
        """
        Pull YouTube autocomplete suggestions for a keyword.
        Uses the public suggest endpoint — no API key required, no quota cost.
        Results are in demand order (most searched first).
        """
        try:
            params = {
                "client": "youtube",
                "q": keyword,
                "ds": "yt",
                "hl": "en",
            }
            resp = requests.get(YOUTUBE_AUTOCOMPLETE_URL, params=params, timeout=10)
            if resp.status_code == 200:
                # Response is JSONP — strip callback wrapper
                text = resp.text
                if text.startswith("window.google.ac.h("):
                    text = text[len("window.google.ac.h("):-1]
                data = json.loads(text)
                suggestions = [item[0] for item in data[1] if isinstance(item, list)]
                return suggestions[:10]
        except Exception:
            pass
        return []

    def search_videos(self, keyword: str, max_results: int = 10) -> List[YouTubeVideo]:
        """
        Search YouTube for a keyword and return top results in rank order.
        Uses search.list (100 quota units).
        """
        if not self.is_configured():
            return []

        try:
            params = {
                "part": "snippet",
                "q": keyword,
                "type": "video",
                "maxResults": max_results,
                "relevanceLanguage": "en",
                "regionCode": "US",
                "key": self.api_key,
            }
            resp = requests.get(YOUTUBE_SEARCH_URL, params=params, timeout=15)
            self._quota_used += QUOTA_SEARCH
            time.sleep(REQUEST_DELAY)

            if resp.status_code != 200:
                return []

            data = resp.json()
            videos = []
            for rank, item in enumerate(data.get("items", []), start=1):
                snippet = item.get("snippet", {})
                video = YouTubeVideo(
                    video_id=item["id"].get("videoId", ""),
                    title=snippet.get("title", ""),
                    description=snippet.get("description", ""),
                    channel_id=snippet.get("channelId", ""),
                    channel_title=snippet.get("channelTitle", ""),
                    published_at=snippet.get("publishedAt", ""),
                    rank_position=rank,
                )
                videos.append(video)

            return videos

        except Exception:
            return []

    def get_video_stats(self, video_ids: List[str]) -> Dict[str, Dict]:
        """
        Get detailed stats for a list of video IDs.
        Uses videos.list (1 quota unit per video).
        """
        if not self.is_configured() or not video_ids:
            return {}

        try:
            params = {
                "part": "statistics,contentDetails,snippet",
                "id": ",".join(video_ids[:50]),  # max 50 per call
                "key": self.api_key,
            }
            resp = requests.get(YOUTUBE_VIDEOS_URL, params=params, timeout=15)
            self._quota_used += len(video_ids)
            time.sleep(REQUEST_DELAY)

            if resp.status_code != 200:
                return {}

            data = resp.json()
            stats = {}
            for item in data.get("items", []):
                vid_id = item["id"]
                statistics = item.get("statistics", {})
                snippet = item.get("snippet", {})
                stats[vid_id] = {
                    "view_count": int(statistics.get("viewCount", 0)),
                    "like_count": int(statistics.get("likeCount", 0)),
                    "comment_count": int(statistics.get("commentCount", 0)),
                    "duration": item.get("contentDetails", {}).get("duration", ""),
                    "tags": snippet.get("tags", []),
                    "description": snippet.get("description", ""),
                }
            return stats

        except Exception:
            return {}

    def extract_chapters(self, description: str) -> List[Tuple[str, str]]:
        """
        Extract chapter timestamps from a video description.
        Returns list of (timestamp, chapter_name) tuples.
        """
        import re
        pattern = r"(\d{1,2}:\d{2}(?::\d{2})?)\s+(.+)"
        chapters = re.findall(pattern, description)
        return [(ts.strip(), name.strip()) for ts, name in chapters]

    def calculate_difficulty_score(self, videos: List[YouTubeVideo]) -> int:
        """
        Calculate keyword difficulty score (0–100) based on competitor data.
        Higher = harder to rank.

        Formula:
          - Competitor count (max 10): 0–30 points
          - Average view count of top 5: 0–40 points
          - Channel authority (subscriber proxy via view count): 0–30 points
        """
        if not videos:
            return 0

        competitor_count = len(videos)
        count_score = min(30, competitor_count * 3)

        # View count score (top 5 average)
        top_5_views = [v.view_count for v in videos[:5] if v.view_count > 0]
        if top_5_views:
            avg_views = sum(top_5_views) / len(top_5_views)
            # Scale: 0 views = 0, 1M+ views = 40
            view_score = min(40, int((avg_views / 1_000_000) * 40))
        else:
            view_score = 0

        # Channel diversity score (more unique channels = harder)
        unique_channels = len(set(v.channel_id for v in videos))
        channel_score = min(30, unique_channels * 3)

        return min(100, count_score + view_score + channel_score)

    def calculate_demand_score(self, autocomplete_suggestions: List[str],
                                keyword: str) -> int:
        """
        Calculate demand score (0–100) based on autocomplete signal.
        More suggestions = higher demand. Position in suggestions = higher demand.
        """
        if not autocomplete_suggestions:
            return 20  # baseline

        keyword_lower = keyword.lower()

        # Exact match in top 3 = high demand
        for i, suggestion in enumerate(autocomplete_suggestions[:3]):
            if keyword_lower in suggestion.lower():
                return min(100, 80 - (i * 10))

        # Keyword appears anywhere in suggestions
        for i, suggestion in enumerate(autocomplete_suggestions):
            if keyword_lower in suggestion.lower():
                return min(100, 60 - (i * 5))

        # Keyword not in suggestions but suggestions exist = moderate demand
        return 40

    def get_trends_score(self, keyword: str) -> int:
        """
        Get Google Trends demand score for a keyword.
        Returns 0–100. Falls back to 50 if pytrends unavailable.
        """
        try:
            from pytrends.request import TrendReq
            pytrends = TrendReq(hl="en-US", tz=360)
            pytrends.build_payload([keyword], timeframe="today 3-m", geo="US")
            data = pytrends.interest_over_time()
            if not data.empty and keyword in data.columns:
                return int(data[keyword].mean())
        except Exception:
            pass
        return 50  # neutral fallback

    def classify_term(self, term: str, autocomplete_suggestions: List[str],
                       competitor_tags: List[str], local_terms: List[str],
                       dead_terms: List[str]) -> str:
        """
        Classify a keyword term using the same taxonomy as the podcast PSO plugin.
        DETECTED = found in YouTube autocomplete (real search demand)
        COMPETITOR = found in competitor video tags/titles
        LOCAL = geographic or niche-specific term
        DEAD = generic term with no search value
        """
        term_lower = term.lower()

        # DETECTED: in autocomplete suggestions
        for suggestion in autocomplete_suggestions:
            if term_lower in suggestion.lower():
                return "DETECTED"

        # DEAD: generic terms
        for dead in dead_terms:
            if term_lower == dead.lower():
                return "DEAD"

        # LOCAL: geographic or niche terms
        for local in local_terms:
            if local.lower() in term_lower:
                return "LOCAL"

        # COMPETITOR: found in competitor metadata
        for comp_tag in competitor_tags:
            if term_lower in comp_tag.lower():
                return "COMPETITOR"

        return "FACTUAL"  # topic-specific but not yet validated

    def analyze_keyword(self, keyword: str, your_channel_id: str = "") -> YouTubeKeywordResult:
        """
        Full PSO analysis for a single keyword.
        Returns YouTubeKeywordResult with all signals.
        """
        result = YouTubeKeywordResult(keyword=keyword)

        # 1. Autocomplete suggestions (no quota cost)
        result.autocomplete_suggestions = self.get_autocomplete_suggestions(keyword)

        # 2. Search results (100 quota units)
        videos = self.search_videos(keyword, max_results=10)

        # 3. Get video stats for top 5 (5 quota units)
        if videos:
            top_video_ids = [v.video_id for v in videos[:5] if v.video_id]
            stats = self.get_video_stats(top_video_ids)
            for video in videos:
                if video.video_id in stats:
                    s = stats[video.video_id]
                    video.view_count = s["view_count"]
                    video.like_count = s["like_count"]
                    video.comment_count = s["comment_count"]
                    video.tags = s["tags"]
                    video.chapters = self.extract_chapters(s["description"])

            result.top_videos = videos
            result.competitor_channels = list(set(v.channel_title for v in videos))

            # Check if your channel appears in results
            if your_channel_id:
                for video in videos:
                    if video.channel_id == your_channel_id:
                        result.your_rank = video.rank_position
                        break

        # 4. Difficulty and demand scores
        result.difficulty_score = self.calculate_difficulty_score(videos)
        result.demand_score = self.calculate_demand_score(
            result.autocomplete_suggestions, keyword
        )

        # 5. Google Trends score
        result.trends_score = self.get_trends_score(keyword)

        return result

    def analyze_channel_keywords(self, keywords: List[str],
                                  your_channel_id: str = "") -> List[YouTubeKeywordResult]:
        """
        Run PSO analysis for a list of keywords.
        Returns results sorted by opportunity score (high demand, low difficulty).
        """
        results = []
        for keyword in keywords:
            result = self.analyze_keyword(keyword, your_channel_id)
            results.append(result)
            time.sleep(REQUEST_DELAY)

        # Sort by opportunity: high demand + low difficulty
        results.sort(
            key=lambda r: (r.demand_score + r.trends_score - r.difficulty_score),
            reverse=True,
        )
        return results

    @property
    def quota_used(self) -> int:
        return self._quota_used

    @property
    def quota_remaining(self) -> int:
        return max(0, 10_000 - self._quota_used)
