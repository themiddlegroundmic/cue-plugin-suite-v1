# Cue PSO Plugin

**Podcast Search Optimization — powered by Cue Intelligence**

A self-contained Python module that replicates and beats Ausha's $50/month PSO Control Panel using 100% free public APIs plus Cue's own built-in LLM. No third-party AI model. No recurring cost.

---

## What This Is

This plugin is designed to be compiled into the Cue platform as a standalone section — the "PSO Control" tab visible in the UI mockup. It can also be run as a standalone Python script for generating Word document action plans.

### The Core Difference From Ausha

| Feature | Ausha PSO ($50/mo) | Cue PSO Plugin |
|---|---|---|
| Apple Podcasts search rank | Yes | **Yes** — same iTunes API source |
| Spotify search rank | Yes | **Yes** — Spotify Web API (free) |
| Search volume estimate | Proprietary | **Google Trends** (real demand, not estimated) |
| Difficulty score | Proprietary formula | **Same formula** — competitor count × depth × recency |
| Weekly rank tracking | Stored in Ausha DB | **Heartbeat scheduler** — runs every Sunday |
| Competitor keyword tab | Dashboard UI | **RSS scraper** — same underlying data |
| AI-generated replacement metadata | **No — Ausha cannot do this** | **Yes** — Cue built-in LLM writes the fix |
| Political safety scoring | No | **Yes** — flags suppression-risk language |
| Bulk catalog repair | Manual only | **Yes** — full catalog in one pass |

---

## Data Sources

All data sources are free. No API key is required for Apple or Google Trends.

| Source | What It Provides | Cost | Auth Required |
|---|---|---|---|
| iTunes Search API | Apple Podcasts rank order | Free | None |
| Spotify Web API | Spotify rank order | Free | Client Credentials (5-min setup) |
| Google Trends (pytrends) | Real search demand 0–100 | Free | None |
| Competitor RSS feeds | Competitor keyword metadata | Free | None |
| Cue Built-in LLM | AI-generated replacement metadata | Included in Cue | BUILT_IN_FORGE_API |

---

## Directory Structure

```
cue_pso_plugin/
├── __init__.py              # Package entry point
├── run_mgm.py               # Standalone runner — The MiddleGround Mic
├── run_rmm.py               # Standalone runner — Raging MI Moderates
├── README.md                # This file
├── requirements.txt         # Python dependencies
├── core/
│   ├── __init__.py
│   ├── plugin.py            # Main PSOPlugin orchestrator
│   ├── feed_parser.py       # RSS feed ingestion → Episode/Show objects
│   ├── apple_detector.py    # iTunes Search API — Apple rank detection
│   ├── spotify_detector.py  # Spotify Web API — Spotify rank detection
│   ├── trends_detector.py   # Google Trends demand signal (pytrends)
│   ├── competitor_scraper.py# RSS scraper for top-ranking competitor shows
│   ├── keyword_classifier.py# Term classification: DETECTED/COMPETITOR/LOCAL/DEAD
│   ├── difficulty_scorer.py # PSO score + difficulty score calculator
│   ├── llm_writer.py        # Cue built-in LLM metadata generator
│   └── doc_generator.py     # Word document output
├── tests/
│   └── test_pso_plugin.py   # Unit tests (pytest)
└── output/                  # Generated reports saved here
```

---

## Quick Start (Standalone)

### 1. Install dependencies

```bash
pip install requests python-docx pytrends pytest
```

### 2. Set environment variables

```bash
# Required for AI metadata generation
export BUILT_IN_FORGE_API_URL="https://your-cue-instance/api"
export BUILT_IN_FORGE_API_KEY="your-built-in-key"

# Optional — for Spotify rank data
# Register a free app at https://developer.spotify.com/dashboard
export SPOTIFY_CLIENT_ID="your-spotify-client-id"
export SPOTIFY_CLIENT_SECRET="your-spotify-client-secret"
```

### 3. Run the audit

```bash
# The MiddleGround Mic
python run_mgm.py

# Raging MI Moderates
python run_rmm.py
```

Output files are saved to `./output/`:
- `MGM_PSO_Action_Plan.docx` — Full Word document with AI-generated metadata
- `MGM_PSO_Report.json` — Machine-readable report for the Cue app API

---

## Integration Into Cue App

This plugin maps directly to the Cue platform's tRPC architecture. The integration points are:

### tRPC Router (server/routers/pso.ts)

```typescript
// Add to server/routers.ts or create server/routers/pso.ts

pso: {
  // Run full PSO audit for a show
  runAudit: protectedProcedure
    .input(z.object({ feedUrl: z.string(), showName: z.string() }))
    .mutation(async ({ input, ctx }) => {
      // Calls PSOPlugin.run() via Python subprocess or Node wrapper
      // Returns keyword_intelligence + episode scores
    }),

  // Get keyword intelligence for a show (cached)
  getKeywords: protectedProcedure
    .input(z.object({ showId: z.string() }))
    .query(async ({ input, ctx }) => {
      // Returns stored keyword_rankings from DB
    }),

  // Generate AI metadata for a single episode
  generateMetadata: protectedProcedure
    .input(z.object({ episodeGuid: z.string(), showId: z.string() }))
    .mutation(async ({ input, ctx }) => {
      // Calls LLMWriter.write_metadata() via Cue built-in LLM
      // Returns { title, description_opening, tags, chapters }
    }),
}
```

### Database Schema (drizzle/schema.ts)

```typescript
// Add these tables for weekly rank tracking

export const keywordRankings = mysqlTable("keyword_rankings", {
  id: int("id").autoincrement().primaryKey(),
  showId: varchar("show_id", { length: 100 }).notNull(),
  keyword: varchar("keyword", { length: 200 }).notNull(),
  appleRank: int("apple_rank"),
  spotifyRank: int("spotify_rank"),
  demandScore: int("demand_score"),
  difficultyScore: int("difficulty_score"),
  checkedAt: bigint("checked_at", { mode: "number" }).notNull(),
});

export const episodePsoScores = mysqlTable("episode_pso_scores", {
  id: int("id").autoincrement().primaryKey(),
  showId: varchar("show_id", { length: 100 }).notNull(),
  episodeGuid: varchar("episode_guid", { length: 500 }).notNull(),
  psoScore: int("pso_score").notNull(),
  priority: varchar("priority", { length: 5 }).notNull(),
  llmTitle: text("llm_title"),
  llmDescription: text("llm_description"),
  llmTags: text("llm_tags"),
  scoredAt: bigint("scored_at", { mode: "number" }).notNull(),
});
```

### Heartbeat Scheduler (weekly rank tracking)

```typescript
// Add to server/_core/heartbeat.ts or create a scheduled job

// Runs every Sunday at 3:00 AM
// Calls PSOPlugin for each registered show
// Stores results in keyword_rankings table
// Enables the rank-change-over-time chart in the UI
```

---

## Spotify Setup — Platform-Level (One-Time, Free)

Spotify credentials are managed by the **Cue platform**, not by individual users. Every user on the platform gets Spotify rank data automatically — no setup required on their end.

**One-time setup for the Cue organization:**
1. Go to [https://developer.spotify.com/dashboard](https://developer.spotify.com/dashboard)
2. Log in with the Cue organization Spotify account
3. Click **Create app** — Name: "Cue PSO" | Redirect URI: `http://localhost`
4. Copy **Client ID** and **Client Secret**
5. Add to the Cue platform environment as `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET`

The plugin reads these automatically from the platform environment — the same pattern as `BUILT_IN_FORGE_API_KEY`. Users never see a Spotify setup screen.

The plugin uses **Client Credentials flow** — no user OAuth, no user login, no user Spotify data accessed. Spotify's terms of service explicitly permit querying public search results this way.

**Rate limit:** 100 requests/minute on the free tier. Sufficient for concurrent audits at launch. Spotify offers a free quota extension via a form submission if needed at scale.

---

## PSO Score Methodology

Each episode receives a PSO Score (0–100) based on:

| Factor | Max Deduction | What Triggers It |
|---|---|---|
| Boilerplate at top of description | -20 | Fan mail link, BuyMeACoffee, sponsor copy in first 150 chars |
| Vague title | -15 | Title starts with "Ep", "Episode", "Part", "Update" |
| Title too long | -10 | Over 80 characters |
| No description | -35 | Empty description field |
| Short description | -10 | Under 50 words |
| No chapters | -5 | No (00:00) timestamp in description |
| All dead tags | -15 | 50%+ of tags are generic (podcast, episode, host, etc.) |
| Safety flags | -5 each | Suppression-risk words: rigged, fraud, traitor, treason, etc. |

**Priority Assignment:**
- **P1** — PSO Score < 55, or any safety flags, or boilerplate at top with score < 60
- **P2** — PSO Score 55–74
- **P3** — PSO Score 75+

---

## Keyword Classification Labels

| Label | Meaning | PSO Action |
|---|---|---|
| DETECTED | Found in Apple Podcasts search results for this topic | Use first in tag set |
| COMPETITOR | Used by top-ranking competitor shows | Use second in tag set |
| FACTUAL | Specific entities: people, legislation, events, countries | Use third |
| LOCAL | Geographic terms: michigan, detroit, midwest, etc. | Use fourth |
| GUEST | Guest names or organizations | Use fifth |
| DEAD | Generic terms with no search value | Remove entirely |

---

## Running Tests

```bash
cd cue_pso_plugin
python -m pytest tests/ -v
```

All tests run offline (no API calls) using mocks. The test suite covers:
- Feed parser duration/date/safety parsing
- Keyword classifier dead tag detection and PSO ordering
- Difficulty scorer formula and label assignment
- Episode PSO score calculation
- LLM writer prompt construction and API response parsing

---

## What Ausha Cannot Do (Cue's Unique Advantage)

Ausha is a dashboard on top of public APIs. It shows you the problem. Cue writes the fix.

The `LLMWriter` module uses Cue's own built-in language model (`BUILT_IN_FORGE_API`) to generate:
- A replacement episode title (≤80 chars, keyword-first)
- A replacement first 150 words (opens with primary keyword, no boilerplate)
- A PSO-ordered tag set (DETECTED → FACTUAL → LOCAL → GUEST → BRAND)
- Chapter names with realistic timestamps
- Political safety rewrites for suppression-risk language

This is the feature that makes Cue structurally superior to Ausha — not just equivalent.

---

## License

Cue Platform — Internal Use Only  
© 2025 Cue Network. All rights reserved.
