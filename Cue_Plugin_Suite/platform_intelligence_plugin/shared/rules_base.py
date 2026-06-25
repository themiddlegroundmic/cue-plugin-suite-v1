"""
shared/rules_base.py
====================
Base compliance checker shared across all three platform modules.
All three Master Guides share the same structural DNA:
  - Eligibility first
  - Identity/topic discipline second
  - Signal/send value third
  - Native packaging fourth
  - Metrics last

This base class encodes the universal rules. Platform-specific
subclasses add their own 12 Laws and surface-specific checks.
"""

from dataclasses import dataclass, field
from typing import List, Optional


# ── Universal political safety flags (all three platforms) ──────────────────
# Words that trigger reduced recommendation eligibility on Meta and YouTube
# when used without attribution, qualifier, or sourced evidence.
POLITICAL_SAFETY_FLAGS = {
    "rigged": "Use 'disputed' or 'contested' with a source citation",
    "fraud": "Use 'alleged fraud' or 'claimed fraud' with attribution",
    "traitor": "Use 'accused of' or name the specific allegation",
    "treason": "Use 'charged with' or 'accused of treason' with source",
    "scam": "Use 'alleged scam' or 'critics call it a scam' with evidence",
    "controls": "Specify who controls what and cite the mechanism",
    "powder keg": "Describe the specific tension without metaphor escalation",
    "stolen election": "Use 'disputed election' or 'election claims' with source",
    "deep state": "Name the specific institution or official being referenced",
    "fake news": "Specify the claim and the evidence against it",
    "witch hunt": "Describe the specific legal or political action",
}

# Universal dead engagement phrases (all three platforms)
ENGAGEMENT_BAIT_PHRASES = [
    "comment below",
    "drop a like",
    "smash the like button",
    "let me know what you think",
    "agree or disagree",
    "share if you agree",
    "tag someone who",
    "follow for more",
    "hit subscribe",
    "what do you think",
]


@dataclass
class ComplianceResult:
    """Result of a platform compliance check."""
    platform: str
    passed: bool
    eligibility_score: int          # 0–100
    flags: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    political_safety_issues: List[str] = field(default_factory=list)
    engagement_bait_found: List[str] = field(default_factory=list)


class PlatformRulesBase:
    """
    Base class for platform compliance checkers.
    Subclassed by FacebookRules, YouTubeRules, InstagramRules.
    """

    PLATFORM_NAME = "base"

    def __init__(self, niche: str = "political commentary", geo: str = "michigan"):
        self.niche = niche
        self.geo = geo

    def check_political_safety(self, text: str) -> List[str]:
        """
        Scan text for political safety flags.
        Returns list of (flagged_word: safer_alternative) strings.
        """
        text_lower = text.lower()
        issues = []
        for flag, suggestion in POLITICAL_SAFETY_FLAGS.items():
            if flag in text_lower:
                issues.append(f'"{flag}" detected — {suggestion}')
        return issues

    def check_engagement_bait(self, text: str) -> List[str]:
        """
        Scan text for engagement bait phrases that reduce recommendation eligibility.
        """
        text_lower = text.lower()
        found = []
        for phrase in ENGAGEMENT_BAIT_PHRASES:
            if phrase in text_lower:
                found.append(phrase)
        return found

    def check_originality(self, text: str) -> List[str]:
        """
        Check for signals of low originality (aggregator-style content).
        """
        warnings = []
        low_originality_signals = [
            "reposted from",
            "via @",
            "credit to",
            "not my content",
            "found this",
            "sharing this",
        ]
        text_lower = text.lower()
        for signal in low_originality_signals:
            if signal in text_lower:
                warnings.append(
                    f'Low-originality signal detected: "{signal}". '
                    "Add original commentary, framing, or analysis."
                )
        return warnings

    def score_eligibility(self, text: str, has_source: bool = False,
                          has_original_commentary: bool = True) -> int:
        """
        Score recommendation eligibility 0–100.
        Deductions applied for each risk factor found.
        """
        score = 100
        safety_issues = self.check_political_safety(text)
        bait = self.check_engagement_bait(text)
        originality_warnings = self.check_originality(text)

        score -= len(safety_issues) * 10
        score -= len(bait) * 8
        score -= len(originality_warnings) * 12

        if not has_source and any(
            word in text.lower() for word in ["claims", "alleges", "sources say", "reportedly"]
        ):
            score -= 10

        if not has_original_commentary:
            score -= 15

        return max(0, min(100, score))

    def check(self, text: str, **kwargs) -> ComplianceResult:
        """
        Run full compliance check. Override in subclasses to add platform rules.
        """
        safety = self.check_political_safety(text)
        bait = self.check_engagement_bait(text)
        originality = self.check_originality(text)
        eligibility = self.score_eligibility(text)

        return ComplianceResult(
            platform=self.PLATFORM_NAME,
            passed=eligibility >= 60 and len(safety) == 0,
            eligibility_score=eligibility,
            political_safety_issues=safety,
            engagement_bait_found=bait,
            warnings=originality,
            flags=[],
            suggestions=[],
        )
