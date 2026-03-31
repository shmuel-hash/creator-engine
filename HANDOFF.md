# Creator Discovery Engine — Handoff Script (Updated March 31, 2026)
## Paste this at the start of a new Claude chat to pick up where we left off

---

## PROJECT OVERVIEW
AI-powered **Creator Discovery Engine** for Luma Nutrition — finds hard-to-find influencer creators (especially doctors, Gen Z, niche wellness) across TikTok, Instagram, YouTube, Reddit, LinkedIn, and UGC marketplaces, then generates personalized outreach strategies for each one.

## WHAT'S BUILT & DEPLOYED

### Backend (Python FastAPI + PostgreSQL on Railway)
- **GitHub repo:** https://github.com/shmuel-hash/creator-engine
- **Live URL:** https://creator-engine-production.up.railway.app
- **Frontend:** https://creator-engine-production.up.railway.app/ (served from FastAPI)
- **Swagger docs:** https://creator-engine-production.up.railway.app/docs
- **Database:** 41 creators imported from Excel + newly discovered ones, PostgreSQL on Railway
- **Stack:** Python 3.12, FastAPI, SQLAlchemy async, Serper.dev (Google SERP), Anthropic Claude

### What's fully working (backend):
- ✅ All CRUD endpoints (30+ API routes)
- ✅ Excel/CSV import (auto-maps 37+ columns)
- ✅ Async discovery pipeline — returns search_id immediately, polls for results
  - Claude AI intent parsing → 15 targeted search queries
  - Serper.dev web search (replaced SearchAPI.io which ran out of credits)
  - Reddit scraper, UGC marketplace search, hashtag research — all wired to real search
  - Claude AI analysis extracts: names, handles, profile URLs, emails, credentials, partnerships
  - Deduplication + relevance scoring (0-100)
  - Found 20 real doctors with handles, profile URLs, credentials in test
- ✅ Async enrichment pipeline with progress tracking
  - Step 1: Email finding (bio scraping, linktree, web search)
  - Step 2: Content analysis (recent posts, brand partnerships)
  - Step 3: AI outreach strategy generation (full personalized email, content ideas, rate estimates)
  - Polls via GET /creators/{id}/enrich/status
- ✅ Save & Enrich combo endpoint (one-click: save discovery result → enrich)
- ✅ GET /creators/{id}/strategy — retrieve stored strategy
- ✅ `extract_json()` helper — robust JSON parsing from Claude responses
- ✅ ClickUp integration code (all custom field IDs mapped)
- ✅ Email templates (4 defaults)
- ✅ Gmail service (ready for OAuth setup)

### Frontend (React JSX served from FastAPI):
- ✅ Day/night mode (auto-detects system preference)
- ✅ Discover tab with natural language search + 6 presets
- ✅ Database tab with search, stage/tier filters, pagination
- ✅ Import tab with drag & drop CSV/Excel
- ✅ Creator cards expand to show details
- ✅ Live search progress bar (parsing intent → searching → analyzing)
- ✅ Enrichment progress bar (finding email → analyzing content → generating strategy)

### What needs fixing/improving:
1. **Frontend Save & Enrich button** — the backend endpoint works perfectly (tested directly), but the frontend React code doesn't properly handle the response. The button fires, the API responds with the new creator + enrichment status, but the frontend fails to:
   - Update the card with the new creator ID (needed for polling)
   - Show the enrichment progress bar
   - Display the strategy when complete
   
2. **Frontend result cards are too sparse** — need to show:
   - Content links (TikTok videos, IG posts) with thumbnails
   - Score reasoning (content_fit from AI analysis)
   - Credentials prominently displayed
   - Other platform profiles (Instagram, YouTube, LinkedIn)
   - Past brand partnerships
   - Email quality indicator (flag generic/brand emails vs personal)

3. **Deduplication against existing DB** — when running a new search, filter out creators already in the database. Check by handle/email/name match before showing results.

4. **Adjustable result count** — let users request 10, 20, 50, or 100 results from the frontend

5. **UI redesign** — current design is functional but basic. User wants it to match the polish of their ClickUp setup. Preferences:
   - Day/night mode mandatory
   - Clean, not busy — reduce visual clutter
   - Light mode should breathe (whitespace, subtle shadows)
   - Clear hierarchy — headlines bright, secondary text dimmer
   - No decorative junk — every element earns its place
   - Key info visible, detail expandable
   - Font: Outfit (display) + DM Mono (data)

## ARCHITECTURE
```
FastAPI Backend (Railway)
├── app/main.py (serves frontend/index.html at / and /app)
├── app/api/routes.py (~900 lines — all API endpoints)
├── app/core/config.py (config — SERPER_API_KEY env var for Serper.dev)
├── app/core/database.py (SQLAlchemy async, async_session_factory)
├── app/models/models.py (8 tables)
├── app/models/schemas.py (includes ai_analysis in CreatorResponse, EnrichmentStatus)
├── app/services/
│   ├── discovery_engine.py (~800 lines)
│   │   ├── extract_json() — robust JSON extraction from Claude responses
│   │   ├── parse_search_intent() — generates 10-15 diverse search queries
│   │   ├── WebSearchProvider — supports Serper.dev (primary) + SearchAPI.io (fallback)
│   │   │   Auto-detects provider from key format
│   │   ├── RedditSearchProvider — searches subreddits via Reddit JSON API
│   │   ├── UGCMarketplaceProvider — searches Collabstr, Billo, JoinBrands via web search
│   │   ├── HashtagResearchProvider — searches hashtag creators via web search
│   │   ├── analyze_results() — Claude AI extracts profiles from raw search results
│   │   ├── deduplicate_results() — merges by handle/email/URL
│   │   └── DiscoveryEngine.discover() — orchestrates full pipeline
│   ├── enrichment_service.py (~500 lines)
│   │   ├── find_creator_email() — bio/linktree/web search email extraction
│   │   ├── analyze_creator_content() — web search for recent content + partnerships
│   │   ├── generate_outreach_strategy() — Claude AI personalized outreach
│   │   ├── enrich_creator() — full pipeline with progress tracking
│   │   └── _enrichment_jobs dict — in-memory progress for polling
│   ├── import_service.py
│   ├── clickup_service.py (all custom field IDs hardcoded)
│   └── gmail_service.py (ready for OAuth)
├── app/scrapers/
│   ├── reddit_scraper.py (73 subreddits, niche-mapped)
│   └── platform_scrapers.py
└── frontend/
    └── index.html (React JSX with Babel, served by FastAPI)
```

## KEY API ENDPOINTS

### Discovery (async)
- `POST /api/discover` → returns `{search_id, status: "starting"}` immediately
- `GET /api/discover/{search_id}` → poll for status + results
- `GET /api/discover/history` → recent searches
- `POST /api/discover/results/{id}/save` → save as creator
- `POST /api/discover/results/{id}/save-and-enrich` → save + start enrichment

### Enrichment (async)
- `POST /api/creators/{id}/enrich` → starts enrichment, returns immediately
- `GET /api/creators/{id}/enrich/status` → poll for progress
- `GET /api/creators/{id}/strategy` → get stored outreach strategy

### CRUD
- `GET /api/creators` → list with filters, pagination
- `GET /api/creators/{id}` → single creator (includes ai_analysis)
- `POST /api/import` → CSV/Excel import
- `GET /api/stats` → dashboard stats

## API KEYS (configured in Railway env vars)
- ANTHROPIC_API_KEY — working ✅
- SERPER_API_KEY — Serper.dev key (was SearchAPI.io, switched because credits ran out) ✅
- CLICKUP_API_TOKEN — configured ✅
- DATABASE_URL — Railway Postgres reference ✅

## SEARCH PROVIDER NOTES
- **Serper.dev** is now the primary search provider (2,500 free searches/month)
- The code auto-detects: Serper keys don't start with "V", SearchAPI.io keys do
- Serper uses POST to `https://google.serper.dev/search` with `X-API-KEY` header
- Response format: `organic` (not `organic_results`), `knowledgeGraph`, `peopleAlsoAsk`

## ENRICHMENT DATA STRUCTURE
When enrichment completes, `creator.ai_analysis` contains:
```json
{
  "enrichment": {
    "email_search": { "emails": [], "primary_email": null, "sources": [] },
    "content_analysis": { "content_results": [...], "total_found": 30 },
    "outreach_strategy": { ... }
  },
  "outreach_strategy": {
    "creator_summary": "...",
    "brand_fit_score": 9,
    "recommended_product": "Heart Health Bundle",
    "past_partnerships": ["IM8 Health", "Eight Sleep"],
    "outreach_angle": "...",
    "personalization_hooks": ["...", "..."],
    "suggested_subject_line": "...",
    "suggested_email_body": "... (full personalized email)",
    "estimated_rate_range": "$8,000 - $15,000",
    "content_ideas": ["...", "..."],
    "red_flags": ["..."],
    "priority_level": "high"
  },
  "last_enriched": "2026-03-31T00:20:51"
}
```

## LUMA NUTRITION CONTEXT
- Products: Heart Health Bundle, Gut Health Protocol, Longevity Protocol, Sleep/Mood, Blood Sugar, NAD+, Berberine, NAC, Probiotic
- Target creators: Doctors (MD/DO/NP), Gen Z wellness, fitness, mom/parenting, gut health niche, UGC creators
- 41 existing creators in DB with 37 columns (rates, quality rankings, MSA status, etc.)

## UI PREFERENCES
- Day/night mode mandatory
- Clean, not busy — reduce visual clutter
- Light mode should breathe (whitespace, subtle shadows)
- Clear hierarchy — headlines bright, secondary text dimmer
- No decorative junk — every element earns its place
- Key info visible, detail expandable
- Font: Outfit (display) + DM Mono (data)

## WHAT TO WORK ON NEXT (PRIORITY ORDER)
1. **Fix frontend Save & Enrich button** — backend works, frontend doesn't handle response
2. **Richer discovery result cards** — show content links, score reasoning, credentials, other profiles, partnerships, email quality flags
3. **Deduplicate against existing DB** — filter out already-saved creators from search results
4. **Adjustable result count** — slider or dropdown for 10/20/50/100
5. **UI redesign** — make it match ClickUp-level polish
6. **ClickUp "Push to Pipeline" button** — functional but not tested end-to-end
7. **Gmail OAuth** — for sending outreach emails directly from the app
