from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from src.core.types.models import CueExportResult, CueIntelligenceReport, CueWriterOutput, to_jsonable


class JsonCueExporter:
    def export(
        self,
        report: CueIntelligenceReport,
        writer_output: Optional[CueWriterOutput] = None,
        path: Optional[str] = None,
    ) -> CueExportResult:
        payload = {
            "input": report.input,
            "showMetadata": report.show,
            "episodeMetadata": report.show.episodes if report.show else [],
            "pluginResultsSummary": [
                {
                    "pluginId": r.pluginId,
                    "platform": r.platform,
                    "status": r.status,
                    "signalCount": len(r.signals),
                    "competitorCount": len(r.competitors),
                    "warnings": r.warnings,
                }
                for r in report.pluginResults
            ],
            "intelligenceReport": report,
            "scoreBreakdown": report.scoreBreakdown,
            "writerOutput": writer_output,
            "createdAt": datetime.utcnow(),
            "version": report.version,
        }
        jsonable = to_jsonable(payload)
        if path:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(jsonable, f, indent=2)
        return CueExportResult(format="json", payload=jsonable)


class WordCueExporter:
    def export(self, *args: Any, **kwargs: Any) -> CueExportResult:
        return CueExportResult(
            format="docx",
            payload={
                "status": "not_implemented",
                "message": "Word export is stubbed in v1. Use JSON export until document dependencies are wired into the host app.",
            },
        )
