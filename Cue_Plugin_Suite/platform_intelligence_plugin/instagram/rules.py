"""
instagram/rules.py
==================
Instagram compliance module built from the Master Instagram Guide.
Encodes the 12 Laws, Six Surfaces, Instagram SEO (Chapter 8),
Sendability Test, Reels formula, Carousel structure, and
Caption/Hashtag doctrine.

Source: Master Instagram Guide — The MiddleGround Mic (June 24, 2026)
Derived from Meta/Instagram public guidance, platform algorithm notes,
and production rules. Not scraped from Instagram's systems.
"""

import re
from typing import List, Dict, Optional
from ..shared.rules_base import PlatformRulesBase, ComplianceResult


# ── Instagram-specific constants ─────────────────────────────────────────────

# The 12 Laws (Chapter 1)
INSTAGRAM_12_LAWS = [
    "Eligibility beats optimization. A risky, misleading, low-quality, or unoriginal post cannot be rescued by a better hashtag set.",
    "Instagram is not one algorithm. Feed, Reels, Stories, Explore, Search, and comments each rank differently. Package for the surface.",
    "Sends are the growth currency. Ask whether someone would DM this to a friend before posting.",
    "Watch time is the first test. Reels must earn the first 3 seconds, then the next 10, then the completion.",
    "Originality is the product. The clip, screenshot, or headline is evidence. Your framing is the content.",
    "Topic clarity beats variety. Random posts confuse the interest graph.",
    "Keywords beat hashtag stuffing. Use natural search terms in profile, first line, caption, on-screen text, alt text, and spoken audio.",
    "Carousels are save machines. Use them for timelines, receipt breakdowns, lists, and explainers people want to return to.",
    "Stories deepen relationships. Stories are for current followers, DMs, polls, questions, behind-the-scenes, and loyalty.",
    "Politics needs claim discipline. Separate proven fact, attribution, visible pattern, and opinion.",
    "No platform watermarks. Upload clean versions made for Instagram.",
    "Review ratios, not vibes. Watch time, sends per reach, saves, profile actions, and follower conversion matter more than emotional reaction.",
]

# Six Instagram surfaces and their jobs (Chapter 3)
INSTAGRAM_SURFACES = {
    "reels": {
        "job": "Discovery and entertainment",
        "use": "Short political arguments, receipt-first reactions, clip analysis, trial hooks, shareable hot takes",
        "aspect_ratio": "9:16",
        "spec": "1080×1920px",
    },
    "feed": {
        "job": "Relationship plus recommendations",
        "use": "Strong single-image statements, quote cards, short arguments, audience identity posts",
        "aspect_ratio": "4:5 (recommended) or 1:1",
        "spec": "1080×1350px or 1080×1080px",
    },
    "carousel": {
        "job": "Saves, swipes, and explainers",
        "use": "Timelines, election receipts, money trails, 'who benefits' breakdowns, court/policy explainers",
        "aspect_ratio": "1:1 or 4:5",
        "spec": "1080×1080px or 1080×1350px",
    },
    "stories": {
        "job": "Existing follower relationship",
        "use": "Polls, questions, behind-the-scenes, source notes, daily process, guest teases, DM prompts",
        "aspect_ratio": "9:16",
        "spec": "1080×1920px",
    },
    "explore": {
        "job": "Cold discovery from interest behavior",
        "use": "Visually clear posts with fast recognition: politics, Michigan, elections, institutional accountability",
        "note": "Explore pulls from Feed and Reels — no separate posting surface",
    },
    "search": {
        "job": "Intent-based discovery",
        "use": "Keyword-rich profile, captions, on-screen text, alt text, spoken audio, city/state names, candidate names, issue words",
        "note": "Optimized via caption and profile keywords — not a separate posting surface",
    },
}

# Instagram SEO keyword placement hierarchy (Chapter 8)
SEO_PLACEMENT_HIERARCHY = [
    "Username and display name (highest weight)",
    "Bio (high weight)",
    "First line of caption (high weight — shown in feed before 'more')",
    "On-screen text in Reels (indexed by audio/text recognition)",
    "Alt text on images (set manually — not auto-generated)",
    "Spoken audio in Reels (indexed via speech recognition)",
    "Hashtags (lower weight than keywords — use 3–5 specific ones)",
    "Caption body (medium weight)",
]

# Hashtag doctrine (Chapter 15) — keywords beat hashtag stuffing
HASHTAG_DOCTRINE = {
    "max_hashtags": 5,
    "type": "Specific niche terms only — not generic (#politics, #news, #michigan)",
    "placement": "End of caption or first comment — not inline with text",
    "dead_hashtags": [
        "#politics", "#news", "#podcast", "#interview", "#michigan",
        "#election", "#vote", "#democracy", "#america", "#usa",
        "#follow", "#like", "#share", "#viral", "#trending",
    ],
    "good_hashtag_examples": [
        "#michiganpolitics", "#downrivermichigan", "#michiganlgbt",
        "#michiganelection2026", "#detroitpolitics", "#lansing",
        "#independentmedia", "#politicalcommentary", "#voterguide",
    ],
}

# Reels formula (Chapter 12)
REELS_FORMULA = {
    "seconds_0_3": "Hook — instant tension, conflict, contradiction, or cost. Sound-off readable.",
    "seconds_3_10": "Proof — the receipt, document, quote, or clip that backs the hook.",
    "seconds_10_30": "Analysis — your original framing of what it means.",
    "close": "Payoff or open loop — strong conclusion or question. No subscribe demand.",
    "rules": [
        "No platform watermarks from TikTok or YouTube Shorts.",
        "Captions/subtitles on — most Reels are watched without sound.",
        "Hook must work with sound off — on-screen text carries the argument.",
        "No blurry, bordered, or visibly recycled video.",
    ],
}

# Carousel structure (Chapter 13)
CAROUSEL_STRUCTURE = {
    "slide_1": "Hook card — the strongest claim or question. Must earn the swipe.",
    "slides_2_to_n_minus_1": "Evidence cards — receipts, timeline, data, quotes, maps.",
    "last_slide": "Conclusion or save prompt — 'Save this for November' or 'Share with someone who needs to see this'.",
    "rules": [
        "Each slide should have one idea — not a wall of text.",
        "Use consistent visual style across all slides.",
        "Slide count: 3–10 slides. Under 3 is a Feed post. Over 10 loses saves.",
        "Alt text on each slide for accessibility and SEO.",
    ],
}

# Sendability test (Chapter 6)
SENDABILITY_TEST = [
    "Would someone DM this to a friend and say 'This is what I meant'?",
    "Does it explain something the viewer feels but cannot articulate?",
    "Does it reveal a power move, double standard, hidden cost, or institutional pattern?",
    "Can someone understand the stakes with the sound off?",
    "Is the central claim safe if a critic reads it word-for-word?",
]

# Caption formula (Chapter 10)
CAPTION_FORMULA = {
    "first_line": "Hook — the one thing that makes the viewer stop scrolling. Shown before 'more'.",
    "body": "Evidence + original analysis. The receipt and your framing of it.",
    "local_stakes": "Tie to Michigan voters, money, institutions, or community impact.",
    "close": "One question or one clear conclusion. No engagement bait.",
    "keywords": "Use natural search terms in the first line and body — not just hashtags.",
}

# Image specs (Chapter 16)
IMAGE_SPECS = {
    "feed_portrait": "1080×1350px (4:5) — recommended for Feed",
    "feed_square": "1080×1080px (1:1)",
    "reel": "1080×1920px (9:16)",
    "story": "1080×1920px (9:16)",
    "carousel_card": "1080×1080px (1:1) or 1080×1350px (4:5)",
    "safe_zone": "Keep text and faces within center 80% — edges may be cropped in Feed",
}


class InstagramRules(PlatformRulesBase):
    """
    Instagram compliance checker built from the Master Instagram Guide.
    """

    PLATFORM_NAME = "instagram"

    def check_sendability(self, text: str) -> List[str]:
        """
        Run the sendability test from Chapter 6.
        Returns list of failed sendability checks.
        """
        issues = []

        # Check for power move / contradiction / receipt signals
        send_signals = [
            "but", "except", "despite", "while", "yet", "however",
            "the record shows", "according to", "the document",
            "the filing", "the vote", "the money", "the cost",
        ]
        has_send_value = any(sig in text.lower() for sig in send_signals)
        if not has_send_value:
            issues.append(
                "Low sendability — no contradiction, receipt, or power move detected. "
                "Ask: would someone DM this to a friend? If not, the idea may be weak (Law 3)."
            )

        # Check sound-off readability (for Reels/video captions)
        # If caption is very short with no on-screen text indicator, flag it
        if len(text) < 20:
            issues.append(
                "Caption is very short. For Reels, ensure on-screen text carries the argument "
                "for viewers watching without sound."
            )

        return issues

    def check_caption(self, caption: str) -> List[str]:
        """
        Check a caption against the caption formula and SEO rules from Chapters 10 and 15.
        """
        issues = []
        lines = caption.strip().split("\n")
        first_line = lines[0] if lines else ""

        # First line should not be a generic opener
        generic_openers = [
            "new post", "check this out", "so i was thinking", "just wanted to share",
            "hey everyone", "good morning", "happy",
        ]
        for opener in generic_openers:
            if first_line.lower().startswith(opener):
                issues.append(
                    f'Weak first line: "{first_line[:40]}...". '
                    "The first line is shown in the feed before 'more' — "
                    "lead with the conflict, cost, or receipt (Law 3, Caption Formula)."
                )
                break

        # Check hashtag count
        hashtags = re.findall(r"#\w+", caption)
        if len(hashtags) > HASHTAG_DOCTRINE["max_hashtags"]:
            issues.append(
                f"{len(hashtags)} hashtags detected — maximum is {HASHTAG_DOCTRINE['max_hashtags']}. "
                "Keywords in the caption body outperform hashtag stuffing (Law 7)."
            )

        # Check for dead hashtags
        caption_lower = caption.lower()
        for dead_tag in HASHTAG_DOCTRINE["dead_hashtags"]:
            if dead_tag.lower() in caption_lower:
                issues.append(
                    f'Dead hashtag detected: "{dead_tag}". '
                    "Replace with a specific niche term — generic hashtags have no search value."
                )

        # Check for local stakes
        local_signals = [
            "michigan", "detroit", "lansing", "downriver", "voters",
            "taxpayers", "residents", "community", "district", "county",
            "grand rapids", "flint", "ann arbor",
        ]
        has_local = any(sig in caption_lower for sig in local_signals)
        if not has_local:
            issues.append(
                "No local stakes detected. Tie the national story to Michigan voters, "
                "money, institutions, or community impact."
            )

        return issues

    def check_reels_script(self, script: str) -> List[str]:
        """
        Check a Reels script against the Reels formula from Chapter 12.
        """
        issues = []
        lines = script.strip().split("\n")
        first_line = lines[0] if lines else ""

        # Check for instant tension
        tension_signals = ["?", ":", "—", "but", "except", "until", "despite", "while", "yet"]
        has_tension = any(sig in first_line for sig in tension_signals)
        if not has_tension:
            issues.append(
                "Reels first line lacks instant tension. "
                "Name the conflict, contradiction, or cost immediately — "
                "the first 3 seconds decide whether the viewer stays (Law 4)."
            )

        # Check for watermark mentions
        watermark_signals = ["tiktok", "youtube shorts", "@tiktok", "yt shorts"]
        script_lower = script.lower()
        for sig in watermark_signals:
            if sig in script_lower:
                issues.append(
                    f'Platform watermark reference detected: "{sig}". '
                    "Upload clean versions made for Instagram — no TikTok or YouTube Shorts watermarks (Law 11)."
                )

        # Check for subscribe/follow CTA
        cta_signals = ["follow me", "hit follow", "subscribe", "turn on notifications"]
        for sig in cta_signals:
            if sig in script_lower:
                issues.append(
                    f'Subscribe/follow CTA detected: "{sig}". '
                    "End with a conclusion or open loop — not a follow demand. "
                    "Recommendation eligibility is reduced by explicit follow CTAs."
                )
                break

        return issues

    def check_carousel(self, slides: List[str]) -> List[str]:
        """
        Check a carousel slide list against the carousel structure from Chapter 13.
        """
        issues = []

        if len(slides) < 3:
            issues.append(
                f"Only {len(slides)} slide(s) — minimum 3 for a carousel. "
                "Under 3 slides should be a Feed post instead."
            )
        if len(slides) > 10:
            issues.append(
                f"{len(slides)} slides detected — maximum 10. "
                "Over 10 slides reduces save rate."
            )

        if slides:
            # First slide should be a hook
            first_slide = slides[0]
            if len(first_slide) > 150:
                issues.append(
                    "First slide has too much text — it should be a hook card with one strong claim or question."
                )

        return issues

    def check(self, text: str, surface: str = "feed",
              is_reel: bool = False, slides: Optional[List[str]] = None) -> ComplianceResult:
        """
        Full Instagram compliance check.
        """
        base = super().check(text)

        caption_issues = self.check_caption(text)
        send_issues = self.check_sendability(text)
        reel_issues = self.check_reels_script(text) if is_reel else []
        carousel_issues = self.check_carousel(slides) if slides else []

        all_flags = base.flags + caption_issues + send_issues + reel_issues + carousel_issues

        eligibility = base.eligibility_score
        eligibility -= len(caption_issues) * 5
        eligibility -= len(send_issues) * 6
        eligibility -= len(reel_issues) * 7
        eligibility -= len(carousel_issues) * 4
        eligibility = max(0, min(100, eligibility))

        suggestions = []
        if eligibility < 60:
            suggestions.append(
                "Eligibility score below 60. Fix political safety and caption issues first — "
                "a risky post cannot be rescued by better hashtags (Law 1)."
            )

        return ComplianceResult(
            platform=self.PLATFORM_NAME,
            passed=eligibility >= 60 and len(base.political_safety_issues) == 0,
            eligibility_score=eligibility,
            flags=all_flags,
            warnings=base.warnings,
            suggestions=suggestions,
            political_safety_issues=base.political_safety_issues,
            engagement_bait_found=base.engagement_bait_found,
        )

    def recommend_surface(self, content_type: str, goal: str) -> Dict[str, str]:
        """
        Recommend the right Instagram surface for a given content type and goal.
        """
        content_lower = content_type.lower()
        goal_lower = goal.lower()

        if "clip" in content_lower or "video" in content_lower or "short" in content_lower:
            return INSTAGRAM_SURFACES["reels"]
        if "timeline" in content_lower or "breakdown" in content_lower or "explainer" in content_lower:
            return INSTAGRAM_SURFACES["carousel"]
        if "poll" in content_lower or "question" in content_lower or "behind" in content_lower:
            return INSTAGRAM_SURFACES["stories"]
        if "discovery" in goal_lower or "reach" in goal_lower or "new audience" in goal_lower:
            return INSTAGRAM_SURFACES["reels"]
        if "save" in goal_lower or "reference" in goal_lower:
            return INSTAGRAM_SURFACES["carousel"]
        if "relationship" in goal_lower or "followers" in goal_lower:
            return INSTAGRAM_SURFACES["stories"]

        return INSTAGRAM_SURFACES["feed"]
