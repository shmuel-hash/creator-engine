# Creator Discovery Engine — Handoff Script (Updated March 31, 2026, Session 3)
## Paste this at the start of a new Claude chat to pick up where we left off

---

## PROJECT OVERVIEW
AI-powered **Creator Discovery Engine** for Luma Nutrition — finds accessible, partnership-ready creators (UGC, micro-doctors, niche wellness) across TikTok, Instagram, YouTube, and generates personalized outreach strategies. Focus on creators who would realistically work at $200-$3,000 per deliverable.

## WHAT'S BUILT & DEPLOYED

### Backend (Python FastAPI + PostgreSQL on Railway)
- **GitHub repo:** https://github.com/shmuel-hash/creator-engine
- **Live URL:** https://creator-engine-production.up.railway.app
- **Frontend:** https://creator-engine-production.up.railway.app/ (served from FastAPI)
- **Swagger docs:** https://creator-engine-production.up.railway.app/docs
- **Database:** 41+ creators imported from Excel + discovered ones, PostgreSQL on Railway
- **Stack:** Python 3.12, FastAPI, SQLAlchemy async, Serper.dev (Google SERP), Anthropic Claude

### What's fully working (backend):
- All CRUD endpoints (30+ API routes)
- Excel/CSV import (auto-maps 37+ columns)
- Async discovery pipeline with strategic targeting
- Async enrichment pipeline with progress tracking + email conflict protection
- Save & Find Contact combo endpoint
- Standardized creator_type + content_niches categories
- URL validation, fake email filtering, quality gates
- ClickUp integration code, email templates, Gmail service (ready for OAuth)

### Frontend (React JSX, Warm Studio design):
- Warm Studio design — Instrument Serif + Plus Jakarta Sans, terracotta accent
- Card-warm pattern with hover lift, slide-out detail panel, grid/list toggle
- Category filters (Creator Type + Content Niche dropdowns)
- Dedup against existing DB, enrichment progress bar, strategy panel
- Email quality indicator, fake email detection, country display

## ARCHITECTURE
```
FastAPI Backend (Railway)
├── app/main.py
├── app/api/routes.py (~925 lines)
├── app/core/config.py, database.py
├── app/models/models.py (8 tables), schemas.py
├── app/services/
│   ├── discovery_engine.py (~970 lines) — intent parsing, search, AI analysis, scoring
│   ├── enrichment_service.py (~530 lines) — email finding, content analysis, outreach strategy
│   ├── import_service.py, clickup_service.py, gmail_service.py
├── app/scrapers/reddit_scraper.py, platform_scrapers.py
└── frontend/index.html (React JSX with Babel, Warm Studio design)
```

## API KEYS (Railway env vars)
- ANTHROPIC_API_KEY ✅, SERPER_API_KEY ✅, CLICKUP_API_TOKEN ✅, DATABASE_URL ✅

## STANDARDIZED CATEGORIES
**Creator Types:** Doctor/Medical, UGC Creator, Health Influencer, Fitness Creator, Mom/Parenting, Wellness/Lifestyle, Nutritionist/Dietitian, Podcaster, Other
**Content Niches:** Heart Health, Gut Health, Longevity, Supplements, Nutrition, Fitness, General Wellness, Weight Loss, Mental Health, Biohacking, Women's Health, Men's Health

## LUMA NUTRITION CONTEXT
- Products: Heart Health Bundle, Gut Health Protocol, Longevity Protocol, Sleep/Mood, Blood Sugar, NAD+, Berberine, NAC, Probiotic
- Budget: $200-$3,000 per creator per deliverable
- US-based creators preferred
- 41 existing creators in DB

## DESIGN SYSTEM
- Fonts: Instrument Serif (display), Plus Jakarta Sans (body), DM Mono (data)
- Colors: Terracotta #C45D3E, Cream #FAF8F5, Sage #5E8B6A
- Cards: card-warm, slide-out detail panel, grid/list toggle
- Reference: CreatorFind Warm Studio design

## WHAT TO WORK ON NEXT (PRIORITY ORDER)
1. Smarter enrichment — parse linktree/beacons pages, construct profile URLs from handle+platform
2. Apify integration — TikTok/Instagram Profile Scraper for real data
3. Profile resolution step — targeted searches to fill card gaps
4. Profile pictures from platform profiles
5. ClickUp Push to Pipeline button
6. Gmail OAuth for sending outreach
7. Country filter in search UI
8. Sortable results (by score, followers, engagement)
