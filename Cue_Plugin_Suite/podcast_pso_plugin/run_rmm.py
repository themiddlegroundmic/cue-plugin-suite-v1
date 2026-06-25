"""
run_rmm.py
==========
Standalone runner for Raging MI Moderates PSO audit.

Usage:
    cd cue_pso_plugin
    python run_rmm.py

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

RMM_FEED_URL = "https://feeds.buzzsprout.com/2592190.rss"
RMM_SHOW_NAME = "Raging MI Moderates"
RMM_ITUNES_ID = "2592190"

OUTPUT_DIR = "output"

if __name__ == "__main__":
    plugin = PSOPlugin(
        feed_url=RMM_FEED_URL,
        show_name=RMM_SHOW_NAME,
        show_itunes_id=RMM_ITUNES_ID,
        cue_api_url=os.environ.get("BUILT_IN_FORGE_API_URL", ""),
        cue_api_key=os.environ.get("BUILT_IN_FORGE_API_KEY", ""),
        # Spotify credentials are read automatically from SPOTIFY_CLIENT_ID
        # and SPOTIFY_CLIENT_SECRET platform environment variables.
        # Users do not configure Spotify — Cue manages one shared app.
        run_llm=bool(os.environ.get("BUILT_IN_FORGE_API_KEY")),
        llm_max_episodes=12,
    )

    report = plugin.run()
    plugin.export_docx(report, f"{OUTPUT_DIR}/RMM_PSO_Action_Plan.docx")
    plugin.export_json(report, f"{OUTPUT_DIR}/RMM_PSO_Report.json")

    print(f"\nDone. Files saved to ./{OUTPUT_DIR}/")
