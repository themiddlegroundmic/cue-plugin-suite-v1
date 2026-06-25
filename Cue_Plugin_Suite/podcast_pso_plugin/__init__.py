"""
Cue PSO Plugin  v1.0.0
======================
Podcast Search Optimization module for the Cue platform.

Replaces Ausha PSO Control Panel ($50/month) using 100% free public APIs
plus Cue's own built-in LLM — no third-party AI model required.

Data sources:
  - iTunes Search API          (Apple Podcasts rank — free, no key)
  - Spotify Web API            (Spotify rank — free, client credentials)
  - Google Trends via pytrends (demand signal — free, no key)
  - Competitor RSS feeds       (metadata scrape — free, public)
  - Cue Built-in LLM           (metadata writer — BUILT_IN_FORGE_API)

Quick start:
    from cue_pso_plugin import PSOPlugin

    plugin = PSOPlugin(
        feed_url="https://feeds.buzzsprout.com/2465711.rss",
        cue_api_url="https://your-cue-instance/api",   # BUILT_IN_FORGE_API_URL
        cue_api_key="your-built-in-key",               # BUILT_IN_FORGE_API_KEY
        spotify_client_id="optional",
        spotify_client_secret="optional",
    )
    report = plugin.run()
    plugin.export_docx(report, "output/MGM_PSO_Report.docx")
"""

from .core.plugin import PSOPlugin
from .core.feed_parser import FeedParser
from .core.apple_detector import AppleDetector
from .core.spotify_detector import SpotifyDetector
from .core.trends_detector import TrendsDetector
from .core.competitor_scraper import CompetitorScraper
from .core.keyword_classifier import KeywordClassifier
from .core.difficulty_scorer import DifficultyScorer
from .core.llm_writer import LLMWriter
from .core.doc_generator import DocGenerator

__version__ = "1.0.0"
__author__ = "Cue Platform"
__all__ = [
    "PSOPlugin",
    "FeedParser",
    "AppleDetector",
    "SpotifyDetector",
    "TrendsDetector",
    "CompetitorScraper",
    "KeywordClassifier",
    "DifficultyScorer",
    "LLMWriter",
    "DocGenerator",
]
