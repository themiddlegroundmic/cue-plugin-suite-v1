# Cue Platform Intelligence Architecture

Cue v1 separates collection, intelligence, scoring, writing, and export.

1. Platform plugins collect normalized signals.
2. `CueIntelligenceEngine` combines plugin results into a structured intelligence report.
3. `CueScorer` calculates Opportunity Score, Platform Readiness Score, and Confidence Score.
4. `CueIntelligenceWriter` consumes only the intelligence report.
5. Exporters package the input, metadata, plugin summary, report, scores, and writer output.

The writer never calls Apple, Spotify, Google Trends, RSS, YouTube, Meta, or TikTok APIs. Data collection and scoring happen first.

## Current v1 Package

- `src/core/types` shared dataclasses and plugin protocol
- `src/core/scoring` weighted scoring model
- `src/core/intelligence` competitor analysis, content gaps, report builder
- `src/core/writer` rule-based writer layer
- `src/core/exports` JSON export and Word export stub
- `src/plugins/rss` reliable RSS parser
- `src/plugins/apple` public iTunes Search API normalization
- `src/plugins/spotify` Spotify Search using Cue org credentials
- `src/plugins/googleTrends` Search Interest Signal wrapper
- `src/plugins/youtube` YouTube Data API v3 demand, competition, freshness, and engagement proxy
- `src/plugins/meta`, `src/plugins/tiktok.py` v1.1 stubs
- `src/services` orchestration, tracking models, weekly heartbeat stub
- `src/api` host-app handler functions
- `src/core/storage` SQLite migrations and repository layer
- `src/cli.py` end-to-end command-line workflow
- `src/services/dashboard.py` frontend-ready dashboard response shaping
- `src/services/comparison.py` run-to-run comparison for tracking
- `src/services/plugin_status.py` plugin health/status reporting
- `src/services/snapshots.py` callable weekly snapshot runner
- `src/api/fastapi_app.py` optional FastAPI adapter
- `src/core/auth.py` tenant-scoping guard helpers

## Tenancy

Host apps pass `CueRequestContext` into router methods. SQLite records store `tenant_id`, `user_id`, optional `workspace_id`, `created_by`, `created_at`, and `updated_at`. Read methods are tenant-scoped and exports are restricted to the configured exports directory.

## End-to-End Flow

`RSS/topic input -> enabled plugins -> CueIntelligenceEngine -> CueScorer -> CueIntelligenceWriter -> JSON export -> SQLite analysis run`

Existing legacy plugin folders remain intact for compatibility while the shared v1 architecture matures.
