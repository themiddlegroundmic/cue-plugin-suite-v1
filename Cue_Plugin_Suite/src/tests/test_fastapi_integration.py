from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from src.api import fastapi_app
from src.api.router import CueApiRouter
from src.core.intelligence.engine import CueIntelligenceEngine
from src.core.storage import CueDatabase, CueTrackingRepository
from src.core.types.models import (
    CueEpisode,
    CueInput,
    CueKeyword,
    CuePluginResult,
    CueRequestContext,
    CueShow,
    CueSignal,
    CueWriterRequest,
)
from src.core.writer.writer import CueIntelligenceWriter

pytestmark = pytest.mark.skipif(
    fastapi_app.FastAPI is None,
    reason="FastAPI is not installed",
)


def _show() -> CueShow:
    return CueShow(
        title="The Test Show",
        description="AI agents for local business automation",
        feedUrl="https://example.com/rss",
        image="https://example.com/show.jpg",
        episodes=[
            CueEpisode(
                guid="1",
                title="AI Agents for Local Business",
                description=" ".join(["automation"] * 80),
                publishedAt=datetime.utcnow() - timedelta(days=5),
                link="https://example.com/1",
                keywords=["ai agents"],
            )
        ],
    )


def _report_with_score(topic: str = "ai agents") -> object:
    report = CueIntelligenceEngine().build_report(
        CueInput(manualTopic=topic),
        [
            CuePluginResult(
                pluginId="rss",
                platform="podcast",
                show=_show(),
                competitors=[{"title": "Comp", "description": "workflow automation"}],
                keywords=[CueKeyword(topic, presentInUserContent=True)],
                signals=[
                    CueSignal(
                        type="search_interest",
                        source="test",
                        value={"averageInterest": 70},
                    )
                ],
            )
        ],
    )
    report.contentGaps = [
        {
            "gap_topic": "workflow automation",
            "reason": "test gap",
            "supporting_signals": ["test"],
            "suggested_angle": "test angle",
            "confidence": 70,
        }
    ]
    return report


class FakeAnalysisService:
    def analyze(self, cue_input):
        return _report_with_score(topic=cue_input.manualTopic or "ai agents")


def _cue_headers(
    tenant_id: str = "tenant-a",
    user_id: str = "u1",
    workspace_id: str | None = None,
    debug: str | None = None,
) -> dict[str, str]:
    headers = {
        "X-Cue-Tenant-Id": tenant_id,
        "X-Cue-User-Id": user_id,
    }
    if workspace_id is not None:
        headers["X-Cue-Workspace-Id"] = workspace_id
    if debug is not None:
        headers["X-Cue-Debug"] = debug
    return headers


def _make_router(tmp_path) -> CueApiRouter:
    return CueApiRouter(
        repository=CueTrackingRepository(CueDatabase(tmp_path / "cue.sqlite3")),
        analysis_service=FakeAnalysisService(),
        export_dir=str(tmp_path / "exports"),
    )


@pytest.fixture
def cue_client(tmp_path):
    from fastapi.testclient import TestClient

    router = _make_router(tmp_path)
    app = fastapi_app.create_app(router)
    with TestClient(app) as client:
        yield client, router, tmp_path


def _save_old_run(repository, context, export_path, days_old: int = 120) -> str:
    report = _report_with_score(topic="old topic")
    writer_output = CueIntelligenceWriter().write(CueWriterRequest(intelligenceReport=report))
    run_id = repository.save_analysis_run(report, writer_output, str(export_path), context=context)
    old = (datetime.utcnow() - timedelta(days=days_old)).isoformat()
    with repository.database.connect() as connection:
        for table in (
            "analysis_runs",
            "score_history",
            "weekly_rank_snapshots",
            "competitor_snapshots",
        ):
            connection.execute(
                f"UPDATE {table} SET created_at = ?, updated_at = ? WHERE tenant_id = ?",
                (old, old, context.tenant_id),
            )
        connection.commit()
    return run_id


def test_fastapi_analyze_topic_with_context_headers(cue_client):
    client, router, tmp_path = cue_client
    headers = _cue_headers(tenant_id="tenant-a", user_id="user-42")

    response = client.post("/analyze", json={"topic": "ai agents"}, headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["primary_topic"] == "ai agents"
    assert body["run_id"]

    stored = router.get_analysis_run(body["run_id"], context=CueRequestContext(tenant_id="tenant-a", user_id="user-42"))
    assert stored["run_id"] == body["run_id"]
    assert router.get_export(body["run_id"], context=CueRequestContext(tenant_id="tenant-a", user_id="user-42"))["payload"]


def test_fastapi_list_runs_scoped_to_tenant(cue_client):
    client, _, _ = cue_client
    tenant_a_headers = _cue_headers(tenant_id="tenant-a", user_id="u1")
    tenant_b_headers = _cue_headers(tenant_id="tenant-b", user_id="u2")

    first = client.post("/analyze", json={"topic": "tenant a topic"}, headers=tenant_a_headers).json()
    second = client.post("/analyze", json={"topic": "tenant b topic"}, headers=tenant_b_headers).json()
    assert first["run_id"] != second["run_id"]

    tenant_a_runs = client.get("/runs", headers=tenant_a_headers).json()
    tenant_b_runs = client.get("/runs", headers=tenant_b_headers).json()

    assert tenant_a_runs["total"] == 1
    assert tenant_b_runs["total"] == 1
    assert tenant_a_runs["items"][0]["run_id"] == first["run_id"]
    assert tenant_b_runs["items"][0]["run_id"] == second["run_id"]


def test_fastapi_get_run_blocks_wrong_tenant(cue_client):
    client, _, _ = cue_client
    tenant_a_headers = _cue_headers(tenant_id="tenant-a", user_id="u1")
    tenant_b_headers = _cue_headers(tenant_id="tenant-b", user_id="u2")

    created = client.post("/analyze", json={"topic": "ai agents"}, headers=tenant_a_headers).json()
    blocked = client.get(f"/runs/{created['run_id']}", headers=tenant_b_headers).json()

    assert blocked["ok"] is False
    assert blocked["error"]["code"] == "not_found"


def test_fastapi_export_blocks_wrong_tenant(cue_client):
    client, _, _ = cue_client
    tenant_a_headers = _cue_headers(tenant_id="tenant-a", user_id="u1")
    tenant_b_headers = _cue_headers(tenant_id="tenant-b", user_id="u2")

    created = client.post("/analyze", json={"topic": "ai agents"}, headers=tenant_a_headers).json()
    allowed = client.get(f"/runs/{created['run_id']}/export", headers=tenant_a_headers).json()
    blocked = client.get(f"/runs/{created['run_id']}/export", headers=tenant_b_headers).json()

    assert allowed["payload"]
    assert blocked["ok"] is False
    assert blocked["error"]["code"] == "not_found"


def test_fastapi_plugins_status_response_shape(cue_client):
    client, _, _ = cue_client

    response = client.get("/plugins/status", headers=_cue_headers())
    assert response.status_code == 200
    body = response.json()
    assert "plugins" in body
    assert body["plugins"]

    expected_keys = {
        "plugin_id",
        "plugin_name",
        "platform",
        "enabled",
        "configured",
        "missing_environment_variables",
        "last_run_status",
        "message",
    }
    for plugin in body["plugins"]:
        assert expected_keys <= set(plugin.keys())


def test_fastapi_retention_preview_uses_tenant_and_does_not_delete(cue_client):
    client, router, tmp_path = cue_client
    context = CueRequestContext(tenant_id="tenant-a", user_id="u1")
    export_dir = tmp_path / "exports"
    export_dir.mkdir()
    export_file = export_dir / "old.json"
    export_file.write_text("{}", encoding="utf-8")
    old_run_id = _save_old_run(repository=router.repository, context=context, export_path=export_file)

    preview = client.post("/retention/preview", json={}, headers=_cue_headers(tenant_id="tenant-a", user_id="u1")).json()

    assert preview["dry_run"] is True
    assert preview["tenant_id"] == "tenant-a"
    assert preview["candidate_counts"]["analysis_runs"] == 1
    assert preview["deleted_counts"]["analysis_runs"] == 0
    assert export_file.exists()
    assert router.repository.get_analysis_run(old_run_id, context=context) is not None


def test_fastapi_retention_run_safe_tenant_scoped_behavior(cue_client):
    client, router, tmp_path = cue_client
    export_dir = tmp_path / "exports"
    export_dir.mkdir()

    tenant_a = CueRequestContext(tenant_id="tenant-a", user_id="u1")
    tenant_b = CueRequestContext(tenant_id="tenant-b", user_id="u2")
    file_a = export_dir / "tenant-a.json"
    file_b = export_dir / "tenant-b.json"
    file_a.write_text("{}", encoding="utf-8")
    file_b.write_text("{}", encoding="utf-8")
    run_a = _save_old_run(router.repository, tenant_a, file_a, days_old=120)
    run_b = _save_old_run(router.repository, tenant_b, file_b, days_old=120)

    dry_run = client.post(
        "/retention/run",
        json={"dry_run": True},
        headers=_cue_headers(tenant_id="tenant-a", user_id="u1"),
    ).json()
    assert dry_run["dry_run"] is True
    assert router.repository.get_analysis_run(run_a, context=tenant_a) is not None
    assert router.repository.get_analysis_run(run_b, context=tenant_b) is not None

    deleted = client.post(
        "/retention/run",
        json={"dry_run": False},
        headers=_cue_headers(tenant_id="tenant-a", user_id="u1"),
    ).json()
    assert deleted["dry_run"] is False
    assert deleted["tenant_id"] == "tenant-a"
    assert router.repository.get_analysis_run(run_a, context=tenant_a) is None
    assert router.repository.get_analysis_run(run_b, context=tenant_b) is not None


def test_fastapi_debug_detail_hidden_unless_debug_header(cue_client):
    client, router, tmp_path = cue_client
    tenant_a = CueRequestContext(tenant_id="tenant-a", user_id="u1")
    report = _report_with_score(topic="bad export")
    writer_output = CueIntelligenceWriter().write(CueWriterRequest(intelligenceReport=report))
    bad_run_id = router.repository.save_analysis_run(
        report,
        writer_output,
        str(tmp_path / ".." / "secret.json"),
        context=tenant_a,
    )

    hidden = client.get(
        f"/runs/{bad_run_id}/export",
        headers=_cue_headers(tenant_id="tenant-a", user_id="u1", debug="false"),
    ).json()
    visible = client.get(
        f"/runs/{bad_run_id}/export",
        headers=_cue_headers(tenant_id="tenant-a", user_id="u1", debug="true"),
    ).json()

    assert hidden["ok"] is False
    assert hidden["error"]["code"] == "forbidden"
    assert "debug_detail" not in hidden["error"]
    assert visible["ok"] is False
    assert visible["error"]["code"] == "forbidden"
    assert "debug_detail" in visible["error"]


def test_fastapi_context_headers_populate_context_fields(cue_client):
    client, router, _ = cue_client
    headers = _cue_headers(
        tenant_id="tenant-x",
        user_id="user-y",
        workspace_id="workspace-z",
        debug="yes",
    )

    created = client.post("/analyze", json={"topic": "context topic"}, headers=headers).json()
    run_row = router.repository.get_analysis_run(created["run_id"], context=CueRequestContext(tenant_id="tenant-x", user_id="user-y"))

    assert run_row["tenant_id"] == "tenant-x"
    assert run_row["user_id"] == "user-y"
    assert run_row["workspace_id"] == "workspace-z"

    context = fastapi_app.context_from_headers("tenant-x", "user-y", "workspace-z", "yes")
    assert context.tenant_id == "tenant-x"
    assert context.user_id == "user-y"
    assert context.workspace_id == "workspace-z"
    assert context.debug is True