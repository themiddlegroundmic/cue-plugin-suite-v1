# Developer Handoff

## What This Package Is

Cue Plugin Suite v1 is a Python backend package for creator intelligence and PSO workflows. It can ingest creator inputs, collect platform/search signals, build a structured intelligence report, score the opportunity/readiness/confidence, generate metadata from that report, export JSON, and persist runs locally in SQLite.

## What This Package Is Not

- It is not the Cue host app.
- It is not an authentication system.
- It is not a full production scheduler.
- It does not claim true Apple, Spotify, or YouTube search volume.
- It does not fully implement Meta, Instagram, or TikTok yet.
- It does not require FastAPI for core CLI/router usage.

## Current Architecture Summary

The main implementation lives under `src/`.

- `src/core/types` shared dataclasses and plugin protocol.
- `src/plugins` interchangeable platform plugins.
- `src/core/intelligence` report building, competitor analysis, and content gaps.
- `src/core/scoring` Opportunity Score, Platform Readiness Score, and Confidence Score.
- `src/core/writer` rule-based writer that consumes `CueIntelligenceReport` only.
- `src/core/exports` JSON export.
- `src/core/storage` SQLite database, migrations, and repository.
- `src/services` orchestration, dashboard shaping, snapshots, retention, comparison, plugin status.
- `src/api` Python router, optional FastAPI adapter, response helpers.
- `src/cli.py` command-line entry point.

Legacy plugin folders remain for compatibility and tests:

- `podcast_pso_plugin`
- `youtube_pso_plugin`
- `platform_intelligence_plugin`
- compatibility aliases: `cue_pso_plugin`, `cue_youtube_pso_plugin`, `cue_platform_plugin`

## Data Flow

```text
CueInput
-> enabled plugins
-> CuePluginResult[]
-> CueIntelligenceEngine
-> CueIntelligenceReport
-> CueScorer
-> CueIntelligenceWriter
-> JsonCueExporter
-> CueTrackingRepository
-> dashboard/API response
```

The writer boundary is intentional: the writer does not call platform APIs. It only receives `CueIntelligenceReport`.

## Plugin Flow

Implemented:

- RSS parser
- Apple Podcasts Search
- Spotify Search
- Google Trends
- optional YouTube Data API v3

Stubs:

- Meta Graph
- Instagram hashtag search
- TikTok

Apple and Spotify plugins produce search visibility / competition signals, not true search volume. Google Trends is relative interest. YouTube is a demand and engagement proxy, not true keyword volume.

## CLI Usage

```powershell
python -m src.cli analyze --topic "Michigan redistricting"
python -m src.cli analyze --rss "https://example.com/feed.xml" --topic "Michigan redistricting"
python -m src.cli snapshots list
python -m src.cli snapshots run
python -m src.cli retention preview --tenant-id local
python -m src.cli retention run --tenant-id local --yes
```

CLI defaults:

```text
tenant_id = local
user_id = cli
roles = ["local"]
```

## API Router Usage

Use `CueApiRouter` for host-app integration without requiring FastAPI.

```python
from src.api.router import CueApiRouter
from src.core.types.models import CueRequestContext

router = CueApiRouter()
context = CueRequestContext(tenant_id="tenant_demo", user_id="user_demo")

dashboard = router.analyze_topic({"topic": "Michigan redistricting"}, context=context)
runs = router.list_analysis_runs(context=context)
run = router.get_analysis_run(dashboard["run_id"], context=context)
preview = router.preview_retention_cleanup({}, context=context)
```

## FastAPI Usage

FastAPI is optional.

```powershell
python -m pip install fastapi uvicorn
uvicorn src.api.fastapi_app:app --reload
```

Context headers:

```text
X-Cue-Tenant-Id: tenant_123
X-Cue-User-Id: user_456
X-Cue-Workspace-Id: workspace_789
X-Cue-Debug: false
```

## Tenant/Context Rules

The host app authenticates users and passes trusted context. This package scopes records by `tenant_id` and stores ownership metadata:

- `tenant_id`
- `user_id`
- `workspace_id`
- `created_by`
- `created_at`
- `updated_at`

Do not trust frontend-provided tenant IDs directly. Build `CueRequestContext` from the host app session/auth layer.

## Export Safety Rules

- Exports are read through stored analysis runs.
- Export reads are tenant-scoped.
- Export paths must stay inside the configured exports directory.
- Path traversal and arbitrary file reads are blocked.

## Retention Cleanup Rules

Retention cleanup is tenant-scoped. Preview before run.

```powershell
python -m src.cli retention preview --tenant-id local
python -m src.cli retention run --tenant-id local --yes
```

Retention can clean old analysis runs, export files, score history, weekly snapshots, and competitor snapshots. It intentionally does not delete tracked shows or tracked episodes in v1.

## Known Limitations

- SQLite is the only persistence backend currently implemented.
- FastAPI is optional and not required by tests/CLI.
- Meta, Instagram, and TikTok are stubs.
- Word export is stubbed.
- Retention policies are not persisted per tenant.
- Weekly snapshots are callable, not daemon-scheduled.

## Recommended Next Milestones

- Wire `CueRequestContext` to the real Cue auth/session layer.
- Add host-app role checks around retention run.
- Add tenant-aware export retention scheduling.
- Add production database adapter if SQLite is not enough.
- Add UI pagination around `items/limit/offset/total/has_more`.
- Implement richer YouTube enrichment before adding Meta/Instagram/TikTok.

