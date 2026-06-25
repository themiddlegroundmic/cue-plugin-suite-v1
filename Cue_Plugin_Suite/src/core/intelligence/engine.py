from __future__ import annotations

from typing import List

from .competitors import CompetitorAnalyzer, extract_keywords
from .content_gaps import ContentGapDetector
from src.core.scoring.scorer import CueScorer
from src.core.types.models import (
    CueInput,
    CueIntelligenceReport,
    CueKeyword,
    CuePluginResult,
    CueSignal,
    CueShow,
)


class CueIntelligenceEngine:
    def __init__(self, scorer: CueScorer | None = None):
        self.scorer = scorer or CueScorer()
        self.competitor_analyzer = CompetitorAnalyzer()
        self.gap_detector = ContentGapDetector()

    def build_report(self, input: CueInput, plugin_results: List[CuePluginResult]) -> CueIntelligenceReport:
        show = self._first_show(plugin_results)
        keywords = self._collect_keywords(input, plugin_results, show)
        competitors = self.competitor_analyzer.analyze(
            [c for result in plugin_results for c in result.competitors],
            user_show=show,
        )
        related_queries = [
            q
            for result in plugin_results
            for signal in result.signals
            if signal.type == "search_interest" and isinstance(signal.value, dict)
            for q in signal.value.get("relatedQueries", [])
        ]
        youtube_terms = self._youtube_terms(plugin_results)
        content_gaps = self.gap_detector.detect(show, competitors, keywords, related_queries, youtube_terms=youtube_terms)
        risk_flags = self._risk_flags(plugin_results, show)
        score = self.scorer.score(plugin_results, show)
        primary_topic = input.manualTopic or (show.title if show else (keywords[0].value if keywords else "Untitled topic"))

        return CueIntelligenceReport(
            input=input,
            primaryTopic=primary_topic,
            keywords=keywords,
            detectedEntities=self._entities(show, keywords),
            competitors=competitors,
            demandSignals=self._signals(plugin_results, "search_interest"),
            competitionSignals=self._signals(plugin_results, "competition"),
            freshnessSignals=self._signals(plugin_results, "freshness"),
            contentGaps=content_gaps,
            riskFlags=risk_flags,
            confidenceScore=score.confidenceScore,
            opportunityScore=score.opportunityScore,
            platformReadinessScore=score.platformReadinessScore,
            scoreBreakdown=score,
            pluginResults=plugin_results,
            show=show,
        )

    def _first_show(self, plugin_results: List[CuePluginResult]) -> CueShow | None:
        for result in plugin_results:
            if result.show:
                return result.show
        return None

    def _collect_keywords(self, input: CueInput, plugin_results: List[CuePluginResult], show: CueShow | None) -> List[CueKeyword]:
        content = ""
        if show:
            content = " ".join([show.title, show.description] + [e.title + " " + e.description for e in show.episodes[:5]]).lower()
        raw = []
        if input.manualTopic:
            raw.append(CueKeyword(input.manualTopic, source="input", weight=1.0, presentInUserContent=input.manualTopic.lower() in content))
        raw.extend(CueKeyword(k, source="input", weight=0.8, presentInUserContent=k.lower() in content) for k in input.alternateKeywords)
        raw.extend(k for result in plugin_results for k in result.keywords)
        if show:
            raw.extend(CueKeyword(k, source="rss", weight=0.4, presentInUserContent=True) for k in extract_keywords(content, limit=12))

        dedup = {}
        for keyword in raw:
            key = keyword.value.strip().lower()
            if not key:
                continue
            existing = dedup.get(key)
            if not existing or keyword.weight > existing.weight:
                dedup[key] = keyword
        return list(dedup.values())[:40]

    def _signals(self, plugin_results: List[CuePluginResult], signal_type: str) -> List[CueSignal]:
        return [s for result in plugin_results for s in result.signals if s.type == signal_type]

    def _risk_flags(self, plugin_results: List[CuePluginResult], show: CueShow | None) -> List[str]:
        flags = [warning for result in plugin_results for warning in result.warnings]
        if show:
            text = f"{show.title} {show.description}".lower()
            if "guaranteed ranking" in text or "true search volume" in text:
                flags.append("Avoid guaranteed ranking or true search volume claims.")
        return sorted(set(flags))

    def _entities(self, show: CueShow | None, keywords: List[CueKeyword]) -> List[str]:
        entities = []
        if show and show.author:
            entities.append(show.author)
        entities.extend(k.value for k in keywords[:8])
        return sorted(set(entities))

    def _youtube_terms(self, plugin_results: List[CuePluginResult]) -> List[str]:
        terms: List[str] = []
        for result in plugin_results:
            if result.pluginId != "youtubeData":
                continue
            for item in result.raw.get("topVideos", []):
                title = item.get("title", "")
                if title:
                    terms.extend(extract_keywords(title, limit=5))
                description = item.get("description", "")
                if description:
                    terms.extend(extract_keywords(description, limit=5))
        seen = []
        for term in terms:
            if term not in seen:
                seen.append(term)
        return seen[:15]
