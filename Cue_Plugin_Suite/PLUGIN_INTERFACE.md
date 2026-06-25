# Cue Plugin Interface

Every platform plugin follows the same contract:

```python
class CuePlugin(Protocol):
    id: str
    name: str
    platform: str
    enabled: bool

    async def analyze(self, input: CueInput) -> CuePluginResult:
        ...
```

Plugins return `CuePluginResult` with structured fields:

- `show` and `episodes` for normalized creator-owned metadata
- `signals` for Search Interest Signal, Competition Signal, freshness, and other measurable inputs
- `competitors` for competing shows/channels/pages
- `keywords` for candidate PSO terms
- `warnings` for source limitations and safety notes

Apple and Spotify results are competition/search visibility signals only. Cue does not claim exact Apple or Spotify search volume.

