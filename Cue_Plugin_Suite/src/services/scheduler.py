from __future__ import annotations

import logging
from datetime import time


DEFAULT_WEEKLY_HEARTBEAT = {
    "day": "Sunday",
    "time": time(hour=3, minute=0),
    "timezone": "host",
}


def run_weekly_tracking_heartbeat() -> dict:
    message = "Weekly tracking heartbeat stub: would refresh trackedShows, trackedEpisodes, weeklyRankSnapshots, scoreHistory, and competitorSnapshots."
    logging.getLogger(__name__).info(message)
    return {"status": "planned", "schedule": DEFAULT_WEEKLY_HEARTBEAT, "message": message}

