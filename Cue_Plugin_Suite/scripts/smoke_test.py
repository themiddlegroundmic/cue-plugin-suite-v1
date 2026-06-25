from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.api.router import CueApiRouter
from src.core.exports import JsonCueExporter
from src.core.storage import CueDatabase, CueTrackingRepository
from src.core.types.models import CueInput, CuePluginResult, CueRequestContext, CueSignal, CueWriterRequest
from src.core.writer import CueIntelligenceWriter
from src.services.orchestrator import CueAnalysisService


class LocalSignalPlugin:
    id = "localSmoke"
    name = "Local Smoke Signal"
    platform = "local"
    enabled = True

    async def analyze(self, cue_input: CueInput) -> CuePluginResult:
        topic = cue_input.manualTopic or "smoke test topic"
        return CuePluginResult(
            pluginId=self.id,
            platform=self.platform,
            input=cue_input,
            keywords=[],
            signals=[
                CueSignal(
                    type="search_interest",
                    source=self.id,
                    value={"keyword": topic, "averageInterest": 55, "trendDirection": "stable"},
                    confidence=0.5,
                    notes="Local smoke-test signal; not a platform volume claim.",
                )
            ],
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a local Cue smoke test without external credentials.")
    parser.add_argument("--topic", default="Michigan redistricting")
    parser.add_argument("--output-dir", default="smoke_outputs")
    parser.add_argument("--db", default="smoke_outputs/smoke.sqlite3")
    args = parser.parse_args(argv)

    try:
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        context = CueRequestContext(tenant_id="smoke", user_id="smoke-test", roles=["local"], debug=True)
        repository = CueTrackingRepository(CueDatabase(args.db))
        service = CueAnalysisService(plugins=[LocalSignalPlugin()], enrichment_plugins=[])
        cue_input = CueInput(manualTopic=args.topic, targetPlatform="podcast")
        report = service.analyze(cue_input)
        writer_output = CueIntelligenceWriter().write(CueWriterRequest(intelligenceReport=report))
        export_path = output_dir / "smoke_report.json"
        JsonCueExporter().export(report, writer_output, str(export_path))
        run_id = repository.save_analysis_run(report, writer_output, str(export_path), context=context)

        router = CueApiRouter(repository=repository, analysis_service=service, export_dir=str(output_dir))
        retention_preview = router.preview_retention_cleanup({}, context=context)

        checks = {
            "report_primary_topic": report.primaryTopic == args.topic,
            "export_exists": export_path.exists(),
            "run_saved": repository.get_analysis_run(run_id, context=context) is not None,
            "retention_preview_dry_run": retention_preview.get("dry_run") is True,
        }
        failed = [name for name, passed in checks.items() if not passed]
        if failed:
            print("SMOKE TEST FAIL")
            for name in failed:
                print(f"FAIL: {name}")
            return 1

        print("SMOKE TEST PASS")
        print(f"Topic: {report.primaryTopic}")
        print(f"Opportunity Score: {report.opportunityScore}")
        print(f"Platform Readiness Score: {report.platformReadinessScore}")
        print(f"Confidence Score: {report.confidenceScore}")
        print(f"Export: {export_path}")
        print(f"SQLite: {args.db}")
        print(f"Run ID: {run_id}")
        return 0
    except Exception as exc:
        print("SMOKE TEST FAIL")
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

