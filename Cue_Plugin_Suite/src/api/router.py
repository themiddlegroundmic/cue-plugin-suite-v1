from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from src.api import handlers
from src.api.responses import error_response
from src.core.auth import CueAuthorizationError, ensure_context
from src.core.exports import JsonCueExporter
from src.core.retention import CueRetentionPolicy
from src.core.storage import CueDatabase, CueTrackingRepository
from src.core.types.models import CueInput, CueIntelligenceReport, CueRequestContext, CueWriterRequest
from src.core.writer import CueIntelligenceWriter
from src.services.comparison import AnalysisComparisonService
from src.services.dashboard import CueDashboardReportBuilder
from src.services.orchestrator import CueAnalysisService
from src.services.plugin_status import CuePluginStatusService
from src.services.retention import CueRetentionService


class CueApiRouter:
    """Host-app integration point with tenant-scoped reads/writes."""

    def __init__(
        self,
        repository: Optional[CueTrackingRepository] = None,
        analysis_service: Optional[CueAnalysisService] = None,
        export_dir: str = "exports",
    ):
        self.repository = repository or CueTrackingRepository(CueDatabase("cue_tracking.sqlite3"))
        self.analysis_service = analysis_service or CueAnalysisService()
        self.export_dir = Path(export_dir)
        self.dashboard = CueDashboardReportBuilder()

    def analyze(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return handlers.analyze(payload)

    def score(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return handlers.score(payload)

    def write(self, report: CueIntelligenceReport, target_platform: str = "podcast") -> Dict[str, Any]:
        return handlers.write(report, target_platform)

    def export(self, report: CueIntelligenceReport, writer_output=None) -> Dict[str, Any]:
        return handlers.export_json(report, writer_output)

    def analyze_topic(self, request: Dict[str, Any], context: CueRequestContext | None = None) -> Dict[str, Any]:
        context = ensure_context(context)
        topic = request.get("manualTopic") or request.get("topic")
        if not topic:
            return error_response("validation_error", "topic or manualTopic is required.", context=context)
        cue_input = CueInput(manualTopic=topic, targetPlatform=request.get("targetPlatform", "podcast"), alternateKeywords=request.get("alternateKeywords", []))
        return self._run_and_store(cue_input, context)

    def analyze_rss(self, request: Dict[str, Any], context: CueRequestContext | None = None) -> Dict[str, Any]:
        context = ensure_context(context)
        rss_url = request.get("rssUrl") or request.get("rss")
        if not rss_url:
            return error_response("validation_error", "rssUrl or rss is required.", context=context)
        cue_input = CueInput(
            rssUrl=rss_url,
            manualTopic=request.get("manualTopic") or request.get("topic"),
            targetPlatform=request.get("targetPlatform", "podcast"),
            alternateKeywords=request.get("alternateKeywords", []),
        )
        return self._run_and_store(cue_input, context)

    def get_analysis_run(self, run_id: str, context: CueRequestContext | None = None) -> Dict[str, Any]:
        context = ensure_context(context)
        run = self.repository.parse_analysis_run(run_id, context=context)
        if not run:
            return error_response("not_found", "Analysis run not found.", recoverable=True, context=context)
        return self.dashboard.from_stored_run(run)

    def list_analysis_runs(self, context: CueRequestContext | None = None, limit: int = 20, offset: int = 0, **filters: Any) -> Dict[str, Any]:
        context = ensure_context(context)
        page = self.repository.list_analysis_runs(limit=limit, offset=offset, context=context, filters=filters)
        return {
            "items": [self.dashboard.from_stored_run(self.repository._parse_run_row(row)) for row in page["items"]],
            "limit": page["limit"],
            "offset": page["offset"],
            "total": page["total"],
            "has_more": page["has_more"],
        }

    def get_score_history(
        self,
        show_id: Optional[str] = None,
        topic: Optional[str] = None,
        context: CueRequestContext | None = None,
        limit: int = 50,
        offset: int = 0,
        **filters: Any,
    ) -> Dict[str, Any]:
        context = ensure_context(context)
        return self.repository.list_score_history(show_id=show_id, topic=topic, limit=limit, offset=offset, context=context, filters=filters)

    def list_recent_dashboard_reports(self, context: CueRequestContext | None = None, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        filters = filters or {}
        return self.list_analysis_runs(context=context, limit=filters.pop("limit", 20), offset=filters.pop("offset", 0), **filters)

    def list_tracked_topics(self, context: CueRequestContext | None = None, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self.list_tracked_shows(context=context, filters=filters)

    def list_tracked_shows(self, context: CueRequestContext | None = None, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        context = ensure_context(context)
        filters = filters or {}
        return self.repository.list_tracked_shows(limit=filters.pop("limit", 100), offset=filters.pop("offset", 0), context=context, filters=filters)

    def get_dashboard_report(self, run_id: str, context: CueRequestContext | None = None) -> Dict[str, Any]:
        return self.get_analysis_run(run_id, context=context)

    def get_latest_dashboard_report_for_topic(self, topic: str, context: CueRequestContext | None = None) -> Dict[str, Any]:
        page = self.list_analysis_runs(context=context, limit=1, topic=topic)
        if not page["items"]:
            return error_response("not_found", "No dashboard report found for topic.", context=ensure_context(context))
        return page["items"][0]

    def get_latest_dashboard_report_for_rss(self, rss_url: str, context: CueRequestContext | None = None) -> Dict[str, Any]:
        page = self.list_analysis_runs(context=context, limit=1, rss_url=rss_url)
        if not page["items"]:
            return error_response("not_found", "No dashboard report found for RSS URL.", context=ensure_context(context))
        return page["items"][0]

    def get_export(self, run_id: str, context: CueRequestContext | None = None) -> Dict[str, Any]:
        context = ensure_context(context)
        run = self.repository.get_analysis_run(run_id, context=context)
        if not run:
            return error_response("not_found", "Analysis run not found.", recoverable=True, context=context)
        try:
            path = self._safe_export_path(run["export_path"])
        except CueAuthorizationError as exc:
            return error_response("forbidden", "Export path is not allowed.", recoverable=False, context=context, debug_detail=str(exc))
        if not path.exists():
            return error_response("export_unavailable", "Export file not found.", recoverable=True, context=context, export_path=str(path))
        return {"run_id": run_id, "export_path": str(path), "payload": json.loads(path.read_text(encoding="utf-8"))}

    def plugin_status(self, context: CueRequestContext | None = None) -> Dict[str, Any]:
        context = ensure_context(context)
        last_status = {}
        page = self.repository.list_analysis_runs(limit=1, context=context)
        for row in page["items"]:
            for item in json.loads(row["plugin_summary_json"]):
                last_status[item["pluginId"]] = item["status"]
        return {"plugins": CuePluginStatusService(last_status=last_status).statuses()}

    def compare_analysis_runs(self, before_run_id: str, after_run_id: str, context: CueRequestContext | None = None) -> Dict[str, Any]:
        context = ensure_context(context)
        before = self.repository.parse_analysis_run(before_run_id, context=context)
        after = self.repository.parse_analysis_run(after_run_id, context=context)
        if not before or not after:
            return error_response("not_found", "Both analysis runs must exist in this tenant.", recoverable=True, context=context)
        return AnalysisComparisonService().compare(before, after)

    def preview_retention_cleanup(self, request: Dict[str, Any], context: CueRequestContext | None = None) -> Dict[str, Any]:
        context = ensure_context(context)
        policy = self._retention_policy_from_request(request, context, dry_run=True)
        return CueRetentionService(self.repository, self.export_dir).preview_retention_cleanup(policy, context)

    def run_retention_cleanup(self, request: Dict[str, Any], context: CueRequestContext | None = None) -> Dict[str, Any]:
        context = ensure_context(context)
        policy = self._retention_policy_from_request(request, context, dry_run=bool(request.get("dry_run", False)))
        return CueRetentionService(self.repository, self.export_dir).run_retention_cleanup(policy, context)

    def _run_and_store(self, cue_input: CueInput, context: CueRequestContext) -> Dict[str, Any]:
        report = self.analysis_service.analyze(cue_input)
        writer_output = CueIntelligenceWriter().write(CueWriterRequest(intelligenceReport=report, targetPlatform=cue_input.targetPlatform))
        export_path = self.export_dir / context.tenant_id / self._filename(report.primaryTopic)
        JsonCueExporter().export(report, writer_output, str(export_path))
        run_id = self.repository.save_analysis_run(report, writer_output, str(export_path), context=context)
        return self.dashboard.build(report, writer_output, run_id=run_id, export_paths={"json": str(export_path)})

    def _safe_export_path(self, stored_path: str) -> Path:
        base = self.export_dir.resolve()
        path = Path(stored_path)
        resolved = path.resolve() if path.is_absolute() else (Path.cwd() / path).resolve()
        try:
            resolved.relative_to(base)
        except ValueError as exc:
            raise CueAuthorizationError("Export path is outside the configured export directory.") from exc
        return resolved

    def _filename(self, topic: str) -> str:
        safe = "".join(ch.lower() if ch.isalnum() else "-" for ch in topic).strip("-") or "cue-analysis"
        return f"{safe[:60]}.json"

    def _retention_policy_from_request(self, request: Dict[str, Any], context: CueRequestContext, dry_run: bool) -> CueRetentionPolicy:
        return CueRetentionPolicy(
            tenant_id=context.tenant_id,
            keep_analysis_runs_days=int(request.get("keep_analysis_runs_days", request.get("analysis_days", 90))),
            keep_exports_days=int(request.get("keep_exports_days", request.get("exports_days", 30))),
            keep_score_history_days=int(request.get("keep_score_history_days", request.get("score_history_days", 180))),
            keep_snapshots_days=int(request.get("keep_snapshots_days", request.get("snapshots_days", 180))),
            keep_competitor_snapshots_days=int(request.get("keep_competitor_snapshots_days", request.get("competitor_days", 180))),
            dry_run=dry_run,
            max_delete_count=int(request["max_delete_count"]) if request.get("max_delete_count") is not None else None,
        )
