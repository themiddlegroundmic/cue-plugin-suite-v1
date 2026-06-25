from __future__ import annotations

import argparse
import re
from datetime import datetime
from pathlib import Path
from typing import List

from src.core.auth import local_context
from src.core.exports.json_exporter import JsonCueExporter
from src.core.storage import CueDatabase, CueTrackingRepository
from src.core.types.models import CueInput, CueWriterRequest
from src.core.writer import CueIntelligenceWriter
from src.services.orchestrator import CueAnalysisService
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
    analyze_parser.add_argument("--no-store", action="store_true", help="Do not save analysis run to SQLite")
    snapshots_parser = subparsers.add_parser("snapshots", help="Run or list weekly tracking snapshots")
    snapshot_subparsers = snapshots_parser.add_subparsers(dest="snapshot_command", required=True)
    snapshot_run = snapshot_subparsers.add_parser("run", help="Run weekly snapshots once")
    snapshot_run.add_argument("--db", default="cue_tracking.sqlite3")
    snapshot_run.add_argument("--export-dir", default="exports")
    snapshot_run.add_argument("--limit", type=int, default=100)
    snapshot_list = snapshot_subparsers.add_parser("list", help="List tracked shows for snapshot runs")
    snapshot_list.add_argument("--db", default="cue_tracking.sqlite3")
    snapshot_list.add_argument("--limit", type=int, default=100)
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
    return 1


def run_analyze(args) -> int:
    if not args.rss_url and not args.topic:
        raise SystemExit("Provide --rss, --topic, or both.")
    cue_input = CueInput(rssUrl=args.rss_url, manualTopic=args.topic, targetPlatform=args.target_platform)
    report = CueAnalysisService().analyze(cue_input)
    writer_output = CueIntelligenceWriter().write(CueWriterRequest(intelligenceReport=report, targetPlatform=args.target_platform))

    export_dir = Path(args.export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)
    filename = _filename(report.primaryTopic)
    export_path = export_dir / filename
    JsonCueExporter().export(report, writer_output, str(export_path))

    if not args.no_store:
        repository = CueTrackingRepository(CueDatabase(args.db))
        repository.save_analysis_run(report, writer_output, str(export_path), context=local_context())

    print(_summary(report, writer_output, export_path))
    return 0


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


if __name__ == "__main__":
    raise SystemExit(main())
