from __future__ import annotations

import os
from typing import Any, Dict, Iterable, List

from src.core.types.plugin import CuePlugin
from src.plugins.apple import ApplePodcastsSearchPlugin
from src.plugins.googleTrends import GoogleTrendsSignalPlugin
from src.plugins.meta import InstagramHashtagPlugin, MetaGraphPlugin
from src.plugins.rss import RssPlugin
from src.plugins.spotify import SpotifySearchPlugin
from src.plugins.tiktok import TikTokPlugin
from src.plugins.youtube import YouTubeAutocompletePlugin, YouTubeDataPlugin


PLUGIN_ENV = {
    "spotify": ["SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET"],
    "youtubeData": ["YOUTUBE_API_KEY"],
    "metaGraph": ["META_APP_ID", "META_APP_SECRET"],
}


PLUGIN_MESSAGES = {
    "spotify": "Spotify analysis is unavailable until platform credentials are configured.",
    "youtubeData": "YouTube signal analysis is optional and currently skipped until YOUTUBE_API_KEY is configured.",
    "metaGraph": "Meta Graph analysis is stubbed for v1 and not required for podcast plus YouTube workflow.",
    "instagramHashtag": "Instagram hashtag analysis is stubbed for v1.",
    "tiktok": "TikTok analysis is stubbed for v1.",
}


class CuePluginStatusService:
    def __init__(self, plugins: Iterable[CuePlugin] | None = None, last_status: Dict[str, str] | None = None):
        self.plugins = list(plugins) if plugins is not None else [
            RssPlugin(),
            ApplePodcastsSearchPlugin(),
            SpotifySearchPlugin(),
            GoogleTrendsSignalPlugin(),
            YouTubeDataPlugin(),
            YouTubeAutocompletePlugin(),
            MetaGraphPlugin(),
            InstagramHashtagPlugin(),
            TikTokPlugin(),
        ]
        self.last_status = last_status or {}

    def statuses(self) -> List[Dict[str, Any]]:
        return [self._status(plugin) for plugin in self.plugins]

    def _status(self, plugin: CuePlugin) -> Dict[str, Any]:
        plugin_id = getattr(plugin, "id", "unknown")
        required = PLUGIN_ENV.get(plugin_id, [])
        missing = [name for name in required if not os.environ.get(name)]
        configured = not missing
        if getattr(plugin, "enabled", True) is False:
            configured = False
        message = PLUGIN_MESSAGES.get(plugin_id)
        if not message:
            message = "Plugin is available." if configured else "Plugin is unavailable until required configuration is present."
        if configured and plugin_id in PLUGIN_ENV:
            message = "Plugin credentials are configured."
        return {
            "plugin_id": plugin_id,
            "plugin_name": getattr(plugin, "name", plugin_id),
            "platform": getattr(plugin, "platform", "unknown"),
            "enabled": getattr(plugin, "enabled", True),
            "configured": configured,
            "missing_environment_variables": missing,
            "last_run_status": self.last_status.get(plugin_id),
            "message": message,
        }

