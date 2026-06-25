"""
core/plugin.py
==============
Main YouTubePSOPlugin orchestrator.

Coordinates all five detection and intelligence modules:
  1. YouTubeSearchRank    — detect current rank for each keyword
  2. get_autocomplete_suggestions — expand and validate keywords
  3. CompetitorScraper    — profile top-ranking competitor channels
  4. YouTubeKeywordClassifier — classify all terms by source
  5. YouTubeDifficultyScorer  — calculate PSO score and difficulty
  6. YouTubeLLMWriter     — generate replacement metadata
  7. YouTubePSODocGenerator   — output Word document

Usage:
  plugin = YouTubePSOPlugin(api_key="YOUR_YOUTUBE_DATA_API_KEY")
  plugin.run(
      channel_id="UCxxxxxxxx",
      channel_name="The MiddleGround Mic",
      keywords=["michigan politics", "detroit budget", "michigan election 2026"],
      output_path="output/YouTube_PSO_Action_Plan.docx",
  )
"""

import os
import logging
from typing import List, Optional, Dict, Any

from .search_rank import YouTubeSearchRank, KeywordRankResult
from .autocomplete import get_autocomplete_suggestions, classify_autocomplete_signal
from .competitor_scraper import CompetitorScraper
from .keyword_classifier import YouTubeKeywordClassifier, ClassifiedKeyword
from .difficulty_scorer import YouTubeDifficultyScorer, DifficultyResult
from .llm_writer import YouTubeLLMWriter
from .doc_generator import YouTubePSODocGenerator

logger = logging.getLogger(__name__)


class YouTubePSOPlugin:
    """
    Full YouTube PSO pipeline — from keyword list to Word document.

    Credentials (all platform-level — users never configure these):
      YOUTUBE_API_KEY        — YouTube Data API v3 key (Cue org account)
      BUILT_IN_FORGE_API_URL — Cue built-in LLM endpoint
      BUILT_IN_FORGE_API_KEY — Cue built-in LLM bearer token
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        niche: str = "political commentary",
        geo: str = "michigan",
    ):
        self.api_key = api_key or os.environ.get("YOUTUBE_API_KEY", "")
        self.niche = niche
        self.geo = geo

        self.search_rank = YouTubeSearchRank(api_key=self.api_key)
        self.competitor_scraper = CompetitorScraper(api_key=self.api_key)
        self.classifier = YouTubeKeywordClassifier()
        self.scorer = YouTubeDifficultyScorer()
        self.llm_writer = YouTubeLLMWriter()

    def status(self) -> Dict[str, Any]:
        """Return plugin status and quota information."""
        return {
            "youtube_api_configured": self.search_rank.is_configured,
            "llm_configured": self.llm_writer.is_configured,
            "quota_status": self.search_rank.quota_status(),
            "niche": self.niche,
            "geo": self.geo,
        }

    def run(
        self,
        channel_id: str,
        channel_name: str,
        keywords: List[str],
        videos: Optional[List[Dict[str, str]]] = None,
        output_path: str = "output/YouTube_PSO_Action_Plan.docx",
        enrich_stats: bool = True,
        max_competitors: int = 5,
    ) -> Dict[str, Any]:
        """
        Run the full YouTube PSO pipeline.

        Args:
            channel_id: YouTube channel ID (e.g. "UCxxxxxxxx").
            channel_name: Human-readable channel name for the document.
            keywords: List of keywords to analyze.
            videos: Optional list of {"title": ..., "description": ...} dicts
                    for videos to generate replacement metadata for.
            output_path: Where to save the Word document.
            enrich_stats: Whether to fetch view/like counts for search results.
            max_competitors: How many competitor channels to profile.

        Returns:
            Dict with results summary and document path.
        """
        logger.info(f"Starting YouTube PSO analysis for {channel_name} ({channel_id})")
        logger.info(f"Keywords: {keywords}")

        # ── Step 1: Search rank detection ────────────────────────────────────
        logger.info("Step 1/6: Detecting YouTube search ranks...")
        rank_results = self.search_rank.batch_search(keywords, channel_id)

        if enrich_stats and rank_results:
            rank_results = self.search_rank.enrich_with_stats(rank_results)

        # ── Step 2: Autocomplete expansion ───────────────────────────────────
        logger.info("Step 2/6: Fetching YouTube autocomplete suggestions...")
        autocomplete_map: Dict[str, List[str]] = {}
        autocomplete_position_map: Dict[str, int] = {}

        for kw in keywords:
            suggestions = get_autocomplete_suggestions(kw)
            if suggestions:
                autocomplete_map[kw] = suggestions
                signal = classify_autocomplete_signal(kw, suggestions)
                if signal["detected"] and signal["position"]:
                    autocomplete_position_map[kw] = signal["position"]

        # ── Step 3: Competitor scraping ───────────────────────────────────────
        logger.info("Step 3/6: Profiling competitor channels...")
        competitor_profiles = self.competitor_scraper.scrape_competitors(
            rank_results,
            top_n_channels=max_competitors,
            exclude_channel_id=channel_id,
        )
        competitor_terms = self.competitor_scraper.extract_competitor_terms(competitor_profiles)

        # ── Step 4: Keyword classification ───────────────────────────────────
        logger.info("Step 4/6: Classifying keywords...")
        classified = self.classifier.classify_batch(
            keywords,
            autocomplete_map=autocomplete_map,
            competitor_terms=competitor_terms,
        )
        classified_sorted = self.classifier.sort_by_priority(classified)

        # ── Step 5: Difficulty scoring ────────────────────────────────────────
        logger.info("Step 5/6: Calculating PSO scores...")
        difficulty_results = self.scorer.score_batch(
            rank_results,
            competitor_profiles=competitor_profiles,
            autocomplete_map=autocomplete_position_map,
        )

        # ── Step 6: LLM metadata generation ──────────────────────────────────
        generated_metadata = []
        if videos:
            logger.info(f"Step 6/6: Generating replacement metadata for {len(videos)} videos...")
            detected_kws = [c.keyword for c in classified if c.classification == "DETECTED"]
            competitor_kws = [c.keyword for c in classified if c.classification == "COMPETITOR"]
            local_kws = [c.keyword for c in classified if c.classification == "LOCAL"]
            entity_kws = [c.keyword for c in classified if c.classification == "GUEST"]

            for video in videos[:20]:  # Cap at 20 videos per run
                meta = self.llm_writer.generate_metadata(
                    current_title=video.get("title", ""),
                    current_description=video.get("description", ""),
                    topic=video.get("topic", keywords[0] if keywords else ""),
                    detected_keywords=detected_kws,
                    competitor_keywords=competitor_kws,
                    local_keywords=local_kws,
                    entity_keywords=entity_kws,
                    channel_name=channel_name,
                )
                meta["original_title"] = video.get("title", "")
                generated_metadata.append(meta)
        else:
            logger.info("Step 6/6: No videos provided — skipping metadata generation.")

        # ── Step 7: Generate Word document ────────────────────────────────────
        logger.info("Step 7/7: Generating Word document...")
        doc_gen = YouTubePSODocGenerator(channel_name=channel_name)
        doc_path = doc_gen.generate(
            keyword_results=rank_results,
            difficulty_results=difficulty_results,
            competitor_profiles=competitor_profiles,
            classified_keywords=classified_sorted,
            generated_metadata=generated_metadata,
            output_path=output_path,
        )

        summary = {
            "channel_id": channel_id,
            "channel_name": channel_name,
            "keywords_analyzed": len(keywords),
            "keywords_ranking": sum(1 for r in rank_results if r.is_ranking),
            "top_opportunity": difficulty_results[0].keyword if difficulty_results else None,
            "top_pso_score": difficulty_results[0].pso_score if difficulty_results else 0,
            "competitor_channels_profiled": len(competitor_profiles),
            "videos_with_new_metadata": len(generated_metadata),
            "quota_used": self.search_rank.units_used,
            "quota_remaining": self.search_rank.units_remaining,
            "document_path": doc_path,
        }

        logger.info(f"YouTube PSO analysis complete. Document saved to {doc_path}")
        logger.info(f"Quota used: {summary['quota_used']}/10,000 units")
        return summary

    def youtube_quota_status(self) -> Dict[str, Any]:
        """Return current YouTube API quota status."""
        return self.search_rank.quota_status()
