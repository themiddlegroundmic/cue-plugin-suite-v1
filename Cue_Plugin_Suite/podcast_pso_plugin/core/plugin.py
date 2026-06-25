"""
plugin.py
=========
Main PSOPlugin orchestrator — ties all modules together into a single
callable interface that mirrors how it will be integrated into the Cue app.

Usage (standalone):
    from cue_pso_plugin import PSOPlugin

    plugin = PSOPlugin(
        feed_url="https://feeds.buzzsprout.com/2465711.rss",
        show_name="The MiddleGround Mic",
        cue_api_url="https://your-cue-instance/api",
        cue_api_key="your-built-in-key",
        spotify_client_id="optional",
        spotify_client_secret="optional",
    )
    report = plugin.run()
    plugin.export_docx(report, "output/MGM_PSO_Report.docx")

Usage (as Cue plugin — called from tRPC router):
    The plugin exposes run() and export_docx() which map directly to
    tRPC procedures in server/routers/pso.ts
"""

import os
from typing import Dict, List, Optional

from .feed_parser import FeedParser, Show
from .apple_detector import AppleDetector
from .spotify_detector import SpotifyDetector
from .trends_detector import TrendsDetector
from .competitor_scraper import CompetitorScraper
from .keyword_classifier import KeywordClassifier
from .difficulty_scorer import DifficultyScorer
from .llm_writer import LLMWriter
from .doc_generator import DocGenerator


# ── Default topic clusters for political commentary shows ────────────────────
# These seed the keyword detection. The plugin expands them via competitor data.
DEFAULT_TOPIC_CLUSTERS = [
    "michigan politics",
    "michigan legislature",
    "michigan governor",
    "michigan redistricting",
    "political commentary",
    "iran nuclear deal",
    "trump tariffs",
    "ukraine war",
    "supreme court",
    "2024 election",
    "2026 midterms",
    "political podcast",
    "news analysis",
    "conservative podcast",
    "independent politics",
]


class PSOPlugin:
    """
    Full PSO pipeline for a single podcast show.
    """

    def __init__(
        self,
        feed_url: str,
        show_name: str,
        cue_api_url: str,
        cue_api_key: str,
        show_itunes_id: Optional[str] = None,
        show_spotify_id: Optional[str] = None,
        topic_clusters: Optional[List[str]] = None,
        country: str = "us",
        geo: str = "US",
        run_llm: bool = True,
        llm_max_episodes: int = 20,
    ):
        self.feed_url = feed_url
        self.show_name = show_name
        self.cue_api_url = cue_api_url
        self.cue_api_key = cue_api_key
        self.show_itunes_id = show_itunes_id
        self.show_spotify_id = show_spotify_id
        self.topic_clusters = topic_clusters or DEFAULT_TOPIC_CLUSTERS
        self.country = country
        self.geo = geo
        self.run_llm = run_llm
        self.llm_max_episodes = llm_max_episodes

        # Spotify credentials are PLATFORM-LEVEL secrets managed by Cue.
        # Users never configure these — they are injected from the Cue
        # platform environment the same way BUILT_IN_FORGE_API_KEY is.
        # Register once at https://developer.spotify.com/dashboard under
        # the Cue organization account. All users share the platform app.
        spotify_client_id = os.environ.get("SPOTIFY_CLIENT_ID", "")
        spotify_client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET", "")

        # Module instances
        self._feed_parser = FeedParser(feed_url)
        self._apple = AppleDetector(
            show_itunes_id=show_itunes_id,
            show_title=show_name,
            country=country,
        )
        self._spotify = None
        if SpotifyDetector.is_configured(spotify_client_id, spotify_client_secret):
            self._spotify = SpotifyDetector(
                client_id=spotify_client_id,
                client_secret=spotify_client_secret,
                show_name=show_name,
                show_spotify_id=show_spotify_id,
            )
        else:
            print("[PSOPlugin] Spotify not configured — add SPOTIFY_CLIENT_ID and "
                  "SPOTIFY_CLIENT_SECRET to the Cue platform environment. "
                  "Register a free app at https://developer.spotify.com/dashboard")
        self._trends = TrendsDetector(geo=geo)
        self._competitor = CompetitorScraper()
        self._scorer = DifficultyScorer()
        self._llm = LLMWriter(api_url=cue_api_url, api_key=cue_api_key) if run_llm else None
        self._docgen = DocGenerator()

    def run(self) -> Dict:
        """
        Execute the full PSO pipeline.
        Returns a report dict containing show, keyword_intelligence, llm_outputs.
        """
        print(f"\n{'='*60}")
        print(f"Cue PSO Plugin — {self.show_name}")
        print(f"{'='*60}\n")

        # Step 1: Parse feed
        print("[1/6] Parsing RSS feed...")
        show = self._feed_parser.parse()
        print(f"      Found {len(show.episodes)} episodes")

        # Step 2: Score all episodes
        print("[2/6] Scoring episodes...")
        show = self._scorer.score_show(show)
        p1 = sum(1 for e in show.episodes if e.priority == "P1")
        p2 = sum(1 for e in show.episodes if e.priority == "P2")
        p3 = sum(1 for e in show.episodes if e.priority == "P3")
        print(f"      P1: {p1}  P2: {p2}  P3: {p3}")

        # Step 3: Keyword detection (Apple + Spotify + Trends)
        print("[3/6] Running keyword detection...")
        keyword_intelligence = {}

        for kw in self.topic_clusters:
            apple_rank, competitors = self._apple.get_rank(kw)
            spotify_rank = None
            if self._spotify:
                spotify_rank, _ = self._spotify.get_rank(kw)

            # Competitor scraping for this keyword
            comp_list = self._apple.get_competitors(kw, top_n=5)
            comp_terms = self._competitor.scrape_competitors(comp_list)

            # Difficulty score
            diff = self._scorer.score_keyword_difficulty(comp_list)

            # Demand signal
            demand = self._trends.get_demand_score(kw)

            keyword_intelligence[kw] = {
                "apple_rank": apple_rank,
                "spotify_rank": spotify_rank,
                "demand": demand,
                "difficulty": diff,
                "competitors": comp_list[:5],
                "competitor_terms": list(comp_terms.keys())[:20],
            }

        # Step 4: Classify keywords per episode
        print("[4/6] Classifying keywords per episode...")
        episode_keyword_data = {}
        p1_episodes = [e for e in show.episodes if e.priority == "P1"][:self.llm_max_episodes]

        for ep in p1_episodes:
            # Build candidate terms from all detected keywords
            all_detected = [kw for kw, data in keyword_intelligence.items()
                            if data.get("apple_rank") is not None]
            all_competitor = {}
            for data in keyword_intelligence.values():
                for term in data.get("competitor_terms", []):
                    all_competitor[term] = all_competitor.get(term, 0) + 1

            classifier = KeywordClassifier(
                detected_terms=all_detected,
                competitor_terms=all_competitor,
                episode_text=f"{ep.title} {ep.description or ''}",
                guest_names=[],
                show_brand=self.show_name,
            )
            classified = classifier.classify()

            # Attach rank data to episode
            ep.detected_keywords = classified.get("detected", [])
            ep.apple_rank = keyword_intelligence.get(
                ep.detected_keywords[0] if ep.detected_keywords else "", {}
            ).get("apple_rank")

            episode_keyword_data[ep.guid] = {
                "detected": classified.get("detected", []),
                "factual": classified.get("factual", []),
                "local": classified.get("local", []),
                "guest": classified.get("guest", []),
                "competitor_terms": list(all_competitor.keys())[:10],
            }

        # Step 5: LLM metadata generation
        llm_outputs = {}
        if self._llm and p1_episodes:
            print(f"[5/6] Generating AI metadata for {len(p1_episodes)} P1 episodes...")
            llm_outputs = self._llm.write_batch(
                episodes=p1_episodes,
                keyword_data=episode_keyword_data,
                show_brand=self.show_name,
                max_episodes=self.llm_max_episodes,
            )
        else:
            print("[5/6] LLM disabled — skipping metadata generation")

        print("[6/6] Pipeline complete.")
        return {
            "show": show,
            "keyword_intelligence": keyword_intelligence,
            "llm_outputs": llm_outputs,
            "episode_keyword_data": episode_keyword_data,
        }

    def export_docx(self, report: Dict, output_path: str):
        """Export the PSO report as a Word document."""
        self._docgen.generate(
            show=report["show"],
            keyword_intelligence=report["keyword_intelligence"],
            llm_outputs=report["llm_outputs"],
            output_path=output_path,
        )

    def export_json(self, report: Dict, output_path: str):
        """Export the keyword intelligence as JSON (for the Cue app API)."""
        import json
        from datetime import datetime

        def serialize(obj):
            if hasattr(obj, "__dict__"):
                return {k: serialize(v) for k, v in obj.__dict__.items()
                        if not k.startswith("_")}
            if isinstance(obj, list):
                return [serialize(i) for i in obj]
            if isinstance(obj, dict):
                return {k: serialize(v) for k, v in obj.items()}
            if hasattr(obj, "isoformat"):
                return obj.isoformat()
            return obj

        data = {
            "generated_at": datetime.utcnow().isoformat(),
            "show": serialize(report["show"]),
            "keyword_intelligence": report["keyword_intelligence"],
            "llm_outputs": report["llm_outputs"],
        }
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2, default=str)
        print(f"[PSOPlugin] JSON saved: {output_path}")
