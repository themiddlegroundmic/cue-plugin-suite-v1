# Host App Integration

The host Cue app can call the shared Python package directly or wrap these calls behind its own HTTP/tRPC layer.

## Python Router Usage

```python
from src.api.router import CueApiRouter
from src.core.types.models import CueRequestContext

router = CueApiRouter()
context = CueRequestContext(
    tenant_id="tenant_123",
    user_id="user_456",
    workspace_id="workspace_789",
    roles=["member"],
)

dashboard_report = router.analyze_topic({
    "topic": "Michigan redistricting",
    "targetPlatform": "podcast"
}, context=context)

rss_dashboard_report = router.analyze_rss({
    "rssUrl": "https://example.com/feed.xml",
    "manualTopic": "Michigan redistricting",
    "targetPlatform": "podcast"
}, context=context)

score_json = router.score({
    "manualTopic": "Michigan redistricting",
    "targetPlatform": "podcast"
})

runs = router.list_analysis_runs(context=context, limit=20, offset=0)
history = router.get_score_history(topic="Michigan redistricting", context=context)
plugin_status = router.plugin_status(context=context)
retention_preview = router.preview_retention_cleanup({}, context=context)
```

The host app authenticates users. This package only scopes storage and exports based on the trusted context the host app passes in.

For in-process workflows that need dataclass objects:

```python
from src.core.exports import JsonCueExporter
from src.core.storage import CueDatabase, CueTrackingRepository
from src.core.types.models import CueInput, CueWriterRequest
from src.core.writer import CueIntelligenceWriter
from src.services.orchestrator import CueAnalysisService

cue_input = CueInput(
    rssUrl="https://example.com/feed.xml",
    manualTopic="Michigan redistricting",
    targetPlatform="podcast",
)

report = CueAnalysisService().analyze(cue_input)
writer_output = CueIntelligenceWriter().write(
    CueWriterRequest(intelligenceReport=report, targetPlatform="podcast")
)
JsonCueExporter().export(report, writer_output, "exports/report.json")

repository = CueTrackingRepository(CueDatabase("cue_tracking.sqlite3"))
repository.save_analysis_run(report, writer_output, "exports/report.json")
```

## Expected Request

```json
{
  "rssUrl": "https://example.com/feed.xml",
  "manualTopic": "Michigan redistricting",
  "targetPlatform": "podcast",
  "alternateKeywords": ["Michigan legislature", "redistricting maps"]
}
```

## Expected Response Shape

```json
{
  "run_id": "sample-run-id",
  "created_at": "2026-06-25T12:00:00Z",
  "input_summary": {
    "rss_url": "https://example.com/feed.xml",
    "manual_topic": "Michigan redistricting",
    "target_platform": "podcast"
  },
  "primary_topic": "Michigan redistricting",
  "overall_status": "ready",
  "scores": {
    "opportunity": 72,
    "platform_readiness": 68,
    "confidence": 61
  },
  "score_cards": [
    {
      "label": "Opportunity",
      "score": 72,
      "grade": "Moderate",
      "short_explanation": "Opportunity Score is moderate based on available signals.",
      "factors": ["Demand Signal: 70/100"],
      "warnings": []
    }
  ],
  "content_gaps": [
    {
      "gap_topic": "local district maps",
      "reason": "Related search interest exists but is not clearly covered.",
      "supporting_signals": ["Google Trends related query"],
      "suggested_angle": "Explain how voters can understand district map changes.",
      "confidence": 72
    }
  ],
  "export_paths": {
    "json": "exports/michigan-redistricting.json"
  }
}
```

## Example Score History Response

```json
{
  "items": [
    {
      "show_id": "tracked-show-id",
      "platform": "podcast",
      "keyword": "Michigan redistricting",
      "score": 72,
      "snapshot_date": "2026-06-25"
    }
  ],
  "limit": 50,
  "offset": 0,
  "total": 1,
  "has_more": false
}
```

## Example Paginated Run List

```json
{
  "items": [],
  "limit": 20,
  "offset": 0,
  "total": 0,
  "has_more": false
}
```

## Example Error Response

```json
{
  "ok": false,
  "error": {
    "code": "not_found",
    "message": "Analysis run not found.",
    "recoverable": true,
    "user_action_required": false
  }
}
```

## Export Security

`get_export(run_id, context)` verifies that the analysis run belongs to the tenant and that the stored export path is inside the configured exports directory. It does not accept arbitrary file paths from the frontend.

## Retention Cleanup

Use preview before run:

```python
preview = router.preview_retention_cleanup({
    "analysis_days": 90,
    "exports_days": 30
}, context=context)

result = router.run_retention_cleanup({
    "analysis_days": 90,
    "exports_days": 30,
    "dry_run": False
}, context=context)
```

The request may override retention windows, but tenant scope comes from `CueRequestContext`, not from user payload fields.

## Frontend Rendering Guidance

Render `score_cards` as the top row, `top_recommendations` as the action list, `recommended_outputs` as editable metadata fields, `competitors` as a table, and `content_gaps` as opportunity cards. Keep `warnings` visible near signal summaries so users understand source limitations.

## Source Claims

Apple and Spotify are Competition Signals/search visibility signals only. YouTube is a demand, competition, freshness, and engagement proxy. Google Trends is relative Search Interest Signal data. Cue scores are estimates, not guarantees.
