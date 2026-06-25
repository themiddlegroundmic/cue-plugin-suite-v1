from __future__ import annotations

import json
import uuid
from datetime import date, datetime
from typing import Any, Dict, Optional

from src.core.auth import ensure_context
from src.core.types.models import CueIntelligenceReport, CueRequestContext, CueWriterOutput, to_jsonable

from .database import CueDatabase


class CueTrackingRepository:
    def __init__(self, database: CueDatabase):
        self.database = database
        self.database.initialize()

    def upsert_tracked_show(self, title: str, rss_url: str = "", platform: str = "podcast", show_id: Optional[str] = None, context: CueRequestContext | None = None) -> str:
        context = ensure_context(context)
        existing = self.get_tracked_show_by_url(rss_url, context=context) if rss_url else None
        if existing:
            return existing["id"]
        record_id = show_id or str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO tracked_shows (
                  id, tenant_id, user_id, workspace_id, created_by, title, rss_url, platform, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (record_id, context.tenant_id, context.user_id, context.workspace_id, context.user_id, title, rss_url, platform, now, now),
            )
            connection.commit()
        return record_id

    def save_tracked_episode(self, show_id: str, title: str, episode_url: str = "", episode_id: Optional[str] = None, context: CueRequestContext | None = None) -> str:
        context = ensure_context(context)
        record_id = episode_id or str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO tracked_episodes (
                  id, tenant_id, user_id, workspace_id, created_by, show_id, title, episode_url, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (record_id, context.tenant_id, context.user_id, context.workspace_id, context.user_id, show_id, title, episode_url, now, now),
            )
            connection.commit()
        return record_id

    def get_tracked_show_by_url(self, rss_url: str, context: CueRequestContext | None = None) -> Optional[Dict[str, Any]]:
        context = ensure_context(context)
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM tracked_shows WHERE rss_url = ? AND tenant_id = ?", (rss_url, context.tenant_id)).fetchone()
            return dict(row) if row else None

    def get_tracked_show_by_id(self, show_id: str, context: CueRequestContext | None = None) -> Optional[Dict[str, Any]]:
        context = ensure_context(context)
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM tracked_shows WHERE id = ? AND tenant_id = ?", (show_id, context.tenant_id)).fetchone()
            return dict(row) if row else None

    def save_score_history(
        self,
        show_id: str,
        platform: str,
        keyword: str,
        score: int,
        episode_id: Optional[str] = None,
        snapshot_date: Optional[date] = None,
        context: CueRequestContext | None = None,
    ) -> str:
        context = ensure_context(context)
        record_id = str(uuid.uuid4())
        snap = (snapshot_date or date.today()).isoformat()
        now = datetime.utcnow().isoformat()
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO score_history (
                  id, tenant_id, user_id, workspace_id, created_by, show_id, episode_id, platform, keyword, score, snapshot_date, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (record_id, context.tenant_id, context.user_id, context.workspace_id, context.user_id, show_id, episode_id, platform, keyword, score, snap, now, now),
            )
            connection.commit()
        return record_id

    def save_weekly_rank_snapshot(
        self,
        show_id: str,
        platform: str,
        keyword: str,
        competitor_count: int,
        rank: Optional[int] = None,
        score: Optional[int] = None,
        episode_id: Optional[str] = None,
        snapshot_date: Optional[date] = None,
        context: CueRequestContext | None = None,
    ) -> str:
        context = ensure_context(context)
        record_id = str(uuid.uuid4())
        snap = (snapshot_date or date.today()).isoformat()
        now = datetime.utcnow().isoformat()
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO weekly_rank_snapshots (
                  id, tenant_id, user_id, workspace_id, created_by, show_id, episode_id, platform, keyword, rank, score, competitor_count, snapshot_date, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (record_id, context.tenant_id, context.user_id, context.workspace_id, context.user_id, show_id, episode_id, platform, keyword, rank, score, competitor_count, snap, now, now),
            )
            connection.commit()
        return record_id

    def save_competitor_snapshot(
        self,
        show_id: str,
        platform: str,
        keyword: str,
        competitor_count: int,
        rank: Optional[int] = None,
        score: Optional[int] = None,
        episode_id: Optional[str] = None,
        snapshot_date: Optional[date] = None,
        context: CueRequestContext | None = None,
    ) -> str:
        context = ensure_context(context)
        record_id = str(uuid.uuid4())
        snap = (snapshot_date or date.today()).isoformat()
        now = datetime.utcnow().isoformat()
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO competitor_snapshots (
                  id, tenant_id, user_id, workspace_id, created_by, show_id, episode_id, platform, keyword, rank, score, competitor_count, snapshot_date, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (record_id, context.tenant_id, context.user_id, context.workspace_id, context.user_id, show_id, episode_id, platform, keyword, rank, score, competitor_count, snap, now, now),
            )
            connection.commit()
        return record_id

    def save_analysis_run(
        self,
        report: CueIntelligenceReport,
        writer_output: CueWriterOutput,
        export_path: str,
        run_id: Optional[str] = None,
        context: CueRequestContext | None = None,
    ) -> str:
        context = ensure_context(context)
        record_id = run_id or str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        plugin_summary = [
            {
                "pluginId": result.pluginId,
                "platform": result.platform,
                "status": result.status,
                "signalCount": len(result.signals),
                "competitorCount": len(result.competitors),
                "warnings": result.warnings,
            }
            for result in report.pluginResults
        ]
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO analysis_runs (
                  id, tenant_id, user_id, workspace_id, created_by, input_json, plugin_summary_json, intelligence_report_json,
                  score_breakdown_json, writer_output_json, export_path, status, primary_topic, target_platform, rss_url,
                  opportunity_score, platform_readiness_score, confidence_score, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    context.tenant_id,
                    context.user_id,
                    context.workspace_id,
                    context.user_id,
                    json.dumps(to_jsonable(report.input)),
                    json.dumps(plugin_summary),
                    json.dumps(to_jsonable(report)),
                    json.dumps(to_jsonable(report.scoreBreakdown)),
                    json.dumps(to_jsonable(writer_output)),
                    export_path,
                    "ready",
                    report.primaryTopic,
                    report.input.targetPlatform,
                    report.input.rssUrl,
                    report.opportunityScore,
                    report.platformReadinessScore,
                    report.confidenceScore,
                    now,
                    now,
                ),
            )
            connection.commit()
        self._save_report_snapshots(report, context)
        return record_id

    def get_analysis_run(self, run_id: str, context: CueRequestContext | None = None) -> Optional[Dict[str, Any]]:
        context = ensure_context(context)
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM analysis_runs WHERE id = ? AND tenant_id = ?", (run_id, context.tenant_id)).fetchone()
            return dict(row) if row else None

    def list_analysis_runs(self, limit: int = 20, offset: int = 0, context: CueRequestContext | None = None, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        context = ensure_context(context)
        filters = filters or {}
        where = ["tenant_id = ?"]
        params: list[Any] = [context.tenant_id]
        self._apply_analysis_filters(where, params, filters)
        sort_by = filters.get("sort_by", "created_at")
        allowed_sort = {"created_at", "opportunity_score", "platform_readiness_score", "confidence_score", "primary_topic"}
        if sort_by not in allowed_sort:
            sort_by = "created_at"
        sort_direction = str(filters.get("sort_direction", "desc")).upper()
        if sort_direction not in {"ASC", "DESC"}:
            sort_direction = "DESC"
        where_sql = " WHERE " + " AND ".join(where)
        with self.database.connect() as connection:
            total = connection.execute(f"SELECT COUNT(*) AS count FROM analysis_runs{where_sql}", params).fetchone()["count"]
            rows = connection.execute(
                f"SELECT * FROM analysis_runs{where_sql} ORDER BY {sort_by} {sort_direction} LIMIT ? OFFSET ?",
                [*params, limit, offset],
            ).fetchall()
            items = [dict(row) for row in rows]
            return {"items": items, "limit": limit, "offset": offset, "total": total, "has_more": offset + len(items) < total}

    def list_tracked_shows(self, limit: int = 100, offset: int = 0, context: CueRequestContext | None = None, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        context = ensure_context(context)
        filters = filters or {}
        where = ["tenant_id = ?"]
        params: list[Any] = [context.tenant_id]
        if filters.get("topic"):
            where.append("title LIKE ?")
            params.append(f"%{filters['topic']}%")
        if filters.get("rss_url"):
            where.append("rss_url = ?")
            params.append(filters["rss_url"])
        if filters.get("platform"):
            where.append("platform = ?")
            params.append(filters["platform"])
        where_sql = " WHERE " + " AND ".join(where)
        with self.database.connect() as connection:
            total = connection.execute(f"SELECT COUNT(*) AS count FROM tracked_shows{where_sql}", params).fetchone()["count"]
            rows = connection.execute(f"SELECT * FROM tracked_shows{where_sql} ORDER BY created_at DESC LIMIT ? OFFSET ?", [*params, limit, offset]).fetchall()
            items = [dict(row) for row in rows]
            return {"items": items, "limit": limit, "offset": offset, "total": total, "has_more": offset + len(items) < total}

    def list_score_history(self, show_id: Optional[str] = None, topic: Optional[str] = None, limit: int = 50, offset: int = 0, context: CueRequestContext | None = None, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        context = ensure_context(context)
        filters = filters or {}
        query = "SELECT * FROM score_history"
        params: list[Any] = [context.tenant_id]
        clauses = ["tenant_id = ?"]
        if show_id:
            clauses.append("show_id = ?")
            params.append(show_id)
        if topic:
            clauses.append("keyword = ?")
            params.append(topic)
        if filters.get("platform"):
            clauses.append("platform = ?")
            params.append(filters["platform"])
        if filters.get("created_after"):
            clauses.append("created_at >= ?")
            params.append(filters["created_after"])
        if filters.get("created_before"):
            clauses.append("created_at <= ?")
            params.append(filters["created_before"])
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        with self.database.connect() as connection:
            total = connection.execute("SELECT COUNT(*) AS count FROM score_history WHERE " + " AND ".join(clauses), params).fetchone()["count"]
            rows = connection.execute(query + " ORDER BY snapshot_date DESC, created_at DESC LIMIT ? OFFSET ?", [*params, limit, offset]).fetchall()
            items = [dict(row) for row in rows]
            return {"items": items, "limit": limit, "offset": offset, "total": total, "has_more": offset + len(items) < total}

    def parse_analysis_run(self, run_id: str, context: CueRequestContext | None = None) -> Optional[Dict[str, Any]]:
        row = self.get_analysis_run(run_id, context=context)
        if not row:
            return None
        return self._parse_run_row(row)

    def _parse_run_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        parsed = dict(row)
        for key in ("input_json", "plugin_summary_json", "intelligence_report_json", "score_breakdown_json", "writer_output_json"):
            parsed[key.replace("_json", "")] = json.loads(row[key])
        return parsed

    def list_competitor_snapshots(self, limit: int = 50, offset: int = 0, context: CueRequestContext | None = None, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        context = ensure_context(context)
        filters = filters or {}
        where = ["tenant_id = ?"]
        params: list[Any] = [context.tenant_id]
        if filters.get("platform"):
            where.append("platform = ?")
            params.append(filters["platform"])
        if filters.get("topic"):
            where.append("keyword = ?")
            params.append(filters["topic"])
        where_sql = " WHERE " + " AND ".join(where)
        with self.database.connect() as connection:
            total = connection.execute(f"SELECT COUNT(*) AS count FROM competitor_snapshots{where_sql}", params).fetchone()["count"]
            rows = connection.execute(f"SELECT * FROM competitor_snapshots{where_sql} ORDER BY snapshot_date DESC, created_at DESC LIMIT ? OFFSET ?", [*params, limit, offset]).fetchall()
            items = [dict(row) for row in rows]
            return {"items": items, "limit": limit, "offset": offset, "total": total, "has_more": offset + len(items) < total}

    def list_analysis_runs_before(self, cutoff_iso: str, context: CueRequestContext | None = None, limit: Optional[int] = None) -> list[Dict[str, Any]]:
        context = ensure_context(context)
        sql = "SELECT * FROM analysis_runs WHERE tenant_id = ? AND created_at < ? ORDER BY created_at ASC"
        params: list[Any] = [context.tenant_id, cutoff_iso]
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        with self.database.connect() as connection:
            return [dict(row) for row in connection.execute(sql, params).fetchall()]

    def list_score_history_before(self, cutoff_iso: str, context: CueRequestContext | None = None, limit: Optional[int] = None) -> list[Dict[str, Any]]:
        return self._list_table_before("score_history", cutoff_iso, context, limit)

    def list_weekly_rank_snapshots_before(self, cutoff_iso: str, context: CueRequestContext | None = None, limit: Optional[int] = None) -> list[Dict[str, Any]]:
        return self._list_table_before("weekly_rank_snapshots", cutoff_iso, context, limit)

    def list_competitor_snapshots_before(self, cutoff_iso: str, context: CueRequestContext | None = None, limit: Optional[int] = None) -> list[Dict[str, Any]]:
        return self._list_table_before("competitor_snapshots", cutoff_iso, context, limit)

    def delete_analysis_runs(self, ids: list[str], context: CueRequestContext | None = None) -> int:
        return self._delete_by_ids("analysis_runs", ids, context)

    def delete_score_history(self, ids: list[str], context: CueRequestContext | None = None) -> int:
        return self._delete_by_ids("score_history", ids, context)

    def delete_weekly_rank_snapshots(self, ids: list[str], context: CueRequestContext | None = None) -> int:
        return self._delete_by_ids("weekly_rank_snapshots", ids, context)

    def delete_competitor_snapshots(self, ids: list[str], context: CueRequestContext | None = None) -> int:
        return self._delete_by_ids("competitor_snapshots", ids, context)

    def _save_report_snapshots(self, report: CueIntelligenceReport, context: CueRequestContext) -> None:
        title = report.show.title if report.show else report.primaryTopic
        rss_url = report.show.feedUrl if report.show else report.input.rssUrl or ""
        show_id = self.upsert_tracked_show(title=title, rss_url=rss_url, platform=report.input.targetPlatform, context=context)
        if report.show:
            for episode in report.show.episodes[:10]:
                self.save_tracked_episode(show_id, episode.title, episode.link, episode.guid, context=context)
        keyword = report.keywords[0].value if report.keywords else report.primaryTopic
        self.save_score_history(show_id, report.input.targetPlatform, keyword, report.opportunityScore, context=context)
        self.save_weekly_rank_snapshot(
            show_id=show_id,
            platform=report.input.targetPlatform,
            keyword=keyword,
            score=report.opportunityScore,
            competitor_count=len(report.competitors),
            context=context,
        )
        self.save_competitor_snapshot(
            show_id=show_id,
            platform=report.input.targetPlatform,
            keyword=keyword,
            score=report.opportunityScore,
            competitor_count=len(report.competitors),
            context=context,
        )

    def _apply_analysis_filters(self, where: list[str], params: list[Any], filters: Dict[str, Any]) -> None:
        if filters.get("topic"):
            where.append("primary_topic LIKE ?")
            params.append(f"%{filters['topic']}%")
        if filters.get("rss_url"):
            where.append("rss_url = ?")
            params.append(filters["rss_url"])
        if filters.get("platform"):
            where.append("target_platform = ?")
            params.append(filters["platform"])
        if filters.get("status"):
            where.append("status = ?")
            params.append(filters["status"])
        if filters.get("created_after"):
            where.append("created_at >= ?")
            params.append(filters["created_after"])
        if filters.get("created_before"):
            where.append("created_at <= ?")
            params.append(filters["created_before"])
        if filters.get("min_opportunity_score") is not None:
            where.append("opportunity_score >= ?")
            params.append(filters["min_opportunity_score"])
        if filters.get("max_opportunity_score") is not None:
            where.append("opportunity_score <= ?")
            params.append(filters["max_opportunity_score"])
        if filters.get("min_confidence_score") is not None:
            where.append("confidence_score >= ?")
            params.append(filters["min_confidence_score"])

    def _list_table_before(self, table: str, cutoff_iso: str, context: CueRequestContext | None, limit: Optional[int]) -> list[Dict[str, Any]]:
        context = ensure_context(context)
        allowed = {"score_history", "weekly_rank_snapshots", "competitor_snapshots"}
        if table not in allowed:
            raise ValueError(f"Unsupported retention table: {table}")
        sql = f"SELECT * FROM {table} WHERE tenant_id = ? AND created_at < ? ORDER BY created_at ASC"
        params: list[Any] = [context.tenant_id, cutoff_iso]
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        with self.database.connect() as connection:
            return [dict(row) for row in connection.execute(sql, params).fetchall()]

    def _delete_by_ids(self, table: str, ids: list[str], context: CueRequestContext | None) -> int:
        context = ensure_context(context)
        allowed = {"analysis_runs", "score_history", "weekly_rank_snapshots", "competitor_snapshots"}
        if table not in allowed or not ids:
            return 0
        placeholders = ",".join("?" for _ in ids)
        with self.database.connect() as connection:
            cursor = connection.execute(
                f"DELETE FROM {table} WHERE tenant_id = ? AND id IN ({placeholders})",
                [context.tenant_id, *ids],
            )
            connection.commit()
            return cursor.rowcount
