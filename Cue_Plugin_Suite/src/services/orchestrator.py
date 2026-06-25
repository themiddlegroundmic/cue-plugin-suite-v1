from __future__ import annotations

import asyncio
from typing import Iterable, List

from src.core.errors import CueErrorResponse
from src.core.intelligence.engine import CueIntelligenceEngine
from src.core.types.models import CueInput, CueIntelligenceReport, CuePluginResult
from src.core.types.plugin import CuePlugin
from src.plugins.apple import ApplePodcastsSearchPlugin
from src.plugins.googleTrends import GoogleTrendsSignalPlugin
from src.plugins.rss import RssPlugin
from src.plugins.spotify import SpotifySearchPlugin
from src.plugins.youtube import YouTubeDataPlugin


class CueAnalysisService:
    def __init__(
        self,
        plugins: Iterable[CuePlugin] | None = None,
        engine: CueIntelligenceEngine | None = None,
        enrichment_plugins: Iterable[CuePlugin] | None = None,
        debug: bool = False,
    ):
        self.plugins = list(plugins) if plugins is not None else [
            RssPlugin(),
            ApplePodcastsSearchPlugin(),
            SpotifySearchPlugin(),
            GoogleTrendsSignalPlugin(),
        ]
        self.enrichment_plugins = list(enrichment_plugins) if enrichment_plugins is not None else [YouTubeDataPlugin()]
        self.engine = engine or CueIntelligenceEngine()
        self.debug = debug

    async def analyze_async(self, input: CueInput) -> CueIntelligenceReport:
        results: List[CuePluginResult] = []
        for plugin in self.plugins:
            if getattr(plugin, "enabled", True):
                results.append(await self._safe_analyze(plugin, input))

        initial_report = self.engine.build_report(input, results)
        enrichment_input = self._enrichment_input(input, initial_report)
        for plugin in self.enrichment_plugins:
            if getattr(plugin, "enabled", True):
                results.append(await self._safe_analyze(plugin, enrichment_input))
        return self.engine.build_report(input, results)

    def analyze(self, input: CueInput) -> CueIntelligenceReport:
        return asyncio.run(self.analyze_async(input))

    async def _safe_analyze(self, plugin: CuePlugin, input: CueInput) -> CuePluginResult:
        try:
            return await plugin.analyze(input)
        except Exception as exc:
            error = CueErrorResponse(
                plugin_id=getattr(plugin, "id", "unknown"),
                error_type=exc.__class__.__name__,
                message="Plugin analysis failed; the remaining analysis continued.",
                recoverable=True,
                user_action_required="Check platform credentials or retry later.",
                debug_detail=str(exc),
            )
            return CuePluginResult(
                pluginId=error.plugin_id,
                platform=getattr(plugin, "platform", "unknown"),
                status="error",
                input=input,
                warnings=[error.as_warning(debug=self.debug)],
                raw={"error": error.__dict__},
            )

    def _enrichment_input(self, input: CueInput, report: CueIntelligenceReport) -> CueInput:
        gap_topics = [gap.get("gap_topic", "") for gap in report.contentGaps if isinstance(gap, dict)]
        keywords = [keyword.value for keyword in report.keywords[:8]]
        alternate = []
        for value in [*input.alternateKeywords, *keywords, *gap_topics]:
            if value and value not in alternate:
                alternate.append(value)
        return CueInput(
            rssUrl=input.rssUrl,
            showUrl=input.showUrl,
            episodeUrl=input.episodeUrl,
            youtubeChannelUrl=input.youtubeChannelUrl,
            facebookUrl=input.facebookUrl,
            instagramUrl=input.instagramUrl,
            tiktokUrl=input.tiktokUrl,
            manualTopic=input.manualTopic or report.primaryTopic,
            targetPlatform=input.targetPlatform,
            alternateKeywords=alternate[:10],
        )
