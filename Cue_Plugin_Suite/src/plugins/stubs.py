from __future__ import annotations

from src.core.types.models import CueInput, CuePluginResult


class NotImplementedCuePlugin:
    id = "notImplemented"
    name = "Not Implemented"
    platform = "unknown"
    enabled = False

    async def analyze(self, input: CueInput) -> CuePluginResult:
        return CuePluginResult(
            pluginId=self.id,
            platform=self.platform,
            status="not_implemented",
            input=input,
            warnings=[f"{self.name} follows the CuePlugin contract but is not implemented in v1."],
        )

