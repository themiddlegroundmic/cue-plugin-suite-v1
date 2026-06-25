"""
apple_detector.py
=================
Queries the Apple iTunes Search API to determine:
  1. The search rank position of a show for a given keyword
  2. The top-10 competing shows for that keyword (for competitor scraping)

API: https://itunes.apple.com/search
Cost: FREE — no API key, no registration required.
Rate limit: ~20 requests/minute (Apple's stated limit).

The order of results IS the Apple Podcasts search rank.
Position 1 = what a listener sees first when they search that term.
This is the same data source Ausha's PSO Control Panel uses.
"""

import time
import requests
from typing import Dict, List, Optional, Tuple


ITUNES_SEARCH_URL = "https://itunes.apple.com/search"
ITUNES_LOOKUP_URL = "https://itunes.apple.com/lookup"
REQUEST_DELAY = 3.5  # seconds between calls to stay under rate limit


class AppleDetector:
    """
    Detects Apple Podcasts search rank for a show across multiple keywords.

    Usage:
        detector = AppleDetector(show_itunes_id="2465711")
        results = detector.detect_ranks(["michigan politics", "iran nuclear deal"])
        # returns: {"michigan politics": 4, "iran nuclear deal": None}
    """

    def __init__(self, show_itunes_id: Optional[str] = None,
                 show_title: Optional[str] = None,
                 country: str = "us"):
        if not show_itunes_id and not show_title:
            raise ValueError("Provide either show_itunes_id or show_title")
        self.show_itunes_id = show_itunes_id
        self.show_title = show_title
        self.country = country
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "CuePSOPlugin/1.0 (+https://cue.fm)"
        })

    def resolve_itunes_id(self, feed_url: str) -> Optional[str]:
        """Look up iTunes ID from a feed URL using the iTunes Search API."""
        # Extract show name from feed URL as fallback search term
        try:
            resp = self._session.get(ITUNES_SEARCH_URL, params={
                "term": self.show_title or "podcast",
                "country": self.country,
                "media": "podcast",
                "entity": "podcast",
                "limit": 25,
            }, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            for item in data.get("results", []):
                if item.get("feedUrl", "").rstrip("/") == feed_url.rstrip("/"):
                    return str(item["collectionId"])
        except Exception:
            pass
        return None

    def search_keyword(self, keyword: str, limit: int = 25) -> List[Dict]:
        """
        Search Apple Podcasts for a keyword.
        Returns results in rank order (index 0 = rank 1).
        """
        time.sleep(REQUEST_DELAY)
        try:
            resp = self._session.get(ITUNES_SEARCH_URL, params={
                "term": keyword,
                "country": self.country,
                "media": "podcast",
                "entity": "podcast",
                "limit": limit,
            }, timeout=12)
            resp.raise_for_status()
            return resp.json().get("results", [])
        except Exception as e:
            print(f"[AppleDetector] Error searching '{keyword}': {e}")
            return []

    def get_rank(self, keyword: str) -> Tuple[Optional[int], List[Dict]]:
        """
        Returns (rank_position, competitor_list) for the configured show.
        rank_position is 1-indexed. None if not in top 25.
        """
        results = self.search_keyword(keyword)
        rank = None
        for i, item in enumerate(results, 1):
            cid = str(item.get("collectionId", ""))
            title = item.get("trackName", "").lower()
            if self.show_itunes_id and cid == str(self.show_itunes_id):
                rank = i
                break
            if self.show_title and self.show_title.lower() in title:
                rank = i
                break
        return rank, results

    def detect_ranks(self, keywords: List[str]) -> Dict[str, Optional[int]]:
        """
        Detect Apple Podcasts rank for each keyword.
        Returns dict: {keyword: rank_or_None}
        """
        ranks = {}
        for kw in keywords:
            rank, _ = self.get_rank(kw)
            ranks[kw] = rank
            print(f"[Apple] '{kw}' → rank {rank}")
        return ranks

    def get_competitors(self, keyword: str, top_n: int = 5) -> List[Dict]:
        """
        Return the top N competing shows for a keyword with their metadata.
        Used by CompetitorScraper to fetch their RSS feeds.
        """
        results = self.search_keyword(keyword, limit=top_n + 2)
        competitors = []
        for item in results[:top_n]:
            competitors.append({
                "itunes_id": str(item.get("collectionId", "")),
                "title": item.get("trackName", ""),
                "author": item.get("artistName", ""),
                "feed_url": item.get("feedUrl", ""),
                "episode_count": item.get("trackCount", 0),
                "genre": item.get("primaryGenreName", ""),
                "artwork": item.get("artworkUrl100", ""),
            })
        return competitors
