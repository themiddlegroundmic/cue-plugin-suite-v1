# Optional FastAPI Adapter

The core Cue plugin suite does not require FastAPI. The optional adapter lives at `src/api/fastapi_app.py`.

Install optional API dependencies:

```bash
pip install fastapi uvicorn
```

Run locally:

```bash
uvicorn src.api.fastapi_app:app --reload
```

Routes:

- `POST /analyze`
- `GET /runs`
- `GET /runs/{run_id}`
- `GET /runs/{run_id}/export`
- `GET /history/{tracked_id}`
- `GET /plugins/status`

Context headers:

```text
X-Cue-Tenant-Id: tenant_123
X-Cue-User-Id: user_456
X-Cue-Workspace-Id: workspace_789
X-Cue-Debug: false
```

The adapter does not implement login or auth. The host app must authenticate the request and pass trusted headers.

The adapter returns JSON-serializable dashboard response dictionaries. It does not change the plugin contract and does not make FastAPI required for CLI or tests.

Source limits remain unchanged: Apple and Spotify are search visibility / competition signals, Google Trends is relative interest, YouTube is a demand and engagement proxy, and scores are estimates for creator decision support.
