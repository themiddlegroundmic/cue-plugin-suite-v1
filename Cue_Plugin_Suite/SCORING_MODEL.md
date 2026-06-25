# Cue Scoring Model

Scores are estimates, not guarantees.

## Opportunity Score

- Demand Signal: 35%
- Trend Momentum: 20%
- Competition Gap: 20%
- Freshness: 15%
- Metadata Quality: 10%

## Platform Readiness Score

- Title Quality: 25%
- Description Quality: 25%
- Keyword Coverage: 20%
- Platform Format Fit: 20%
- Risk/Safety Flags: 10%

## Confidence Score

Confidence is based on source coverage, signal count, signal agreement, and plugin status quality. RSS + Apple + Spotify + Google Trends returning useful data should score higher than a single weak signal.

## Explanation Fields

Each score includes:

- `score`
- `label`
- `factors`
- `explanation`
- `warnings`

These fields are meant for the Cue UI and reports so users can see why a score moved without reverse-engineering component weights.

## Source Language

- Apple Podcasts Search: Competition Signal, not true Apple search volume.
- Spotify Search: Competition Signal, not true Spotify search volume.
- Google Trends: Search Interest Signal, relative interest only.
- YouTube Data API: demand, competition, freshness, and engagement proxy only; not true keyword search volume.
