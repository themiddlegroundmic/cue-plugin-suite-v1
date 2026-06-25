from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Iterable, List

from src.core.types.models import CuePluginResult, CueScoreBreakdown, CueScoreDetail, CueShow, CueSignal


DEFAULT_SCORING_WEIGHTS = {
    "opportunity": {
        "demandSignal": 0.35,
        "trendMomentum": 0.20,
        "competitionGap": 0.20,
        "freshness": 0.15,
        "metadataQuality": 0.10,
    },
    "platformReadiness": {
        "titleQuality": 0.25,
        "descriptionQuality": 0.25,
        "keywordCoverage": 0.20,
        "platformFormatFit": 0.20,
        "riskSafetyFlags": 0.10,
    },
}


def _clamp_score(value: float) -> int:
    return int(max(0, min(100, round(value))))


def _average(values: Iterable[float], fallback: float = 50.0) -> float:
    clean = [v for v in values if v is not None]
    return sum(clean) / len(clean) if clean else fallback


@dataclass
class CueScorer:
    weights: Dict[str, Dict[str, float]] = field(default_factory=lambda: DEFAULT_SCORING_WEIGHTS)

    def score(self, plugin_results: List[CuePluginResult], show: CueShow | None = None) -> CueScoreBreakdown:
        demand = self._score_demand(plugin_results)
        trend = self._score_trend(plugin_results)
        competition_gap = self._score_competition_gap(plugin_results)
        freshness = self._score_freshness(show)
        metadata = self._score_metadata(show)
        opportunity_weights = self.weights["opportunity"]
        opportunity = _clamp_score(
            demand * opportunity_weights["demandSignal"]
            + trend * opportunity_weights["trendMomentum"]
            + competition_gap * opportunity_weights["competitionGap"]
            + freshness * opportunity_weights["freshness"]
            + metadata * opportunity_weights["metadataQuality"]
        )

        title = self._score_title(show)
        description = self._score_description(show)
        keyword_coverage = self._score_keyword_coverage(plugin_results, show)
        platform_fit = self._score_platform_fit(show)
        risk = self._score_risk(show)
        readiness_weights = self.weights["platformReadiness"]
        readiness = _clamp_score(
            title * readiness_weights["titleQuality"]
            + description * readiness_weights["descriptionQuality"]
            + keyword_coverage * readiness_weights["keywordCoverage"]
            + platform_fit * readiness_weights["platformFormatFit"]
            + risk * readiness_weights["riskSafetyFlags"]
        )

        confidence_components = self._confidence_components(plugin_results)
        confidence = _clamp_score(_average(confidence_components.values(), 35))

        return CueScoreBreakdown(
            opportunityScore=opportunity,
            platformReadinessScore=readiness,
            confidenceScore=confidence,
            opportunityComponents={
                "demandSignal": demand,
                "trendMomentum": trend,
                "competitionGap": competition_gap,
                "freshness": freshness,
                "metadataQuality": metadata,
            },
            readinessComponents={
                "titleQuality": title,
                "descriptionQuality": description,
                "keywordCoverage": keyword_coverage,
                "platformFormatFit": platform_fit,
                "riskSafetyFlags": risk,
            },
            confidenceComponents=confidence_components,
            opportunity=self._detail(
                "Opportunity Score",
                opportunity,
                [
                    self._factor("Demand Signal", demand),
                    self._factor("Trend Momentum", trend),
                    self._factor("Competition Gap", competition_gap),
                    self._factor("Freshness", freshness),
                    self._factor("Metadata Quality", metadata),
                ],
                plugin_results,
            ),
            platformReadiness=self._detail(
                "Platform Readiness Score",
                readiness,
                [
                    self._factor("Title Quality", title),
                    self._factor("Description Quality", description),
                    self._factor("Keyword Coverage", keyword_coverage),
                    self._factor("Platform Format Fit", platform_fit),
                    self._factor("Risk/Safety Flags", risk),
                ],
                plugin_results,
            ),
            confidence=self._detail(
                "Confidence Score",
                confidence,
                [
                    self._factor("Source Coverage", confidence_components["sourceCoverage"]),
                    self._factor("Signal Count", confidence_components["signalCount"]),
                    self._factor("Signal Agreement", confidence_components["signalAgreement"]),
                    self._factor("Status Quality", confidence_components["statusQuality"]),
                ],
                plugin_results,
            ),
        )

    def _signals(self, plugin_results: List[CuePluginResult], signal_type: str) -> List[CueSignal]:
        return [s for r in plugin_results for s in r.signals if s.type == signal_type]

    def _score_demand(self, plugin_results: List[CuePluginResult]) -> float:
        signals = self._signals(plugin_results, "search_interest")
        values = []
        for signal in signals:
            if not isinstance(signal.value, dict):
                continue
            if "averageInterest" in signal.value:
                values.append(float(signal.value.get("averageInterest", 0)))
            if "engagementScore" in signal.value:
                values.append(float(signal.value.get("engagementScore", 0)))
        return _average(values, 45)

    def _score_trend(self, plugin_results: List[CuePluginResult]) -> float:
        directions = [s.value.get("trendDirection") for s in self._signals(plugin_results, "search_interest") if isinstance(s.value, dict)]
        freshness_values = [
            s.value.get("recencyScore")
            for s in self._signals(plugin_results, "freshness")
            if isinstance(s.value, dict) and s.value.get("recencyScore") is not None
        ]
        if "rising" in directions:
            return 80
        if "falling" in directions:
            return 35
        if freshness_values:
            return _average([float(v) for v in freshness_values], 55)
        return 55 if directions else 45

    def _score_competition_gap(self, plugin_results: List[CuePluginResult]) -> float:
        competitors = sum(len(r.competitors) for r in plugin_results if r.status == "ok")
        youtube_result_counts = [
            s.value.get("resultCount")
            for s in self._signals(plugin_results, "competition")
            if isinstance(s.value, dict) and s.source == "youtubeData" and s.value.get("resultCount") is not None
        ]
        own_ranks = [
            s.value.get("rankPosition")
            for s in self._signals(plugin_results, "competition")
            if isinstance(s.value, dict) and s.value.get("rankPosition")
        ]
        if not competitors:
            return 60
        if own_ranks:
            return max(35, 100 - min(own_ranks) * 3)
        if youtube_result_counts:
            avg_results = _average([float(v) for v in youtube_result_counts], 0)
            if avg_results > 500000:
                return 35
            if avg_results > 100000:
                return 50
            return 65
        return max(25, 75 - competitors)

    def _score_freshness(self, show: CueShow | None) -> float:
        if not show or not show.episodes:
            return 45
        dates = [e.publishedAt for e in show.episodes if e.publishedAt]
        if not dates:
            return 45
        latest = max(dates)
        if latest.tzinfo:
            latest = latest.astimezone(timezone.utc).replace(tzinfo=None)
        days = (datetime.utcnow() - latest).days
        if days <= 14:
            return 90
        if days <= 45:
            return 70
        if days <= 120:
            return 50
        return 30

    def _score_metadata(self, show: CueShow | None) -> float:
        if not show or not show.episodes:
            return 45
        episodes = show.episodes[:10]
        return _average([self._episode_metadata_score(e.title, e.description, e.keywords) for e in episodes])

    def _episode_metadata_score(self, title: str, description: str, keywords: List[str]) -> float:
        score = 50
        if 25 <= len(title) <= 80:
            score += 20
        if len(description.split()) >= 75:
            score += 20
        if keywords:
            score += 10
        return min(score, 100)

    def _score_title(self, show: CueShow | None) -> float:
        if not show or not show.episodes:
            return 50
        return _average([90 if 25 <= len(e.title) <= 80 else 55 for e in show.episodes[:10]])

    def _score_description(self, show: CueShow | None) -> float:
        if not show or not show.episodes:
            return 50
        return _average([90 if len(e.description.split()) >= 75 else 45 for e in show.episodes[:10]])

    def _score_keyword_coverage(self, plugin_results: List[CuePluginResult], show: CueShow | None) -> float:
        found = {k.value.lower() for r in plugin_results for k in r.keywords}
        if not found:
            return 40
        content = ""
        if show:
            content = " ".join([show.title, show.description] + [e.title + " " + e.description for e in show.episodes[:5]]).lower()
        covered = sum(1 for kw in found if kw in content)
        return _clamp_score((covered / max(len(found), 1)) * 100)

    def _score_platform_fit(self, show: CueShow | None) -> float:
        if not show:
            return 50
        has_feed = bool(show.feedUrl)
        has_image = bool(show.image)
        has_episode_links = any(e.link for e in show.episodes)
        return _clamp_score((40 if has_feed else 0) + (25 if has_image else 0) + (35 if has_episode_links else 0))

    def _score_risk(self, show: CueShow | None) -> float:
        if not show:
            return 80
        risky_terms = ["guaranteed", "fraud", "rigged", "compliance guarantee", "true search volume"]
        text = " ".join([show.title, show.description] + [e.title + " " + e.description for e in show.episodes[:5]]).lower()
        flags = sum(1 for term in risky_terms if term in text)
        return max(20, 100 - flags * 20)

    def _confidence_components(self, plugin_results: List[CuePluginResult]) -> Dict[str, float]:
        useful = [r for r in plugin_results if r.status == "ok" and (r.signals or r.show or r.competitors)]
        configured = [r for r in plugin_results if r.status in {"ok", "not_implemented", "not_configured"}]
        source_coverage = min(100, len(useful) * 25)
        signal_count = min(100, sum(len(r.signals) for r in useful) * 12)
        agreement = 60
        demand_values = [
            s.value.get("averageInterest")
            for r in useful
            for s in r.signals
            if s.type == "search_interest" and isinstance(s.value, dict)
        ]
        if len(demand_values) > 1 and max(demand_values) - min(demand_values) < 25:
            agreement = 80
        status_quality = (len(useful) / max(len(configured), 1)) * 100
        return {
            "sourceCoverage": source_coverage,
            "signalCount": signal_count,
            "signalAgreement": agreement,
            "statusQuality": status_quality,
        }

    def _label(self, score: int) -> str:
        if score >= 80:
            return "strong"
        if score >= 60:
            return "medium"
        if score >= 40:
            return "limited"
        return "weak"

    def _factor(self, name: str, value: float) -> str:
        return f"{name}: {_clamp_score(value)}/100"

    def _detail(self, name: str, score: int, factors: List[str], plugin_results: List[CuePluginResult]) -> CueScoreDetail:
        useful_sources = sorted({r.pluginId for r in plugin_results if r.status == "ok" and (r.signals or r.show or r.competitors)})
        warnings = sorted({warning for r in plugin_results for warning in r.warnings})
        source_phrase = ", ".join(useful_sources) if useful_sources else "limited available sources"
        explanation = f"{name} is {self._label(score)} based on {source_phrase}. " + " ".join(factors[:3])
        return CueScoreDetail(
            score=score,
            label=self._label(score),
            factors=factors,
            explanation=explanation,
            warnings=warnings,
        )
