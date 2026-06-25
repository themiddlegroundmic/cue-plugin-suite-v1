"""
tests/test_platform_plugin.py
==============================
Unit tests for the Cue Platform Intelligence Plugin.
Tests all three platform rule modules and the orchestrator.
Run with: python -m pytest cue_platform_plugin/tests/ -v
"""

import pytest
from cue_platform_plugin.facebook.rules import FacebookRules
from cue_platform_plugin.youtube.rules import YouTubeRules
from cue_platform_plugin.instagram.rules import InstagramRules
from cue_platform_plugin.shared.rules_base import PlatformRulesBase, ComplianceResult
from cue_platform_plugin.plugin import CuePlatformPlugin


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def plugin():
    return CuePlatformPlugin(niche="political commentary", geo="michigan")

@pytest.fixture
def fb():
    return FacebookRules(niche="political commentary", geo="michigan")

@pytest.fixture
def yt():
    return YouTubeRules(niche="political commentary", geo="michigan")

@pytest.fixture
def ig():
    return InstagramRules(niche="political commentary", geo="michigan")


# ── Base rules tests ──────────────────────────────────────────────────────────

class TestPlatformRulesBase:
    def test_political_safety_flag_rigged(self):
        base = PlatformRulesBase()
        issues = base.check_political_safety("The election was rigged by outside forces.")
        assert any("rigged" in i for i in issues)

    def test_political_safety_flag_fraud(self):
        base = PlatformRulesBase()
        issues = base.check_political_safety("This is clear fraud by the administration.")
        assert any("fraud" in i for i in issues)

    def test_political_safety_clean_text(self):
        base = PlatformRulesBase()
        issues = base.check_political_safety("The budget vote passed 6-3 according to records.")
        assert len(issues) == 0

    def test_engagement_bait_detection(self):
        base = PlatformRulesBase()
        found = base.check_engagement_bait("Comment below what you think about this!")
        assert "comment below" in found

    def test_engagement_bait_clean(self):
        base = PlatformRulesBase()
        found = base.check_engagement_bait("The vote was 6-3. Here is what it means.")
        assert len(found) == 0

    def test_eligibility_score_clean(self):
        base = PlatformRulesBase()
        score = base.score_eligibility("The budget vote passed 6-3 according to city records.")
        assert score >= 80

    def test_eligibility_score_with_flags(self):
        base = PlatformRulesBase()
        score = base.score_eligibility("This is rigged fraud and you should comment below.")
        assert score < 80


# ── Facebook rules tests ──────────────────────────────────────────────────────

class TestFacebookRules:
    def test_clean_post_passes(self, fb):
        text = (
            "The city council voted 6-3 to approve the transit budget. "
            "According to the meeting records, the $2.4M allocation goes to bus routes "
            "that serve Downriver communities. Here is what that means for riders."
        )
        result = fb.check(text, has_source=True)
        assert result.eligibility_score >= 60

    def test_engagement_bait_fails(self, fb):
        text = "Share if you agree that the council made the wrong call. Comment below!"
        result = fb.check(text)
        assert not result.passed
        assert len(result.engagement_bait_found) > 0

    def test_political_safety_flag_reduces_score(self, fb):
        text = "The election was rigged and this is clear fraud by the administration."
        result = fb.check(text)
        assert len(result.political_safety_issues) >= 2
        assert result.eligibility_score < 80

    def test_check_returns_compliance_result(self, fb):
        result = fb.check("Test post about Michigan politics.")
        assert isinstance(result, ComplianceResult)
        assert result.platform == "facebook"

    def test_post_formula_check_exists(self, fb):
        # Method should exist and return a list
        issues = fb.check_post_formula("Test post.")
        assert isinstance(issues, list)


# ── YouTube rules tests ───────────────────────────────────────────────────────

class TestYouTubeRules:
    def test_title_too_long(self, yt):
        long_title = "A" * 75
        issues = yt.check_title(long_title)
        assert any("70" in i or "characters" in i for i in issues)

    def test_title_dead_keyword(self, yt):
        issues = yt.check_title("Episode 42: Interview with the Mayor")
        assert any("dead" in i.lower() or "podcast" in i.lower() or "episode" in i.lower()
                   for i in issues)

    def test_title_clean(self, yt):
        issues = yt.check_title("The Budget Fight Detroit Voters Missed")
        assert len(issues) == 0

    def test_description_boilerplate_in_opening(self, yt):
        desc = "Subscribe to our channel! This week we talk about the budget vote..."
        issues = yt.check_description(desc)
        assert any("boilerplate" in i.lower() or "subscribe" in i.lower() for i in issues)

    def test_description_no_chapters(self, yt):
        desc = "This is a video about Michigan politics and the budget vote."
        issues = yt.check_description(desc)
        assert any("chapter" in i.lower() for i in issues)

    def test_description_with_chapters_passes(self, yt):
        desc = (
            "The budget vote passed 6-3. Here is what it means.\n\n"
            "00:00 The vote breakdown\n"
            "02:30 What the money funds\n"
            "05:00 What riders should know"
        )
        issues = yt.check_description(desc)
        assert not any("chapter" in i.lower() for i in issues)

    def test_hook_raw_intro_detected(self, yt):
        issues = yt.check_hook("Welcome back everyone! Today we have a special guest...")
        assert len(issues) > 0

    def test_hook_tension_first_passes(self, yt):
        issues = yt.check_hook(
            "The city just approved a $2.4M budget — and by the end of this video, "
            "you'll understand exactly who benefits and who pays."
        )
        assert len(issues) == 0

    def test_chapters_minimum_three(self, yt):
        issues = yt.check_chapters([("0:00", "Opening"), ("2:00", "Discussion")])
        assert any("minimum" in i.lower() or "3" in i for i in issues)

    def test_chapters_first_not_at_zero(self, yt):
        issues = yt.check_chapters([("0:30", "Opening"), ("2:00", "Middle"), ("5:00", "Close")])
        assert any("00:00" in i or "0:00" in i for i in issues)

    def test_chapters_generic_names_flagged(self, yt):
        issues = yt.check_chapters([
            ("0:00", "Introduction"),
            ("2:00", "Main Topic"),
            ("5:00", "Conclusion"),
        ])
        assert len(issues) > 0

    def test_check_returns_compliance_result(self, yt):
        result = yt.check("Test script about Michigan politics.")
        assert isinstance(result, ComplianceResult)
        assert result.platform == "youtube"


# ── Instagram rules tests ─────────────────────────────────────────────────────

class TestInstagramRules:
    def test_too_many_hashtags(self, ig):
        caption = "Michigan politics #politics #news #michigan #vote #democracy #election #usa #podcast"
        issues = ig.check_caption(caption)
        assert any("hashtag" in i.lower() for i in issues)

    def test_dead_hashtag_detected(self, ig):
        caption = "The vote passed. #politics #viral #trending"
        issues = ig.check_caption(caption)
        assert any("dead" in i.lower() for i in issues)

    def test_weak_first_line(self, ig):
        caption = "New post! Check this out about the budget vote."
        issues = ig.check_caption(caption)
        assert any("first line" in i.lower() or "weak" in i.lower() for i in issues)

    def test_no_local_stakes(self, ig):
        caption = "The budget vote passed. Here is what it means for transit riders."
        issues = ig.check_caption(caption)
        assert any("local" in i.lower() for i in issues)

    def test_caption_with_local_passes(self, ig):
        caption = (
            "The Detroit transit budget just passed 6-3 — "
            "here is what Michigan riders need to know. #michiganpolitics #detroitpolitics #independentmedia"
        )
        issues = ig.check_caption(caption)
        # Should not flag local stakes
        assert not any("local" in i.lower() for i in issues)

    def test_reel_raw_intro_flagged(self, ig):
        issues = ig.check_reels_script("Welcome back everyone! Today we're talking about...")
        assert len(issues) > 0

    def test_reel_watermark_flagged(self, ig):
        issues = ig.check_reels_script("This clip is from TikTok originally but here's the breakdown.")
        assert any("watermark" in i.lower() or "tiktok" in i.lower() for i in issues)

    def test_carousel_too_few_slides(self, ig):
        issues = ig.check_carousel(["Slide 1", "Slide 2"])
        assert any("minimum" in i.lower() or "3" in i for i in issues)

    def test_carousel_too_many_slides(self, ig):
        slides = [f"Slide {i}" for i in range(12)]
        issues = ig.check_carousel(slides)
        assert any("10" in i or "maximum" in i.lower() for i in issues)

    def test_check_returns_compliance_result(self, ig):
        result = ig.check("Test caption about Michigan politics.")
        assert isinstance(result, ComplianceResult)
        assert result.platform == "instagram"

    def test_recommend_surface_reels_for_video(self, ig):
        surface = ig.recommend_surface("short video clip", "reach new audience")
        assert surface.get("job") is not None


# ── Plugin orchestrator tests ─────────────────────────────────────────────────

class TestCuePlatformPlugin:
    def test_status_returns_dict(self, plugin):
        status = plugin.status()
        assert isinstance(status, dict)
        assert "facebook_rules" in status
        assert "youtube_rules" in status
        assert "instagram_rules" in status

    def test_rules_always_available(self, plugin):
        status = plugin.status()
        assert status["facebook_rules"] is True
        assert status["youtube_rules"] is True
        assert status["instagram_rules"] is True

    def test_check_facebook_post(self, plugin):
        result = plugin.check_facebook_post(
            "The city council voted 6-3. According to records, the budget funds bus routes."
        )
        assert isinstance(result, ComplianceResult)
        assert result.platform == "facebook"

    def test_check_youtube_content(self, plugin):
        result = plugin.check_youtube_content(
            "The budget vote passed.",
            title="The Detroit Budget Fight Nobody Explained",
            description="00:00 The vote\n02:00 What it funds\n05:00 What riders need to know",
        )
        assert isinstance(result, ComplianceResult)
        assert result.platform == "youtube"

    def test_check_instagram_content(self, plugin):
        result = plugin.check_instagram_content(
            "The Detroit transit budget passed 6-3. Here is what Michigan riders need to know. #michiganpolitics"
        )
        assert isinstance(result, ComplianceResult)
        assert result.platform == "instagram"

    def test_youtube_quota_status(self, plugin):
        quota = plugin.youtube_quota_status()
        assert "used" in quota
        assert "remaining" in quota
        assert quota["daily_limit"] == 10_000

    def test_recommend_instagram_surface(self, plugin):
        surface = plugin.recommend_instagram_surface("short video clip", "reach new audience")
        assert isinstance(surface, dict)

    def test_generate_instagram_hashtag_set(self, plugin):
        tags = plugin.generate_instagram_hashtag_set("transit budget vote")
        assert isinstance(tags, list)
        assert len(tags) <= 5
