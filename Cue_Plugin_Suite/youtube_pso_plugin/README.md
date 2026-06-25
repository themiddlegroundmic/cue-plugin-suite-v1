# Cue YouTube PSO Plugin

**Version:** 1.0.0  
**Part of:** Cue Platform Intelligence Suite  
**Tests:** 26 passing  
**Cost to run:** $0 (YouTube Data API v3 free tier — 10,000 units/day)

---

## What This Is

The Cue YouTube PSO Plugin detects where your YouTube channel ranks for target keywords, profiles the top-ranking competitor channels in your niche, classifies every keyword by detection source, scores each keyword by opportunity (PSO Score), and generates replacement titles, descriptions, hooks, and chapter names using Cue's built-in LLM.

It is the YouTube equivalent of the Cue Podcast PSO Plugin — same architecture, same output format, calibrated for YouTube's search algorithm.

---

## What It Does That No Free Tool Does

| Capability | What Cue Does |
|---|---|
| YouTube search rank | Detects your channel's current rank for each keyword via YouTube Data API v3 |
| Autocomplete validation | Confirms keyword demand using YouTube's own suggest endpoint (same one the search bar uses) |
| Competitor metadata | Scrapes top-ranking channel titles and tags to identify what works in your niche |
| Keyword classification | Labels every term: DETECTED / COMPETITOR / LOCAL / GUEST / DEAD |
| PSO Score | Calculates opportunity score (0–100) from demand × (100 − difficulty) |
| AI metadata writer | Generates replacement titles (≤60 chars), descriptions, hooks, and chapters using Cue's built-in LLM — no OpenAI, no Anthropic |
| Political safety | Flags "rigged," "fraud," "traitor," "scam" and rewrites with attribution |
| Word document output | Full action plan in .docx format with keyword table, competitor profiles, replacement metadata, 30/60/90-day plan, and upload checklist |

---

## Credentials

All credentials are **platform-level** — stored once in the Cue platform environment. Users never configure them.

| Variable | Source | Cost |
|---|---|---|
| `YOUTUBE_API_KEY` | Google Cloud Console — Cue org account | Free (10,000 units/day) |
| `BUILT_IN_FORGE_API_URL` | Cue platform — auto-injected | Included in Cue |
| `BUILT_IN_FORGE_API_KEY` | Cue platform — auto-injected | Included in Cue |

### One-Time YouTube API Setup (Cue Org Account)

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a project named "Cue Platform"
3. Enable the **YouTube Data API v3**
4. Create an **API Key** credential (no OAuth needed — this is a server-side key)
5. Add the key as `YOUTUBE_API_KEY` in the Cue platform secrets

That's it. Every user on the platform gets YouTube rank data automatically.

### Quota Management

The YouTube Data API v3 gives 10,000 units per day for free. Costs:
- `Search.list` (rank detection): **100 units per keyword**
- `Videos.list` (stats enrichment): **1 unit per batch of 50**
- `Channels.list` (competitor profiles): **1 unit per channel**

At 100 units per keyword search, you get **100 free keyword searches per day**. For a typical audit of 18 keywords, that uses 1,800 units — leaving 8,200 units for other queries.

If Cue scales to require more, Google's quota extension request is free and typically approved within 48 hours.

---

## Module Structure

```
cue_youtube_pso_plugin/
├── __init__.py                  ← Exports YouTubePSOPlugin
├── core/
│   ├── __init__.py
│   ├── search_rank.py           ← YouTube Data API v3 rank detection
│   ├── autocomplete.py          ← YouTube suggest endpoint (no API key needed)
│   ├── competitor_scraper.py    ← Top-ranking channel metadata scraper
│   ├── keyword_classifier.py    ← DETECTED/COMPETITOR/LOCAL/GUEST/DEAD labeling
│   ├── difficulty_scorer.py     ← PSO score (0–100) + difficulty formula
│   ├── llm_writer.py            ← Cue built-in LLM metadata generator
│   ├── doc_generator.py         ← Word document output
│   └── plugin.py                ← Main YouTubePSOPlugin orchestrator
├── tests/
│   └── test_youtube_pso.py      ← 26 unit tests, all passing
├── run_mgm_youtube.py           ← Standalone runner for The MiddleGround Mic
├── output/                      ← Generated .docx files saved here
├── docs/                        ← Architecture diagrams
├── requirements.txt
└── README.md
```

---

## Standalone Usage

```bash
# Install dependencies
pip install -r requirements.txt

# Set platform credentials
export YOUTUBE_API_KEY="your-youtube-api-key"
export BUILT_IN_FORGE_API_URL="your-cue-api-url"
export BUILT_IN_FORGE_API_KEY="your-cue-api-key"

# Run the MGM YouTube audit
python run_mgm_youtube.py
# Output: output/MGM_YouTube_PSO_Action_Plan.docx
```

---

## Integration with Cue App

The plugin is designed to wire into the Cue web app as the **YouTube PSO** tab in the Platform Intelligence section.

### tRPC Router Procedure (server/routers/youtube-pso.ts)

```typescript
youtubePso: protectedProcedure
  .input(z.object({
    channelId: z.string(),
    keywords: z.array(z.string()),
    videos: z.array(z.object({ title: z.string(), description: z.string() })).optional(),
  }))
  .mutation(async ({ input, ctx }) => {
    // Call Python plugin via child_process or HTTP microservice
    // Returns: { keywords, psoScores, competitors, generatedMetadata, documentUrl }
  }),
```

### Drizzle Schema Tables

```typescript
// drizzle/schema.ts additions
export const youtubePsoScans = sqliteTable("youtube_pso_scans", {
  id: text("id").primaryKey(),
  userId: text("user_id").notNull(),
  channelId: text("channel_id").notNull(),
  keywords: text("keywords").notNull(),       // JSON array
  results: text("results").notNull(),          // JSON blob
  documentUrl: text("document_url"),
  createdAt: integer("created_at").notNull(),
});

export const youtubeKeywordRanks = sqliteTable("youtube_keyword_ranks", {
  id: text("id").primaryKey(),
  scanId: text("scan_id").notNull(),
  keyword: text("keyword").notNull(),
  rank: integer("rank"),                       // null = not ranking
  psoScore: integer("pso_score").notNull(),
  difficulty: integer("difficulty").notNull(),
  demandScore: integer("demand_score").notNull(),
  classification: text("classification").notNull(),
  checkedAt: integer("checked_at").notNull(),
});
```

---

## PSO Score Formula

```
PSO Score = (Demand × (100 − Difficulty)) / 100
```

- **Demand** is derived from autocomplete position (position 1 = 90, not in autocomplete = 30) blended with Google Trends score when available.
- **Difficulty** is derived from competitor channel subscriber count (0–40 pts), average views on top results (0–35 pts), and autocomplete position (0–25 pts).
- **PSO Score ≥ 60** = High Opportunity — target in next 3 videos
- **PSO Score 35–59** = Moderate Opportunity — use in description and tags
- **PSO Score < 35** = Low Opportunity — supporting tag only

---

## YouTube Guide Rules Encoded in the LLM Writer

The LLM system prompt encodes the full Master YouTube Guide:

- **Title Rules:** ≤60 chars, leads with topic/entity, tension word required, no "Episode/Ep./Interview" prefix
- **Hook Formula:** Opens with tension/stakes, names specific entity/vote/event, states what viewer will understand
- **Description Rules:** First 150 chars keyword-rich, chapters in MM:SS format, links below chapters
- **Chapter Naming:** Specific argument names, not "Introduction/Main Topic/Conclusion"
- **Tag Order:** DETECTED → COMPETITOR → LOCAL → ENTITY → BRAND; no dead tags
- **Political Safety:** "rigged" → "disputed", "fraud" → "alleged fraud", "traitor" → "accused of"

---

## Running Tests

```bash
cd /path/to/cue_youtube_pso_plugin
python -m pytest tests/test_youtube_pso.py -v
# 26 passed
```

All tests run without API credentials — external calls are mocked.

---

## Relationship to Other Cue Plugins

| Plugin | Platform | Key API | LLM Writer |
|---|---|---|---|
| `cue_pso_plugin` | Apple Podcasts + Spotify | iTunes Search API + Spotify Web API | Yes — Cue built-in |
| `cue_youtube_pso_plugin` | YouTube | YouTube Data API v3 | Yes — Cue built-in |
| `cue_platform_plugin` | Facebook + Instagram + YouTube | Meta Graph API + YouTube Data API | Yes — Cue built-in |

All three plugins share the same credential pattern (platform-level secrets), the same LLM writer architecture (Cue BUILT_IN_FORGE_API), and the same Word document output format.
