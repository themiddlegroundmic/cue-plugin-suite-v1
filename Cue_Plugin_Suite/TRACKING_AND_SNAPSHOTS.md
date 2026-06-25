# Tracking And Snapshots

SQLite persistence stores:

- `tracked_shows`
- `tracked_episodes`
- `weekly_rank_snapshots`
- `score_history`
- `competitor_snapshots`
- `analysis_runs`

All tables include tenant/user ownership fields:

- `tenant_id`
- `user_id`
- `workspace_id`
- `created_by`
- `created_at`
- `updated_at`

Run weekly snapshots manually:

```bash
python -m src.cli snapshots run
```

List tracked shows:

```bash
python -m src.cli snapshots list
```

The snapshot runner is callable, not a daemon. It loads tracked shows, reruns analysis, saves score history, competitor snapshots, weekly rank snapshots, analysis runs, and JSON exports.

This prepares Cue for weekly tracking without creating fragile background scheduling in v1.

Old generated history can be cleaned with the tenant-scoped retention service. See `RETENTION.md`.
