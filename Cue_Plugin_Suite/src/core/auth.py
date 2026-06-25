from __future__ import annotations

from typing import Any, Dict

from src.core.types.models import CueRequestContext


class CueAuthorizationError(PermissionError):
    pass


def local_context() -> CueRequestContext:
    return CueRequestContext(tenant_id="local", user_id="cli", roles=["local"])


def ensure_context(context: CueRequestContext | None) -> CueRequestContext:
    return context or local_context()


def require_tenant_access(record: Dict[str, Any] | None, context: CueRequestContext) -> None:
    if not record:
        return
    if record.get("tenant_id") != context.tenant_id:
        raise CueAuthorizationError("Record is not available in this tenant.")


def require_role(context: CueRequestContext, role: str) -> None:
    if role not in context.roles:
        raise CueAuthorizationError(f"Required role missing: {role}")


def can_read_analysis(record: Dict[str, Any] | None, context: CueRequestContext) -> bool:
    if not record:
        return False
    return record.get("tenant_id") == context.tenant_id


def can_write_analysis(record: Dict[str, Any] | None, context: CueRequestContext) -> bool:
    if not record:
        return True
    return record.get("tenant_id") == context.tenant_id

