"""
competitor_scraper.py
=====================
Fetches and parses the RSS feeds of top-ranking competitor shows
to extract the metadata terms they use: titles, descriptions, tags.

This is the same data Ausha shows in its "Competitor Keywords" tab.
The underlying source is public RSS feeds — no scraping of private data.

For each competitor show, we extract:
  - Episode titles (last 20 episodes)
  - Description keywords (first 150 words of each description)
  - iTunes keyword tags
  - Show-level title and description terms
"""

import re
import time
import requests
import xml.etree.ElementTree as ET
from collections import Counter
from typing import Dict, List, Optional


ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"
REQUEST_DELAY = 1.5
STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "this", "that", "these", "those", "it", "its",
    "we", "our", "you", "your", "he", "she", "they", "their", "i", "my",
    "us", "him", "her", "what", "how", "why", "when", "where", "who",
    "podcast", "episode", "show", "listen", "subscribe", "follow", "host",
    "guest", "interview", "audio", "new", "week", "today", "now", "get",
    "also", "just", "more", "about", "up", "out", "so", "if", "as",
}


def _tokenize(text: str) -> List[str]:
    """Extract meaningful words and bigrams from text."""
    text = text.lower()
    words = re.findall(r"\b[a-z][a-z\-']{2,}\b", text)
    words = [w for w in words if w not in STOP_WORDS and len(w) > 2]
    # Add bigrams
    bigrams = [f"{words[i]} {words[i+1]}" for i in range(len(words) - 1)
               if words[i] not in STOP_WORDS and words[i+1] not in STOP_WORDS]
    return words + bigrams


class CompetitorScraper:
    """
    Scrapes RSS feeds of competitor shows to build a keyword frequency map.

    Usage:
        scraper = CompetitorScraper()
        terms = scraper.scrape_competitors(competitor_list)
        # competitor_list from AppleDetector.get_competitors()
    """

    def __init__(self, max_episodes_per_show: int = 20, timeout: int = 12):
        self.max_episodes = max_episodes_per_show
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "CuePSOPlugin/1.0 (+https://cue.fm)"
        })

    def fetch_feed(self, feed_url: str) -> Optional[ET.Element]:
        """Fetch and parse an RSS feed. Returns root element or None."""
        if not feed_url:
            return None
        time.sleep(REQUEST_DELAY)
        try:
            resp = self._session.get(feed_url, timeout=self.timeout)
            resp.raise_for_status()
            return ET.fromstring(resp.content)
        except Exception as e:
            print(f"[CompetitorScraper] Failed to fetch {feed_url}: {e}")
            return None

    def extract_terms(self, root: ET.Element, show_title: str) -> Dict[str, int]:
        """Extract keyword frequency from a parsed RSS feed."""
        channel = root.find("channel")
        if channel is None:
            return {}

        all_text = []

        # Show-level title and description
        show_desc = channel.findtext("description") or ""
        all_text.extend(_tokenize(show_title))
        all_text.extend(_tokenize(show_desc[:300]))

        # iTunes keywords at show level
        kw_el = channel.find(f"{{{ITUNES_NS}}}keywords")
        if kw_el is not None and kw_el.text:
            for kw in re.split(r"[,;]", kw_el.text):
                kw = kw.strip().lower()
                if kw and kw not in STOP_WORDS:
                    all_text.append(kw)

        # Episode-level data (last N episodes)
        items = channel.findall("item")[:self.max_episodes]
        for item in items:
            ep_title = item.findtext("title") or ""
            ep_desc = item.findtext("description") or ""
            ep_kw_el = item.find(f"{{{ITUNES_NS}}}keywords")

            all_text.extend(_tokenize(ep_title))
            all_text.extend(_tokenize(ep_desc[:150]))  # first 150 words only

            if ep_kw_el is not None and ep_kw_el.text:
                for kw in re.split(r"[,;]", ep_kw_el.text):
                    kw = kw.strip().lower()
                    if kw and kw not in STOP_WORDS:
                        all_text.append(kw)

        return dict(Counter(all_text))

    def scrape_competitors(self, competitors: List[Dict]) -> Dict[str, int]:
        """
        Scrape all competitor feeds and return a merged term frequency map.
        Terms used by more competitors rank higher in the merged count.

        competitors: list of dicts from AppleDetector.get_competitors()
        """
        merged: Counter = Counter()
        for comp in competitors:
            feed_url = comp.get("feed_url", "")
            title = comp.get("title", "")
            if not feed_url:
                continue
            root = self.fetch_feed(feed_url)
            if root is None:
                continue
            terms = self.extract_terms(root, title)
            # Weight by competitor rank (first competitor = highest weight)
            weight = max(1, len(competitors) - competitors.index(comp))
            for term, count in terms.items():
                merged[term] += count * weight
            print(f"[Competitor] Scraped: {title} ({len(terms)} terms)")

        return dict(merged.most_common(200))
