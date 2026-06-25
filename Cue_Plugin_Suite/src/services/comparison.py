from __future__ import annotations

from typing import Any, Dict, Iterable


class AnalysisComparisonService:
    def compare(self, before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
        before_report = before["intelligence_report"]
        after_report = after["intelligence_report"]
        before_competitors = self._names(before_report.get("competitors", []))
        after_competitors = self._names(after_report.get("competitors", []))
        before_gaps = self._gap_topics(before_report.get("contentGaps", []))
        after_gaps = self._gap_topics(after_report.get("contentGaps", []))
        return {
            "before_run_id": before["id"],
            "after_run_id": after["id"],
            "score_changes": {
                "opportunity": self._delta(before_report.get("opportunityScore", 0), after_report.get("opportunityScore", 0)),
                "platform_readiness": self._delta(before_report.get("platformReadinessScore", 0), after_report.get("platformReadinessScore", 0)),
                "confidence": self._delta(before_report.get("confidenceScore", 0), after_report.get("confidenceScore", 0)),
            },
            "new_competitors": sorted(after_competitors - before_competitors),
            "removed_competitors": sorted(before_competitors - after_competitors),
            "new_content_gaps": sorted(after_gaps - before_gaps),
            "resolved_content_gaps": sorted(before_gaps - after_gaps),
            "signal_changes": {
                "demand": self._delta(len(before_report.get("demandSignals", [])), len(after_report.get("demandSignals", []))),
                "competition": self._delta(len(before_report.get("competitionSignals", [])), len(after_report.get("competitionSignals", []))),
                "freshness": self._delta(len(before_report.get("freshnessSignals", [])), len(after_report.get("freshnessSignals", []))),
            },
        }

    def _delta(self, before: int, after: int) -> Dict[str, int]:
        return {"before": before, "after": after, "delta": after - before}

    def _names(self, competitors: Iterable[Dict[str, Any]]) -> set[str]:
        return {c.get("showTitle") or c.get("title") for c in competitors if c.get("showTitle") or c.get("title")}

    def _gap_topics(self, gaps: Iterable[Any]) -> set[str]:
        topics = set()
        for gap in gaps:
            if isinstance(gap, dict) and gap.get("gap_topic"):
                topics.add(gap["gap_topic"])
            elif isinstance(gap, str):
                topics.add(gap)
        return topics

