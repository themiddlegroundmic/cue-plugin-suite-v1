from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import List, Optional

import requests

from src.core.types.models import CueEpisode, CueInput, CueKeyword, CuePluginResult, CueShow, CueSignal


ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"
CONTENT_NS = "http://purl.org/rss/1.0/modules/content/"
PSC_NS = "http://podlove.org/simple-chapters"


def _duration_seconds(raw: str) -> Optional[int]:
    if not raw:
        return None
    parts = raw.strip().split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        return int(float(parts[0]))
    except ValueError:
        return None


def _date(raw: str) -> Optional[datetime]:
    if not raw:
        return None
    try:
        return parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None


def _text(parent: ET.Element, tag: str, namespace: Optional[str] = None) -> str:
    el = parent.find(f"{{{namespace}}}{tag}" if namespace else tag)
    return (el.text or "").strip() if el is not None else ""


def _categories(parent: ET.Element) -> List[str]:
    categories = []
    for el in parent.findall("category"):
        if el.text:
            categories.append(el.text.strip())
    for el in parent.findall(f"{{{ITUNES_NS}}}category"):
        text = el.get("text")
        if text:
            categories.append(text.strip())
        for child in el.findall(f"{{{ITUNES_NS}}}category"):
            child_text = child.get("text")
            if child_text:
                categories.append(child_text.strip())
    return sorted(set(c for c in categories if c))


def _image(parent: ET.Element) -> str:
    image = parent.find(f"{{{ITUNES_NS}}}image")
    if image is not None:
        return image.get("href", "")
    image = parent.find("image/url")
    return (image.text or "").strip() if image is not None else ""


def _chapters(item: ET.Element) -> List[dict]:
    chapters = []
    for chapter in item.findall(f".//{{{PSC_NS}}}chapter"):
        chapters.append({
            "time": chapter.get("start", ""),
            "name": chapter.get("title", ""),
            "url": chapter.get("href", ""),
        })
    return chapters


def _keywords(text: str, limit: int = 12) -> List[CueKeyword]:
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9-]{3,}", text.lower())
    stop = {"this", "that", "with", "from", "podcast", "episode", "show", "about", "your"}
    seen = []
    for word in words:
        if word not in stop and word not in seen:
            seen.append(word)
    return [CueKeyword(value=w, source="rss", weight=0.4, presentInUserContent=True) for w in seen[:limit]]


class RssPlugin:
    id = "rss"
    name = "RSS Parser"
    platform = "podcast"
    enabled = True

    def __init__(self, session: requests.Session | None = None, timeout: int = 15):
        self.session = session or requests.Session()
        self.timeout = timeout

    async def analyze(self, input: CueInput) -> CuePluginResult:
        if not input.rssUrl:
            return CuePluginResult(pluginId=self.id, platform=self.platform, status="not_configured", input=input, warnings=["rssUrl is required for RSS analysis."])
        try:
            response = self.session.get(input.rssUrl, timeout=self.timeout, headers={"User-Agent": "CuePlatformIntelligence/1.0"})
            response.raise_for_status()
            show = self.parse_xml(response.content, input.rssUrl)
            keywords = _keywords(show.title + " " + show.description + " " + " ".join(e.title for e in show.episodes[:5]))
            return CuePluginResult(
                pluginId=self.id,
                platform=self.platform,
                input=input,
                show=show,
                episodes=show.episodes,
                keywords=keywords,
                signals=[
                    CueSignal(type="freshness", source=self.id, value={"episodeCount": len(show.episodes)}, confidence=0.9),
                ],
            )
        except Exception as exc:
            return CuePluginResult(pluginId=self.id, platform=self.platform, status="error", input=input, warnings=[str(exc)])

    def parse_xml(self, content: bytes, feed_url: str = "") -> CueShow:
        root = ET.fromstring(content)
        channel = root.find("channel")
        if channel is None:
            raise ValueError("RSS feed has no channel element")
        show = CueShow(
            title=_text(channel, "title"),
            description=_text(channel, "description") or _text(channel, "summary", ITUNES_NS),
            author=_text(channel, "author", ITUNES_NS),
            feedUrl=feed_url,
            link=_text(channel, "link"),
            categories=_categories(channel),
            image=_image(channel),
            language=_text(channel, "language") or "en",
        )
        for item in channel.findall("item"):
            raw_keywords = _text(item, "keywords", ITUNES_NS)
            keywords = [k.strip() for k in re.split(r"[,;]", raw_keywords) if k.strip()]
            description = _text(item, "description") or _text(item, "encoded", CONTENT_NS) or _text(item, "summary", ITUNES_NS)
            show.episodes.append(CueEpisode(
                guid=_text(item, "guid") or _text(item, "link") or _text(item, "title"),
                title=_text(item, "title"),
                description=description,
                publishedAt=_date(_text(item, "pubDate")),
                durationSeconds=_duration_seconds(_text(item, "duration", ITUNES_NS)),
                link=_text(item, "link"),
                author=_text(item, "author", ITUNES_NS) or show.author,
                categories=_categories(item),
                image=_image(item) or show.image,
                chapters=_chapters(item),
                keywords=keywords,
            ))
        return show

