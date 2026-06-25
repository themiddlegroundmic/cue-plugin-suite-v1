from __future__ import annotations

import base64
import os
import time
from typing import Any, Dict, List, Optional

import requests

from src.core.types.models import CueInput, CueKeyword, CuePluginResult, CueSignal


class SpotifySearchPlugin:
    id = "spotify"
    name = "Spotify Search"
    platform = "podcast"
    enabled = True
    token_url = "https://accounts.spotify.com/api/token"
    search_url = "https://api.spotify.com/v1/search"

    def __init__(self, client_id: Optional[str] = None, client_secret: Optional[str] = None, session: requests.Session | None = None, market: str = "US"):
        self.client_id = client_id or os.environ.get("SPOTIFY_CLIENT_ID", "")
        self.client_secret = client_secret or os.environ.get("SPOTIFY_CLIENT_SECRET", "")
        self.session = session or requests.Session()
        self.market = market
        self._token = ""
        self._token_expires = 0.0

    async def analyze(self, input: CueInput) -> CuePluginResult:
        if not self.client_id or not self.client_secret:
            return CuePluginResult(pluginId=self.id, platform=self.platform, status="not_configured", input=input, warnings=["SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET must be configured by the Cue platform."])
        term = input.manualTopic or input.showUrl or input.episodeUrl
        if not term:
            return CuePluginResult(pluginId=self.id, platform=self.platform, status="not_configured", input=input, warnings=["manualTopic, showUrl, or episodeUrl is required for Spotify search."])
        try:
            token = self._get_token()
            response = self.session.get(self.search_url, params={"q": term, "type": "show,episode", "market": self.market, "limit": 20}, headers={"Authorization": f"Bearer {token}"}, timeout=12)
            response.raise_for_status()
            return self.normalize(input, term, response.json())
        except Exception as exc:
            return CuePluginResult(pluginId=self.id, platform=self.platform, status="error", input=input, warnings=[str(exc)])

    def _get_token(self) -> str:
        if self._token and time.time() < self._token_expires - 60:
            return self._token
        encoded = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        response = self.session.post(self.token_url, data={"grant_type": "client_credentials"}, headers={"Authorization": f"Basic {encoded}", "Content-Type": "application/x-www-form-urlencoded"}, timeout=10)
        response.raise_for_status()
        payload = response.json()
        self._token = payload["access_token"]
        self._token_expires = time.time() + payload.get("expires_in", 3600)
        return self._token

    def normalize(self, input: CueInput, term: str, payload: Dict[str, Any], user_show_title: Optional[str] = None) -> CuePluginResult:
        shows = payload.get("shows", {}).get("items", []) or []
        episodes = payload.get("episodes", {}).get("items", []) or []
        user_title = (user_show_title or input.manualTopic or "").lower()
        rank = None
        competitors: List[Dict[str, Any]] = []
        for index, item in enumerate(shows, 1):
            if not item:
                continue
            title = item.get("name", "")
            if user_title and user_title in title.lower() and rank is None:
                rank = index
            competitors.append({
                "source": self.id,
                "title": title,
                "publisher": item.get("publisher", ""),
                "description": item.get("description", ""),
                "externalUrl": item.get("external_urls", {}).get("spotify", ""),
                "episodeCount": item.get("total_episodes"),
            })
        return CuePluginResult(
            pluginId=self.id,
            platform=self.platform,
            input=input,
            competitors=competitors,
            keywords=[CueKeyword(value=term, source=self.id, weight=0.8)],
            signals=[CueSignal(
                type="competition",
                source=self.id,
                value={
                    "rankPosition": rank,
                    "topMatchingShows": [c["title"] for c in competitors[:10]],
                    "topMatchingEpisodes": [e.get("name", "") for e in episodes[:10] if e],
                    "note": "Competition/search visibility signal only. This is not Spotify search volume.",
                },
                confidence=0.75,
            )],
            raw={"showCount": len(shows), "episodeCount": len(episodes)},
            warnings=["Spotify results are competition/search visibility signals, not real Spotify search volume."],
        )

