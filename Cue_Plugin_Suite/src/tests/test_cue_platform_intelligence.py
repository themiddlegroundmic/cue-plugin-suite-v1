import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path

from src.core.intelligence.content_gaps import ContentGapDetector
from src.core.intelligence.engine import CueIntelligenceEngine
from src.core.auth import local_context
from src.core.retention import CueRetentionPolicy
from src.core.scoring.scorer import CueScorer
from src.core.storage import CueDatabase, CueTrackingRepository
from src.core.types.models import CueInput, CueKeyword, CuePluginResult, CueRequestContext, CueShow, CueEpisode, CueSignal, CueWriterRequest
from src.core.types.plugin import CuePlugin
from src.core.writer.writer import CueIntelligenceWriter
from src.services.comparison import AnalysisComparisonService
from src.services.dashboard import CueDashboardReportBuilder
from src.services.retention import CueRetentionService
from src.plugins.apple import ApplePodcastsSearchPlugin
from src.plugins.googleTrends import GoogleTrendsSignalPlugin
from src.plugins.rss import RssPlugin
from src.plugins.spotify import SpotifySearchPlugin
from src.plugins.youtube import YouTubeDataPlugin


RSS_XML = b"""<?xml version="1.0"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" xmlns:psc="http://podlove.org/simple-chapters">
  <channel>
    <title>The Test Show</title>
    <description>Local business automation and AI agents.</description>
    <itunes:author>Cue</itunes:author>
    <language>en-us</language>
    <itunes:image href="https://example.com/show.jpg" />
    <itunes:category text="Business"><itunes:category text="Entrepreneurship" /></itunes:category>
    <item>
      <guid>ep-1</guid>
      <title>AI Agents for Local Business</title>
      <description>How local operators can use automation without hype.</description>
      <pubDate>Mon, 01 Jan 2024 12:00:00 +0000</pubDate>
      <itunes:duration>00:45:30</itunes:duration>
      <link>https://example.com/ep-1</link>
      <itunes:keywords>ai agents, local business</itunes:keywords>
      <psc:chapters><psc:chapter start="00:00:00" title="Opening" /></psc:chapters>
    </item>
  </channel>
</rss>"""


def test_rss_parser_normalizes_show_and_episodes():
    show = RssPlugin().parse_xml(RSS_XML, "https://example.com/rss")
    assert show.title == "The Test Show"
    assert show.author == "Cue"
    assert "Business" in show.categories
    assert show.episodes[0].durationSeconds == 2730
    assert show.episodes[0].chapters[0]["name"] == "Opening"


def test_plugin_interface_contract_shape():
    plugin: CuePlugin = RssPlugin()
    assert plugin.id == "rss"
    assert plugin.enabled is True


def test_apple_search_parsing():
    payload = {"resultCount": 1, "results": [{"trackName": "The Test Show", "artistName": "Cue", "feedUrl": "https://example.com/rss", "genres": ["Business"], "trackCount": 10}]}
    result = ApplePodcastsSearchPlugin().normalize(CueInput(manualTopic="The Test Show"), "The Test Show", payload)
    assert result.signals[0].value["rankPosition"] == 1
    assert result.competitors[0]["feedUrl"] == "https://example.com/rss"


def test_spotify_result_normalization():
    payload = {"shows": {"items": [{"name": "The Test Show", "publisher": "Cue", "description": "A show", "external_urls": {"spotify": "https://open.spotify.com/show/1"}, "total_episodes": 5}]}, "episodes": {"items": [{"name": "Episode"}]}}
    result = SpotifySearchPlugin(client_id="id", client_secret="secret").normalize(CueInput(manualTopic="The Test Show"), "The Test Show", payload)
    assert result.signals[0].value["rankPosition"] == 1
    assert result.signals[0].value["topMatchingEpisodes"] == ["Episode"]


def test_google_trends_signal_normalization():
    class FakeSeries:
        def __init__(self, values):
            self._values = values
        def tolist(self):
            return self._values
    class FakeInterest:
        columns = ["ai agents"]
        def __getitem__(self, item):
            return FakeSeries([10, 20, 50, 80])
    result = GoogleTrendsSignalPlugin().normalize(CueInput(manualTopic="ai agents"), ["ai agents"], {"interest": FakeInterest(), "related": {}})
    assert result.signals[0].value["averageInterest"] == 40
    assert result.signals[0].value["trendDirection"] == "rising"


def _show():
    return CueShow(
        title="The Test Show",
        description="AI agents for local business automation",
        feedUrl="https://example.com/rss",
        image="https://example.com/show.jpg",
        episodes=[CueEpisode(guid="1", title="AI Agents for Local Business", description=" ".join(["automation"] * 80), publishedAt=datetime.utcnow() - timedelta(days=5), link="https://example.com/1", keywords=["ai agents"])],
    )


def test_opportunity_platform_and_confidence_scores():
    results = [
        CuePluginResult(pluginId="rss", platform="podcast", show=_show(), signals=[CueSignal(type="freshness", source="rss", value={"episodeCount": 1})]),
        CuePluginResult(pluginId="googleTrends", platform="search", signals=[CueSignal(type="search_interest", source="googleTrends", value={"averageInterest": 80, "trendDirection": "rising"})]),
        CuePluginResult(pluginId="apple", platform="podcast", competitors=[{"title": "Comp"}], signals=[CueSignal(type="competition", source="apple", value={"rankPosition": 4})]),
    ]
    score = CueScorer().score(results, _show())
    assert score.opportunityScore > 60
    assert score.platformReadinessScore > 70
    assert score.confidenceScore > 40


def test_content_gap_detector_plain_explanations():
    gaps = ContentGapDetector().detect(_show(), [{"showTitle": "Comp", "description": "workflow automation templates"}], [CueKeyword("workflow automation", presentInUserContent=False)], ["local automation"])
    assert any("workflow" in str(gap).lower() for gap in gaps)
    assert {"gap_topic", "reason", "supporting_signals", "suggested_angle", "confidence"} <= set(gaps[0].keys())


def test_writer_input_validation_and_output():
    report = CueIntelligenceEngine().build_report(CueInput(manualTopic="ai agents"), [CuePluginResult(pluginId="rss", platform="podcast", show=_show(), keywords=[CueKeyword("ai agents", presentInUserContent=True)])])
    output = CueIntelligenceWriter().write(CueWriterRequest(intelligenceReport=report))
    assert "episodeTitle" in output.generatedText
    assert output.whyThisWorks


def test_stub_plugin_returns_not_implemented():
    from src.plugins.youtube import YouTubeAutocompletePlugin
    result = asyncio.run(YouTubeAutocompletePlugin().analyze(CueInput(manualTopic="test")))
    assert result.status == "not_implemented"


def test_youtube_plugin_returns_not_configured_without_key():
    result = asyncio.run(YouTubeDataPlugin(api_key="").analyze(CueInput(manualTopic="ai agents")))
    assert result.status == "not_configured"


def test_youtube_plugin_normalizes_mocked_api_responses():
    search_payload = {
        "pageInfo": {"totalResults": 128000},
        "items": [{
            "id": {"videoId": "abc123"},
            "snippet": {
                "title": "AI Automation for Local Business",
                "channelTitle": "Ops Channel",
                "description": "AI agents for admin workflows",
                "publishedAt": datetime.utcnow().isoformat() + "Z",
            },
        }],
    }
    stats_payload = {
        "items": [{
            "id": "abc123",
            "statistics": {"viewCount": "50000", "likeCount": "2000", "commentCount": "300"},
        }]
    }
    result = YouTubeDataPlugin(api_key="key").normalize(CueInput(manualTopic="ai automation"), "ai automation", search_payload, stats_payload)
    assert result.status == "ok"
    assert result.raw["topVideos"][0]["viewCount"] == 50000
    assert any(signal.source == "youtubeData" for signal in result.signals)


def test_scoring_includes_explanation_fields_and_youtube_signals():
    results = [
        CuePluginResult(pluginId="youtubeData", platform="youtube", competitors=[{"title": "Comp"}], signals=[
            CueSignal(type="search_interest", source="youtubeData", value={"averageInterest": 85, "engagementScore": 85}),
            CueSignal(type="competition", source="youtubeData", value={"resultCount": 80000}),
            CueSignal(type="freshness", source="youtubeData", value={"recencyScore": 90}),
        ])
    ]
    score = CueScorer().score(results, _show())
    assert score.opportunity is not None
    assert score.opportunity.score == score.opportunityScore
    assert score.opportunity.factors


def test_storage_initialization_and_repository_round_trip(tmp_path):
    repository = CueTrackingRepository(CueDatabase(tmp_path / "cue.sqlite3"))
    show_id = repository.upsert_tracked_show("The Test Show", "https://example.com/rss")
    assert repository.get_tracked_show_by_id(show_id)["title"] == "The Test Show"
    assert repository.get_tracked_show_by_url("https://example.com/rss")["id"] == show_id
    repository.save_score_history(show_id, "podcast", "ai agents", 82)
    repository.save_weekly_rank_snapshot(show_id, "podcast", "ai agents", competitor_count=4, rank=3, score=82)


def test_storage_saves_analysis_run(tmp_path):
    report = CueIntelligenceEngine().build_report(CueInput(manualTopic="ai agents"), [CuePluginResult(pluginId="rss", platform="podcast", show=_show(), keywords=[CueKeyword("ai agents", presentInUserContent=True)])])
    writer_output = CueIntelligenceWriter().write(CueWriterRequest(intelligenceReport=report))
    repository = CueTrackingRepository(CueDatabase(tmp_path / "cue.sqlite3"))
    run_id = repository.save_analysis_run(report, writer_output, "exports/out.json")
    row = repository.get_analysis_run(run_id)
    assert row is not None
    assert json.loads(row["score_breakdown_json"])["opportunityScore"] == report.opportunityScore


def test_cli_analyze_writes_export_and_database(tmp_path, monkeypatch, capsys):
    from src import cli

    report = CueIntelligenceEngine().build_report(CueInput(manualTopic="ai agents"), [CuePluginResult(pluginId="rss", platform="podcast", show=_show(), keywords=[CueKeyword("ai agents", presentInUserContent=True)])])

    class FakeService:
        def analyze(self, cue_input):
            return report

    monkeypatch.setattr(cli, "CueAnalysisService", lambda: FakeService())
    exit_code = cli.main([
        "analyze",
        "--topic",
        "ai agents",
        "--export-dir",
        str(tmp_path / "exports"),
        "--db",
        str(tmp_path / "cue.sqlite3"),
    ])
    assert exit_code == 0
    assert list((tmp_path / "exports").glob("*.json"))
    stdout = capsys.readouterr().out
    assert "Opportunity Score" in stdout
    assert not stdout.lstrip().startswith("{")


def _report_with_score(topic="ai agents", score_offset=0, competitor="Comp", gap_topic="workflow automation"):
    report = CueIntelligenceEngine().build_report(CueInput(manualTopic=topic), [
        CuePluginResult(
            pluginId="rss",
            platform="podcast",
            show=_show(),
            competitors=[{"title": competitor, "description": "workflow automation"}],
            keywords=[CueKeyword(topic, presentInUserContent=True)],
            signals=[CueSignal(type="search_interest", source="test", value={"averageInterest": 70 + score_offset})],
        )
    ])
    report.contentGaps = [{
        "gap_topic": gap_topic,
        "reason": "test gap",
        "supporting_signals": ["test"],
        "suggested_angle": "test angle",
        "confidence": 70,
    }]
    return report


def test_cli_analyze_json_outputs_parseable_json(tmp_path, monkeypatch, capsys):
    from src import cli

    class FakeService:
        def analyze(self, cue_input):
            print("plugin warning on stdout")
            report = _report_with_score(topic=cue_input.manualTopic)
            report.input = cue_input
            return report

    monkeypatch.setattr(cli, "CueAnalysisService", lambda: FakeService())
    exit_code = cli.main([
        "analyze",
        "--json",
        "--topic",
        "ai agents",
        "--export-dir",
        str(tmp_path / "exports"),
        "--db",
        str(tmp_path / "cue.sqlite3"),
    ])

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert exit_code == 0
    assert data["ok"] is True
    assert data["topic"] == "ai agents"
    assert data["target_platform"] == "podcast"
    assert data["opportunity_score"] == data["intelligenceReport"]["opportunityScore"]
    assert data["score_explanations"]["opportunityScore"] == data["opportunity_score"]
    assert data["content_gaps"]
    assert data["recommendations"]["generatedText"]
    assert data["plugin_status"]
    assert Path(data["export_path"]).exists()
    assert "plugin warning on stdout" in captured.err


def test_cli_analyze_json_no_store_works(tmp_path, monkeypatch, capsys):
    from src import cli

    class FakeService:
        def analyze(self, cue_input):
            report = _report_with_score(topic=cue_input.manualTopic)
            report.input = cue_input
            return report

    db_path = tmp_path / "cue.sqlite3"
    monkeypatch.setattr(cli, "CueAnalysisService", lambda: FakeService())
    exit_code = cli.main([
        "analyze",
        "--json",
        "--no-store",
        "--topic",
        "ai agents",
        "--export-dir",
        str(tmp_path / "exports"),
        "--db",
        str(db_path),
    ])

    data = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert data["ok"] is True
    assert not db_path.exists()
    assert Path(data["export_path"]).exists()


def test_cli_analyze_json_with_topic_works(tmp_path, monkeypatch, capsys):
    from src import cli

    class FakeService:
        def analyze(self, cue_input):
            report = _report_with_score(topic=cue_input.manualTopic)
            report.input = cue_input
            return report

    monkeypatch.setattr(cli, "CueAnalysisService", lambda: FakeService())
    exit_code = cli.main([
        "analyze",
        "--json",
        "--topic",
        "platform search optimization",
        "--export-dir",
        str(tmp_path / "exports"),
        "--db",
        str(tmp_path / "cue.sqlite3"),
    ])

    data = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert data["topic"] == "platform search optimization"
    assert data["input"]["manualTopic"] == "platform search optimization"


def test_cli_analyze_json_with_rss_argument_is_accepted(tmp_path, monkeypatch, capsys):
    from src import cli

    class FakeService:
        def analyze(self, cue_input):
            report = _report_with_score(topic=cue_input.manualTopic or "The Test Show")
            report.input = cue_input
            return report

    monkeypatch.setattr(cli, "CueAnalysisService", lambda: FakeService())
    exit_code = cli.main([
        "analyze",
        "--json",
        "--rss",
        "https://example.com/rss",
        "--export-dir",
        str(tmp_path / "exports"),
        "--db",
        str(tmp_path / "cue.sqlite3"),
    ])

    data = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert data["rss_url"] == "https://example.com/rss"
    assert data["input"]["rssUrl"] == "https://example.com/rss"


def test_dashboard_report_response_model():
    report = _report_with_score()
    writer_output = CueIntelligenceWriter().write(CueWriterRequest(intelligenceReport=report))
    dashboard = CueDashboardReportBuilder().build(report, writer_output, run_id="run-1", export_paths={"json": "exports/out.json"})
    assert dashboard["run_id"] == "run-1"
    assert dashboard["score_cards"][0]["grade"] in {"Excellent", "Strong", "Moderate", "Weak", "Poor"}
    assert dashboard["recommended_outputs"]["episodeTitle"]


def test_router_analyze_topic_and_get_stored_run(tmp_path):
    from src.api.router import CueApiRouter

    class FakeService:
        def analyze(self, cue_input):
            return _report_with_score(topic=cue_input.manualTopic)

    router = CueApiRouter(
        repository=CueTrackingRepository(CueDatabase(tmp_path / "cue.sqlite3")),
        analysis_service=FakeService(),
        export_dir=str(tmp_path / "exports"),
    )
    dashboard = router.analyze_topic({"topic": "ai agents"})
    assert dashboard["primary_topic"] == "ai agents"
    stored = router.get_analysis_run(dashboard["run_id"])
    assert stored["run_id"] == dashboard["run_id"]
    assert router.list_analysis_runs()["items"]
    assert router.get_export(dashboard["run_id"])["payload"]


def test_router_analyze_rss_and_history(tmp_path):
    from src.api.router import CueApiRouter

    class FakeService:
        def analyze(self, cue_input):
            report = _report_with_score(topic=cue_input.manualTopic or "The Test Show")
            report.input = cue_input
            return report

    router = CueApiRouter(
        repository=CueTrackingRepository(CueDatabase(tmp_path / "cue.sqlite3")),
        analysis_service=FakeService(),
        export_dir=str(tmp_path / "exports"),
    )
    dashboard = router.analyze_rss({"rssUrl": "https://example.com/rss", "manualTopic": "rss topic"})
    assert dashboard["input_summary"]["rss_url"] == "https://example.com/rss"
    assert router.get_score_history(topic="rss topic")["items"]


def test_plugin_health_status_reporting(monkeypatch):
    from src.services.plugin_status import CuePluginStatusService

    monkeypatch.delenv("SPOTIFY_CLIENT_ID", raising=False)
    monkeypatch.delenv("SPOTIFY_CLIENT_SECRET", raising=False)
    statuses = CuePluginStatusService().statuses()
    spotify = next(item for item in statuses if item["plugin_id"] == "spotify")
    assert spotify["configured"] is False
    assert "SPOTIFY_CLIENT_ID" in spotify["missing_environment_variables"]


def test_analysis_comparison_logic(tmp_path):
    repository = CueTrackingRepository(CueDatabase(tmp_path / "cue.sqlite3"))
    before = _report_with_score(topic="ai agents", competitor="Old Comp", gap_topic="old gap")
    after = _report_with_score(topic="ai agents", score_offset=10, competitor="New Comp", gap_topic="new gap")
    before_writer = CueIntelligenceWriter().write(CueWriterRequest(intelligenceReport=before))
    after_writer = CueIntelligenceWriter().write(CueWriterRequest(intelligenceReport=after))
    before_id = repository.save_analysis_run(before, before_writer, "exports/before.json")
    after_id = repository.save_analysis_run(after, after_writer, "exports/after.json")
    comparison = AnalysisComparisonService().compare(repository.parse_analysis_run(before_id), repository.parse_analysis_run(after_id))
    assert "New Comp" in comparison["new_competitors"]
    assert "new gap" in comparison["new_content_gaps"]


def test_weekly_snapshot_runner(tmp_path):
    from src.services.snapshots import run_weekly_snapshots

    repository = CueTrackingRepository(CueDatabase(tmp_path / "cue.sqlite3"))
    repository.upsert_tracked_show("Tracked Show", "https://example.com/rss")

    class FakeService:
        def analyze(self, cue_input):
            return _report_with_score(topic=cue_input.manualTopic)

    summary = run_weekly_snapshots(repository, analysis_service=FakeService(), export_dir=str(tmp_path / "exports"))
    assert summary["checked_count"] == 1
    assert summary["saved_runs"]


def test_cli_snapshot_commands(tmp_path, capsys):
    from src import cli

    repository = CueTrackingRepository(CueDatabase(tmp_path / "cue.sqlite3"))
    repository.upsert_tracked_show("Tracked Show", "https://example.com/rss")
    exit_code = cli.main(["snapshots", "list", "--db", str(tmp_path / "cue.sqlite3")])
    assert exit_code == 0
    assert "Tracked Show" in capsys.readouterr().out


def test_fastapi_adapter_imports_without_required_core_dependency():
    from src.api import fastapi_app

    assert hasattr(fastapi_app, "create_app")


def test_graceful_optional_plugin_failure():
    from src.services.orchestrator import CueAnalysisService

    class BrokenPlugin:
        id = "broken"
        name = "Broken"
        platform = "test"
        enabled = True

        async def analyze(self, cue_input):
            raise RuntimeError("boom")

    report = CueAnalysisService(plugins=[BrokenPlugin()], enrichment_plugins=[]).analyze(CueInput(manualTopic="test"))
    assert report.pluginResults[0].status == "error"
    assert report.riskFlags or report.pluginResults[0].warnings


def test_dashboard_sample_output_validity():
    path = Path("sample_outputs/dashboard_report.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["score_cards"][0]["grade"] == "Strong"
    assert "content_gaps" in data


def test_request_context_defaults():
    context = CueRequestContext()
    assert context.tenant_id == "local"
    assert context.user_id == "cli"
    assert local_context().roles == ["local"]


def test_tenant_scoped_analysis_creation_and_read(tmp_path):
    repository = CueTrackingRepository(CueDatabase(tmp_path / "cue.sqlite3"))
    tenant_a = CueRequestContext(tenant_id="tenant-a", user_id="u1")
    tenant_b = CueRequestContext(tenant_id="tenant-b", user_id="u2")
    report = _report_with_score(topic="tenant topic")
    writer_output = CueIntelligenceWriter().write(CueWriterRequest(intelligenceReport=report))
    run_id = repository.save_analysis_run(report, writer_output, "exports/tenant-a/out.json", context=tenant_a)
    assert repository.get_analysis_run(run_id, context=tenant_a)["tenant_id"] == "tenant-a"
    assert repository.get_analysis_run(run_id, context=tenant_b) is None


def test_list_analysis_runs_pagination_and_filters(tmp_path):
    repository = CueTrackingRepository(CueDatabase(tmp_path / "cue.sqlite3"))
    context = CueRequestContext(tenant_id="tenant-a", user_id="u1")
    writer_output = CueIntelligenceWriter().write(CueWriterRequest(intelligenceReport=_report_with_score(topic="first topic")))
    repository.save_analysis_run(_report_with_score(topic="first topic"), writer_output, "exports/tenant-a/first.json", context=context)
    repository.save_analysis_run(_report_with_score(topic="second topic"), writer_output, "exports/tenant-a/second.json", context=context)
    page = repository.list_analysis_runs(limit=1, offset=0, context=context)
    assert page["total"] == 2
    assert page["has_more"] is True
    filtered = repository.list_analysis_runs(context=context, filters={"topic": "second"})
    assert filtered["total"] == 1
    assert filtered["items"][0]["primary_topic"] == "second topic"


def test_router_wrong_tenant_read_blocked(tmp_path):
    from src.api.router import CueApiRouter

    class FakeService:
        def analyze(self, cue_input):
            return _report_with_score(topic=cue_input.manualTopic)

    router = CueApiRouter(
        repository=CueTrackingRepository(CueDatabase(tmp_path / "cue.sqlite3")),
        analysis_service=FakeService(),
        export_dir=str(tmp_path / "exports"),
    )
    tenant_a = CueRequestContext(tenant_id="tenant-a", user_id="u1")
    tenant_b = CueRequestContext(tenant_id="tenant-b", user_id="u2")
    dashboard = router.analyze_topic({"topic": "ai agents"}, context=tenant_a)
    blocked = router.get_analysis_run(dashboard["run_id"], context=tenant_b)
    assert blocked["ok"] is False
    assert blocked["error"]["code"] == "not_found"


def test_export_access_valid_wrong_tenant_and_path_traversal(tmp_path):
    from src.api.router import CueApiRouter

    class FakeService:
        def analyze(self, cue_input):
            return _report_with_score(topic=cue_input.manualTopic)

    repository = CueTrackingRepository(CueDatabase(tmp_path / "cue.sqlite3"))
    router = CueApiRouter(repository=repository, analysis_service=FakeService(), export_dir=str(tmp_path / "exports"))
    tenant_a = CueRequestContext(tenant_id="tenant-a", user_id="u1")
    tenant_b = CueRequestContext(tenant_id="tenant-b", user_id="u2")
    dashboard = router.analyze_topic({"topic": "ai agents"}, context=tenant_a)
    assert router.get_export(dashboard["run_id"], context=tenant_a)["payload"]
    assert router.get_export(dashboard["run_id"], context=tenant_b)["ok"] is False

    report = _report_with_score(topic="bad export")
    writer_output = CueIntelligenceWriter().write(CueWriterRequest(intelligenceReport=report))
    bad_run = repository.save_analysis_run(report, writer_output, str(tmp_path / ".." / "secret.json"), context=tenant_a)
    blocked = router.get_export(bad_run, context=tenant_a)
    assert blocked["ok"] is False
    assert blocked["error"]["code"] == "forbidden"


def test_standardized_error_response_debug_detail():
    from src.api.responses import error_response

    hidden = error_response("storage_error", "Storage failed.", context=CueRequestContext(debug=False), debug_detail="secret")
    visible = error_response("storage_error", "Storage failed.", context=CueRequestContext(debug=True), debug_detail="secret")
    assert hidden["ok"] is False
    assert "debug_detail" not in hidden["error"]
    assert visible["error"]["debug_detail"] == "secret"


def test_old_database_migration_defaults_tenant_and_user(tmp_path):
    import sqlite3

    db_path = tmp_path / "old.sqlite3"
    with sqlite3.connect(db_path) as connection:
        connection.execute("CREATE TABLE analysis_runs (id TEXT PRIMARY KEY, input_json TEXT NOT NULL, plugin_summary_json TEXT NOT NULL, intelligence_report_json TEXT NOT NULL, score_breakdown_json TEXT NOT NULL, writer_output_json TEXT NOT NULL, export_path TEXT NOT NULL, created_at TEXT NOT NULL)")
        connection.execute("INSERT INTO analysis_runs VALUES ('old-run', '{}', '[]', '{}', '{}', '{}', 'exports/old.json', '2026-01-01T00:00:00')")
        connection.commit()
    CueDatabase(db_path).initialize()
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute("SELECT tenant_id, user_id, updated_at FROM analysis_runs WHERE id = 'old-run'").fetchone()
    assert row["tenant_id"] == "local"
    assert row["user_id"] == "legacy"
    assert row["updated_at"]


def test_fastapi_context_headers_helper():
    from src.api.fastapi_app import context_from_headers

    context = context_from_headers("tenant-x", "user-y", "workspace-z", "true")
    assert context.tenant_id == "tenant-x"
    assert context.user_id == "user-y"
    assert context.workspace_id == "workspace-z"
    assert context.debug is True


def test_default_retention_policy():
    policy = CueRetentionPolicy()
    assert policy.tenant_id == "local"
    assert policy.keep_analysis_runs_days == 90
    assert policy.keep_exports_days == 30
    assert policy.dry_run is True
    assert policy.max_delete_count is None


def test_retention_preview_does_not_delete(tmp_path):
    repository = CueTrackingRepository(CueDatabase(tmp_path / "cue.sqlite3"))
    context = CueRequestContext(tenant_id="tenant-a", user_id="u1")
    export_dir = tmp_path / "exports"
    export_dir.mkdir()
    export_file = export_dir / "old.json"
    export_file.write_text("{}", encoding="utf-8")
    run_id = _save_old_run(repository, context, export_file, days_old=120)
    summary = CueRetentionService(repository, export_dir).preview_retention_cleanup(CueRetentionPolicy(dry_run=True), context)
    assert summary["candidate_counts"]["analysis_runs"] == 1
    assert summary["deleted_counts"]["analysis_runs"] == 0
    assert export_file.exists()
    assert repository.get_analysis_run(run_id, context=context) is not None


def test_retention_run_deletes_only_matching_tenant_records(tmp_path):
    repository = CueTrackingRepository(CueDatabase(tmp_path / "cue.sqlite3"))
    export_dir = tmp_path / "exports"
    export_dir.mkdir()
    tenant_a = CueRequestContext(tenant_id="tenant-a", user_id="u1")
    tenant_b = CueRequestContext(tenant_id="tenant-b", user_id="u2")
    file_a = export_dir / "a.json"
    file_b = export_dir / "b.json"
    file_a.write_text("{}", encoding="utf-8")
    file_b.write_text("{}", encoding="utf-8")
    run_a = _save_old_run(repository, tenant_a, file_a, days_old=120)
    run_b = _save_old_run(repository, tenant_b, file_b, days_old=120)
    summary = CueRetentionService(repository, export_dir).run_retention_cleanup(CueRetentionPolicy(dry_run=False), tenant_a)
    assert summary["deleted_counts"]["analysis_runs"] == 1
    assert repository.get_analysis_run(run_a, context=tenant_a) is None
    assert repository.get_analysis_run(run_b, context=tenant_b) is not None
    assert not file_a.exists()
    assert file_b.exists()


def test_retention_export_path_traversal_blocked(tmp_path):
    repository = CueTrackingRepository(CueDatabase(tmp_path / "cue.sqlite3"))
    context = CueRequestContext(tenant_id="tenant-a", user_id="u1")
    export_dir = tmp_path / "exports"
    export_dir.mkdir()
    unsafe_path = tmp_path / "outside.json"
    unsafe_path.write_text("{}", encoding="utf-8")
    _save_old_run(repository, context, unsafe_path, days_old=120)
    summary = CueRetentionService(repository, export_dir).run_retention_cleanup(CueRetentionPolicy(dry_run=False), context)
    assert summary["warnings"]
    assert unsafe_path.exists()


def test_retention_missing_export_file_reported(tmp_path):
    repository = CueTrackingRepository(CueDatabase(tmp_path / "cue.sqlite3"))
    context = CueRequestContext(tenant_id="tenant-a", user_id="u1")
    export_dir = tmp_path / "exports"
    export_dir.mkdir()
    missing = export_dir / "missing.json"
    _save_old_run(repository, context, missing, days_old=120)
    summary = CueRetentionService(repository, export_dir).run_retention_cleanup(CueRetentionPolicy(dry_run=False), context)
    assert str(missing) in summary["export_files_missing"]


def test_retention_max_delete_count_respected(tmp_path):
    repository = CueTrackingRepository(CueDatabase(tmp_path / "cue.sqlite3"))
    context = CueRequestContext(tenant_id="tenant-a", user_id="u1")
    show_id = repository.upsert_tracked_show("Show", "https://example.com/rss", context=context)
    repository.save_score_history(show_id, "podcast", "one", 1, context=context)
    repository.save_score_history(show_id, "podcast", "two", 2, context=context)
    _backdate_table(repository, "score_history", context.tenant_id, days_old=365)
    policy = CueRetentionPolicy(dry_run=False, max_delete_count=1)
    summary = CueRetentionService(repository, tmp_path / "exports").run_retention_cleanup(policy, context)
    assert summary["deleted_counts"]["score_history"] == 1
    assert repository.list_score_history(context=context)["total"] == 1


def test_cli_retention_preview_command(tmp_path, capsys):
    from src import cli

    repository = CueTrackingRepository(CueDatabase(tmp_path / "cue.sqlite3"))
    context = local_context()
    export_dir = tmp_path / "exports"
    export_dir.mkdir()
    _save_old_run(repository, context, export_dir / "old.json", days_old=120)
    exit_code = cli.main(["retention", "preview", "--tenant-id", "local", "--db", str(tmp_path / "cue.sqlite3"), "--export-dir", str(export_dir)])
    assert exit_code == 0
    assert "Cue Retention Cleanup Summary" in capsys.readouterr().out


def test_cli_retention_run_requires_yes(tmp_path):
    from src import cli

    try:
        cli.main(["retention", "run", "--tenant-id", "local", "--db", str(tmp_path / "cue.sqlite3")])
    except SystemExit as exc:
        assert "--yes" in str(exc)
    else:
        raise AssertionError("retention run without --yes should exit")


def test_router_retention_preview_and_run(tmp_path):
    from src.api.router import CueApiRouter

    repository = CueTrackingRepository(CueDatabase(tmp_path / "cue.sqlite3"))
    context = CueRequestContext(tenant_id="tenant-a", user_id="u1")
    export_dir = tmp_path / "exports"
    export_dir.mkdir()
    _save_old_run(repository, context, export_dir / "old.json", days_old=120)
    router = CueApiRouter(repository=repository, export_dir=str(export_dir))
    preview = router.preview_retention_cleanup({}, context=context)
    assert preview["dry_run"] is True
    run = router.run_retention_cleanup({"dry_run": False}, context=context)
    assert run["deleted_counts"]["analysis_runs"] == 1


def test_fastapi_retention_routes_registered_if_available():
    from src.api import fastapi_app

    if fastapi_app.FastAPI is not None:
        routes = {route.path for route in fastapi_app.app.routes}
        assert "/retention/preview" in routes
        assert "/retention/run" in routes


def test_smoke_test_script_runs_with_temp_outputs(tmp_path):
    import importlib.util

    script_path = Path("scripts/smoke_test.py")
    spec = importlib.util.spec_from_file_location("cue_smoke_test", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    output_dir = tmp_path / "smoke_outputs"
    exit_code = module.main([
        "--topic",
        "Michigan redistricting",
        "--output-dir",
        str(output_dir),
        "--db",
        str(tmp_path / "smoke.sqlite3"),
    ])

    assert exit_code == 0
    assert (output_dir / "smoke_report.json").exists()


def _save_old_run(repository, context, export_path, days_old=120):
    report = _report_with_score(topic="old topic")
    writer_output = CueIntelligenceWriter().write(CueWriterRequest(intelligenceReport=report))
    run_id = repository.save_analysis_run(report, writer_output, str(export_path), context=context)
    _backdate_table(repository, "analysis_runs", context.tenant_id, days_old=days_old)
    _backdate_table(repository, "score_history", context.tenant_id, days_old=days_old)
    _backdate_table(repository, "weekly_rank_snapshots", context.tenant_id, days_old=days_old)
    _backdate_table(repository, "competitor_snapshots", context.tenant_id, days_old=days_old)
    return run_id


def _backdate_table(repository, table, tenant_id, days_old=365):
    old = (datetime.utcnow() - timedelta(days=days_old)).isoformat()
    with repository.database.connect() as connection:
        connection.execute(f"UPDATE {table} SET created_at = ?, updated_at = ? WHERE tenant_id = ?", (old, old, tenant_id))
        connection.commit()
