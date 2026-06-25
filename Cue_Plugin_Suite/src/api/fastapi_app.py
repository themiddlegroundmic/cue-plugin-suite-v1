from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, Dict

from src.api.router import CueApiRouter
from src.core.types.models import CueRequestContext

try:
    from fastapi import Depends, FastAPI, Header
except ImportError:  # pragma: no cover - exercised by import smoke tests only
    FastAPI = None
    def Header(default=None, alias=None):
        return default
    def Depends(dependency):
        return None


def context_from_headers(
    x_cue_tenant_id: str = Header("local", alias="X-Cue-Tenant-Id"),
    x_cue_user_id: str = Header("api", alias="X-Cue-User-Id"),
    x_cue_workspace_id: str | None = Header(None, alias="X-Cue-Workspace-Id"),
    x_cue_debug: str | None = Header(None, alias="X-Cue-Debug"),
) -> CueRequestContext:
    return CueRequestContext(
        tenant_id=x_cue_tenant_id,
        user_id=x_cue_user_id,
        workspace_id=x_cue_workspace_id,
        roles=["api"],
        debug=str(x_cue_debug).lower() in {"1", "true", "yes"},
    )


def create_app(router: CueApiRouter | None = None):
    if FastAPI is None:
        raise ImportError("FastAPI is optional. Install with: pip install fastapi uvicorn")

    cue_router = router or CueApiRouter()
    app = FastAPI(title="Cue Creator Intelligence API", version="1.0.0")

    @app.post("/analyze")
    def analyze(request: Dict[str, Any], context: CueRequestContext = Depends(context_from_headers)):
        if request.get("rssUrl") or request.get("rss"):
            return cue_router.analyze_rss(request, context=context)
        return cue_router.analyze_topic(request, context=context)

    @app.get("/runs")
    def runs(limit: int = 20, offset: int = 0, context: CueRequestContext = Depends(context_from_headers)):
        return cue_router.list_analysis_runs(context=context, limit=limit, offset=offset)

    @app.get("/runs/{run_id}")
    def run(run_id: str, context: CueRequestContext = Depends(context_from_headers)):
        return cue_router.get_analysis_run(run_id, context=context)

    @app.get("/runs/{run_id}/export")
    def export(run_id: str, context: CueRequestContext = Depends(context_from_headers)):
        return cue_router.get_export(run_id, context=context)

    @app.get("/history/{tracked_id}")
    def history(tracked_id: str, limit: int = 50, offset: int = 0, context: CueRequestContext = Depends(context_from_headers)):
        return cue_router.get_score_history(show_id=tracked_id, context=context, limit=limit, offset=offset)

    @app.get("/plugins/status")
    def plugins_status(context: CueRequestContext = Depends(context_from_headers)):
        return cue_router.plugin_status(context=context)

    @app.post("/retention/preview")
    def retention_preview(request: Dict[str, Any], context: CueRequestContext = Depends(context_from_headers)):
        return cue_router.preview_retention_cleanup(request, context=context)

    @app.post("/retention/run")
    def retention_run(request: Dict[str, Any], context: CueRequestContext = Depends(context_from_headers)):
        return cue_router.run_retention_cleanup(request, context=context)

    return app

if FastAPI is not None:
    @asynccontextmanager
    async def lifespan(app_instance):
        app_instance.state.cue_router = CueApiRouter()
        yield

    app = FastAPI(title="Cue Creator Intelligence API", version="1.0.0", lifespan=lifespan)

    @app.post("/analyze")
    def analyze(request: Dict[str, Any], context: CueRequestContext = Depends(context_from_headers)):
        router = app.state.cue_router
        if request.get("rssUrl") or request.get("rss"):
            return router.analyze_rss(request, context=context)
        return router.analyze_topic(request, context=context)

    @app.get("/runs")
    def runs(limit: int = 20, offset: int = 0, context: CueRequestContext = Depends(context_from_headers)):
        return app.state.cue_router.list_analysis_runs(context=context, limit=limit, offset=offset)

    @app.get("/runs/{run_id}")
    def run(run_id: str, context: CueRequestContext = Depends(context_from_headers)):
        return app.state.cue_router.get_analysis_run(run_id, context=context)

    @app.get("/runs/{run_id}/export")
    def export(run_id: str, context: CueRequestContext = Depends(context_from_headers)):
        return app.state.cue_router.get_export(run_id, context=context)

    @app.get("/history/{tracked_id}")
    def history(tracked_id: str, limit: int = 50, offset: int = 0, context: CueRequestContext = Depends(context_from_headers)):
        return app.state.cue_router.get_score_history(show_id=tracked_id, context=context, limit=limit, offset=offset)

    @app.get("/plugins/status")
    def plugins_status(context: CueRequestContext = Depends(context_from_headers)):
        return app.state.cue_router.plugin_status(context=context)

    @app.post("/retention/preview")
    def retention_preview(request: Dict[str, Any], context: CueRequestContext = Depends(context_from_headers)):
        return app.state.cue_router.preview_retention_cleanup(request, context=context)

    @app.post("/retention/run")
    def retention_run(request: Dict[str, Any], context: CueRequestContext = Depends(context_from_headers)):
        return app.state.cue_router.run_retention_cleanup(request, context=context)
else:
    app = None
