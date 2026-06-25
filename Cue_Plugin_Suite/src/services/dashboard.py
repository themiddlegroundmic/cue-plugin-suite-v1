from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from src.core.types.models import CueIntelligenceReport, CueWriterOutput, to_jsonable


def grade(score: int) -> str:
    if score >= 90:
        return "Excellent"
    if score >= 75:
        return "Strong"
    if score >= 60:
        return "Moderate"
    if score >= 40:
        return "Weak"
    return "Poor"


class CueDashboardReportBuilder:
    def build(
        self,
        report: CueIntelligenceReport,
        writer_output: CueWriterOutput,
        run_id: Optional[str] = None,
        export_paths: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        score_cards = [
            self._score_card("Opportunity", report.scoreBreakdown.opportunityScore, report.scoreBreakdown.opportunity),
            self._score_card("Platform Readiness", report.scoreBreakdown.platformReadinessScore, report.scoreBreakdown.platformReadiness),
            self._score_card("Confidence", report.scoreBreakdown.confidenceScore, report.scoreBreakdown.confidence),
        ]
        return to_jsonable({
            "run_id": run_id,
            "created_at": report.createdAt,
            "input_summary": {
                "rss_url": report.input.rssUrl,
                "manual_topic": report.input.manualTopic,
                "target_platform": report.input.targetPlatform,
            },
            "primary_topic": report.primaryTopic,
            "overall_status": self._overall_status(report),
            "scores": {
                "opportunity": report.opportunityScore,
                "platform_readiness": report.platformReadinessScore,
                "confidence": report.confidenceScore,
            },
            "score_cards": score_cards,
            "top_recommendations": self._recommendations(report, writer_output),
            "recommended_outputs": writer_output.generatedText,
            "competitors": report.competitors[:10],
            "content_gaps": report.contentGaps[:10],
            "signal_summary": self._signal_summary(report),
            "warnings": self._warnings(report),
            "export_paths": export_paths or {},
        })

    def from_stored_run(self, run: Dict[str, Any]) -> Dict[str, Any]:
        report = run["intelligence_report"]
        writer = run["writer_output"]
        score = report.get("scoreBreakdown", {})
        score_cards = [
            self._stored_score_card("Opportunity", score.get("opportunityScore", report.get("opportunityScore", 0)), score.get("opportunity")),
            self._stored_score_card("Platform Readiness", score.get("platformReadinessScore", report.get("platformReadinessScore", 0)), score.get("platformReadiness")),
            self._stored_score_card("Confidence", score.get("confidenceScore", report.get("confidenceScore", 0)), score.get("confidence")),
        ]
        return {
            "run_id": run["id"],
            "created_at": run["created_at"],
            "input_summary": {
                "rss_url": report.get("input", {}).get("rssUrl"),
                "manual_topic": report.get("input", {}).get("manualTopic"),
                "target_platform": report.get("input", {}).get("targetPlatform"),
            },
            "primary_topic": report.get("primaryTopic"),
            "overall_status": "ready",
            "scores": {
                "opportunity": report.get("opportunityScore", 0),
                "platform_readiness": report.get("platformReadinessScore", 0),
                "confidence": report.get("confidenceScore", 0),
            },
            "score_cards": score_cards,
            "top_recommendations": writer.get("whyThisWorks", [])[:5],
            "recommended_outputs": writer.get("generatedText", {}),
            "competitors": report.get("competitors", [])[:10],
            "content_gaps": report.get("contentGaps", [])[:10],
            "signal_summary": {
                "demand": len(report.get("demandSignals", [])),
                "competition": len(report.get("competitionSignals", [])),
                "freshness": len(report.get("freshnessSignals", [])),
            },
            "warnings": self._stored_warnings(run),
            "export_paths": {"json": run.get("export_path", "")},
        }

    def _score_card(self, label: str, score: int, detail: Any) -> Dict[str, Any]:
        return {
            "label": label,
            "score": score,
            "grade": grade(score),
            "short_explanation": detail.explanation if detail else "",
            "factors": detail.factors if detail else [],
            "warnings": detail.warnings if detail else [],
        }

    def _stored_score_card(self, label: str, score: int, detail: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        return {
            "label": label,
            "score": score,
            "grade": grade(score),
            "short_explanation": (detail or {}).get("explanation", ""),
            "factors": (detail or {}).get("factors", []),
            "warnings": (detail or {}).get("warnings", []),
        }

    def _overall_status(self, report: CueIntelligenceReport) -> str:
        if report.riskFlags:
            return "needs_review"
        if report.confidenceScore < 40:
            return "limited_signals"
        return "ready"

    def _recommendations(self, report: CueIntelligenceReport, writer_output: CueWriterOutput) -> list[str]:
        recs = list(writer_output.whyThisWorks[:3])
        for gap in report.contentGaps[:2]:
            if isinstance(gap, dict) and gap.get("suggested_angle"):
                recs.append(gap["suggested_angle"])
        return recs[:5]

    def _signal_summary(self, report: CueIntelligenceReport) -> Dict[str, Any]:
        return {
            "demand": len(report.demandSignals),
            "competition": len(report.competitionSignals),
            "freshness": len(report.freshnessSignals),
            "plugins": [
                {
                    "plugin_id": result.pluginId,
                    "status": result.status,
                    "signal_count": len(result.signals),
                    "competitor_count": len(result.competitors),
                }
                for result in report.pluginResults
            ],
        }

    def _warnings(self, report: CueIntelligenceReport) -> list[str]:
        warnings = list(report.riskFlags)
        for result in report.pluginResults:
            warnings.extend(result.warnings)
        return sorted(set(warnings))

    def _stored_warnings(self, run: Dict[str, Any]) -> list[str]:
        warnings: list[str] = []
        for plugin in run.get("plugin_summary", []):
            warnings.extend(plugin.get("warnings", []))
        warnings.extend(run.get("intelligence_report", {}).get("riskFlags", []))
        return sorted(set(warnings))

