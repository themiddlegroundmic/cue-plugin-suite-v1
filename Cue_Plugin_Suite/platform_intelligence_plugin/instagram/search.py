"""
instagram/search.py
===================
Instagram search intelligence layer.
Uses Instagram Graph API for hashtag search and account insights.
Uses Google Trends as the universal demand signal.

Platform credentials (set once by Cue org):
  - META_APP_ID: Meta App ID
  - META_APP_SECRET: Meta App Secret
  - INSTAGRAM_ACCESS_TOKEN: Long-lived page access token (per user, stored in DB)

Note: Instagram Graph API requires a connected Business or Creator account.
The Meta App ID and Secret are platform-level. The access token is per-user
and obtained via the Meta OAuth flow in the Cue app.
"""

import os
import time
import requests
from typing import List, Dict, Optional
from dataclasses import dataclass, field


# ── Configuration ─────────────────────────────────────────────────────────────

META_APP_ID = os.environ.get("META_APP_ID", "1653457239314715")
META_APP_SECRET = os.environ.get("META_APP_SECRET", "")
INSTAGRAM_GRAPH_URL = "https://graph.instagram.com/v19.0"
META_GRAPH_URL = "https://graph.facebook.com/v19.0"

REQUEST_DELAY = 0.5


@dataclass
class HashtagResult:
    """Search intelligence result for a single hashtag/keyword."""
    term: str
    media_count: int = 0           # Number of posts using this hashtag
    top_post_ids: List[str] = field(default_factory=list)
    recent_post_ids: List[str] = field(default_factory=list)
    demand_score: int = 0          # 0–100 proxy from media count
    trends_score: int = 0          # 0–100 from Google Trends
    classification: str = ""       # DETECTED / COMPETITOR / LOCAL / DEAD
    recommended: bool = False      # Whether Cue recommends using this term


@dataclass
class InstagramAccountInsights:
    """Insights for a connected Instagram Business/Creator account."""
    account_id: str
    username: str
    follower_count: int = 0
    media_count: int = 0
    reach_7d: int = 0
    impressions_7d: int = 0
    profile_views_7d: int = 0
    top_performing_posts: List[Dict] = field(default_factory=list)


class InstagramSearch:
    """
    Instagram search intelligence engine.
    Uses Instagram Graph API + Google Trends.
    """

    def __init__(self, access_token: str = "", app_id: str = "", app_secret: str = ""):
        self.access_token = access_token
        self.app_id = app_id or META_APP_ID
        self.app_secret = app_secret or META_APP_SECRET

    def is_configured(self) -> bool:
        return bool(self.access_token)

    def get_hashtag_id(self, hashtag: str) -> Optional[str]:
        """
        Get the Instagram hashtag ID for a given hashtag term.
        Required before querying hashtag media counts.
        """
        if not self.is_configured():
            return None

        # Strip # if present
        hashtag = hashtag.lstrip("#")

        try:
            params = {
                "user_id": self._get_ig_user_id(),
                "q": hashtag,
                "access_token": self.access_token,
            }
            resp = requests.get(
                f"{META_GRAPH_URL}/ig_hashtag_search",
                params=params,
                timeout=10,
            )
            time.sleep(REQUEST_DELAY)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("data", [])
                if items:
                    return items[0].get("id")
        except Exception:
            pass
        return None

    def get_hashtag_media_count(self, hashtag_id: str) -> int:
        """
        Get the media count for a hashtag ID.
        Higher count = more posts = more competition but also more demand.
        """
        if not self.is_configured() or not hashtag_id:
            return 0

        try:
            params = {
                "fields": "media_count",
                "access_token": self.access_token,
            }
            resp = requests.get(
                f"{META_GRAPH_URL}/{hashtag_id}",
                params=params,
                timeout=10,
            )
            time.sleep(REQUEST_DELAY)
            if resp.status_code == 200:
                return resp.json().get("media_count", 0)
        except Exception:
            pass
        return 0

    def get_hashtag_top_posts(self, hashtag_id: str, limit: int = 10) -> List[str]:
        """
        Get top post IDs for a hashtag.
        """
        if not self.is_configured() or not hashtag_id:
            return []

        try:
            ig_user_id = self._get_ig_user_id()
            params = {
                "fields": "id,media_type,timestamp,like_count,comments_count",
                "access_token": self.access_token,
            }
            resp = requests.get(
                f"{META_GRAPH_URL}/{hashtag_id}/top_media",
                params={**params, "user_id": ig_user_id},
                timeout=10,
            )
            time.sleep(REQUEST_DELAY)
            if resp.status_code == 200:
                items = resp.json().get("data", [])
                return [item["id"] for item in items[:limit]]
        except Exception:
            pass
        return []

    def _get_ig_user_id(self) -> str:
        """
        Get the Instagram Business/Creator account ID from the access token.
        Cached after first call.
        """
        if hasattr(self, "_ig_user_id"):
            return self._ig_user_id

        try:
            params = {
                "fields": "id,username",
                "access_token": self.access_token,
            }
            resp = requests.get(f"{INSTAGRAM_GRAPH_URL}/me", params=params, timeout=10)
            if resp.status_code == 200:
                self._ig_user_id = resp.json().get("id", "")
                return self._ig_user_id
        except Exception:
            pass
        return ""

    def get_account_insights(self, ig_user_id: str) -> InstagramAccountInsights:
        """
        Get account-level insights for a connected Instagram Business account.
        """
        if not self.is_configured():
            return InstagramAccountInsights(account_id=ig_user_id, username="")

        try:
            params = {
                "fields": "id,username,followers_count,media_count",
                "access_token": self.access_token,
            }
            resp = requests.get(
                f"{META_GRAPH_URL}/{ig_user_id}",
                params=params,
                timeout=10,
            )
            time.sleep(REQUEST_DELAY)
            if resp.status_code == 200:
                data = resp.json()
                insights = InstagramAccountInsights(
                    account_id=ig_user_id,
                    username=data.get("username", ""),
                    follower_count=data.get("followers_count", 0),
                    media_count=data.get("media_count", 0),
                )
                return insights
        except Exception:
            pass
        return InstagramAccountInsights(account_id=ig_user_id, username="")

    def calculate_demand_score_from_count(self, media_count: int) -> int:
        """
        Convert hashtag media count to a 0–100 demand score.
        Scale:
          < 1K posts = 10 (niche, low demand)
          1K–10K = 30
          10K–100K = 50
          100K–1M = 70
          1M–10M = 85
          10M+ = 95 (too broad — likely dead hashtag)
        """
        if media_count < 1_000:
            return 10
        elif media_count < 10_000:
            return 30
        elif media_count < 100_000:
            return 50
        elif media_count < 1_000_000:
            return 70
        elif media_count < 10_000_000:
            return 85
        else:
            return 95  # Very high count = too broad = dead hashtag territory

    def get_trends_score(self, keyword: str) -> int:
        """
        Get Google Trends demand score for a keyword.
        Returns 0–100. Falls back to 50 if pytrends unavailable.
        """
        try:
            from pytrends.request import TrendReq
            pytrends = TrendReq(hl="en-US", tz=360)
            pytrends.build_payload([keyword], timeframe="today 3-m", geo="US")
            data = pytrends.interest_over_time()
            if not data.empty and keyword in data.columns:
                return int(data[keyword].mean())
        except Exception:
            pass
        return 50

    def classify_hashtag(self, term: str, media_count: int,
                          demand_score: int) -> str:
        """
        Classify a hashtag using the Instagram SEO taxonomy.
        """
        from .rules import HASHTAG_DOCTRINE

        term_lower = term.lower().lstrip("#")

        # DEAD: in the dead hashtag list or too broad (10M+ posts)
        for dead in HASHTAG_DOCTRINE["dead_hashtags"]:
            if term_lower == dead.lstrip("#").lower():
                return "DEAD"
        if media_count > 10_000_000:
            return "DEAD"

        # LOCAL: geographic terms
        local_signals = [
            "michigan", "detroit", "lansing", "downriver", "flint",
            "annarbor", "grandrapids", "michiganpolitics",
        ]
        for local in local_signals:
            if local in term_lower:
                return "LOCAL"

        # DETECTED: 10K–1M posts = sweet spot for niche political content
        if 10_000 <= media_count <= 1_000_000:
            return "DETECTED"

        return "COMPETITOR"

    def analyze_hashtag(self, term: str) -> HashtagResult:
        """
        Full search intelligence analysis for a single hashtag/keyword.
        """
        result = HashtagResult(term=term)

        if self.is_configured():
            hashtag_id = self.get_hashtag_id(term)
            if hashtag_id:
                result.media_count = self.get_hashtag_media_count(hashtag_id)
                result.top_post_ids = self.get_hashtag_top_posts(hashtag_id)
                result.demand_score = self.calculate_demand_score_from_count(result.media_count)
        else:
            # Fallback: use Google Trends only
            result.demand_score = 50

        result.trends_score = self.get_trends_score(term)
        result.classification = self.classify_hashtag(term, result.media_count, result.demand_score)
        result.recommended = (
            result.classification in ("DETECTED", "LOCAL")
            and result.demand_score >= 30
            and result.demand_score <= 85
        )

        return result

    def generate_hashtag_set(self, topic: str, geo: str = "michigan",
                              max_tags: int = 5) -> List[str]:
        """
        Generate a recommended hashtag set for a topic.
        Follows the Instagram Guide doctrine: max 5 specific tags,
        keywords beat hashtag stuffing, no dead generic tags.
        """
        # Build candidate list from topic
        words = topic.lower().split()
        candidates = []

        # Topic-specific compound tags
        if geo:
            candidates.append(f"#{geo}{words[0]}" if words else f"#{geo}politics")
        candidates.append(f"#{''.join(words[:2])}" if len(words) >= 2 else f"#{words[0]}")
        candidates.append(f"#{geo}politics" if geo else "#independentpolitics")
        candidates.append("#politicalcommentary")
        candidates.append("#independentmedia")

        # Filter to max_tags
        return candidates[:max_tags]
