"""
tests/test_youtube_pso.py
=========================
Unit tests for the Cue YouTube PSO Plugin.
All tests run without API credentials — mocking external calls.
"""

import pytest
from unittest.mock import patch, MagicMock
from cue_youtube_pso_plugin.core.search_rank import YouTubeSearchRank, KeywordRankResult, SearchResult
from cue_youtube_pso_plugin.core.autocomplete import get_autocomplete_suggestions, classify_autocomplete_signal
from cue_youtube_pso_plugin.core.keyword_classifier import YouTubeKeywordClassifier, ClassifiedKeyword
from cue_youtube_pso_plugin.core.difficulty_scorer import YouTubeDifficultyScorer
from cue_youtube_pso_plugin.core.llm_writer import YouTubeLLMWriter
from cue_youtube_pso_plugin.core.competitor_scraper import CompetitorProfile, CompetitorVideo


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_rank_result():
    return KeywordRankResult(
        keyword="michigan politics",
        channel_id="UCtest123",
        channel_rank=3,
        top_results=[
            SearchResult(rank=1, video_id="v1", title="Michigan Politics Explained", channel_id="UCother1", channel_title="MI News", description="", published_at="", view_count=50000),
            SearchResult(rank=2, video_id="v2", title="Michigan Legislature Fight", channel_id="UCother2", channel_title="Lansing Report", description="", published_at="", view_count=30000),
            SearchResult(rank=3, video_id="v3", title="Michigan Politics Today", channel_id="UCtest123", channel_title="The MiddleGround Mic", description="", published_at="", view_count=8000),
        ],
    )

@pytest.fixture
def sample_competitor_profile():
    return CompetitorProfile(
        channel_id="UCother1",
        channel_title="MI News",
        subscriber_count=25000,
        video_count=150,
        top_videos=[
            CompetitorVideo(video_id="v1", title="Michigan Politics Exposed", description="", tags=["michigan politics", "lansing"], channel_id="UCother1", channel_title="MI News", view_count=50000, like_count=1200, published_at="2025-01-01"),
            CompetitorVideo(video_id="v2", title="Detroit Budget Fight 2025", description="", tags=["detroit", "michigan budget"], channel_id="UCother1", channel_title="MI News", view_count=35000, like_count=900, published_at="2025-02-01"),
        ]
    )


# ── Search Rank Tests ─────────────────────────────────────────────────────────

class TestYouTubeSearchRank:
    def test_not_configured_returns_error(self):
        rank = YouTubeSearchRank(api_key="")
        result = rank.search_keyword("michigan politics", "UCtest")
        assert result.error is not None
        assert "not configured" in result.error.lower()

    def test_is_configured_with_key(self):
        rank = YouTubeSearchRank(api_key="fake_key_123")
        assert rank.is_configured is True

    def test_quota_tracking(self):
        rank = YouTubeSearchRank(api_key="fake_key")
        assert rank.units_used == 0
        assert rank.units_remaining == 10000

    def test_rank_label_not_ranking(self):
        result = KeywordRankResult(keyword="test", channel_id="UC1", channel_rank=None)
        assert result.rank_label == "Not ranking"
        assert result.is_ranking is False

    def test_rank_label_ranking(self):
        result = KeywordRankResult(keyword="test", channel_id="UC1", channel_rank=5)
        assert result.rank_label == "#5"
        assert result.is_ranking is True

    @patch("cue_youtube_pso_plugin.core.search_rank.requests.get")
    def test_search_returns_rank_order(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "items": [
                {"id": {"videoId": "v1"}, "snippet": {"channelId": "UCother", "channelTitle": "Other", "title": "Other Video", "description": "", "publishedAt": ""}},
                {"id": {"videoId": "v2"}, "snippet": {"channelId": "UCtest", "channelTitle": "Mine", "title": "My Video", "description": "", "publishedAt": ""}},
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        rank = YouTubeSearchRank(api_key="fake_key")
        result = rank.search_keyword("michigan politics", "UCtest")
        assert result.channel_rank == 2
        assert len(result.top_results) == 2
        assert result.units_used == 100


# ── Autocomplete Tests ────────────────────────────────────────────────────────

class TestAutocomplete:
    def test_classify_detected_strong(self):
        suggestions = ["michigan politics 2025", "michigan politics explained", "michigan politics today"]
        signal = classify_autocomplete_signal("michigan politics", suggestions)
        assert signal["detected"] is True
        assert signal["position"] == 1
        assert signal["signal_strength"] == "STRONG"

    def test_classify_not_detected(self):
        suggestions = ["ohio politics", "illinois budget", "indiana governor"]
        signal = classify_autocomplete_signal("michigan politics", suggestions)
        assert signal["detected"] is False
        assert signal["signal_strength"] == "NONE"

    def test_classify_moderate_position(self):
        suggestions = ["ohio politics", "illinois budget", "indiana governor", "michigan politics today", "kentucky race"]
        signal = classify_autocomplete_signal("michigan politics", suggestions)
        assert signal["detected"] is True
        assert signal["position"] == 4
        assert signal["signal_strength"] == "MODERATE"


# ── Keyword Classifier Tests ──────────────────────────────────────────────────

class TestYouTubeKeywordClassifier:
    def setup_method(self):
        self.clf = YouTubeKeywordClassifier()

    def test_detected_takes_priority_over_local(self):
        result = self.clf.classify(
            "michigan politics",
            autocomplete_suggestions=["michigan politics 2025", "michigan politics explained"],
            competitor_terms={"michigan": 10},
        )
        assert result.classification == "DETECTED"

    def test_competitor_classification(self):
        result = self.clf.classify(
            "lansing budget fight",
            autocomplete_suggestions=None,
            competitor_terms={"lansing budget fight": 4},
        )
        assert result.classification == "COMPETITOR"

    def test_local_classification(self):
        result = self.clf.classify("detroit city council", autocomplete_suggestions=None, competitor_terms=None)
        assert result.classification == "LOCAL"

    def test_guest_classification(self):
        result = self.clf.classify("gretchen whitmer veto", autocomplete_suggestions=None, competitor_terms=None)
        assert result.classification == "GUEST"

    def test_dead_classification(self):
        result = self.clf.classify("podcast episode interview", autocomplete_suggestions=None, competitor_terms=None)
        assert result.classification == "DEAD"

    def test_sort_by_priority(self):
        keywords = [
            ClassifiedKeyword("dead_kw", "DEAD", "generic"),
            ClassifiedKeyword("local_kw", "LOCAL", "geo"),
            ClassifiedKeyword("detected_kw", "DETECTED", "autocomplete"),
            ClassifiedKeyword("competitor_kw", "COMPETITOR", "title"),
        ]
        sorted_kws = self.clf.sort_by_priority(keywords)
        assert sorted_kws[0].classification == "DETECTED"
        assert sorted_kws[-1].classification == "DEAD"

    def test_filter_dead(self):
        keywords = [
            ClassifiedKeyword("good_kw", "DETECTED", "autocomplete"),
            ClassifiedKeyword("dead_kw", "DEAD", "generic"),
        ]
        filtered = self.clf.filter_dead(keywords)
        assert len(filtered) == 1
        assert filtered[0].keyword == "good_kw"


# ── Difficulty Scorer Tests ───────────────────────────────────────────────────

class TestYouTubeDifficultyScorer:
    def setup_method(self):
        self.scorer = YouTubeDifficultyScorer()

    def test_score_returns_result(self, sample_rank_result):
        result = self.scorer.score(sample_rank_result)
        assert 0 <= result.difficulty <= 100
        assert 0 <= result.pso_score <= 100
        assert 0 <= result.demand_score <= 100
        assert result.difficulty_label in ("LOW", "MEDIUM", "HIGH")

    def test_high_autocomplete_position_increases_demand(self, sample_rank_result):
        result_with_ac = self.scorer.score(sample_rank_result, autocomplete_position=1)
        result_without_ac = self.scorer.score(sample_rank_result, autocomplete_position=None)
        assert result_with_ac.demand_score > result_without_ac.demand_score

    def test_batch_sorted_by_pso_score(self, sample_rank_result):
        low_result = KeywordRankResult(keyword="generic video", channel_id="UC1", channel_rank=None, top_results=[])
        results = self.scorer.score_batch([sample_rank_result, low_result])
        assert results[0].pso_score >= results[-1].pso_score

    def test_pso_score_formula(self, sample_rank_result):
        result = self.scorer.score(sample_rank_result, autocomplete_position=2)
        expected = int((result.demand_score * (100 - result.difficulty)) / 100)
        assert result.pso_score == expected

    def test_your_rank_label(self, sample_rank_result):
        result = self.scorer.score(sample_rank_result)
        assert result.rank_label == "#3"


# ── LLM Writer Tests ──────────────────────────────────────────────────────────

class TestYouTubeLLMWriter:
    def setup_method(self):
        self.writer = YouTubeLLMWriter(api_url="", api_key="")

    def test_fallback_when_not_configured(self):
        result = self.writer.generate_metadata(
            current_title="Michigan Budget 2025",
            current_description="We discuss the budget.",
            topic="michigan budget",
            detected_keywords=["michigan budget"],
            competitor_keywords=["lansing spending"],
            local_keywords=["michigan"],
            entity_keywords=["gretchen whitmer"],
        )
        assert "title" in result
        assert "description" in result
        assert "tags" in result
        assert "chapters" in result
        assert len(result["tags"]) > 0

    def test_fallback_title_under_60_chars(self):
        result = self.writer.generate_metadata(
            current_title="A Very Long Title That Goes On And On About Michigan Politics Today",
            current_description="",
            topic="michigan politics",
            detected_keywords=["michigan politics"],
            competitor_keywords=[],
            local_keywords=["michigan"],
            entity_keywords=[],
        )
        assert len(result["title"]) <= 60

    def test_fallback_tags_in_pso_order(self):
        result = self.writer.generate_metadata(
            current_title="Test",
            current_description="",
            topic="detroit budget",
            detected_keywords=["detroit budget"],
            competitor_keywords=["lansing spending"],
            local_keywords=["detroit"],
            entity_keywords=["mike duggan"],
        )
        tags = result["tags"]
        # Detected keyword should appear before competitor keyword
        if "detroit budget" in tags and "lansing spending" in tags:
            assert tags.index("detroit budget") < tags.index("lansing spending")

    def test_fallback_chapters_start_at_zero(self):
        result = self.writer.generate_metadata(
            current_title="Test",
            current_description="",
            topic="michigan election",
            detected_keywords=["michigan election"],
            competitor_keywords=[],
            local_keywords=[],
            entity_keywords=[],
        )
        chapters = result["chapters"]
        assert len(chapters) >= 1
        assert chapters[0]["timestamp"] == "00:00"

    @patch("cue_youtube_pso_plugin.core.llm_writer.requests.post")
    def test_llm_api_call_when_configured(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '{"title":"Michigan Budget Exposed","description":"Full desc","hook":"Hook text","chapters":[{"timestamp":"00:00","name":"The Budget"}],"tags":["michigan budget"],"safety_notes":[],"pso_notes":"PSO improved"}'}}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        writer = YouTubeLLMWriter(api_url="https://api.cue.test", api_key="test_key")
        result = writer.generate_metadata(
            current_title="Michigan Budget",
            current_description="",
            topic="michigan budget",
            detected_keywords=["michigan budget"],
            competitor_keywords=[],
            local_keywords=["michigan"],
            entity_keywords=[],
        )
        assert result["title"] == "Michigan Budget Exposed"
        assert result["chapters"][0]["timestamp"] == "00:00"
