from __future__ import annotations

from typing import Any, Dict, List

from src.core.types.models import CueInput, CueKeyword, CuePluginResult, CueSignal

try:
    from pytrends.request import TrendReq
except ImportError:
    TrendReq = None


class GoogleTrendsSignalPlugin:
    id = "googleTrends"
    name = "Google Trends Search Interest"
    platform = "search"
    enabled = True

    def __init__(self, geo: str = "US", timeframe: str = "today 12-m", client: Any = None):
        self.geo = geo
        self.timeframe = timeframe
        self.client = client

    async def analyze(self, input: CueInput) -> CuePluginResult:
        keywords = [k for k in [input.manualTopic, *input.alternateKeywords] if k]
        if not keywords:
            return CuePluginResult(pluginId=self.id, platform=self.platform, status="not_configured", input=input, warnings=["manualTopic or alternateKeywords are required for Google Trends."])
        if TrendReq is None and self.client is None:
            return CuePluginResult(pluginId=self.id, platform=self.platform, status="not_configured", input=input, warnings=["pytrends is not installed; Search Interest Signal unavailable."])
        try:
            payload = self.fetch(keywords[:5])
            return self.normalize(input, keywords, payload)
        except Exception as exc:
            return CuePluginResult(pluginId=self.id, platform=self.platform, status="error", input=input, warnings=[str(exc)])

    def fetch(self, keywords: List[str]) -> Dict[str, Any]:
        client = self.client or TrendReq(hl="en-US", tz=360, timeout=(10, 25))
        client.build_payload(keywords, timeframe=self.timeframe, geo=self.geo)
        interest = client.interest_over_time()
        related = client.related_queries()
        return {"interest": interest, "related": related}

    def normalize(self, input: CueInput, keywords: List[str], payload: Dict[str, Any]) -> CuePluginResult:
        interest = payload.get("interest")
        related = payload.get("related", {}) or {}
        signals = []
        cue_keywords = []
        for keyword in keywords:
            values = []
            if interest is not None and hasattr(interest, "columns") and keyword in interest.columns:
                values = [int(v) for v in interest[keyword].tolist()]
            average = int(sum(values) / len(values)) if values else 0
            direction = self._direction(values)
            related_queries = self._related(keyword, related)
            cue_keywords.append(CueKeyword(value=keyword, source=self.id, weight=0.9))
            signals.append(CueSignal(
                type="search_interest",
                source=self.id,
                value={
                    "keyword": keyword,
                    "interestOverTime": values,
                    "averageInterest": average,
                    "trendDirection": direction,
                    "regionalInterest": [],
                    "relatedQueries": related_queries,
                    "note": "Google Trends is relative search interest, not actual search volume.",
                },
                confidence=0.7 if values else 0.35,
            ))
        return CuePluginResult(
            pluginId=self.id,
            platform=self.platform,
            input=input,
            keywords=cue_keywords,
            signals=signals,
            warnings=["Google Trends is relative search interest, not actual search volume."],
        )

    def _direction(self, values: List[int]) -> str:
        if len(values) < 4:
            return "unknown"
        early = sum(values[: len(values) // 2]) / max(len(values[: len(values) // 2]), 1)
        late = sum(values[len(values) // 2 :]) / max(len(values[len(values) // 2 :]), 1)
        if late > early + 10:
            return "rising"
        if late < early - 10:
            return "falling"
        return "stable"

    def _related(self, keyword: str, related: Dict[str, Any]) -> List[str]:
        bucket = related.get(keyword, {}) if isinstance(related, dict) else {}
        queries = []
        for name in ("rising", "top"):
            frame = bucket.get(name) if isinstance(bucket, dict) else None
            if frame is not None and hasattr(frame, "__getitem__") and "query" in getattr(frame, "columns", []):
                queries.extend(str(q) for q in frame["query"].tolist()[:5])
        return queries[:10]

