"""
run_mgm_youtube.py
==================
Standalone runner for The MiddleGround Mic YouTube PSO analysis.

Usage:
  export YOUTUBE_API_KEY="your-key-here"
  export BUILT_IN_FORGE_API_URL="your-cue-api-url"
  export BUILT_IN_FORGE_API_KEY="your-cue-api-key"
  python run_mgm_youtube.py

Output: output/MGM_YouTube_PSO_Action_Plan.docx
"""

import logging
import json
from cue_youtube_pso_plugin import YouTubePSOPlugin

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ── MGM channel configuration ─────────────────────────────────────────────────
CHANNEL_ID = "UCxxxxxxxxxxxxxxxx"   # Replace with actual MGM YouTube channel ID
CHANNEL_NAME = "The MiddleGround Mic"

# Keywords derived from the Master YouTube Guide topic clusters
KEYWORDS = [
    "michigan politics",
    "michigan election 2026",
    "detroit city budget",
    "michigan legislature",
    "michigan governor",
    "grand rapids politics",
    "michigan school funding",
    "michigan economy",
    "michigan housing crisis",
    "michigan water crisis",
    "michigan redistricting",
    "michigan supreme court",
    "michigan police reform",
    "michigan energy policy",
    "michigan roads funding",
    "midwest political commentary",
    "independent political analysis",
    "political commentary michigan",
]

# Sample videos to generate replacement metadata for
# Replace with actual video titles and descriptions from your channel
VIDEOS = [
    {
        "title": "Michigan Budget 2025 Explained",
        "description": "We break down the Michigan state budget for 2025.",
        "topic": "michigan state budget",
    },
    {
        "title": "Detroit City Council Vote",
        "description": "The Detroit city council voted on a major ordinance this week.",
        "topic": "detroit city council",
    },
]

if __name__ == "__main__":
    plugin = YouTubePSOPlugin(niche="political commentary", geo="michigan")

    print("\n=== Cue YouTube PSO Plugin — The MiddleGround Mic ===\n")
    print("Status:", json.dumps(plugin.status(), indent=2))

    results = plugin.run(
        channel_id=CHANNEL_ID,
        channel_name=CHANNEL_NAME,
        keywords=KEYWORDS,
        videos=VIDEOS,
        output_path="output/MGM_YouTube_PSO_Action_Plan.docx",
    )

    print("\n=== Results Summary ===")
    for key, value in results.items():
        print(f"  {key}: {value}")
    print(f"\nDocument saved to: {results['document_path']}")
