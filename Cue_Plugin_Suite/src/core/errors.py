from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class CueErrorResponse:
    plugin_id: str
    error_type: str
    message: str
    recoverable: bool = True
    user_action_required: Optional[str] = None
    debug_detail: Optional[str] = None

    def as_warning(self, debug: bool = False) -> str:
        suffix = f" Debug: {self.debug_detail}" if debug and self.debug_detail else ""
        action = f" Action: {self.user_action_required}" if self.user_action_required else ""
        return f"{self.plugin_id} {self.error_type}: {self.message}{action}{suffix}"

