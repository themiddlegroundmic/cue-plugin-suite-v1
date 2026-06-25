# Quickstart

Run from the package root:

```powershell
cd E:\Repos\themiddlegroundmic\cue-plugin-suite-v1\Cue_Plugin_Suite
python -m pip install -r requirements.txt
python -m pytest -q
python -m src.cli analyze --topic "Michigan redistricting"
python -m src.cli retention preview --tenant-id local
```

Expected outputs:

- `python -m pytest -q` prints the passing test count.
- `python -m src.cli analyze --topic "Michigan redistricting"` prints a console score summary.
- Analyze creates `exports/*.json`.
- Analyze creates or updates `cue_tracking.sqlite3`.
- Retention preview prints candidate counts and does not delete anything.

No platform credentials are required for the basic CLI command. Optional plugins such as Spotify and YouTube are skipped or limited when credentials are missing.

Run the local smoke test:

```powershell
python scripts/smoke_test.py
```

PowerShell wrapper:

```powershell
.\scripts\smoke_test.ps1
```

