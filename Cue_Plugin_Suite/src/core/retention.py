from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class CueRetentionPolicy:
    tenant_id: str = "local"
    keep_analysis_runs_days: int = 90
    keep_exports_days: int = 30
    keep_score_history_days: int = 180
    keep_snapshots_days: int = 180
    keep_competitor_snapshots_days: int = 180
    dry_run: bool = True
    max_delete_count: Optional[int] = None

