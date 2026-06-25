from __future__ import annotations

from typing import Protocol

from .models import CueInput, CuePluginResult


class CuePlugin(Protocol):
    id: str
    name: str
    platform: str
    enabled: bool

    async def analyze(self, input: CueInput) -> CuePluginResult:
        ...

