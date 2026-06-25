"""
run_mgm.py
==========
Standalone runner for The MiddleGround Mic PSO audit.

Usage:
    cd cue_pso_plugin
    python run_mgm.py

Environment variables required (set in .env or Cue platform):
    BUILT_IN_FORGE_API_URL   — Cue LLM API base URL
    BUILT_IN_FORGE_API_KEY   — Cue LLM API key

Optional (for Spotify rank data):
    SPOTIFY_CLIENT_ID
    SPOTIFY_CLIENT_SECRET
"""

import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from core.plugin import PSOPlugin

MGM_FEED_URL = "https://feeds.buzzsprout.com/2465711.rss"
MGM_SHOW_NAME = "The MiddleGround Mic"
MGM_ITUNES_ID = "2465711"

OUTPUT_DIR = "output"

if __name__ == "__main__":
    plugin = PSOPlugin(
        feed_url=MGM_FEED_URL,
        show_name=MGM_SHOW_NAME,
        show_itunes_id=MGM_ITUNES_ID,
        cue_api_url=os.environ.get("BUILT_IN_FORGE_API_URL", ""),
        cue_api_key=os.environ.get("BUILT_IN_FORGE_API_KEY", ""),
        # Spotify credentials are read automatically from SPOTIFY_CLIENT_ID
        # and SPOTIFY_CLIENT_SECRET platform environment variables.
        # Users do not configure Spotify — Cue manages one shared app.
        run_llm=bool(os.environ.get("BUILT_IN_FORGE_API_KEY")),
        llm_max_episodes=20,
    )

    report = plugin.run()
    plugin.export_docx(report, f"{OUTPUT_DIR}/MGM_PSO_Action_Plan.docx")
    plugin.export_json(report, f"{OUTPUT_DIR}/MGM_PSO_Report.json")

    print(f"\nDone. Files saved to ./{OUTPUT_DIR}/")
