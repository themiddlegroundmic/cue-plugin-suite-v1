from __future__ import annotations

from typing import Any, Dict, List, Optional

import requests

from src.core.types.models import CueInput, CueKeyword, CuePluginResult, CueSignal


class ApplePodcastsSearchPlugin:
    id = "apple"
    name = "Apple Podcasts Search"
    platform = "podcast"
    enabled = True
    search_url = "https://itunes.apple.com/search"

    def __init__(self, country: str = "us", session: requests.Session | None = None):
        self.country = country
        self.session = session or requests.Session()

    async def analyze(self, input: CueInput) -> CuePluginResult:
        term = input.manualTopic or input.showUrl or input.episodeUrl
        if not term:
            return CuePluginResult(pluginId=self.id, platform=self.platform, status="not_configured", input=input, warnings=["manualTopic, showUrl, or episodeUrl is required for Apple search."])
        try:
            response = self.session.get(self.search_url, params={
                "term": term,
                "country": self.country,
                "media": "podcast",
                "entity": "podcast",
                "limit": 25,
            }, timeout=12)
            response.raise_for_status()
            return self.normalize(input, term, response.json())
        except Exception as exc:
            return CuePluginResult(pluginId=self.id, platform=self.platform, status="error", input=input, warnings=[str(exc)])

    def normalize(self, input: CueInput, term: str, payload: Dict[str, Any], user_show_title: Optional[str] = None) -> CuePluginResult:
        results = payload.get("results", [])
        user_title = (user_show_title or input.manualTopic or "").lower()
        rank = None
        competitors: List[Dict[str, Any]] = []
        for index, item in enumerate(results, 1):
            title = item.get("trackName", "")
            if user_title and user_title in title.lower() and rank is None:
                rank = index
            competitors.append({
                "source": self.id,
                "title": title,
                "artistName": item.get("artistName", ""),
                "feedUrl": item.get("feedUrl", ""),
                "genres": item.get("genres", []),
                "episodeCount": item.get("trackCount"),
                "externalUrl": item.get("collectionViewUrl", ""),
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
                    "resultCount": payload.get("resultCount", len(results)),
                    "rankPosition": rank,
                    "competingShowNames": [c["title"] for c in competitors[:10]],
                    "note": "Competition/search visibility signal only. This is not Apple search volume.",
                },
                confidence=0.75,
            )],
            raw={"resultCount": payload.get("resultCount", len(results))},
            warnings=["Apple Podcasts results are competition/search visibility signals, not real Apple search volume."],
        )

