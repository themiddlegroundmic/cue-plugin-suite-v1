"""
feed_parser.py
==============
Parses a Buzzsprout (or any standard) RSS feed into structured episode data.
Extracts: title, description, tags, pub_date, duration, guid, episode_number.
"""

import re
import time
import requests
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"
CONTENT_NS = "http://purl.org/rss/1.0/modules/content/"

POLITICAL_SAFETY_WORDS = [
    "rigged", "fraud", "traitor", "treason", "scam", "controls",
    "powder keg", "criminal", "corrupt", "stolen", "fake", "hoax",
    "conspiracy", "cover-up", "liar", "lies",
]


@dataclass
class Episode:
    guid: str
    title: str
    description: str
    tags: List[str]
    pub_date: Optional[datetime]
    duration_seconds: int
    episode_number: Optional[int]
    season_number: Optional[int]
    audio_url: str
    link: str
    # Computed fields (populated by scorer)
    pso_score: int = 0
    priority: str = "P3"
    safety_flags: List[str] = field(default_factory=list)
    detected_keywords: List[str] = field(default_factory=list)
    apple_rank: Optional[int] = None
    spotify_rank: Optional[int] = None
    demand_score: int = 0
    difficulty_score: int = 0


@dataclass
class Show:
    title: str
    description: str
    author: str
    feed_url: str
    itunes_id: Optional[str]
    language: str
    category: str
    episodes: List[Episode] = field(default_factory=list)


def _parse_duration(raw: str) -> int:
    """Convert HH:MM:SS or MM:SS or plain seconds string to integer seconds."""
    if not raw:
        return 0
    parts = raw.strip().split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        else:
            return int(parts[0])
    except (ValueError, IndexError):
        return 0


def _parse_date(raw: str) -> Optional[datetime]:
    """Parse RFC 2822 date string into datetime."""
    if not raw:
        return None
    formats = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%a, %d %b %Y %H:%M:%S",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(raw.strip(), fmt)
        except ValueError:
            continue
    return None


def _check_safety(text: str) -> List[str]:
    """Return list of political safety flag words found in text."""
    lower = text.lower()
    return [w for w in POLITICAL_SAFETY_WORDS if w in lower]


def _has_boilerplate_at_top(description: str) -> bool:
    """Detect if boilerplate (fan mail, BuyMeACoffee, sponsor copy) leads the description."""
    first_150 = description[:150].lower()
    boilerplate_signals = [
        "send us", "fan mail", "buymeacoffee", "buy me a coffee",
        "brio", "trimmer", "sponsor", "support the show",
        "follow us on", "subscribe", "leave a review",
    ]
    return any(sig in first_150 for sig in boilerplate_signals)


class FeedParser:
    """
    Fetches and parses a podcast RSS feed URL into a Show + Episode list.

    Usage:
        parser = FeedParser("https://feeds.buzzsprout.com/2465711.rss")
        show = parser.parse()
    """

    def __init__(self, feed_url: str, timeout: int = 15):
        self.feed_url = feed_url
        self.timeout = timeout

    def parse(self) -> Show:
        resp = requests.get(self.feed_url, timeout=self.timeout, headers={
            "User-Agent": "CuePSOPlugin/1.0 (+https://cue.fm)"
        })
        resp.raise_for_status()
        return self._parse_xml(resp.content)

    def _parse_xml(self, content: bytes) -> Show:
        root = ET.fromstring(content)
        channel = root.find("channel")
        if channel is None:
            raise ValueError("RSS feed has no <channel> element")

        def it(tag: str) -> str:
            el = channel.find(f"{{{ITUNES_NS}}}{tag}")
            return el.text.strip() if el is not None and el.text else ""

        def plain(tag: str) -> str:
            el = channel.find(tag)
            return el.text.strip() if el is not None and el.text else ""

        show = Show(
            title=plain("title"),
            description=plain("description"),
            author=it("author"),
            feed_url=self.feed_url,
            itunes_id=None,
            language=plain("language") or "en",
            category=it("category"),
            episodes=[],
        )

        for item in channel.findall("item"):
            def iit(tag: str) -> str:
                el = item.find(f"{{{ITUNES_NS}}}{tag}")
                return el.text.strip() if el is not None and el.text else ""

            def ipl(tag: str) -> str:
                el = item.find(tag)
                return el.text.strip() if el is not None and el.text else ""

            # Tags from itunes:keywords
            raw_tags = iit("keywords")
            tags = [t.strip() for t in re.split(r"[,;]", raw_tags) if t.strip()] if raw_tags else []

            # Episode / season numbers
            ep_num = None
            try:
                ep_num = int(iit("episode"))
            except (ValueError, TypeError):
                pass

            sn_num = None
            try:
                sn_num = int(iit("season"))
            except (ValueError, TypeError):
                pass

            # Audio URL
            enc = item.find("enclosure")
            audio_url = enc.get("url", "") if enc is not None else ""

            description = ipl("description") or iit("summary")
            title = ipl("title")

            safety = _check_safety(title + " " + description)

            episode = Episode(
                guid=ipl("guid") or audio_url,
                title=title,
                description=description,
                tags=tags,
                pub_date=_parse_date(ipl("pubDate")),
                duration_seconds=_parse_duration(iit("duration")),
                episode_number=ep_num,
                season_number=sn_num,
                audio_url=audio_url,
                link=ipl("link"),
                safety_flags=safety,
            )
            show.episodes.append(episode)

        return show
