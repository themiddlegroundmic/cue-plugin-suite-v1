# Project Phases

## Project Summary

The Cue Platform Intelligence Plugin Suite is a Python plugin package under `Cue_Plugin_Suite`. It provides shared Creator Intelligence Engine modules, platform/search signal plugins, scoring, report building, writer/export helpers, storage, CLI workflows, and legacy podcast/YouTube/platform intelligence plugin packages for downstream Cue desktop or host-app integration.

## Detected Stack

- Python
- pytest and pytest-mock
- `requirements.txt`
- CLI entrypoint via `python -m src.cli`
- SQLite tracking database support
- JSON and Word export paths
- Plugin modules for RSS, Apple, Spotify, Google Trends, YouTube, Meta/TikTok stubs, Podcast PSO, YouTube PSO, and Platform Intelligence

## Known Verification Commands

From `Cue_Plugin_Suite`:

- `python -m pip install -r requirements.txt`
- `python -m pytest -q`
- `python -m pytest src/tests -q`
- `python -m src.cli analyze --topic "Michigan redistricting"`
- `python -m src.cli retention preview --tenant-id local`
- `python scripts/smoke_test.py`
- `./scripts/smoke_test.ps1`
- `cd podcast_pso_plugin && python -m pytest tests/ -v`
- `cd youtube_pso_plugin && python -m pytest tests/ -v`

## Completed Phases

- Version 1.0.0 documented.
- README reports 104 passing tests across legacy plugin tests and Creator Intelligence Engine tests.
- Shared Creator Intelligence Engine under `src/` documented.
- CLI analyze and snapshot workflows documented.
- Host-app integration, security/tenancy, retention, scoring, and plugin interface docs exist.
- 2026-07-10: Added project-specific multi-agent coordination docs.

## Current Phase

Phase name: Coordination baseline

Goal: Keep future plugin changes coordinated, modular, and compatible with downstream desktop integration.

Status: Placeholder for next assigned implementation phase.

## Backlog

- Define the next plugin, scoring, writer, storage, or host-integration phase.
- Keep sample outputs in sync with response schemas when compatibility changes are intentional.
- Expand targeted tests when shared DTOs, CLI behavior, or host handlers change.

## Risks

- Changes to shared types, CLI output, or API-style handlers can break the desktop app or host integrations.
- Optional credential-backed plugins must degrade safely when credentials are missing.
- Generated exports, SQLite databases, and local output reports should not be committed accidentally.
- Score and signal claims must remain estimates/proxies, not exact platform volume or ranking guarantees.

## Testing Gaps

- Live API coverage depends on optional platform credentials and should not be required for basic tests.
- End-to-end desktop packaging depends on adjacent workspace integration.
- Generated Word export behavior may need manual or fixture-based verification.

## Notes For Future Agents

- Use `Cue_Plugin_Suite` as the package root.
- Keep collectors, intelligence, scoring, writer, exports, storage, and CLI boundaries clean.
- Preserve documented fallback behavior when credentials or external APIs are unavailable.
- Do not commit credentials, local exports, `cue_tracking.sqlite3`, output reports, or cache folders.
