from __future__ import annotations

from typing import Any, Dict

from src.core.exports.json_exporter import JsonCueExporter, WordCueExporter
from src.core.scoring.scorer import CueScorer
from src.core.types.models import CueInput, CueIntelligenceReport, CueWriterRequest, to_jsonable
from src.core.writer.writer import CueIntelligenceWriter
from src.services.orchestrator import CueAnalysisService


def _input(payload: Dict[str, Any]) -> CueInput:
    return CueInput(**payload)


def analyze(payload: Dict[str, Any]) -> Dict[str, Any]:
    report = CueAnalysisService().analyze(_input(payload))
    return to_jsonable(report)


def score(payload: Dict[str, Any]) -> Dict[str, Any]:
    if "pluginResults" in payload:
        raise ValueError("Use CueIntelligenceEngine for structured report scoring; raw pluginResults must be dataclass instances.")
    report = CueAnalysisService().analyze(_input(payload))
    return to_jsonable(report.scoreBreakdown)


def write(report: CueIntelligenceReport, target_platform: str = "podcast") -> Dict[str, Any]:
    output = CueIntelligenceWriter().write(CueWriterRequest(intelligenceReport=report, targetPlatform=target_platform))
    return to_jsonable(output)


def export_json(report: CueIntelligenceReport, writer_output=None) -> Dict[str, Any]:
    return JsonCueExporter().export(report, writer_output).payload


def export_word_stub() -> Dict[str, Any]:
    return to_jsonable(WordCueExporter().export())

