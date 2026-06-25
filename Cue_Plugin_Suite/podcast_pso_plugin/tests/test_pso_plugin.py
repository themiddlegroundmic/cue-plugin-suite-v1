"""
test_pso_plugin.py
==================
Unit tests for the Cue PSO Plugin modules.
Run with: python -m pytest tests/ -v
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core.feed_parser import FeedParser, Episode, _parse_duration, _parse_date, _check_safety
from core.keyword_classifier import KeywordClassifier, DEAD_TAGS
from core.difficulty_scorer import (
    calculate_difficulty, difficulty_label, score_episode, assign_priority, DifficultyScorer
)
from core.llm_writer import LLMWriter, build_user_prompt


# ── FeedParser unit tests ────────────────────────────────────────────────────

class TestFeedParser:
    def test_parse_duration_hms(self):
        assert _parse_duration("01:23:45") == 5025

    def test_parse_duration_ms(self):
        assert _parse_duration("45:30") == 2730

    def test_parse_duration_seconds(self):
        assert _parse_duration("3600") == 3600

    def test_parse_duration_empty(self):
        assert _parse_duration("") == 0

    def test_parse_date_valid(self):
        d = _parse_date("Mon, 01 Jan 2024 12:00:00 +0000")
        assert d is not None
        assert d.year == 2024

    def test_parse_date_invalid(self):
        assert _parse_date("not a date") is None

    def test_safety_check_detects_flags(self):
        flags = _check_safety("The election was rigged and it was fraud")
        assert "rigged" in flags
        assert "fraud" in flags

    def test_safety_check_clean(self):
        flags = _check_safety("Michigan politics discussion about redistricting")
        assert flags == []


# ── KeywordClassifier unit tests ─────────────────────────────────────────────

class TestKeywordClassifier:
    def setup_method(self):
        self.classifier = KeywordClassifier(
            detected_terms=["michigan politics", "iran nuclear deal"],
            competitor_terms={"political commentary": 8, "michigan redistricting": 5},
            episode_text="michigan politics iran nuclear deal discussion",
            guest_names=["John Smith"],
            show_brand="the middleground mic",
        )

    def test_dead_tag_classification(self):
        assert KeywordClassifier.is_dead_tag("podcast") is True
        assert KeywordClassifier.is_dead_tag("episode") is True
        assert KeywordClassifier.is_dead_tag("michigan politics") is False

    def test_detected_classification(self):
        result = self.classifier.classify()
        assert "michigan politics" in result["detected"]
        assert "iran nuclear deal" in result["detected"]

    def test_local_classification(self):
        c = KeywordClassifier(
            detected_terms=["michigan politics"],
            competitor_terms={},
            episode_text="michigan politics",
        )
        result = c.classify()
        # michigan politics contains "michigan" which is a local signal
        assert "michigan politics" in result["local"] or "michigan politics" in result["detected"]

    def test_pso_tag_set_excludes_dead(self):
        tags = self.classifier.build_pso_tag_set()
        for tag in tags:
            assert tag not in DEAD_TAGS

    def test_pso_tag_set_max_length(self):
        tags = self.classifier.build_pso_tag_set(max_tags=8)
        assert len(tags) <= 8


# ── DifficultyScorer unit tests ──────────────────────────────────────────────

class TestDifficultyScorer:
    def test_difficulty_low(self):
        score = calculate_difficulty(2, 20, 180)
        assert score < 40

    def test_difficulty_high(self):
        score = calculate_difficulty(10, 300, 3)
        assert score >= 60

    def test_difficulty_label_easy(self):
        assert difficulty_label(20) == "Easy"

    def test_difficulty_label_medium(self):
        assert difficulty_label(55) == "Medium"

    def test_difficulty_label_hard(self):
        assert difficulty_label(80) == "Hard"

    def test_score_episode_boilerplate_penalty(self):
        ep = Episode(
            guid="test-1",
            title="Michigan Politics Today",
            description="Send us Fan Mail! Support the show on BuyMeACoffee. Today we discuss...",
            tags=["michigan", "politics"],
            pub_date=None,
            duration_seconds=3600,
            episode_number=1,
            season_number=None,
            audio_url="",
            link="",
        )
        score = score_episode(ep)
        assert score < 80  # boilerplate penalty applied

    def test_score_episode_clean(self):
        ep = Episode(
            guid="test-2",
            title="Michigan Redistricting 2025: What It Means for Voters",
            description=(
                "Michigan redistricting is reshaping the state's political map. "
                "We break down the latest court rulings, what they mean for 2026 elections, "
                "and how Michigan voters can track changes in their districts. "
                "(00:00) Introduction (05:00) Court ruling breakdown (18:00) Voter impact"
            ),
            tags=["michigan redistricting", "michigan politics", "2026 election"],
            pub_date=None,
            duration_seconds=3600,
            episode_number=5,
            season_number=None,
            audio_url="",
            link="",
        )
        score = score_episode(ep)
        assert score >= 75

    def test_priority_assignment_p1(self):
        assert assign_priority(40, [], False) == "P1"
        assert assign_priority(70, ["rigged"], False) == "P1"

    def test_priority_assignment_p2(self):
        assert assign_priority(65, [], False) == "P2"

    def test_priority_assignment_p3(self):
        assert assign_priority(85, [], False) == "P3"


# ── LLMWriter unit tests ─────────────────────────────────────────────────────

class TestLLMWriter:
    def test_prompt_contains_episode_title(self):
        ep = Episode(
            guid="test-3",
            title="Iran Nuclear Deal Update",
            description="Today we discuss the latest Iran nuclear negotiations.",
            tags=["iran", "nuclear"],
            pub_date=None,
            duration_seconds=2700,
            episode_number=10,
            season_number=None,
            audio_url="",
            link="",
        )
        prompt = build_user_prompt(
            episode=ep,
            detected_keywords=["iran nuclear deal"],
            factual_keywords=["nuclear nonproliferation"],
            local_keywords=["michigan"],
            guest_names=[],
            show_brand="The MiddleGround Mic",
            competitor_terms=["iran podcast", "middle east politics"],
        )
        assert "Iran Nuclear Deal Update" in prompt
        assert "iran nuclear deal" in prompt
        assert "The MiddleGround Mic" in prompt

    def test_from_env_raises_without_vars(self):
        import os
        # Temporarily remove env vars
        old_url = os.environ.pop("BUILT_IN_FORGE_API_URL", None)
        old_key = os.environ.pop("BUILT_IN_FORGE_API_KEY", None)
        with pytest.raises(EnvironmentError):
            LLMWriter.from_env()
        # Restore
        if old_url:
            os.environ["BUILT_IN_FORGE_API_URL"] = old_url
        if old_key:
            os.environ["BUILT_IN_FORGE_API_KEY"] = old_key

    @patch("requests.Session.post")
    def test_write_metadata_returns_dict(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": '{"title": "Iran Nuclear Deal 2025", "description_opening": "Iran nuclear deal talks resumed...", "tags": ["iran nuclear deal", "michigan politics"], "chapters": [{"time": "00:00", "name": "Intro"}], "safety_rewrites": {}, "reasoning": "Primary keyword is iran nuclear deal."}'
                }
            }]
        }
        mock_post.return_value = mock_response

        writer = LLMWriter(api_url="https://fake.cue.api", api_key="fake-key")
        ep = Episode(
            guid="test-4",
            title="Iran Situation",
            description="Iran is in the news again.",
            tags=[],
            pub_date=None,
            duration_seconds=1800,
            episode_number=3,
            season_number=None,
            audio_url="",
            link="",
        )
        result = writer.write_metadata(
            episode=ep,
            detected_keywords=["iran nuclear deal"],
            factual_keywords=["nuclear"],
            local_keywords=[],
            guest_names=[],
            show_brand="The MiddleGround Mic",
            competitor_terms=[],
        )
        assert result is not None
        assert result["title"] == "Iran Nuclear Deal 2025"
        assert len(result["tags"]) > 0
