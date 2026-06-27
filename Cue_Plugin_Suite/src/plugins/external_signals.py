from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from src.core.types.models import CueInput, CueKeyword, CuePluginResult, CueSignal


class ExternalSignalsPlugin:
    id = "buzzsprout"
    name = "Buzzsprout Snapshot"
    platform = "podcast"
    enabled = True

    def __init__(self, snapshot_path: str):
        self.snapshot_path = snapshot_path

    async def analyze(self, input: CueInput) -> CuePluginResult:
        if not self.snapshot_path:
            return CuePluginResult(
                pluginId=self.id,
                platform=self.platform,
                status="not_configured",
                input=input,
                warnings=["Buzzsprout snapshot path was not provided."],
            )

        try:
            payload = json.loads(Path(self.snapshot_path).read_text(encoding="utf-8"))
        except Exception as exc:
            return CuePluginResult(
                pluginId=self.id,
                platform=self.platform,
                status="error",
                input=input,
                warnings=[f"Buzzsprout snapshot unavailable: {exc}"],
            )

        if payload.get("source") != "buzzsprout":
            return CuePluginResult(
                pluginId=self.id,
                platform=self.platform,
                status="error",
                input=input,
                warnings=["External signals file was not a Buzzsprout snapshot."],
            )

        episodes = payload.get("episodes", []) if isinstance(payload.get("episodes"), list) else []
        top_episodes = payload.get("topEpisodes", []) if isinstance(payload.get("topEpisodes"), list) else []
        keywords = self._keywords(episodes)
        total_plays = self._int(payload.get("totalPlays"))
        episode_count = self._int(payload.get("episodeCount")) or len(episodes)

        return CuePluginResult(
            pluginId=self.id,
            platform=self.platform,
            status="ok",
            input=input,
            keywords=[CueKeyword(value=value, source=self.id, weight=0.65, presentInUserContent=True) for value in keywords[:12]],
            signals=[
                CueSignal(
                    type="freshness",
                    source=self.id,
                    value={
                        "episodeCount": episode_count,
                        "recentEpisodeTitles": payload.get("recentEpisodeTitles", []),
                    },
                    confidence=0.75 if episode_count else 0.35,
                ),
                CueSignal(
                    type="demand",
                    source=self.id,
                    value={
                        "totalPlays": total_plays,
                        "topEpisodes": top_episodes,
                        "note": "Buzzsprout plays are first-party podcast engagement signals from a sanitized Volma snapshot.",
                    },
                    confidence=0.75 if total_plays else 0.4,
                ),
            ],
            raw={
                "source": "buzzsprout",
                "podcastId": payload.get("podcastId", ""),
                "rssUrl": payload.get("rssUrl", ""),
                "episodeCount": episode_count,
                "totalPlays": total_plays,
                "topEpisodes": top_episodes,
            },
            warnings=["Buzzsprout stats came from a sanitized Volma snapshot; no Buzzsprout API token was provided to Cue Plugin Suite."],
        )

    def _keywords(self, episodes: List[Dict[str, Any]]) -> List[str]:
        seen: List[str] = []
        for episode in episodes[:10]:
            for tag in episode.get("tags", []) or []:
                self._add(seen, str(tag))
            title = str(episode.get("title", ""))
            for word in title.lower().replace("|", " ").replace(":", " ").split():
                clean = "".join(ch for ch in word if ch.isalnum() or ch == "-")
                if len(clean) >= 4 and clean not in {"podcast", "episode", "with", "from"}:
                    self._add(seen, clean)
        return seen

    def _add(self, seen: List[str], value: str) -> None:
        clean = value.strip()
        if clean and clean.lower() not in [item.lower() for item in seen]:
            seen.append(clean)

    def _int(self, value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0
