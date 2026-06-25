# Environment

Spotify is platform-managed. Users should never configure Spotify credentials.

Required for Spotify Search:

```bash
SPOTIFY_CLIENT_ID=...
SPOTIFY_CLIENT_SECRET=...
```

Optional for YouTube Data API v3:

```bash
YOUTUBE_API_KEY=...
```

Optional legacy variables still used by older plugin folders:

```bash
META_APP_ID=...
META_APP_SECRET=...
BUILT_IN_FORGE_API_URL=...
BUILT_IN_FORGE_API_KEY=...
```

Google Trends uses `pytrends` when installed. If `pytrends` is unavailable, the Google Trends plugin returns a clean `not_configured` result rather than fake data.

Optional API adapter dependencies:

```bash
pip install fastapi uvicorn
```

FastAPI context headers are provided by the host app after authentication:

```text
X-Cue-Tenant-Id
X-Cue-User-Id
X-Cue-Workspace-Id
X-Cue-Debug
```
