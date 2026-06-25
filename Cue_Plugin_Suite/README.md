# Cue Platform Intelligence Plugin Suite

**Version:** 1.0.0  
**Total tests:** 104 passing (legacy plugin tests + new Creator Intelligence Engine tests)  
**Total cost to run:** $0 (all APIs are free public or free-with-registration)

---

## What Is In This Suite

This suite now includes the first working version of the shared Cue Creator Intelligence Engine under `src/`.

Cue is not just an AI writer. The v1 architecture collects platform/search signals first, produces a structured intelligence report, scores the opportunity, then lets the writer generate metadata from that report. The writer does not call Apple, Spotify, Google Trends, RSS, Meta, YouTube, or TikTok APIs directly.

New shared v1 modules:

| Area | Folder | Purpose |
|---|---|---|
| Shared types | `src/core/types/` | `CueInput`, `CueShow`, `CueEpisode`, `CueSignal`, `CuePluginResult`, reports, scores, writer/export DTOs |
| Plugin contract | `src/core/types/plugin.py` | Common `CuePlugin` protocol with async `analyze(input)` |
| RSS plugin | `src/plugins/rss/` | Reliable RSS show/episode parser |
| Apple plugin | `src/plugins/apple/` | iTunes Search API competition/search visibility signal |
| Spotify plugin | `src/plugins/spotify/` | Spotify Search with Cue org-level credentials |
| Google Trends | `src/plugins/googleTrends/` | Search Interest Signal, relative interest only |
| YouTube plugin | `src/plugins/youtube/` | YouTube Data API v3 demand, competition, freshness, and engagement proxy |
| Stubs | `src/plugins/meta/`, `src/plugins/tiktok.py` | Safe not-implemented v1.1 plugin stubs |
| Intelligence | `src/core/intelligence/` | Competitor analyzer, content gap detector, report builder |
| Scoring | `src/core/scoring/` | Opportunity Score, Platform Readiness Score, Confidence Score |
| Writer | `src/core/writer/` | Metadata writer that consumes only `CueIntelligenceReport` |
| Export | `src/core/exports/` | JSON export, Word export stub |
| Services/API | `src/services/`, `src/api/` | Orchestration, endpoint-style handlers, tracking models, weekly heartbeat stub |
| Storage | `src/core/storage/` | SQLite persistence for tracked shows, episodes, score history, snapshots, and analysis runs |
| CLI | `src/cli.py` | End-to-end command-line workflow |

Three self-contained plugins that together replace $50+/month of third-party SEO and analytics tools. Each plugin is designed as a "compile-and-drop" module into the Cue web application — same credential pattern, same LLM writer architecture, same Word document output format.

| Plugin | Folder | Platform | Key API | Tests |
|---|---|---|---|---|
| Podcast PSO | `podcast_pso_plugin/` | Apple Podcasts + Spotify | iTunes Search API + Spotify Web API | 26 passing |
| YouTube PSO | `youtube_pso_plugin/` | YouTube | YouTube Data API v3 | 26 passing |
| Platform Intelligence | `platform_intelligence_plugin/` | Facebook + Instagram + YouTube | Meta Graph API + YouTube Data API | 43 passing |

---

## Credentials — Platform-Level, Users Never Configure These

All three plugins read credentials from the Cue platform environment. No user ever sees a setup screen.

| Variable | Used By | Source | Cost |
|---|---|---|---|
| `SPOTIFY_CLIENT_ID` | Podcast PSO | Spotify Developer — Cue org app | Free |
| `SPOTIFY_CLIENT_SECRET` | Podcast PSO | Spotify Developer — Cue org app | Free |
| `YOUTUBE_API_KEY` | YouTube PSO + Platform Intelligence | Google Cloud Console — Cue org | Free (10k units/day) |
| `META_APP_ID` | Platform Intelligence | Meta for Developers — Cue org app | Free |
| `META_APP_SECRET` | Platform Intelligence | Meta for Developers — Cue org app | Free |
| `BUILT_IN_FORGE_API_URL` | All three | Cue platform — auto-injected | Included in Cue |
| `BUILT_IN_FORGE_API_KEY` | All three | Cue platform — auto-injected | Included in Cue |

### One-Time Setup Checklist (Cue Org Account)

- [ ] **Spotify:** Register free app at developer.spotify.com → Client Credentials flow → add `SPOTIFY_CLIENT_ID` + `SPOTIFY_CLIENT_SECRET`
- [ ] **YouTube:** Enable YouTube Data API v3 in Google Cloud Console → create API Key → add `YOUTUBE_API_KEY`
- [ ] **Meta:** Create app at developers.facebook.com → add `META_APP_ID` + `META_APP_SECRET`

After these three one-time steps, every user on the Cue platform gets all three plugins fully functional.

---

## Plugin 1 — Podcast PSO (`podcast_pso_plugin/`)

Detects Apple Podcasts and Spotify search rank for podcast keywords. Profiles competitor shows. Classifies keywords. Scores PSO opportunity. Generates replacement episode titles, descriptions, and tags using Cue's built-in LLM.

**See:** `podcast_pso_plugin/README.md`

**Run:**
```bash
cd podcast_pso_plugin
export SPOTIFY_CLIENT_ID="..." SPOTIFY_CLIENT_SECRET="..."
export BUILT_IN_FORGE_API_URL="..." BUILT_IN_FORGE_API_KEY="..."
python run_mgm.py   # → output/MGM_PSO_Action_Plan.docx
python run_rmm.py   # → output/RMM_PSO_Action_Plan.docx
```

---

## Plugin 2 — YouTube PSO (`youtube_pso_plugin/`)

Detects YouTube search rank for video keywords. Profiles competitor channels. Classifies keywords. Scores PSO opportunity. Generates replacement titles (≤60 chars), descriptions, hooks, and chapter names using Cue's built-in LLM, following the Master YouTube Guide rules.

**See:** `youtube_pso_plugin/README.md`

**Run:**
```bash
cd youtube_pso_plugin
export YOUTUBE_API_KEY="..."
export BUILT_IN_FORGE_API_URL="..." BUILT_IN_FORGE_API_KEY="..."
python run_mgm_youtube.py   # → output/MGM_YouTube_PSO_Action_Plan.docx
```

**YouTube API Quota:** 10,000 units/day free. Each keyword search costs 100 units → 100 free keyword searches per day.

---

## Plugin 3 — Platform Intelligence (`platform_intelligence_plugin/`)

Applies the Master Guide compliance rules to Facebook posts, YouTube videos, and Instagram content before output. Checks every piece of content against the 12 Laws, political safety rules, platform-specific formatting requirements, and engagement eligibility criteria.

**See:** `platform_intelligence_plugin/README.md` (inside the folder)

**Modules:**
- `facebook/rules.py` — 12 Laws, post formula, claim ladder, Reels structure, pre-publish checklist
- `youtube/rules.py` — Three-Layer Video Test, title rules, hook formula, chapter naming, upload checklist
- `instagram/rules.py` — 12 Laws, Six Surfaces, SEO doctrine, sendability test, carousel/Reels structure
- `shared/llm_writer.py` — Cue built-in LLM writer for all three platforms
- `plugin.py` — Main CuePlatformPlugin orchestrator

---

## Architecture Diagrams

All diagrams are in the `docs/` folder:

| File | Shows |
|---|---|
| `docs/podcast_pso_flow.png` | Podcast PSO pipeline — 5 swim lanes from RSS feed to Word document |
| `docs/podcast_pso_ui.png` | Podcast PSO UI mockup — PSO Control tab inside Cue |
| `docs/platform_flow.png` | Platform Intelligence pipeline — all four platforms in one flow |
| `docs/platform_ui.png` | Platform Intelligence UI mockup — Facebook/YouTube/Instagram tabs |

---

## How the Writer Works (All Three Plugins)

Every legacy plugin can use `BUILT_IN_FORGE_API`, Cue's configured writer endpoint. In the new shared `src/` architecture, writing is deliberately downstream from collection and scoring: the writer consumes `CueIntelligenceReport` instead of calling platform APIs or inventing strategy from raw text.

Each platform has its own system prompt that encodes the relevant Master Guide rules:
- **Podcast:** Episode title rules, description first-150-words doctrine, tag PSO order, political safety flags
- **YouTube:** Title ≤60 chars, hook formula, chapter naming rules, description structure, political safety
- **Facebook:** 12 Laws, post formula, claim ladder, Reels structure, engagement eligibility
- **Instagram:** 12 Laws, Six Surfaces, keyword-first caption doctrine, hashtag vs keyword guidance, sendability test

If the Cue LLM API is unavailable, all three plugins fall back to rule-based template generation automatically — no crash, no empty output.

---

## Running All Tests

```bash
# From Cue_Plugin_Suite/
python -m pytest -q
# 104 passed

# New shared Creator Intelligence Engine tests only
python -m pytest src/tests -q

# Podcast PSO
cd podcast_pso_plugin && python -m pytest tests/ -v
# 26 passed

# YouTube PSO
cd youtube_pso_plugin && python -m pytest tests/ -v
# 26 passed

# Platform Intelligence
cd platform_intelligence_plugin && python -m pytest tests/ -v
# 43 passed
```

---

## End-to-End CLI

```bash
python -m src.cli analyze --rss "https://example.com/feed.xml"
python -m src.cli analyze --topic "Michigan redistricting"
python -m src.cli analyze --rss "https://example.com/feed.xml" --topic "Michigan redistricting"
```

The CLI runs input normalization, enabled plugins, intelligence report generation, scoring, writer output, JSON export, and SQLite analysis-run persistence.

Default outputs:

- JSON export: `exports/<timestamp>-<topic>.json`
- SQLite database: `cue_tracking.sqlite3`

Use `--no-store` to skip database persistence. See `sample_outputs/` for a representative JSON artifact.

Weekly snapshot runner:

```bash
python -m src.cli snapshots run
python -m src.cli snapshots list
```

---

## Wiring Into the Cue App

Each plugin README contains the exact tRPC router procedure signatures and Drizzle schema table definitions needed to integrate that plugin as a tab in the Cue web application. The integration pattern is identical across all three:

1. Add the Python plugin as a subprocess or microservice called from the tRPC router
2. Store scan results in the Drizzle schema tables
3. Serve results to the frontend via the tRPC procedure
4. Display in the Platform Intelligence section of the Cue UI

The new shared package also exposes API-style handlers:

- `POST /api/analyze` maps to `src.api.handlers.analyze`
- `POST /api/score` maps to `src.api.handlers.score`
- `POST /api/write` maps to `src.api.handlers.write`
- `POST /api/export` maps to `src.api.handlers.export_json`

These are plain Python handler functions for host-app integration; no production web server is introduced in this pass.

See `HOST_APP_INTEGRATION.md`, `DASHBOARD_RESPONSE.md`, `API_ADAPTER.md`, `TRACKING_AND_SNAPSHOTS.md`, and `SECURITY_AND_TENANCY.md` for host-app usage details.
See `RETENTION.md` for tenant-scoped cleanup of old runs, exports, score history, and snapshots.

---

## Signal and Score Claims

Cue does not claim exact Apple or Spotify search volume.

- Apple Podcasts Search results are Competition Signals / search visibility signals.
- Spotify Search results are Competition Signals / search visibility signals.
- Google Trends is a Search Interest Signal with relative interest, not actual search volume.
- YouTube Data API results are demand, competition, freshness, and engagement proxies, not true keyword search volume.
- Opportunity Score, Platform Readiness Score, and Confidence Score are estimates, not guarantees.

---

## What Each Plugin Replaces

| Tool | Monthly Cost | What Cue Replaces It With |
|---|---|---|
| Ausha PSO Control Panel | $50/month | Podcast PSO Plugin |
| TubeBuddy Pro | $19/month | YouTube PSO Plugin |
| Sprout Social / Hootsuite analytics | $99+/month | Platform Intelligence Plugin |
| **Total replaced** | **$168+/month** | **$0 — all free APIs** |
