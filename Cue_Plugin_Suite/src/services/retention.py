from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable

from src.core.auth import CueAuthorizationError, ensure_context
from src.core.retention import CueRetentionPolicy
from src.core.storage import CueTrackingRepository
from src.core.types.models import CueRequestContext


class CueRetentionService:
    def __init__(self, repository: CueTrackingRepository, export_dir: str | Path = "exports"):
        self.repository = repository
        self.export_dir = Path(export_dir)

    def preview_retention_cleanup(self, policy: CueRetentionPolicy, context: CueRequestContext | None = None) -> Dict[str, Any]:
        policy = self._scoped_policy(policy, context, dry_run=True)
        return self._cleanup(policy, ensure_context(context))

    def run_retention_cleanup(self, policy: CueRetentionPolicy, context: CueRequestContext | None = None) -> Dict[str, Any]:
        policy = self._scoped_policy(policy, context, dry_run=policy.dry_run)
        return self._cleanup(policy, ensure_context(context))

    def _cleanup(self, policy: CueRetentionPolicy, context: CueRequestContext) -> Dict[str, Any]:
        cutoffs = self._cutoffs(policy)
        budget = policy.max_delete_count
        warnings: list[str] = []
        errors: list[str] = []
        export_files_deleted: list[str] = []
        export_files_missing: list[str] = []
        database_records_deleted: dict[str, list[str]] = {
            "analysis_runs": [],
            "score_history": [],
            "weekly_rank_snapshots": [],
            "competitor_snapshots": [],
        }

        export_candidates = self.repository.list_analysis_runs_before(cutoffs["exports"], context=context)
        analysis_candidates = self.repository.list_analysis_runs_before(cutoffs["analysis_runs"], context=context)
        score_candidates = self.repository.list_score_history_before(cutoffs["score_history"], context=context)
        weekly_candidates = self.repository.list_weekly_rank_snapshots_before(cutoffs["weekly_rank_snapshots"], context=context)
        competitor_candidates = self.repository.list_competitor_snapshots_before(cutoffs["competitor_snapshots"], context=context)

        candidate_counts = {
            "analysis_runs": len(analysis_candidates),
            "exports": len(export_candidates),
            "score_history": len(score_candidates),
            "weekly_rank_snapshots": len(weekly_candidates),
            "competitor_snapshots": len(competitor_candidates),
        }
        deleted_counts = {key: 0 for key in candidate_counts}
        skipped_counts = {key: 0 for key in candidate_counts}

        for run in export_candidates:
            if not self._can_delete_more(budget, deleted_counts):
                skipped_counts["exports"] += 1
                continue
            path_value = run.get("export_path") or ""
            try:
                path = self._safe_export_path(path_value)
            except CueAuthorizationError:
                warnings.append(f"Unsafe export path skipped for run {run.get('id')}: {path_value}")
                skipped_counts["exports"] += 1
                continue
            if not path.exists():
                export_files_missing.append(str(path))
                skipped_counts["exports"] += 1
                continue
            if policy.dry_run:
                continue
            try:
                path.unlink()
            except OSError as exc:
                errors.append(f"Failed to delete export file {path}: {exc}")
                skipped_counts["exports"] += 1
                continue
            export_files_deleted.append(str(path))
            deleted_counts["exports"] += 1

        self._delete_records(
            "analysis_runs",
            analysis_candidates,
            context,
            policy,
            budget,
            deleted_counts,
            skipped_counts,
            database_records_deleted,
            self.repository.delete_analysis_runs,
        )
        self._delete_records(
            "score_history",
            score_candidates,
            context,
            policy,
            budget,
            deleted_counts,
            skipped_counts,
            database_records_deleted,
            self.repository.delete_score_history,
        )
        self._delete_records(
            "weekly_rank_snapshots",
            weekly_candidates,
            context,
            policy,
            budget,
            deleted_counts,
            skipped_counts,
            database_records_deleted,
            self.repository.delete_weekly_rank_snapshots,
        )
        self._delete_records(
            "competitor_snapshots",
            competitor_candidates,
            context,
            policy,
            budget,
            deleted_counts,
            skipped_counts,
            database_records_deleted,
            self.repository.delete_competitor_snapshots,
        )

        return {
            "tenant_id": context.tenant_id,
            "dry_run": policy.dry_run,
            "cutoff_dates": cutoffs,
            "candidate_counts": candidate_counts,
            "deleted_counts": deleted_counts,
            "skipped_counts": skipped_counts,
            "warnings": warnings,
            "errors": errors,
            "export_files_deleted": export_files_deleted,
            "export_files_missing": export_files_missing,
            "database_records_deleted": database_records_deleted,
        }

    def _delete_records(
        self,
        key: str,
        candidates: list[Dict[str, Any]],
        context: CueRequestContext,
        policy: CueRetentionPolicy,
        budget: int | None,
        deleted_counts: Dict[str, int],
        skipped_counts: Dict[str, int],
        database_records_deleted: Dict[str, list[str]],
        delete_fn,
    ) -> None:
        if policy.dry_run:
            return
        ids: list[str] = []
        for row in candidates:
            if not self._can_delete_more(budget, deleted_counts):
                skipped_counts[key] += 1
                continue
            ids.append(row["id"])
            database_records_deleted[key].append(row["id"])
            deleted_counts[key] += 1
        if ids and not policy.dry_run:
            delete_fn(ids, context=context)

    def _can_delete_more(self, budget: int | None, deleted_counts: Dict[str, int]) -> bool:
        if budget is None:
            return True
        return sum(deleted_counts.values()) < budget

    def _scoped_policy(self, policy: CueRetentionPolicy, context: CueRequestContext | None, dry_run: bool) -> CueRetentionPolicy:
        context = ensure_context(context)
        return CueRetentionPolicy(
            tenant_id=context.tenant_id,
            keep_analysis_runs_days=policy.keep_analysis_runs_days,
            keep_exports_days=policy.keep_exports_days,
            keep_score_history_days=policy.keep_score_history_days,
            keep_snapshots_days=policy.keep_snapshots_days,
            keep_competitor_snapshots_days=policy.keep_competitor_snapshots_days,
            dry_run=dry_run,
            max_delete_count=policy.max_delete_count,
        )

    def _cutoffs(self, policy: CueRetentionPolicy) -> Dict[str, str]:
        now = datetime.utcnow()
        return {
            "analysis_runs": (now - timedelta(days=policy.keep_analysis_runs_days)).isoformat(),
            "exports": (now - timedelta(days=policy.keep_exports_days)).isoformat(),
            "score_history": (now - timedelta(days=policy.keep_score_history_days)).isoformat(),
            "weekly_rank_snapshots": (now - timedelta(days=policy.keep_snapshots_days)).isoformat(),
            "competitor_snapshots": (now - timedelta(days=policy.keep_competitor_snapshots_days)).isoformat(),
        }

    def _safe_export_path(self, stored_path: str) -> Path:
        base = self.export_dir.resolve()
        path = Path(stored_path)
        resolved = path.resolve() if path.is_absolute() else (Path.cwd() / path).resolve()
        try:
            resolved.relative_to(base)
        except ValueError as exc:
            raise CueAuthorizationError("Export path is outside the configured export directory.") from exc
        return resolved


def preview_retention_cleanup(policy: CueRetentionPolicy, context: CueRequestContext, repository: CueTrackingRepository, export_dir: str | Path = "exports") -> Dict[str, Any]:
    return CueRetentionService(repository, export_dir).preview_retention_cleanup(policy, context)


def run_retention_cleanup(policy: CueRetentionPolicy, context: CueRequestContext, repository: CueTrackingRepository, export_dir: str | Path = "exports") -> Dict[str, Any]:
    return CueRetentionService(repository, export_dir).run_retention_cleanup(policy, context)
