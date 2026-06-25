# Sample Outputs

This folder contains representative Cue Creator Intelligence output.

The sample JSON shows the v1 workflow shape:

1. `input` - normalized request values such as RSS URL, manual topic, and target platform.
2. `showMetadata` and `episodeMetadata` - normalized RSS metadata when available.
3. `pluginResultsSummary` - plugin status, signal count, competitor count, and source warnings.
4. `intelligenceReport` - primary topic, keywords, signals, competitors, structured content gaps, risk flags, and scores.
5. `scoreBreakdown` - numeric components plus human-readable score explanations.
6. `writerOutput` - generated metadata and reasoning fields based only on the intelligence report.

Apple and Spotify entries are competition/search visibility signals only. YouTube entries are demand, competition, freshness, and engagement proxies. None of these sample fields claim exact platform search volume.

