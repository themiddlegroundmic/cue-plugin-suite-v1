from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.api.router import CueApiRouter
from src.core.storage import CueDatabase, CueTrackingRepository
from src.core.types.models import CueInput, CuePluginResult, CueRequestContext, CueSignal
from src.services.orchestrator import CueAnalysisService


class DemoSignalPlugin:
    id = "demoSignal"
    name = "Demo Signal"
    platform = "local"
    enabled = True

    async def analyze(self, cue_input: CueInput) -> CuePluginResult:
        topic = cue_input.manualTopic or "demo topic"
        return CuePluginResult(
            pluginId=self.id,
            platform=self.platform,
            input=cue_input,
            signals=[
                CueSignal(
                    type="search_interest",
                    source=self.id,
                    value={"keyword": topic, "averageInterest": 60, "trendDirection": "stable"},
                    confidence=0.5,
                    notes="Demo-only local signal.",
                )
            ],
        )


def main() -> None:
    context = CueRequestContext(
        tenant_id="demo_tenant",
        user_id="demo_user",
        workspace_id="demo_workspace",
        roles=["member"],
    )
    repository = CueTrackingRepository(CueDatabase("examples/demo_cue.sqlite3"))
    analysis_service = CueAnalysisService(plugins=[DemoSignalPlugin()], enrichment_plugins=[])
    router = CueApiRouter(repository=repository, analysis_service=analysis_service, export_dir="examples/exports")

    dashboard = router.analyze_topic({"topic": "Michigan redistricting"}, context=context)
    runs = router.list_analysis_runs(context=context, limit=10)
    run = router.get_analysis_run(dashboard["run_id"], context=context)
    retention_preview = router.preview_retention_cleanup({}, context=context)

    print("Dashboard run:", dashboard["run_id"])
    print("Run count:", runs["total"])
    print("Loaded run:", run["run_id"])
    print("Retention dry run:", retention_preview["dry_run"])


if __name__ == "__main__":
    main()

