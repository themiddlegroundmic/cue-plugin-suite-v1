from __future__ import annotations

import argparse
import contextlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, List

from src.core.auth import local_context
from src.core.exports.json_exporter import JsonCueExporter
from src.core.retention import CueRetentionPolicy
from src.core.storage import CueDatabase, CueTrackingRepository
from src.core.types.models import CueInput, CueWriterRequest, to_jsonable
from src.core.writer import CueIntelligenceWriter
from src.plugins.external_signals import ExternalSignalsPlugin
from src.services.orchestrator import CueAnalysisService
from src.services.retention import CueRetentionService
from src.services.snapshots import run_weekly_snapshots


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m src.cli", description="Cue Creator Intelligence CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    analyze_parser = subparsers.add_parser("analyze", help="Run RSS/topic analysis and export JSON")
    analyze_parser.add_argument("--rss", dest="rss_url", help="Podcast RSS feed URL")
    analyze_parser.add_argument("--topic", dest="topic", help="Manual topic or keyword")
    analyze_parser.add_argument("--target-platform", default="podcast", choices=["podcast", "youtube", "facebook", "instagram", "tiktok"])
    analyze_parser.add_argument("--export-dir", default="exports")
    analyze_parser.add_argument("--db", default="cue_tracking.sqlite3")
    analyze_parser.add_argument("--external-signals", dest="external_signals", help="Path to a sanitized host-provided external signals snapshot")
    analyze_parser.add_argument("--no-store", action="store_true", help="Do not save analysis run to SQLite")
    analyze_parser.add_argument("--json", action="store_true", help="Write machine-readable JSON to stdout")
    snapshots_parser = subparsers.add_parser("snapshots", help="Run or list weekly tracking snapshots")
    snapshot_subparsers = snapshots_parser.add_subparsers(dest="snapshot_command", required=True)
    snapshot_run = snapshot_subparsers.add_parser("run", help="Run weekly snapshots once")
    snapshot_run.add_argument("--db", default="cue_tracking.sqlite3")
    snapshot_run.add_argument("--export-dir", default="exports")
    snapshot_run.add_argument("--limit", type=int, default=100)
    snapshot_list = snapshot_subparsers.add_parser("list", help="List tracked shows for snapshot runs")
    snapshot_list.add_argument("--db", default="cue_tracking.sqlite3")
    snapshot_list.add_argument("--limit", type=int, default=100)
    retention_parser = subparsers.add_parser("retention", help="Preview or run tenant-scoped retention cleanup")
    retention_subparsers = retention_parser.add_subparsers(dest="retention_command", required=True)
    for command_name in ("preview", "run"):
        command = retention_subparsers.add_parser(command_name, help=f"{command_name.title()} retention cleanup")
        command.add_argument("--tenant-id", default="local")
        command.add_argument("--analysis-days", type=int, default=90)
        command.add_argument("--exports-days", type=int, default=30)
        command.add_argument("--score-history-days", type=int, default=180)
        command.add_argument("--snapshots-days", type=int, default=180)
        command.add_argument("--competitor-days", type=int, default=180)
        command.add_argument("--max-delete-count", type=int)
        command.add_argument("--dry-run", action="store_true")
        command.add_argument("--yes", action="store_true")
        command.add_argument("--db", default="cue_tracking.sqlite3")
        command.add_argument("--export-dir", default="exports")
    args = parser.parse_args(argv)

    if args.command == "analyze":
        return run_analyze(args)
    if args.command == "snapshots":
        if args.snapshot_command == "run":
            repository = CueTrackingRepository(CueDatabase(args.db))
            summary = run_weekly_snapshots(repository, export_dir=args.export_dir, limit=args.limit, context=local_context())
            print(summary)
            return 0
        if args.snapshot_command == "list":
            repository = CueTrackingRepository(CueDatabase(args.db))
            for show in repository.list_tracked_shows(limit=args.limit, context=local_context())["items"]:
                print(f"{show['id']} | {show['platform']} | {show['title']} | {show.get('rss_url') or ''}")
            return 0
    if args.command == "retention":
        return run_retention(args)
    return 1


def run_retention(args) -> int:
    context = local_context()
    context.tenant_id = args.tenant_id
    repository = CueTrackingRepository(CueDatabase(args.db))
    policy = CueRetentionPolicy(
        tenant_id=context.tenant_id,
        keep_analysis_runs_days=args.analysis_days,
        keep_exports_days=args.exports_days,
        keep_score_history_days=args.score_history_days,
        keep_snapshots_days=args.snapshots_days,
        keep_competitor_snapshots_days=args.competitor_days,
        dry_run=True if args.retention_command == "preview" else args.dry_run,
        max_delete_count=args.max_delete_count,
    )
    if args.retention_command == "run" and not policy.dry_run and not args.yes:
        raise SystemExit("Retention run requires --yes unless --dry-run is set.")
    service = CueRetentionService(repository, export_dir=args.export_dir)
    summary = service.preview_retention_cleanup(policy, context) if args.retention_command == "preview" else service.run_retention_cleanup(policy, context)
    print(_retention_summary(summary))
    return 0


def run_analyze(args) -> int:
    if args.json:
        return _run_analyze_json(args)

    result = _analyze_and_export(args)
    print(_summary(result["report"], result["writer_output"], result["export_path"]))
    return 0


def _run_analyze_json(args) -> int:
    try:
        with contextlib.redirect_stdout(sys.stderr):
            result = _analyze_and_export(args)
    except SystemExit as exc:
        message = str(exc) or "Analysis failed."
        print(message, file=sys.stderr)
        print(json.dumps(_json_error(message), sort_keys=True))
        return _exit_code(exc)
    except Exception as exc:
        print(f"Analysis failed: {exc}", file=sys.stderr)
        print(json.dumps(_json_error(str(exc)), sort_keys=True))
        return 1

    print(json.dumps(_json_payload(result), sort_keys=True))
    return 0


def _analyze_and_export(args) -> dict[str, Any]:
    if not args.rss_url and not args.topic:
        raise SystemExit("Provide --rss, --topic, or both.")
    cue_input = CueInput(rssUrl=args.rss_url, manualTopic=args.topic, targetPlatform=args.target_platform)
    extra_plugins = [ExternalSignalsPlugin(args.external_signals)] if getattr(args, "external_signals", None) else []
    service = CueAnalysisService(extra_plugins=extra_plugins) if extra_plugins else CueAnalysisService()
    report = service.analyze(cue_input)
    writer_output = CueIntelligenceWriter().write(CueWriterRequest(intelligenceReport=report, targetPlatform=args.target_platform))

    export_dir = Path(args.export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)
    filename = _filename(report.primaryTopic)
    export_path = export_dir / filename
    export_result = JsonCueExporter().export(report, writer_output, str(export_path))

    if not args.no_store:
        repository = CueTrackingRepository(CueDatabase(args.db))
        repository.save_analysis_run(report, writer_output, str(export_path), context=local_context())

    return {
        "report": report,
        "writer_output": writer_output,
        "export_path": export_path,
        "export_result": export_result,
    }


def _json_payload(result: dict[str, Any]) -> dict[str, Any]:
    report = result["report"]
    writer_output = result["writer_output"]
    export_path = result["export_path"]
    export_payload = dict(result["export_result"].payload)
    plugin_status = export_payload.get("pluginResultsSummary", [])
    payload = {
        **export_payload,
        "ok": True,
        "topic": report.primaryTopic,
        "rss_url": report.input.rssUrl,
        "target_platform": report.input.targetPlatform,
        "opportunity_score": report.opportunityScore,
        "platform_readiness_score": report.platformReadinessScore,
        "confidence_score": report.confidenceScore,
        "score_explanations": to_jsonable(report.scoreBreakdown),
        "content_gaps": to_jsonable(report.contentGaps),
        "recommendations": to_jsonable(writer_output),
        "plugin_status": plugin_status,
        "export_path": str(export_path),
        "export": {
            "format": "json",
            "path": str(export_path),
        },
    }
    return to_jsonable(payload)


def _json_error(message: str) -> dict[str, Any]:
    return {
        "ok": False,
        "error": {
            "code": "analysis_failed",
            "message": message,
        },
    }


def _exit_code(exc: SystemExit) -> int:
    if isinstance(exc.code, int):
        return exc.code if exc.code != 0 else 1
    return 1


def _filename(topic: str) -> str:
    stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    safe = re.sub(r"[^a-zA-Z0-9]+", "-", topic.lower()).strip("-") or "cue-analysis"
    return f"{stamp}-{safe[:60]}.json"


def _summary(report, writer_output, export_path: Path) -> str:
    keywords = ", ".join(k.value for k in report.keywords[:8]) or "none"
    competitors = ", ".join(c.get("showTitle", "") for c in report.competitors[:5] if c.get("showTitle")) or "none"
    gaps = "; ".join(_gap_line(gap) for gap in report.contentGaps[:3]) or "none"
    title = writer_output.generatedText.get("episodeTitle", "")
    description = writer_output.generatedText.get("descriptionOpening150Words", "")
    return "\n".join([
        "Cue Creator Intelligence Summary",
        f"Primary topic: {report.primaryTopic}",
        f"Opportunity Score: {report.opportunityScore}",
        f"Platform Readiness Score: {report.platformReadinessScore}",
        f"Confidence Score: {report.confidenceScore}",
        f"Top keywords: {keywords}",
        f"Top competitors: {competitors}",
        f"Content gaps: {gaps}",
        f"Recommended title: {title}",
        f"Recommended description preview: {description[:240]}",
        f"Export file: {export_path}",
    ])


def _gap_line(gap) -> str:
    if isinstance(gap, dict):
        return f"{gap.get('gap_topic')}: {gap.get('reason')}"
    return str(gap)


def _retention_summary(summary) -> str:
    return "\n".join([
        "Cue Retention Cleanup Summary",
        f"Tenant: {summary['tenant_id']}",
        f"Dry run: {summary['dry_run']}",
        f"Candidate counts: {summary['candidate_counts']}",
        f"Deleted counts: {summary['deleted_counts']}",
        f"Skipped counts: {summary['skipped_counts']}",
        f"Export files deleted: {len(summary['export_files_deleted'])}",
        f"Export files missing: {len(summary['export_files_missing'])}",
        f"Warnings: {len(summary['warnings'])}",
        f"Errors: {len(summary['errors'])}",
    ])


if __name__ == "__main__":
    raise SystemExit(main())
