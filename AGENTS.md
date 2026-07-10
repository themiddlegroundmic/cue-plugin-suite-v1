# Agent Coordination Guide

This repository contains the Cue Platform Intelligence Plugin Suite. The active package root is `Cue_Plugin_Suite`.

## Required First Steps

1. Run `git status --short` from this repository root before editing.
2. Read `Cue_Plugin_Suite/README.md`, `Cue_Plugin_Suite/QUICKSTART.md`, `PHASES.md`, `TASKS.md`, and `HANDOFF.md`.
3. Inspect relevant module docs such as `ARCHITECTURE.md`, `PLUGIN_INTERFACE.md`, `HOST_APP_INTEGRATION.md`, `SECURITY_AND_TENANCY.md`, and `ENVIRONMENT.md` before changing plugin behavior.
4. Check `TASKS.md` for file ownership and avoid overlapping edits.

## Core Rules

- Preserve user changes and other agent changes.
- Avoid destructive Git commands unless explicitly requested.
- Keep changes focused on the current plugin or shared module boundary.
- Match existing Python, pytest, and Markdown style.
- Avoid unrelated refactors, broad module moves, and generated output churn.
- Preserve downstream desktop integration expectations: `python.exe -m src.cli`, `PYTHONPATH`, CLI response shapes, JSON exports, and documented host-app handlers.
- Keep plugin boundaries clean. Writers consume reports; collectors gather signals; scoring stays in scoring modules.
- Do not commit credentials, local exports, SQLite tracking databases, generated Word reports, or platform secrets.
- Run relevant pytest and smoke checks after source changes.
- Coordinate phase state through `PHASES.md`, `TASKS.md`, and `HANDOFF.md`.

## Roles

### Planner Agent

- Defines the plugin/module scope, expected response compatibility, allowed files, and verification plan.

### Builder Agent

- Implements focused Python or docs changes inside `Cue_Plugin_Suite`.
- Avoids breaking CLI, host-app integration handlers, and desktop packaging expectations.

### Tester/Reviewer Agent

- Runs pytest targets and smoke tests appropriate to the touched plugin.
- Reviews for boundary violations, credential leaks, generated output commits, and compatibility regressions.

### Docs/Release Agent

- Updates README, quickstart, handoff, architecture, and integration docs when assigned.
- Preserves useful existing documentation.

## Avoiding File Conflicts

- Claim intended files in `TASKS.md`.
- One agent owns a plugin package or shared core module at a time.
- Sequence edits that touch `src/cli.py`, shared DTO/type modules, scoring, writer, or host API handlers.
- Avoid generated folders and output artifacts unless the task explicitly targets examples.

## Final Response Formats

Successful work:

```text
Done.

Changed:
- <file or area>

Verification:
- <command>: passed

Notes:
- <important context or none>

Next recommended step:
- <specific next action>
```

Work with failures:

```text
Completed with failures.

Changed:
- <file or area>

Verification:
- <command>: failed

Failure details:
- <concise error or blocker>

Risks:
- <remaining risk>

Next recommended step:
- <specific recovery action>
```
