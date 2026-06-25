from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional


@dataclass
class TrackedShow:
    id: str
    title: str
    rssUrl: str = ""
    platform: str = "podcast"
    createdAt: datetime = field(default_factory=datetime.utcnow)


@dataclass
class TrackedEpisode:
    id: str
    showId: str
    title: str
    episodeUrl: str = ""
    createdAt: datetime = field(default_factory=datetime.utcnow)


@dataclass
class WeeklyRankSnapshot:
    id: str
    showId: str
    episodeId: Optional[str]
    platform: str
    keyword: str
    rank: Optional[int]
    score: Optional[int]
    competitorCount: int
    snapshotDate: date
    createdAt: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ScoreHistory:
    id: str
    showId: str
    episodeId: Optional[str]
    platform: str
    keyword: str
    score: int
    snapshotDate: date
    createdAt: datetime = field(default_factory=datetime.utcnow)


@dataclass
class CompetitorSnapshot:
    id: str
    showId: str
    episodeId: Optional[str]
    platform: str
    keyword: str
    rank: Optional[int]
    score: Optional[int]
    competitorCount: int
    snapshotDate: date
    createdAt: datetime = field(default_factory=datetime.utcnow)


TRACKING_TABLE_SQL = """
CREATE TABLE trackedShows (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  rssUrl TEXT,
  platform TEXT NOT NULL,
  createdAt TEXT NOT NULL
);

CREATE TABLE trackedEpisodes (
  id TEXT PRIMARY KEY,
  showId TEXT NOT NULL,
  title TEXT NOT NULL,
  episodeUrl TEXT,
  createdAt TEXT NOT NULL
);

CREATE TABLE weeklyRankSnapshots (
  id TEXT PRIMARY KEY,
  showId TEXT NOT NULL,
  episodeId TEXT,
  platform TEXT NOT NULL,
  keyword TEXT NOT NULL,
  rank INTEGER,
  score INTEGER,
  competitorCount INTEGER NOT NULL,
  snapshotDate TEXT NOT NULL,
  createdAt TEXT NOT NULL
);

CREATE TABLE scoreHistory (
  id TEXT PRIMARY KEY,
  showId TEXT NOT NULL,
  episodeId TEXT,
  platform TEXT NOT NULL,
  keyword TEXT NOT NULL,
  score INTEGER NOT NULL,
  snapshotDate TEXT NOT NULL,
  createdAt TEXT NOT NULL
);

CREATE TABLE competitorSnapshots (
  id TEXT PRIMARY KEY,
  showId TEXT NOT NULL,
  episodeId TEXT,
  platform TEXT NOT NULL,
  keyword TEXT NOT NULL,
  rank INTEGER,
  score INTEGER,
  competitorCount INTEGER NOT NULL,
  snapshotDate TEXT NOT NULL,
  createdAt TEXT NOT NULL
);
"""

