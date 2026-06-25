"""
youtube/rules.py
================
YouTube compliance module built from the Master YouTube Guide.
Encodes the Three-Layer Video Test, Title Rules, Hook Formula,
Retention Structure, Metadata Order, and Chapter Rules.

Source: Master YouTube Guide — The MiddleGround Mic (June 23, 2026)
Derived from YouTube official help/creator documentation, analytics
transcripts, and production rules. Not scraped from YouTube's systems.
"""

import re
from typing import List, Dict, Optional, Tuple
from ..shared.rules_base import PlatformRulesBase, ComplianceResult


# ── YouTube-specific constants ───────────────────────────────────────────────

# Non-negotiable rules (Chapter 1)
YOUTUBE_NON_NEGOTIABLE_RULES = [
    "No raw intro — do not open with greetings, logo-first pacing, housekeeping, or guest background.",
    "Tension first — name the conflict, contradiction, cost, claim, or document immediately.",
    "Payoff promise — within the first 10 seconds, tell the viewer what they will understand by the end.",
    "One idea — one video should answer one core question.",
    "Pattern interrupt — change visual or informational mode every 20–35 seconds in long-form cuts.",
    "Receipts on screen — use documents, maps, headlines, filings, charts, and quotes that match the claim.",
    "Payoff before CTA — deliver the promised understanding before asking for the next action.",
]

# Strong title shapes (Chapter 5)
STRONG_TITLE_SHAPES = [
    "The [Money/Map/Document] Fight Nobody Explained",
    "Why [Race/Issue] Was Decided Before November",
    "The AI Money Behind This Primary",
    "What [Candidate/Institution] Wants Voters to Miss",
    "This Local Tax Fight Is Bigger Than Buses",
]

# Dead podcast keywords that should NOT be used as YouTube titles (Chapter 5)
DEAD_PODCAST_KEYWORDS_AS_TITLES = [
    "episode",
    "ep.",
    "podcast",
    "show",
    "interview with",
    "talking with",
    "conversation with",
    "chat with",
    "sits down with",
    "joins us",
]

# Hook formula (Chapter 6): Promise + Proof + Path
HOOK_FORMULA = {
    "promise": "What the viewer will understand by the end",
    "proof": "Why this video can deliver it (the receipt, document, or credential)",
    "path": "How the video will get there (the argument structure in one sentence)",
}

# Retention structure for long-form (Chapter 7)
RETENTION_STRUCTURE = {
    "seconds_0_30": "Hook — tension, promise, proof, path",
    "minutes_1_3": "First proof segment — strongest receipt or document",
    "minutes_3_5": "Complication — what makes this harder than it looks",
    "minutes_5_7": "Analysis — original framing of what the evidence means",
    "close": "Payoff — deliver the promised understanding, then CTA",
    "pattern_interrupt_interval": "Every 20–35 seconds: cut, graphic, quote card, or new question",
}

# Seven-minute political cut rules (Chapter 8)
SEVEN_MINUTE_CUT_RULES = [
    "Remove the waiting room — no intro music, logo hold, or guest bio.",
    "Start with the strongest moment from the full episode.",
    "Keep only the proof ladder — claim, receipt, implication.",
    "Cut any segment where the host or guest restates what was just said.",
    "End before the conversation winds down — cut on a strong conclusion.",
]

# Metadata order (Chapter 17)
METADATA_ORDER = {
    "title": "Searchable subject first, conflict second, under 70 characters",
    "description_first_150": "Answer the search query in the first 150 characters — no boilerplate",
    "description_body": "Timestamps, key claims, sources, guest info, links",
    "description_close": "Subscribe CTA, social links, show links — after all content",
    "tags": "Specific topic terms first, guest name, location, then show name last",
    "chapters": "First chapter at 00:00, minimum 3 chapters, specific names not generic labels",
}

# Chapter rules (Chapter 17)
CHAPTER_RULES = [
    "First chapter must be at 00:00.",
    "Minimum 3 chapters.",
    "Chapter names must be specific — not 'Introduction' or 'Main Topic'.",
    "Chapter names should be searchable — use the actual claim or subject.",
    "Each chapter should represent a distinct argument segment, not a time block.",
]

# Thumbnail rules (Chapter 5)
THUMBNAIL_RULES = [
    "One face or one object of authority.",
    "One emotion.",
    "One readable text phrase.",
    "No clutter.",
    "No fake documents.",
    "No claim the video does not prove.",
]

# Three-Layer Video Test failure patterns (Chapter 4)
THREE_LAYER_FAILURES = {
    "high_ctr_low_retention": "Package worked but video did not deliver fast enough — fix opening and segment structure.",
    "low_ctr_good_retention": "Video works for those who click but package is unclear — improve title and thumbnail.",
    "good_hook_middle_drop": "Hook is strong but body lacks movement — add proof segments and visual pattern interrupts.",
    "good_video_low_impressions": "Topic may be narrow or audience signal not built yet — build clusters around the same viewer.",
}

# Shorts formula (Chapter 9)
SHORTS_FORMULA = {
    "structure": "One receipt + one open loop + one payoff",
    "rule": "A Short is not a random clip. It is a single argument compressed.",
    "angle_bank": [
        "The one line from the episode that changes the whole argument",
        "The receipt nobody showed you",
        "The question the guest answered that nobody asked",
        "The local number that makes the national story real",
        "The contradiction in the official statement",
    ],
}


class YouTubeRules(PlatformRulesBase):
    """
    YouTube compliance checker built from the Master YouTube Guide.
    """

    PLATFORM_NAME = "youtube"

    def check_title(self, title: str) -> List[str]:
        """
        Check a YouTube title against the title rules from Chapter 5.
        """
        issues = []

        # Length check
        if len(title) > 70:
            issues.append(
                f"Title is {len(title)} characters — keep under 70 for full display in search results."
            )

        # Dead podcast keywords
        title_lower = title.lower()
        for dead_kw in DEAD_PODCAST_KEYWORDS_AS_TITLES:
            if dead_kw in title_lower:
                issues.append(
                    f'Dead podcast keyword in title: "{dead_kw}". '
                    "YouTube titles should use viewer-search language, not podcast metadata terms."
                )

        # Check if subject comes first
        if title_lower.startswith(("the ", "a ", "an ")):
            # Acceptable — article-led titles are fine
            pass
        elif title_lower.startswith(("ep", "episode", "#")):
            issues.append(
                "Title starts with episode number — put the searchable subject first."
            )

        # Check for clickbait without substance signals
        clickbait_patterns = [
            r"\byou won'?t believe\b",
            r"\bshocking\b",
            r"\bblew my mind\b",
            r"\bcrazy\b",
            r"\binsane\b",
        ]
        for pattern in clickbait_patterns:
            if re.search(pattern, title_lower):
                issues.append(
                    f"Clickbait language detected in title. "
                    "YouTube warns that high clicks with low retention can hurt recommendation potential."
                )
                break

        return issues

    def check_description(self, description: str) -> List[str]:
        """
        Check a YouTube description against the metadata order from Chapter 17.
        """
        issues = []

        # First 150 characters check
        first_150 = description[:150]
        boilerplate_signals = [
            "subscribe", "follow us", "support the show", "buy me a coffee",
            "fan mail", "buzzsprout", "bmc", "patreon", "merch",
        ]
        for sig in boilerplate_signals:
            if sig in first_150.lower():
                issues.append(
                    f'Boilerplate detected in first 150 characters: "{sig}". '
                    "The first 150 characters are indexed by YouTube search — "
                    "move all boilerplate after the episode content."
                )
                break

        # Check for chapters
        chapter_pattern = r"\d{1,2}:\d{2}"
        has_chapters = bool(re.search(chapter_pattern, description))
        if not has_chapters:
            issues.append(
                "No chapter timestamps detected in description. "
                "Add at least 3 chapters starting with 00:00 — "
                "chapters improve search indexing and viewer navigation."
            )
        else:
            # Check that first chapter is at 00:00
            if "0:00" not in description and "00:00" not in description:
                issues.append(
                    "Chapters detected but first chapter is not at 00:00. "
                    "YouTube requires the first chapter to start at 00:00."
                )

        return issues

    def check_hook(self, script_opening: str, max_seconds: int = 30) -> List[str]:
        """
        Check the opening of a video script against the hook formula from Chapter 6.
        """
        issues = []
        text_lower = script_opening.lower()

        # Check for raw intro violations
        raw_intro_signals = [
            "welcome back", "hey everyone", "what's up", "good morning",
            "thanks for joining", "before we get started", "make sure you subscribe",
            "don't forget to like", "today we have", "my guest today",
        ]
        for sig in raw_intro_signals:
            if sig in text_lower:
                issues.append(
                    f'Raw intro detected: "{sig}". '
                    "Do not open with greetings, housekeeping, or guest background. "
                    "Start with tension — the conflict, contradiction, cost, or document."
                )
                break

        # Check for promise (payoff statement)
        promise_signals = [
            "by the end", "you'll understand", "i'm going to show", "here's what",
            "this video", "today i'll", "we're going to",
        ]
        has_promise = any(sig in text_lower for sig in promise_signals)
        if not has_promise:
            issues.append(
                "No payoff promise detected in opening. "
                "Within the first 10 seconds, tell the viewer what they will understand by the end."
            )

        return issues

    def check_chapters(self, chapters: List[Tuple[str, str]]) -> List[str]:
        """
        Check a list of (timestamp, chapter_name) tuples against chapter rules.
        """
        issues = []

        if len(chapters) < 3:
            issues.append(
                f"Only {len(chapters)} chapter(s) detected — minimum 3 required."
            )

        if chapters:
            first_ts = chapters[0][0]
            if first_ts not in ("0:00", "00:00"):
                issues.append(
                    f"First chapter timestamp is '{first_ts}' — must be 00:00."
                )

        # Check for generic chapter names
        generic_names = [
            "introduction", "intro", "main topic", "discussion", "conclusion",
            "outro", "closing", "beginning", "start", "end",
        ]
        for ts, name in chapters:
            if name.lower().strip() in generic_names:
                issues.append(
                    f'Generic chapter name: "{name}" at {ts}. '
                    "Use the actual claim or subject — chapter names are indexed by YouTube search."
                )

        return issues

    def check(self, text: str, title: str = "", description: str = "",
              chapters: Optional[List[Tuple[str, str]]] = None) -> ComplianceResult:
        """
        Full YouTube compliance check.
        """
        base = super().check(text)

        title_issues = self.check_title(title) if title else []
        desc_issues = self.check_description(description) if description else []
        hook_issues = self.check_hook(text[:500]) if text else []
        chapter_issues = self.check_chapters(chapters) if chapters else []

        all_flags = base.flags + title_issues + desc_issues + hook_issues + chapter_issues

        eligibility = base.eligibility_score
        eligibility -= len(title_issues) * 6
        eligibility -= len(desc_issues) * 5
        eligibility -= len(hook_issues) * 8
        eligibility -= len(chapter_issues) * 3
        eligibility = max(0, min(100, eligibility))

        suggestions = []
        if eligibility < 60:
            suggestions.append(
                "Eligibility score below 60. Fix hook and title issues first — "
                "these directly affect click-through rate and retention."
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

    def generate_metadata_template(self, topic: str, guest: str = "",
                                    local_angle: str = "") -> Dict[str, str]:
        """
        Generate a YouTube metadata template for a given topic.
        """
        local_note = local_angle or "Michigan"
        guest_note = f" with {guest}" if guest else ""

        return {
            "title": f"[Conflict/Subject in {topic}] — under 70 characters",
            "description_first_150": (
                f"[Answer the search query about {topic}{guest_note} in {local_note} "
                f"— no boilerplate, no subscribe CTA]"
            ),
            "description_body": (
                f"[Timestamps]\n"
                f"00:00 [First chapter — specific name]\n"
                f"[MM:SS] [Second chapter — specific name]\n"
                f"[MM:SS] [Third chapter — specific name]\n\n"
                f"[Key claims and sources]\n"
                f"[Guest info if applicable]\n"
            ),
            "description_close": "[Subscribe CTA, social links, show links — after all content]",
            "tags": f"[specific topic term], [guest name], [{local_note}], [show name last]",
        }
