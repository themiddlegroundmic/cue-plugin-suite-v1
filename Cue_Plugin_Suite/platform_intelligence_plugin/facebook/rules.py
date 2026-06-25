"""
facebook/rules.py
=================
Facebook compliance module built from the Master Facebook Guide.
Encodes the 12 Laws, Recommendation Eligibility test, Signal Stack,
Post Formula, Claim Ladder, and Reels structure.

Source: Master Facebook Guide — The MiddleGround Mic (June 23, 2026)
Derived from Meta public guidance, platform algorithm notes, and
production rules. Not scraped from Meta's systems.
"""

import re
from typing import List, Optional, Dict
from ..shared.rules_base import PlatformRulesBase, ComplianceResult, POLITICAL_SAFETY_FLAGS


# ── Facebook-specific constants ──────────────────────────────────────────────

# Post types
POST_TYPE_TEXT = "text"
POST_TYPE_IMAGE = "image"
POST_TYPE_REEL = "reel"
POST_TYPE_CAROUSEL = "carousel"
POST_TYPE_LINK = "link"

# Signal hierarchy (Chapter 5 — The Signal Stack)
# Higher index = stronger signal
SIGNAL_HIERARCHY = {
    "like": 1,
    "comment": 3,
    "meaningful_comment": 5,
    "share": 7,
    "private_share": 9,
    "save": 6,
}

# The 12 Laws (Chapter 1)
FACEBOOK_12_LAWS = [
    "Eligibility beats optimization. A risky or low-quality post cannot be saved by a better caption.",
    "The Page must have a lane. Scattered topics confuse the audience profile.",
    "Original commentary is the product. The headline or clip is evidence; your framing is the content.",
    "Private-share value beats casual likes. Write posts people would send to someone else.",
    "Meaningful comments beat comment bait. Earn discussion; do not demand it.",
    "Reels need instant tension. The first seconds decide whether the rest matters.",
    "Receipts protect reach and trust. Political heat without evidence burns the Page.",
    "Local stakes make national politics usable. Tie national fights to money, trust, voters, communities, and institutions.",
    "Each post gets one argument. If the draft has two theses, split it.",
    "The image must match the caption. A misleading image creates negative feedback and trust loss.",
    "First-window replies matter. Real comments should be answered while the post is alive.",
    "Review patterns, not vibes. One flop is a data point; five similar flops are a rule.",
]

# Claim ladder (Chapter 9)
CLAIM_LADDER = {
    "proven_fact": "State directly with source citation",
    "attributed_claim": "Use 'X claims' or 'according to Y'",
    "visible_pattern": "Use 'the record shows' or 'this is the third time'",
    "opinion": "Use 'I think' or 'this looks like' — clearly labeled",
    "unknown": "Use 'we don't know yet' or 'this is unconfirmed'",
}

# Recommendation eligibility risks (Chapter 4)
ELIGIBILITY_RISKS = [
    "violent imagery",
    "sexualized content",
    "contest mechanics",
    "giveaway",
    "fake urgency",
    "miracle claim",
    "scam claim",
    "unsupported guarantee",
    "coordinated comment",
    "deceptive landing",
]

# Post formula (Chapter 8)
POST_FORMULA = {
    "first_line": "Hook — the one thing that makes the viewer stop scrolling",
    "body": "Evidence + original analysis (the receipt and your framing of it)",
    "local_stakes": "Tie to money, voters, institutions, or community impact",
    "close": "One question or one clear conclusion — not a CTA demand",
}

# Reels structure (Chapter 10)
REELS_STRUCTURE = {
    "seconds_0_3": "Instant tension — name the conflict, contradiction, or cost",
    "seconds_3_15": "Evidence — show the receipt, document, or clip",
    "seconds_15_45": "Analysis — your original framing of what it means",
    "close": "Strong ending — conclusion or open loop, not a subscribe demand",
}

# Optimal post timing windows (Chapter 12)
TIMING_WINDOWS = {
    "weekday_morning": "7:00–9:00 AM",
    "weekday_lunch": "11:30 AM–1:00 PM",
    "weekday_evening": "6:00–9:00 PM",
    "weekend_morning": "8:00–11:00 AM",
}

# Image specs (Chapter 11)
IMAGE_SPECS = {
    "feed_image": "1200×630px (1.91:1)",
    "feed_square": "1080×1080px (1:1)",
    "reel": "1080×1920px (9:16)",
    "story": "1080×1920px (9:16)",
    "carousel_card": "1080×1080px (1:1)",
}


class FacebookRules(PlatformRulesBase):
    """
    Facebook compliance checker built from the Master Facebook Guide.
    """

    PLATFORM_NAME = "facebook"

    def check_post_formula(self, text: str) -> List[str]:
        """
        Check whether a post follows the Facebook post formula from Chapter 8.
        Returns list of issues found.
        """
        issues = []
        lines = text.strip().split("\n")
        first_line = lines[0] if lines else ""

        # First line should not start with a question (weak hook)
        if first_line.startswith("What ") or first_line.startswith("Do you "):
            issues.append(
                "First line opens with a question — weak hook. "
                "Lead with the conflict, cost, contradiction, or receipt instead."
            )

        # Check for local stakes
        local_signals = ["michigan", "detroit", "lansing", "downriver", "voters", "taxpayers",
                         "residents", "community", "district", "county"]
        has_local = any(sig in text.lower() for sig in local_signals)
        if not has_local:
            issues.append(
                "No local stakes detected. Tie the national story to Michigan voters, "
                "money, institutions, or community impact (Law 8)."
            )

        # Check for single argument (Law 9)
        thesis_signals = ["but also", "and another thing", "additionally", "furthermore",
                          "on top of that", "not only that"]
        for signal in thesis_signals:
            if signal in text.lower():
                issues.append(
                    f'Multiple argument signal detected: "{signal}". '
                    "Each post gets one argument — split into two posts if needed (Law 9)."
                )
                break

        return issues

    def check_claim_ladder(self, text: str) -> List[str]:
        """
        Check whether political claims follow the claim ladder from Chapter 9.
        Returns list of unattributed claim risks.
        """
        issues = []
        text_lower = text.lower()

        # Unattributed accusation patterns
        accusation_patterns = [
            (r"\b(he|she|they|it) (lied|cheated|stole|defrauded|betrayed)\b",
             "Direct accusation without attribution — use 'X claims' or cite the record"),
            (r"\bproved? (that|he|she|they)\b",
             "'Proved' is a strong claim — use 'the record shows' or cite the specific evidence"),
            (r"\beveryone knows\b",
             "'Everyone knows' is unsupported — state the specific evidence"),
        ]

        for pattern, message in accusation_patterns:
            if re.search(pattern, text_lower):
                issues.append(message)

        return issues

    def check_reels_structure(self, script: str) -> List[str]:
        """
        Check a Reels script against the Reels structure from Chapter 10.
        """
        issues = []
        lines = script.strip().split("\n")
        first_line = lines[0] if lines else ""

        # Check for instant tension in first line
        tension_signals = ["?", ":", "—", "but", "except", "until", "despite", "while"]
        has_tension = any(sig in first_line for sig in tension_signals)
        if not has_tension:
            issues.append(
                "Reels first line lacks instant tension. "
                "Name the conflict, contradiction, or cost immediately (Law 6)."
            )

        # Check for subscribe/follow CTA at end (reduces recommendation eligibility)
        subscribe_signals = ["subscribe", "follow me", "hit the bell", "turn on notifications"]
        script_lower = script.lower()
        for sig in subscribe_signals:
            if sig in script_lower:
                issues.append(
                    f'Subscribe/follow CTA detected: "{sig}". '
                    "End with a conclusion or open loop — not a subscribe demand. "
                    "Recommendation eligibility is hurt by explicit follow CTAs."
                )
                break

        return issues

    def check(self, text: str, post_type: str = POST_TYPE_TEXT,
              has_source: bool = False, is_reel: bool = False) -> ComplianceResult:
        """
        Full Facebook compliance check.
        """
        # Base checks (political safety, engagement bait, originality)
        base = super().check(text)

        # Facebook-specific checks
        post_issues = self.check_post_formula(text)
        claim_issues = self.check_claim_ladder(text)
        reel_issues = self.check_reels_structure(text) if is_reel else []

        all_flags = base.flags + post_issues + claim_issues + reel_issues

        # Eligibility deductions
        eligibility = base.eligibility_score
        eligibility -= len(post_issues) * 5
        eligibility -= len(claim_issues) * 8
        eligibility -= len(reel_issues) * 6
        eligibility = max(0, min(100, eligibility))

        # Build suggestions
        suggestions = []
        if eligibility < 60:
            suggestions.append(
                "Eligibility score is below 60. Fix political safety and claim issues "
                "before optimizing caption or timing."
            )
        if not has_source and any(
            word in text.lower() for word in ["claims", "alleges", "reportedly", "sources say"]
        ):
            suggestions.append(
                "Attribution language detected without a cited source. "
                "Add the source (document, filing, statement, headline) before publishing."
            )

        return ComplianceResult(
            platform=self.PLATFORM_NAME,
            passed=eligibility >= 60 and len(base.political_safety_issues) == 0 and len(base.engagement_bait_found) == 0,
            eligibility_score=eligibility,
            flags=all_flags,
            warnings=base.warnings,
            suggestions=suggestions,
            political_safety_issues=base.political_safety_issues,
            engagement_bait_found=base.engagement_bait_found,
        )

    def generate_post_template(self, topic: str, claim_type: str = "visible_pattern",
                                local_angle: str = "") -> Dict[str, str]:
        """
        Generate a Facebook post template structure for a given topic.
        Returns a dict with first_line, body, local_stakes, close placeholders.
        """
        claim_instruction = CLAIM_LADDER.get(claim_type, CLAIM_LADDER["attributed_claim"])
        local_note = local_angle or f"Michigan voters / {self.geo} community impact"

        return {
            "first_line": f"[Hook: name the conflict or cost in {topic}]",
            "body": f"[Evidence: the receipt, document, or record] — {claim_instruction}",
            "local_stakes": f"[Local stakes: what this means for {local_note}]",
            "close": "[One question or one clear conclusion — no subscribe CTA]",
            "claim_type": claim_type,
            "claim_instruction": claim_instruction,
        }
