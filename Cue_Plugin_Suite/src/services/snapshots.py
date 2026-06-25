from __future__ import annotations

from typing import Any, Dict

from src.core.exports import JsonCueExporter
from src.core.storage import CueTrackingRepository
from src.core.types.models import CueInput, CueRequestContext, CueWriterRequest
from src.core.writer import CueIntelligenceWriter
from src.services.orchestrator import CueAnalysisService


def run_weekly_snapshots(
    repository: CueTrackingRepository,
    analysis_service: CueAnalysisService | None = None,
    export_dir: str = "exports",
    limit: int = 100,
    context: CueRequestContext | None = None,
) -> Dict[str, Any]:
    service = analysis_service or CueAnalysisService()
    shows = repository.list_tracked_shows(limit=limit, context=context)["items"]
    runs = []
    errors = []
    for show in shows:
        try:
            cue_input = CueInput(rssUrl=show.get("rss_url") or None, manualTopic=show.get("title"), targetPlatform=show.get("platform") or "podcast")
            report = service.analyze(cue_input)
            writer_output = CueIntelligenceWriter().write(CueWriterRequest(intelligenceReport=report, targetPlatform=cue_input.targetPlatform))
            export_path = f"{export_dir}/snapshot-{show['id']}.json"
            JsonCueExporter().export(report, writer_output, export_path)
            run_id = repository.save_analysis_run(report, writer_output, export_path, context=context)
            runs.append({"show_id": show["id"], "run_id": run_id, "export_path": export_path})
        except Exception as exc:
            errors.append({"show_id": show.get("id"), "message": str(exc)})
    return {
        "status": "complete" if not errors else "completed_with_errors",
        "checked_count": len(shows),
        "saved_runs": runs,
        "errors": errors,
    }
