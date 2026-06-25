from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional


Platform = Literal["podcast", "youtube", "facebook", "instagram", "tiktok"]


@dataclass
class CueRequestContext:
    tenant_id: str = "local"
    user_id: str = "cli"
    workspace_id: Optional[str] = None
    roles: List[str] = field(default_factory=list)
    debug: bool = False


@dataclass
class CueInput:
    rssUrl: Optional[str] = None
    showUrl: Optional[str] = None
    episodeUrl: Optional[str] = None
    youtubeChannelUrl: Optional[str] = None
    facebookUrl: Optional[str] = None
    instagramUrl: Optional[str] = None
    tiktokUrl: Optional[str] = None
    manualTopic: Optional[str] = None
    targetPlatform: Platform = "podcast"
    alternateKeywords: List[str] = field(default_factory=list)


@dataclass
class CueEpisode:
    guid: str
    title: str
    description: str = ""
    publishedAt: Optional[datetime] = None
    durationSeconds: Optional[int] = None
    link: str = ""
    author: str = ""
    categories: List[str] = field(default_factory=list)
    image: str = ""
    chapters: List[Dict[str, Any]] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)


@dataclass
class CueShow:
    title: str
    description: str = ""
    author: str = ""
    feedUrl: str = ""
    link: str = ""
    categories: List[str] = field(default_factory=list)
    image: str = ""
    language: str = "en"
    episodes: List[CueEpisode] = field(default_factory=list)


@dataclass
class CueKeyword:
    value: str
    source: str = "derived"
    weight: float = 1.0
    presentInUserContent: bool = False


@dataclass
class CueSignal:
    type: str
    source: str
    value: Any
    confidence: float = 0.5
    notes: str = ""


@dataclass
class CuePluginResult:
    pluginId: str
    platform: str
    status: Literal["ok", "not_configured", "not_implemented", "error"] = "ok"
    input: Optional[CueInput] = None
    show: Optional[CueShow] = None
    episodes: List[CueEpisode] = field(default_factory=list)
    signals: List[CueSignal] = field(default_factory=list)
    competitors: List[Dict[str, Any]] = field(default_factory=list)
    keywords: List[CueKeyword] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)


@dataclass
class CueScoreDetail:
    score: int
    label: str
    factors: List[str] = field(default_factory=list)
    explanation: str = ""
    warnings: List[str] = field(default_factory=list)


@dataclass
class CueScoreBreakdown:
    opportunityScore: int
    platformReadinessScore: int
    confidenceScore: int
    opportunityComponents: Dict[str, float]
    readinessComponents: Dict[str, float]
    confidenceComponents: Dict[str, float]
    opportunity: Optional[CueScoreDetail] = None
    platformReadiness: Optional[CueScoreDetail] = None
    confidence: Optional[CueScoreDetail] = None


@dataclass
class CueIntelligenceReport:
    input: CueInput
    primaryTopic: str
    keywords: List[CueKeyword]
    detectedEntities: List[str]
    competitors: List[Dict[str, Any]]
    demandSignals: List[CueSignal]
    competitionSignals: List[CueSignal]
    freshnessSignals: List[CueSignal]
    contentGaps: List[Dict[str, Any]]
    riskFlags: List[str]
    confidenceScore: int
    opportunityScore: int
    platformReadinessScore: int
    scoreBreakdown: CueScoreBreakdown
    pluginResults: List[CuePluginResult] = field(default_factory=list)
    show: Optional[CueShow] = None
    createdAt: datetime = field(default_factory=datetime.utcnow)
    version: str = "1.0.0"


@dataclass
class CueWriterRequest:
    intelligenceReport: CueIntelligenceReport
    targetPlatform: Platform = "podcast"
    episode: Optional[CueEpisode] = None


@dataclass
class CueWriterOutput:
    generatedText: Dict[str, Any]
    whyThisWorks: List[str]
    keywordsUsed: List[str]
    riskNotes: List[str]
    scoreImpactEstimate: Dict[str, int]


@dataclass
class CueExportResult:
    format: str
    payload: Any
    createdAt: datetime = field(default_factory=datetime.utcnow)
    version: str = "1.0.0"


def to_jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value):
        return {k: to_jsonable(v) for k, v in asdict(value).items()}
    if isinstance(value, list):
        return [to_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: to_jsonable(v) for k, v in value.items()}
    return value
