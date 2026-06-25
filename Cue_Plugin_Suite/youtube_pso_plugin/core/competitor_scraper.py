"""
core/competitor_scraper.py
==========================
Top-ranking YouTube channel metadata scraper.

Given a list of KeywordRankResults from the search rank module,
this module extracts the top-ranking channels and fetches their
video metadata to identify what titles, descriptions, and tags
the highest-performing content in the niche is using.

API cost: 1 unit per Channels.list call, 1 unit per Videos.list call.
"""

import logging
import os
import time
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, field

import requests

from .search_rank import KeywordRankResult, SearchResult

logger = logging.getLogger(__name__)

YOUTUBE_CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"
YOUTUBE_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"
YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"


@dataclass
class CompetitorVideo:
    """Metadata for a competitor video."""
    video_id: str
    title: str
    description: str
    tags: List[str]
    channel_id: str
    channel_title: str
    view_count: int
    like_count: int
    published_at: str
    duration: str = ""

    @property
    def title_words(self) -> List[str]:
        """Return meaningful words from the title (3+ chars, no stopwords)."""
        stopwords = {
            "the", "and", "for", "with", "this", "that", "from", "have",
            "are", "was", "were", "will", "been", "has", "had", "not",
            "but", "what", "when", "how", "why", "who", "can", "its",
        }
        return [
            w.lower().strip(".,!?:;\"'")
            for w in self.title.split()
            if len(w) >= 3 and w.lower() not in stopwords
        ]


@dataclass
class CompetitorProfile:
    """Aggregated metadata for a competitor channel."""
    channel_id: str
    channel_title: str
    subscriber_count: int
    video_count: int
    top_videos: List[CompetitorVideo] = field(default_factory=list)

    @property
    def common_title_terms(self) -> Dict[str, int]:
        """Count how often each word appears across top video titles."""
        counts: Dict[str, int] = {}
        for video in self.top_videos:
            for word in video.title_words:
                counts[word] = counts.get(word, 0) + 1
        return dict(sorted(counts.items(), key=lambda x: x[1], reverse=True))

    @property
    def all_tags(self) -> List[str]:
        """All tags used across top videos, deduplicated."""
        seen: Set[str] = set()
        tags = []
        for video in self.top_videos:
            for tag in video.tags:
                tag_lower = tag.lower()
                if tag_lower not in seen:
                    seen.add(tag_lower)
                    tags.append(tag)
        return tags


class CompetitorScraper:
    """
    Scrapes metadata from top-ranking YouTube channels for a set of keywords.
    Uses the YouTube Data API v3 — all calls counted against the daily quota.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("YOUTUBE_API_KEY", "")
        self._units_used = 0

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def scrape_competitors(
        self,
        rank_results: List[KeywordRankResult],
        top_n_channels: int = 5,
        videos_per_channel: int = 10,
        exclude_channel_id: Optional[str] = None,
    ) -> List[CompetitorProfile]:
        """
        Given search rank results, identify the top-ranking competitor channels
        and fetch their video metadata.

        Args:
            rank_results: Results from YouTubeSearchRank.batch_search().
            top_n_channels: How many unique competitor channels to profile.
            videos_per_channel: How many recent videos to fetch per channel.
            exclude_channel_id: The user's own channel ID — exclude from competitors.

        Returns:
            List of CompetitorProfile objects.
        """
        if not self.is_configured:
            logger.warning("YOUTUBE_API_KEY not configured. Competitor scraping skipped.")
            return []

        # Collect unique competitor channel IDs from top search results
        channel_counts: Dict[str, int] = {}
        for result in rank_results:
            for sr in result.top_results[:10]:
                if sr.channel_id and sr.channel_id != exclude_channel_id:
                    channel_counts[sr.channel_id] = channel_counts.get(sr.channel_id, 0) + 1

        # Sort by frequency (channels appearing across more keywords = stronger competitors)
        sorted_channels = sorted(channel_counts.items(), key=lambda x: x[1], reverse=True)
        top_channel_ids = [ch_id for ch_id, _ in sorted_channels[:top_n_channels]]

        profiles = []
        for channel_id in top_channel_ids:
            profile = self._build_channel_profile(channel_id, videos_per_channel)
            if profile:
                profiles.append(profile)
            time.sleep(0.3)

        return profiles

    def _build_channel_profile(
        self, channel_id: str, videos_per_channel: int
    ) -> Optional[CompetitorProfile]:
        """Fetch channel stats and top video metadata."""
        # Get channel stats
        params = {
            "part": "snippet,statistics",
            "id": channel_id,
            "key": self.api_key,
        }
        try:
            resp = requests.get(YOUTUBE_CHANNELS_URL, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            self._units_used += 1
        except requests.RequestException as e:
            logger.warning(f"Could not fetch channel {channel_id}: {e}")
            return None

        items = data.get("items", [])
        if not items:
            return None

        item = items[0]
        stats = item.get("statistics", {})
        snippet = item.get("snippet", {})

        profile = CompetitorProfile(
            channel_id=channel_id,
            channel_title=snippet.get("title", ""),
            subscriber_count=int(stats.get("subscriberCount", 0)),
            video_count=int(stats.get("videoCount", 0)),
        )

        # Get recent videos from this channel
        search_params = {
            "part": "snippet",
            "channelId": channel_id,
            "type": "video",
            "order": "viewCount",
            "maxResults": min(videos_per_channel, 50),
            "key": self.api_key,
        }
        try:
            resp = requests.get(YOUTUBE_SEARCH_URL, params=search_params, timeout=10)
            resp.raise_for_status()
            search_data = resp.json()
            self._units_used += 100  # Search.list costs 100 units
        except requests.RequestException as e:
            logger.warning(f"Could not fetch videos for channel {channel_id}: {e}")
            return profile

        video_ids = [
            item.get("id", {}).get("videoId", "")
            for item in search_data.get("items", [])
            if item.get("id", {}).get("videoId")
        ]

        if not video_ids:
            return profile

        # Fetch full video metadata including tags
        video_params = {
            "part": "snippet,statistics,contentDetails",
            "id": ",".join(video_ids),
            "key": self.api_key,
        }
        try:
            resp = requests.get(YOUTUBE_VIDEOS_URL, params=video_params, timeout=10)
            resp.raise_for_status()
            video_data = resp.json()
            self._units_used += 1
        except requests.RequestException as e:
            logger.warning(f"Could not fetch video details for channel {channel_id}: {e}")
            return profile

        for v in video_data.get("items", []):
            snip = v.get("snippet", {})
            vstats = v.get("statistics", {})
            profile.top_videos.append(CompetitorVideo(
                video_id=v.get("id", ""),
                title=snip.get("title", ""),
                description=snip.get("description", "")[:500],
                tags=snip.get("tags", []),
                channel_id=channel_id,
                channel_title=profile.channel_title,
                view_count=int(vstats.get("viewCount", 0)),
                like_count=int(vstats.get("likeCount", 0)),
                published_at=snip.get("publishedAt", ""),
                duration=v.get("contentDetails", {}).get("duration", ""),
            ))

        return profile

    def extract_competitor_terms(
        self, profiles: List[CompetitorProfile], min_frequency: int = 2
    ) -> Dict[str, int]:
        """
        Aggregate all competitor title terms and return those appearing
        in at least min_frequency videos across all competitor channels.

        Returns:
            Dict mapping term → frequency count.
        """
        all_counts: Dict[str, int] = {}
        for profile in profiles:
            for term, count in profile.common_title_terms.items():
                all_counts[term] = all_counts.get(term, 0) + count

        return {
            term: count
            for term, count in sorted(all_counts.items(), key=lambda x: x[1], reverse=True)
            if count >= min_frequency
        }
