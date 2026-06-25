"""
spotify_detector.py
===================
Queries the Spotify Web API to determine search rank position for a show.

API: https://api.spotify.com/v1/search?type=show
Auth: Client Credentials flow (no user login required).
Cost: FREE — register a free app at https://developer.spotify.com/dashboard

Setup (one-time, 5 minutes):
  1. Go to https://developer.spotify.com/dashboard
  2. Create an app (any name, redirect URI = http://localhost)
  3. Copy Client ID and Client Secret into your .env or pass directly

The order of results IS the Spotify search rank — same principle as iTunes.
"""

import time
import base64
import requests
from typing import Dict, List, Optional, Tuple


SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_SEARCH_URL = "https://api.spotify.com/v1/search"
REQUEST_DELAY = 1.0


class SpotifyDetector:
    """
    Detects Spotify podcast search rank for a show across multiple keywords.

    Usage:
        detector = SpotifyDetector(
            client_id="your_client_id",
            client_secret="your_client_secret",
            show_name="The MiddleGround Mic",
        )
        results = detector.detect_ranks(["michigan politics", "iran nuclear deal"])
    """

    def __init__(self, client_id: str, client_secret: str,
                 show_name: Optional[str] = None,
                 show_spotify_id: Optional[str] = None,
                 market: str = "US"):
        self.client_id = client_id
        self.client_secret = client_secret
        self.show_name = show_name
        self.show_spotify_id = show_spotify_id
        self.market = market
        self._token: Optional[str] = None
        self._token_expires: float = 0.0
        self._session = requests.Session()

    def _get_token(self) -> str:
        """Obtain or refresh the Client Credentials bearer token."""
        if self._token and time.time() < self._token_expires - 60:
            return self._token
        credentials = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()
        resp = self._session.post(SPOTIFY_TOKEN_URL, data={
            "grant_type": "client_credentials"
        }, headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        }, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        self._token = data["access_token"]
        self._token_expires = time.time() + data.get("expires_in", 3600)
        return self._token

    def search_keyword(self, keyword: str, limit: int = 25) -> List[Dict]:
        """
        Search Spotify for podcast shows matching a keyword.
        Returns results in rank order (index 0 = rank 1).
        """
        time.sleep(REQUEST_DELAY)
        try:
            token = self._get_token()
            resp = self._session.get(SPOTIFY_SEARCH_URL, params={
                "q": keyword,
                "type": "show",
                "market": self.market,
                "limit": limit,
            }, headers={
                "Authorization": f"Bearer {token}",
            }, timeout=12)
            resp.raise_for_status()
            return resp.json().get("shows", {}).get("items", [])
        except Exception as e:
            print(f"[SpotifyDetector] Error searching '{keyword}': {e}")
            return []

    def get_rank(self, keyword: str) -> Tuple[Optional[int], List[Dict]]:
        """
        Returns (rank_position, competitor_list) for the configured show.
        rank_position is 1-indexed. None if not in top 25.
        """
        results = self.search_keyword(keyword)
        rank = None
        for i, item in enumerate(results, 1):
            sid = item.get("id", "")
            name = item.get("name", "").lower()
            if self.show_spotify_id and sid == self.show_spotify_id:
                rank = i
                break
            if self.show_name and self.show_name.lower() in name:
                rank = i
                break
        return rank, results

    def detect_ranks(self, keywords: List[str]) -> Dict[str, Optional[int]]:
        """
        Detect Spotify rank for each keyword.
        Returns dict: {keyword: rank_or_None}
        """
        ranks = {}
        for kw in keywords:
            rank, _ = self.get_rank(kw)
            ranks[kw] = rank
            print(f"[Spotify] '{kw}' → rank {rank}")
        return ranks

    @staticmethod
    def is_configured(client_id: str, client_secret: str) -> bool:
        """Check if valid credentials are provided (non-empty placeholders)."""
        return bool(client_id and client_secret and
                    client_id != "YOUR_SPOTIFY_CLIENT_ID" and
                    client_secret != "YOUR_SPOTIFY_CLIENT_SECRET")
