# Creator Discovery Engine

AI-powered creator discovery and outreach management for Luma Nutrition.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Creator Discovery Engine                      │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────┐ │
│  │   Frontend    │  │   FastAPI    │  │      PostgreSQL        │ │
│  │   (React)     │──│   Backend    │──│     Database           │ │
│  │              │  │              │  │                        │ │
│  └──────────────┘  └──────┬───────┘  └────────────────────────┘ │
│                           │                                      │
│           ┌───────────────┼───────────────┐                     │
│           │               │               │                     │
│     ┌─────▼─────┐  ┌─────▼─────┐  ┌─────▼─────┐              │
│     │ Discovery  │  │  Gmail    │  │  ClickUp  │              │
│     │  Engine    │  │  Service  │  │  Service  │              │
│     └─────┬──────┘  └───────────┘  └───────────┘              │
│           │                                                     │
│     ┌─────▼─────────────────────────────────┐                  │
│     │         Search Providers               │                  │
│     │  ┌─────────┐ ┌────────┐ ┌──────────┐ │                  │
│     │  │Web/API  │ │Reddit  │ │UGC Mkts  │ │                  │
│     │  │Search   │ │Scraper │ │Scraper   │ │                  │
│     │  └─────────┘ └────────┘ └──────────┘ │                  │
│     │  ┌──────────────────────────────────┐ │                  │
│     │  │ Claude AI (Intent + Analysis)    │ │                  │
│     │  └──────────────────────────────────┘ │                  │
│     └───────────────────────────────────────┘                  │
└─────────────────────────────────────────────────────────────────┘
```

## How Discovery Works

1. **Coordinator searches**: "Find doctors who talk about heart health on TikTok"

2. **AI Intent Parser** (Claude) breaks this down:
   - Niche: Doctor / Medical Professional
   - Topic: Heart health, cardiology, supplements
   - Platform priority: TikTok > Instagram > YouTube > Twitter
   - Credential signals: MD, DO, NP in bio
   - Search strategy: 6-8 specific queries + hashtags + subreddits

3. **Search Fanout** runs in parallel:
   - Web search for profiles matching criteria
   - Reddit scrape (r/UGCcreators, r/Supplements, medical subs)
   - UGC marketplace scan (Collabstr, Billo, JoinBrands)
   - Hashtag research (#hearthealth, #cardiology, #doctortok)

4. **AI Analyzer** (Claude) processes each result:
   - Verifies credentials (is this person actually a doctor?)
   - Scores content fit for Luma products (0-100)
   - Identifies red flags (fake followers, irrelevant content)
   - Extracts contact info from bios

5. **Results** are deduplicated, ranked, and stored.

## API Endpoints

### Creators
- `GET    /api/creators` — List/filter/search creators
- `GET    /api/creators/{id}` — Get creator details
- `POST   /api/creators` — Create creator manually
- `PATCH  /api/creators/{id}` — Update creator
- `DELETE /api/creators/{id}` — Delete creator

### Discovery
- `POST   /api/discover` — Run AI-powered discovery search
- `POST   /api/discover/results/{id}/save` — Save result as creator
- `GET    /api/discover/history` — View search history

### Import
- `POST   /api/import` — Upload CSV/Excel file

### Outreach
- `POST   /api/outreach` — Create outreach email
- `POST   /api/outreach/{id}/send` — Send via Gmail
- `GET    /api/outreach/creator/{id}` — Get outreach history

### Templates
- `GET    /api/templates` — List email templates
- `POST   /api/templates` — Create template

### ClickUp
- `POST   /api/creators/{id}/push-to-clickup` — Sync to ClickUp
- `POST   /api/creators/bulk-push-to-clickup` — Bulk sync

### Dashboard
- `GET    /api/stats` — Dashboard statistics

## Database Schema

**creators** — Central profile (maps to ClickUp Creator Pipeline fields)
**creator_tags** — Flexible tagging
**creator_notes** — Activity log
**outreach_emails** — Email tracking (syncs with Gmail)
**email_templates** — Reusable outreach templates
**discovery_searches** — Search log for learning
**discovery_results** — Raw results before saving
**scraper_jobs** — Background scraping state

## Setup

### 1. Clone and configure
```bash
cp .env.example .env
# Fill in your API keys
```

### 2. Required API keys
- `ANTHROPIC_API_KEY` — For AI intent parsing and analysis
- `CLICKUP_API_TOKEN` — For ClickUp sync
- `GOOGLE_CLIENT_ID/SECRET` — For Gmail OAuth (outreach)

### 3. Optional: Search API
The discovery engine needs a web search API. Options:
- **Brave Search** (free tier: 2000 queries/month) — recommended to start
- **SerpAPI** ($50/month, 5000 searches)
- **Google Custom Search** (100 free/day)

Configure in `.env` and wire up in `discovery_engine.py > WebSearchProvider`

### 4. Run locally
```bash
# Start PostgreSQL (Docker)
docker run -d --name creator-db -p 5432:5432 \
  -e POSTGRES_DB=creator_engine \
  -e POSTGRES_PASSWORD=password \
  postgres:16

# Install deps
pip install -r requirements.txt

# Run
uvicorn app.main:app --reload
```

### 5. Deploy to Railway
```bash
# Push to GitHub, then in Railway:
# 1. New Project → Deploy from GitHub
# 2. Add PostgreSQL plugin
# 3. Set environment variables
# 4. Deploy
```

## ClickUp Integration

Syncs with your existing ClickUp structure:
- **Marketing 2.0 → Influencer Partnerships**
  - Creator Pool (prospects) ← new discoveries go here
  - Creator Pipeline (active) ← progressed creators
  - Creator Content (producing) ← content tracking

All custom fields are mapped: Category, Email, Phone, Quality,
Agreed Rate, WL Rate, Portfolio, Production Months, etc.

## Excel Import

Auto-maps 37+ columns from your existing creator spreadsheets:
- Influencer Name, Email, Phone, Age, Gender
- TikTok/IG/YT/FB pages
- Content Categories (parsed into tags)
- Quality Ranking, Status
- Hero Video Rate, WL Rate
- MSA status, Core Team flag
- Lifestyle tags (Kids, Pets, Lawn, Modern Home)
- And more...

Handles deduplication by email address.

## Next Steps

- [ ] Wire up Brave Search API for web search provider
- [ ] Add Reddit OAuth for authenticated scraping
- [ ] Set up Gmail OAuth flow for outreach
- [ ] Build scheduled scraper jobs (Celery + Redis)
- [ ] Add creator enrichment pipeline (cross-platform profile linking)
- [ ] Connect frontend to live API
- [ ] Integrate into Luma Intelligence Dashboard
