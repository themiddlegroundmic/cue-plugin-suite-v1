from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from .migrations import SCHEMA_SQL


class CueDatabase:
    def __init__(self, path: str | Path = "cue_tracking.sqlite3"):
        self.path = Path(path)

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA_SQL)
            self._migrate_ownership_columns(connection)
            connection.commit()

    def _migrate_ownership_columns(self, connection: sqlite3.Connection) -> None:
        tables = [
            "tracked_shows",
            "tracked_episodes",
            "weekly_rank_snapshots",
            "score_history",
            "competitor_snapshots",
            "analysis_runs",
        ]
        common_columns: dict[str, tuple[str, Any]] = {
            "tenant_id": ("TEXT NOT NULL DEFAULT 'local'", "local"),
            "user_id": ("TEXT NOT NULL DEFAULT 'legacy'", "legacy"),
            "workspace_id": ("TEXT", None),
            "created_by": ("TEXT NOT NULL DEFAULT 'legacy'", "legacy"),
            "updated_at": ("TEXT", None),
        }
        analysis_columns: dict[str, tuple[str, Any]] = {
            "status": ("TEXT NOT NULL DEFAULT 'ready'", "ready"),
            "primary_topic": ("TEXT", None),
            "target_platform": ("TEXT", None),
            "rss_url": ("TEXT", None),
            "opportunity_score": ("INTEGER", None),
            "platform_readiness_score": ("INTEGER", None),
            "confidence_score": ("INTEGER", None),
        }
        for table in tables:
            existing = {row["name"] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()}
            for column, (definition, default) in common_columns.items():
                if column not in existing:
                    connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
                    if column == "updated_at":
                        connection.execute(f"UPDATE {table} SET updated_at = COALESCE(created_at, ?)", (datetime.utcnow().isoformat(),))
                    elif default is not None:
                        connection.execute(f"UPDATE {table} SET {column} = ? WHERE {column} IS NULL", (default,))
            if table == "analysis_runs":
                existing = {row["name"] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()}
                for column, (definition, default) in analysis_columns.items():
                    if column not in existing:
                        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
                        if default is not None:
                            connection.execute(f"UPDATE {table} SET {column} = ? WHERE {column} IS NULL", (default,))
