"""
trends_detector.py
==================
Pulls Google Trends interest data for podcast topic keywords using pytrends.

This gives Cue a multi-platform demand signal that Ausha does NOT have.
Ausha's "search volume" is estimated from Apple Podcasts API call counts.
Cue's demand score is real human search interest from Google — a broader,
more reliable signal of actual audience demand for a topic.

Cost: FREE — no API key, no registration.
Library: pytrends (unofficial Google Trends API wrapper)
Install: pip install pytrends

The returned score is a 0–100 index (Google's relative interest scale).
100 = peak interest for that keyword in the selected time window.
"""

import time
from typing import Dict, List, Optional

try:
    from pytrends.request import TrendReq
    PYTRENDS_AVAILABLE = True
except ImportError:
    PYTRENDS_AVAILABLE = False


REQUEST_DELAY = 2.0
MAX_KEYWORDS_PER_BATCH = 5  # Google Trends limit per request


class TrendsDetector:
    """
    Fetches Google Trends interest scores for a list of keywords.

    Usage:
        detector = TrendsDetector(geo="US", timeframe="today 12-m")
        scores = detector.get_demand_scores(["michigan politics", "iran nuclear deal"])
        # returns: {"michigan politics": 72, "iran nuclear deal": 58}
    """

    def __init__(self, geo: str = "US", timeframe: str = "today 12-m",
                 hl: str = "en-US"):
        self.geo = geo
        self.timeframe = timeframe
        self.hl = hl
        self._pytrends = None

        if not PYTRENDS_AVAILABLE:
            print("[TrendsDetector] WARNING: pytrends not installed. "
                  "Run: pip install pytrends")
            print("[TrendsDetector] Demand scores will default to 50.")

    def _get_client(self):
        if self._pytrends is None:
            if not PYTRENDS_AVAILABLE:
                return None
            self._pytrends = TrendReq(hl=self.hl, tz=360, timeout=(10, 25))
        return self._pytrends

    def get_demand_score(self, keyword: str) -> int:
        """
        Returns the average Google Trends interest score (0–100) for a keyword
        over the configured timeframe and geography.
        """
        client = self._get_client()
        if client is None:
            return 50  # neutral fallback when pytrends unavailable

        time.sleep(REQUEST_DELAY)
        try:
            client.build_payload(
                kw_list=[keyword],
                cat=0,
                timeframe=self.timeframe,
                geo=self.geo,
                gprop="",
            )
            df = client.interest_over_time()
            if df.empty or keyword not in df.columns:
                return 0
            avg = int(df[keyword].mean())
            return min(100, max(0, avg))
        except Exception as e:
            print(f"[TrendsDetector] Error for '{keyword}': {e}")
            return 50

    def get_demand_scores(self, keywords: List[str]) -> Dict[str, int]:
        """
        Returns demand scores for a list of keywords.
        Batches requests to stay within Google Trends limits.
        """
        scores = {}
        # Process in batches of MAX_KEYWORDS_PER_BATCH
        for i in range(0, len(keywords), MAX_KEYWORDS_PER_BATCH):
            batch = keywords[i:i + MAX_KEYWORDS_PER_BATCH]
            client = self._get_client()

            if client is None:
                for kw in batch:
                    scores[kw] = 50
                continue

            time.sleep(REQUEST_DELAY)
            try:
                client.build_payload(
                    kw_list=batch,
                    cat=0,
                    timeframe=self.timeframe,
                    geo=self.geo,
                    gprop="",
                )
                df = client.interest_over_time()
                for kw in batch:
                    if not df.empty and kw in df.columns:
                        scores[kw] = min(100, max(0, int(df[kw].mean())))
                    else:
                        scores[kw] = 0
            except Exception as e:
                print(f"[TrendsDetector] Batch error: {e}")
                for kw in batch:
                    scores[kw] = scores.get(kw, 50)

        for kw, score in scores.items():
            print(f"[Trends] '{kw}' → demand {score}/100")
        return scores

    def get_related_queries(self, keyword: str) -> List[str]:
        """
        Returns related/rising queries from Google Trends.
        These are candidate satellite keywords for the PSO strategy.
        """
        client = self._get_client()
        if client is None:
            return []
        time.sleep(REQUEST_DELAY)
        try:
            client.build_payload(
                kw_list=[keyword],
                timeframe=self.timeframe,
                geo=self.geo,
            )
            related = client.related_queries()
            rising = related.get(keyword, {}).get("rising")
            if rising is not None and not rising.empty:
                return rising["query"].tolist()[:10]
        except Exception as e:
            print(f"[TrendsDetector] Related queries error for '{keyword}': {e}")
        return []
