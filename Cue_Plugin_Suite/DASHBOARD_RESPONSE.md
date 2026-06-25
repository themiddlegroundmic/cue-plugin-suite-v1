# Dashboard Response

`CueDashboardReport` is the frontend-ready response shape returned by `CueApiRouter.analyze_topic()` and `CueApiRouter.analyze_rss()`.

Top-level fields:

- `run_id`
- `created_at`
- `input_summary`
- `primary_topic`
- `overall_status`
- `scores`
- `score_cards`
- `top_recommendations`
- `recommended_outputs`
- `competitors`
- `content_gaps`
- `signal_summary`
- `warnings`
- `export_paths`

List endpoints return:

- `items`
- `limit`
- `offset`
- `total`
- `has_more`

Each score card includes:

- `label`
- `score`
- `grade`
- `short_explanation`
- `factors`
- `warnings`

Grade mapping:

- 90-100: Excellent
- 75-89: Strong
- 60-74: Moderate
- 40-59: Weak
- 0-39: Poor

Frontend guidance:

- Use `score_cards` for summary cards.
- Use `top_recommendations` as the primary action list.
- Use `recommended_outputs` for editable metadata fields.
- Use `content_gaps` as structured opportunity cards.
- Show `warnings` near source details so users understand signal limits.
