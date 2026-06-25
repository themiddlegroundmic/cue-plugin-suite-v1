SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS tracked_shows (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL DEFAULT 'local',
  user_id TEXT NOT NULL DEFAULT 'legacy',
  workspace_id TEXT,
  created_by TEXT NOT NULL DEFAULT 'legacy',
  title TEXT NOT NULL,
  rss_url TEXT,
  platform TEXT NOT NULL DEFAULT 'podcast',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

DROP INDEX IF EXISTS idx_tracked_shows_rss_url;
CREATE INDEX IF NOT EXISTS idx_tracked_shows_tenant_rss_url ON tracked_shows(tenant_id, rss_url);

CREATE TABLE IF NOT EXISTS tracked_episodes (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL DEFAULT 'local',
  user_id TEXT NOT NULL DEFAULT 'legacy',
  workspace_id TEXT,
  created_by TEXT NOT NULL DEFAULT 'legacy',
  show_id TEXT NOT NULL,
  title TEXT NOT NULL,
  episode_url TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(show_id) REFERENCES tracked_shows(id)
);

CREATE TABLE IF NOT EXISTS weekly_rank_snapshots (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL DEFAULT 'local',
  user_id TEXT NOT NULL DEFAULT 'legacy',
  workspace_id TEXT,
  created_by TEXT NOT NULL DEFAULT 'legacy',
  show_id TEXT NOT NULL,
  episode_id TEXT,
  platform TEXT NOT NULL,
  keyword TEXT NOT NULL,
  rank INTEGER,
  score INTEGER,
  competitor_count INTEGER NOT NULL,
  snapshot_date TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS score_history (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL DEFAULT 'local',
  user_id TEXT NOT NULL DEFAULT 'legacy',
  workspace_id TEXT,
  created_by TEXT NOT NULL DEFAULT 'legacy',
  show_id TEXT NOT NULL,
  episode_id TEXT,
  platform TEXT NOT NULL,
  keyword TEXT NOT NULL,
  score INTEGER NOT NULL,
  snapshot_date TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS competitor_snapshots (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL DEFAULT 'local',
  user_id TEXT NOT NULL DEFAULT 'legacy',
  workspace_id TEXT,
  created_by TEXT NOT NULL DEFAULT 'legacy',
  show_id TEXT NOT NULL,
  episode_id TEXT,
  platform TEXT NOT NULL,
  keyword TEXT NOT NULL,
  rank INTEGER,
  score INTEGER,
  competitor_count INTEGER NOT NULL,
  snapshot_date TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS analysis_runs (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL DEFAULT 'local',
  user_id TEXT NOT NULL DEFAULT 'legacy',
  workspace_id TEXT,
  created_by TEXT NOT NULL DEFAULT 'legacy',
  input_json TEXT NOT NULL,
  plugin_summary_json TEXT NOT NULL,
  intelligence_report_json TEXT NOT NULL,
  score_breakdown_json TEXT NOT NULL,
  writer_output_json TEXT NOT NULL,
  export_path TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'ready',
  primary_topic TEXT,
  target_platform TEXT,
  rss_url TEXT,
  opportunity_score INTEGER,
  platform_readiness_score INTEGER,
  confidence_score INTEGER,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
"""
