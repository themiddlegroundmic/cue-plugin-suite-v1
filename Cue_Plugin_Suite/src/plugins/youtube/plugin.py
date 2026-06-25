from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests

from src.core.types.models import CueInput, CueKeyword, CuePluginResult, CueSignal
from src.plugins.stubs import NotImplementedCuePlugin


class YouTubeDataPlugin:
    id = "youtubeData"
    name = "YouTube Data API v3"
    platform = "youtube"
    enabled = True
    search_url = "https://www.googleapis.com/youtube/v3/search"
    videos_url = "https://www.googleapis.com/youtube/v3/videos"

    def __init__(self, api_key: Optional[str] = None, session: requests.Session | None = None, max_results: int = 10):
        self.api_key = api_key or os.environ.get("YOUTUBE_API_KEY", "")
        self.session = session or requests.Session()
        self.max_results = max_results

    async def analyze(self, input: CueInput) -> CuePluginResult:
        if not self.api_key:
            return CuePluginResult(
                pluginId=self.id,
                platform=self.platform,
                status="not_configured",
                input=input,
                warnings=["YOUTUBE_API_KEY is not configured; YouTube demand and engagement proxy unavailable."],
            )
        query = self._query(input)
        if not query:
            return CuePluginResult(
                pluginId=self.id,
                platform=self.platform,
                status="not_configured",
                input=input,
                warnings=["manualTopic, showUrl, episodeUrl, or alternateKeywords are required for YouTube analysis."],
            )
        try:
            search_payload = self._search(query)
            video_ids = [
                item.get("id", {}).get("videoId")
                for item in search_payload.get("items", [])
                if item.get("id", {}).get("videoId")
            ]
            stats_payload = self._video_stats(video_ids) if video_ids else {"items": []}
            return self.normalize(input, query, search_payload, stats_payload)
        except Exception as exc:
            return CuePluginResult(pluginId=self.id, platform=self.platform, status="error", input=input, warnings=[str(exc)])

    def _query(self, input: CueInput) -> str:
        parts = [input.manualTopic, *input.alternateKeywords]
        return " ".join(p for p in parts if p).strip()

    def _search(self, query: str) -> Dict[str, Any]:
        response = self.session.get(
            self.search_url,
            params={
                "key": self.api_key,
                "part": "snippet",
                "q": query,
                "type": "video",
                "maxResults": self.max_results,
                "order": "relevance",
            },
            timeout=12,
        )
        response.raise_for_status()
        return response.json()

    def _video_stats(self, video_ids: List[str]) -> Dict[str, Any]:
        response = self.session.get(
            self.videos_url,
            params={
                "key": self.api_key,
                "part": "statistics,snippet",
                "id": ",".join(video_ids),
            },
            timeout=12,
        )
        response.raise_for_status()
        return response.json()

    def normalize(self, input: CueInput, query: str, search_payload: Dict[str, Any], stats_payload: Dict[str, Any]) -> CuePluginResult:
        stats_by_id = {item.get("id"): item for item in stats_payload.get("items", []) if item.get("id")}
        videos: List[Dict[str, Any]] = []
        competitors: List[Dict[str, Any]] = []
        publish_dates: List[datetime] = []
        views: List[int] = []
        likes: List[int] = []
        comments: List[int] = []

        for index, item in enumerate(search_payload.get("items", []), 1):
            video_id = item.get("id", {}).get("videoId", "")
            snippet = item.get("snippet", {}) or {}
            stat_item = stats_by_id.get(video_id, {})
            stat = stat_item.get("statistics", {}) or {}
            published_at = snippet.get("publishedAt", "")
            parsed_date = self._parse_date(published_at)
            if parsed_date:
                publish_dates.append(parsed_date)
            view_count = self._int(stat.get("viewCount"))
            like_count = self._int(stat.get("likeCount"))
            comment_count = self._int(stat.get("commentCount"))
            views.append(view_count)
            likes.append(like_count)
            comments.append(comment_count)
            video = {
                "rank": index,
                "videoId": video_id,
                "title": snippet.get("title", ""),
                "channelName": snippet.get("channelTitle", ""),
                "description": snippet.get("description", ""),
                "publishedAt": published_at,
                "viewCount": view_count,
                "likeCount": like_count,
                "commentCount": comment_count,
                "externalUrl": f"https://www.youtube.com/watch?v={video_id}" if video_id else "",
            }
            videos.append(video)
            competitors.append({
                "source": self.id,
                "title": snippet.get("channelTitle", ""),
                "description": snippet.get("description", ""),
                "recentEpisodeTitles": [snippet.get("title", "")],
                "externalUrl": video["externalUrl"],
            })

        result_count = self._int(search_payload.get("pageInfo", {}).get("totalResults"))
        engagement_score = self._engagement_score(views, likes, comments)
        recency_score = self._recency_score(publish_dates)
        return CuePluginResult(
            pluginId=self.id,
            platform=self.platform,
            input=input,
            competitors=competitors,
            keywords=[CueKeyword(value=query, source=self.id, weight=0.85)],
            signals=[
                CueSignal(
                    type="search_interest",
                    source=self.id,
                    value={
                        "keyword": query,
                        "averageInterest": engagement_score,
                        "engagementScore": engagement_score,
                        "videoCountForQuery": result_count,
                        "note": "YouTube is an engagement and demand proxy, not true keyword search volume.",
                    },
                    confidence=0.72 if videos else 0.35,
                ),
                CueSignal(
                    type="competition",
                    source=self.id,
                    value={
                        "resultCount": result_count,
                        "topMatchingVideos": [video["title"] for video in videos[:10]],
                        "note": "YouTube result count is a competition proxy, not exact opportunity volume.",
                    },
                    confidence=0.7 if videos else 0.35,
                ),
                CueSignal(
                    type="freshness",
                    source=self.id,
                    value={
                        "recencyScore": recency_score,
                        "latestPublishedAt": max((d.isoformat() for d in publish_dates), default=None),
                    },
                    confidence=0.65 if publish_dates else 0.35,
                ),
            ],
            raw={"query": query, "topVideos": videos, "resultCount": result_count},
            warnings=["YouTube Data API does not provide true keyword search volume; Cue treats it as demand, competition, freshness, and engagement proxy data."],
        )

    def _int(self, value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    def _parse_date(self, raw: str) -> Optional[datetime]:
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None

    def _engagement_score(self, views: List[int], likes: List[int], comments: List[int]) -> int:
        if not views:
            return 0
        avg_views = sum(views) / len(views)
        avg_likes = sum(likes) / max(len(likes), 1)
        avg_comments = sum(comments) / max(len(comments), 1)
        raw = min(100, (avg_views / 5000) + (avg_likes / 250) + (avg_comments / 50))
        return int(max(0, min(100, round(raw))))

    def _recency_score(self, dates: List[datetime]) -> int:
        if not dates:
            return 0
        latest = max(dates)
        if latest.tzinfo:
            latest = latest.astimezone(timezone.utc).replace(tzinfo=None)
        days = (datetime.utcnow() - latest).days
        if days <= 14:
            return 90
        if days <= 45:
            return 75
        if days <= 120:
            return 55
        return 35


class YouTubeAutocompletePlugin(NotImplementedCuePlugin):
    id = "youtubeAutocomplete"
    name = "YouTube Autocomplete"
    platform = "youtube"
