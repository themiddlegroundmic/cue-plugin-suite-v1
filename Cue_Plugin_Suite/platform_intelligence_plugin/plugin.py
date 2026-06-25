"""
plugin.py
=========
Main CuePlatformPlugin orchestrator.
Single entry point for all platform intelligence functions.

Wires together:
  - FacebookRules (compliance checker)
  - YouTubeRules (compliance checker)
  - InstagramRules (compliance checker)
  - YouTubePSO (search rank + keyword intelligence)
  - InstagramSearch (hashtag search intelligence)
  - CueLLMWriter (Cue built-in LLM metadata writer)
"""

import os
from typing import List, Optional, Dict, Tuple

from .facebook.rules import FacebookRules
from .youtube.rules import YouTubeRules
from .youtube.pso import YouTubePSO, YouTubeKeywordResult
from .instagram.rules import InstagramRules
from .instagram.search import InstagramSearch, HashtagResult
from .shared.rules_base import ComplianceResult
from .shared.llm_writer import CueLLMWriter


class CuePlatformPlugin:
    """
    Cue Platform Intelligence Plugin.
    
    Platform-level credentials (set once by Cue org, never per-user):
      - YOUTUBE_API_KEY: YouTube Data API v3 key
      - META_APP_ID: Meta App ID (1653457239314715)
      - META_APP_SECRET: Meta App Secret
      - BUILT_IN_FORGE_API_URL: Cue LLM API URL
      - BUILT_IN_FORGE_API_KEY: Cue LLM API key
    
    Per-user credentials (stored in DB after OAuth):
      - instagram_access_token: Long-lived Instagram Graph API token
    """

    def __init__(
        self,
        youtube_api_key: str = "",
        meta_app_id: str = "",
        meta_app_secret: str = "",
        instagram_access_token: str = "",
        forge_api_url: str = "",
        forge_api_key: str = "",
        niche: str = "political commentary",
        geo: str = "michigan",
    ):
        # Platform credentials — read from environment if not passed
        self.youtube_api_key = youtube_api_key or os.environ.get("YOUTUBE_API_KEY", "")
        self.meta_app_id = meta_app_id or os.environ.get("META_APP_ID", "1653457239314715")
        self.meta_app_secret = meta_app_secret or os.environ.get("META_APP_SECRET", "")
        self.instagram_access_token = instagram_access_token

        # Compliance checkers
        self.facebook = FacebookRules(niche=niche, geo=geo)
        self.youtube_rules = YouTubeRules(niche=niche, geo=geo)
        self.instagram_rules = InstagramRules(niche=niche, geo=geo)

        # PSO and search engines
        self.youtube_pso = YouTubePSO(api_key=self.youtube_api_key)
        self.instagram_search = InstagramSearch(
            access_token=instagram_access_token,
            app_id=self.meta_app_id,
            app_secret=self.meta_app_secret,
        )

        # LLM writer (Cue built-in — no third-party model)
        self.llm = CueLLMWriter(
            api_url=forge_api_url or os.environ.get("BUILT_IN_FORGE_API_URL", ""),
            api_key=forge_api_key or os.environ.get("BUILT_IN_FORGE_API_KEY", ""),
        )

        self.niche = niche
        self.geo = geo

    # ── Facebook ──────────────────────────────────────────────────────────────

    def check_facebook_post(self, text: str, post_type: str = "text",
                             has_source: bool = False,
                             is_reel: bool = False) -> ComplianceResult:
        """Run full Facebook compliance check against the Master Facebook Guide rules."""
        return self.facebook.check(text, post_type=post_type,
                                   has_source=has_source, is_reel=is_reel)

    def write_facebook_post(self, topic: str, keywords: List[str],
                             local_angle: str = "",
                             claim_type: str = "attributed_claim",
                             has_receipt: bool = True) -> Dict[str, str]:
        """
        Write a Facebook post using the Cue LLM + Master Facebook Guide rules.
        Returns {'content': str, 'compliance': ComplianceResult}.
        """
        content = self.llm.write_facebook_post(
            topic=topic, keywords=keywords, local_angle=local_angle,
            claim_type=claim_type, has_receipt=has_receipt,
        )
        compliance = self.check_facebook_post(content, has_source=has_receipt)
        
        # Auto-fix if compliance fails
        if not compliance.passed and compliance.flags:
            content = self.llm.fix_compliance_issues("facebook", content, compliance.flags)
            compliance = self.check_facebook_post(content, has_source=has_receipt)

        return {"content": content, "compliance": compliance}

    # ── YouTube ───────────────────────────────────────────────────────────────

    def check_youtube_content(self, text: str, title: str = "",
                               description: str = "",
                               chapters: Optional[List[Tuple[str, str]]] = None) -> ComplianceResult:
        """Run full YouTube compliance check against the Master YouTube Guide rules."""
        return self.youtube_rules.check(text, title=title,
                                        description=description, chapters=chapters)

    def write_youtube_title(self, topic: str, keywords: List[str],
                             guest: str = "", conflict: str = "") -> str:
        """Write a YouTube title using the Cue LLM + Master YouTube Guide rules."""
        return self.llm.write_youtube_title(topic=topic, keywords=keywords,
                                             guest=guest, conflict=conflict)

    def write_youtube_description(self, topic: str, keywords: List[str],
                                   guest: str = "", chapters: List[str] = None,
                                   local_angle: str = "") -> str:
        """Write a YouTube description using the Cue LLM + Master YouTube Guide metadata order."""
        return self.llm.write_youtube_description(
            topic=topic, keywords=keywords, guest=guest,
            chapters=chapters, local_angle=local_angle,
        )

    def analyze_youtube_keyword(self, keyword: str,
                                 your_channel_id: str = "") -> YouTubeKeywordResult:
        """
        Full YouTube PSO analysis for a keyword.
        Returns search rank, competitor metadata, autocomplete suggestions,
        difficulty score, demand score, and Google Trends signal.
        """
        return self.youtube_pso.analyze_keyword(keyword, your_channel_id)

    def analyze_youtube_keywords(self, keywords: List[str],
                                  your_channel_id: str = "") -> List[YouTubeKeywordResult]:
        """Run YouTube PSO analysis for a list of keywords, sorted by opportunity."""
        return self.youtube_pso.analyze_channel_keywords(keywords, your_channel_id)

    # ── Instagram ─────────────────────────────────────────────────────────────

    def check_instagram_content(self, text: str, surface: str = "feed",
                                  is_reel: bool = False,
                                  slides: Optional[List[str]] = None) -> ComplianceResult:
        """Run full Instagram compliance check against the Master Instagram Guide rules."""
        return self.instagram_rules.check(text, surface=surface,
                                          is_reel=is_reel, slides=slides)

    def write_instagram_caption(self, topic: str, keywords: List[str],
                                 surface: str = "feed", local_angle: str = "",
                                 hashtags: List[str] = None) -> Dict[str, str]:
        """
        Write an Instagram caption using the Cue LLM + Master Instagram Guide rules.
        Returns {'content': str, 'compliance': ComplianceResult}.
        """
        content = self.llm.write_instagram_caption(
            topic=topic, keywords=keywords, surface=surface,
            local_angle=local_angle, hashtags=hashtags,
        )
        compliance = self.check_instagram_content(content, surface=surface)

        if not compliance.passed and compliance.flags:
            content = self.llm.fix_compliance_issues("instagram", content, compliance.flags)
            compliance = self.check_instagram_content(content, surface=surface)

        return {"content": content, "compliance": compliance}

    def write_instagram_reel_script(self, topic: str, keywords: List[str],
                                     receipt: str = "",
                                     local_angle: str = "") -> str:
        """Write an Instagram Reels script using the Cue LLM + Reels formula."""
        return self.llm.write_instagram_reel_script(
            topic=topic, keywords=keywords, receipt=receipt, local_angle=local_angle,
        )

    def analyze_instagram_hashtag(self, term: str) -> HashtagResult:
        """Analyze a hashtag for demand, classification, and recommendation."""
        return self.instagram_search.analyze_hashtag(term)

    def recommend_instagram_surface(self, content_type: str, goal: str) -> Dict:
        """Recommend the right Instagram surface for a given content type and goal."""
        return self.instagram_rules.recommend_surface(content_type, goal)

    def generate_instagram_hashtag_set(self, topic: str, max_tags: int = 5) -> List[str]:
        """Generate a recommended hashtag set following the Instagram Guide doctrine."""
        return self.instagram_search.generate_hashtag_set(topic, self.geo, max_tags)

    # ── Status ────────────────────────────────────────────────────────────────

    def status(self) -> Dict[str, bool]:
        """Return configuration status for all platform integrations."""
        return {
            "youtube_pso": self.youtube_pso.is_configured(),
            "instagram_search": self.instagram_search.is_configured(),
            "llm_writer": self.llm.is_configured(),
            "facebook_rules": True,   # Rules-only, no API required
            "youtube_rules": True,    # Rules-only, no API required
            "instagram_rules": True,  # Rules-only, no API required
        }

    def youtube_quota_status(self) -> Dict[str, int]:
        """Return YouTube API quota usage."""
        return {
            "used": self.youtube_pso.quota_used,
            "remaining": self.youtube_pso.quota_remaining,
            "daily_limit": 10_000,
        }
