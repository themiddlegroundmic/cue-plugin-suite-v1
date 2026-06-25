from __future__ import annotations

from typing import Any, Dict, Optional

from src.core.types.models import CueRequestContext


def ok(data: Dict[str, Any] | list[Any] | None = None, **extra: Any) -> Dict[str, Any]:
    response: Dict[str, Any] = {"ok": True}
    if data is not None:
        response["data"] = data
    response.update(extra)
    return response


def error_response(
    code: str,
    message: str,
    recoverable: bool = True,
    user_action_required: bool = False,
    context: Optional[CueRequestContext] = None,
    debug_detail: Optional[str] = None,
    **extra: Any,
) -> Dict[str, Any]:
    error: Dict[str, Any] = {
        "code": code,
        "message": message,
        "recoverable": recoverable,
        "user_action_required": user_action_required,
    }
    if context and context.debug and debug_detail:
        error["debug_detail"] = debug_detail
    error.update(extra)
    return {"ok": False, "error": error}

