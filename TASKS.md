# Active Mission Board

## Current Phase

Coordination baseline

## Current Goal

Provide project-specific multi-agent instructions for Python plugin suite work.

## Planner Task

Define plugin boundaries, compatibility risks, allowed files, avoid list, and verification commands.

Status: Complete.

## Builder Task

Create project-specific coordination docs only.

Status: Complete.

## Tester/Reviewer Task

Confirm docs exist and repo status shows only intended coordination files.

Status: Pending review.

## Docs/Release Task

Keep coordination docs aligned with plugin README, quickstart, architecture, and host integration docs.

Status: Active.

## Files Allowed

- `AGENTS.md`
- `PHASES.md`
- `TASKS.md`
- `HANDOFF.md`

## Files To Avoid

- `Cue_Plugin_Suite/src/**` unless explicitly assigned.
- `Cue_Plugin_Suite/*_plugin/**` unless explicitly assigned.
- `Cue_Plugin_Suite/exports/**`
- `Cue_Plugin_Suite/output/**`
- `Cue_Plugin_Suite/.pytest_cache/**`
- `Cue_Plugin_Suite/**/__pycache__/**`
- `Cue_Plugin_Suite/cue_tracking.sqlite3`
- Generated Word/JSON reports unless explicitly assigned.
- Any local credentials or environment files.

## Verification Commands

From `Cue_Plugin_Suite`:

- `git status --short`
- `python -m pytest -q`
- `python -m pytest src/tests -q`
- `python scripts/smoke_test.py`
- `python -m src.cli analyze --topic "Michigan redistricting"`
- `python -m src.cli retention preview --tenant-id local`

## Blockers

- No blocker for coordination docs.
- Full test verification may depend on Python dependencies being installed.

## Notes

- This phase intentionally does not modify plugin source code.
- Future implementation tasks should name the target plugin or shared module before editing.
