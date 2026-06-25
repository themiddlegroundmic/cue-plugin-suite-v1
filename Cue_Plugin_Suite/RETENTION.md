# Retention Cleanup

Retention cleanup is a tenant-scoped maintenance feature for old analysis data and exports.

It can clean:

- `analysis_runs`
- JSON export files linked from analysis runs
- `score_history`
- `weekly_rank_snapshots`
- `competitor_snapshots`

It does not delete tracked shows or tracked episodes in v1. Those records are intentionally conservative because they represent user tracking configuration, not generated history.

## Default Local Policy

```text
tenant_id = local
keep_analysis_runs_days = 90
keep_exports_days = 30
keep_score_history_days = 180
keep_snapshots_days = 180
keep_competitor_snapshots_days = 180
dry_run = true
max_delete_count = None
```

## CLI

Preview first:

```bash
python -m src.cli retention preview --tenant-id local
```

Run cleanup:

```bash
python -m src.cli retention run --tenant-id local --yes
```

Custom retention windows:

```bash
python -m src.cli retention run --tenant-id local --analysis-days 30 --exports-days 14 --yes
```

`retention run` requires `--yes` unless `--dry-run` is set.

## Safety

- Cleanup is always scoped by `tenant_id`.
- Request payloads cannot clean another tenant; trusted context controls tenant scoping.
- Export deletion is restricted to the configured exports directory.
- Path traversal and arbitrary file paths are skipped and reported as warnings.
- Missing export files are reported but do not fail cleanup.
- Preview mode never deletes records or files.

## Host App Responsibility

The host app should choose production retention windows and pass trusted tenant/user context. This package does not authenticate users.

This feature does not change platform signal limitations: Apple and Spotify are search visibility / competition signals, Google Trends is relative interest, YouTube is a demand and engagement proxy, and scores are creator decision-support estimates.

