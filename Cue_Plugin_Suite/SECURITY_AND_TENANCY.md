# Security And Tenancy

This package does not authenticate users. The host Cue app must authenticate users and pass trusted context into the plugin suite.

The plugin suite enforces storage scoping and guardrails using `CueRequestContext`:

- `tenant_id`
- `user_id`
- `workspace_id`
- `roles`
- `debug`

Rules:

- Every persisted analysis, tracked show, tracked episode, score history row, weekly snapshot, competitor snapshot, and analysis run is stored with tenant/user ownership fields.
- Read methods are scoped by `tenant_id` at minimum.
- Wrong-tenant reads return not-found style errors and do not leak records.
- Exports are read only through the stored analysis run record.
- Export paths are restricted to the configured exports directory.
- Path traversal and arbitrary file reads are blocked.
- Retention cleanup is tenant-scoped and cannot clean another tenant by request payload.
- Retention export deletion is restricted to the configured exports directory.

FastAPI header context:

```text
X-Cue-Tenant-Id: tenant_123
X-Cue-User-Id: user_456
X-Cue-Workspace-Id: workspace_789
X-Cue-Debug: false
```

Plugin credentials are platform-level environment variables. Do not expose raw environment variables to the frontend.

Signal language:

- Apple and Spotify are search visibility / competition signals, not true search volume.
- Google Trends is relative interest.
- YouTube is a demand and engagement proxy, not true keyword volume.
- Scores are creator decision-support estimates, not guarantees.
