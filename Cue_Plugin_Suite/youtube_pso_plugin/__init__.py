"""
Cue YouTube PSO Plugin
======================
Search optimization for YouTube using the free YouTube Data API v3.
Parallel architecture to the Cue Podcast PSO Plugin.

Modules:
  core/search_rank.py        — YouTube Data API v3 search rank detection
  core/autocomplete.py       — YouTube autocomplete keyword suggestions
  core/competitor_scraper.py — Top-ranking channel metadata scraper
  core/keyword_classifier.py — Term classification (DETECTED/COMPETITOR/LOCAL/DEAD)
  core/difficulty_scorer.py  — PSO score (0–100) + difficulty formula
  core/llm_writer.py         — Cue built-in LLM metadata writer
  core/doc_generator.py      — Word document output
  core/plugin.py             — Main YouTubePSOPlugin orchestrator

Usage:
  from cue_youtube_pso_plugin import YouTubePSOPlugin
  plugin = YouTubePSOPlugin(api_key="YOUR_YOUTUBE_DATA_API_KEY")
  results = plugin.run(channel_id="UCxxxxxxxx", keywords=["michigan politics", "detroit budget"])
"""

from .core.plugin import YouTubePSOPlugin

__all__ = ["YouTubePSOPlugin"]
__version__ = "1.0.0"
