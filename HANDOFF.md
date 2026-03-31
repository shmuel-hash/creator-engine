# Creator Discovery Engine — Handoff (Updated March 31, 2026, End of Session 3)

## CORE INSIGHT FROM THIS SESSION
This is NOT a scraper — it's a **creator research tool for an influencer coordinator**. The coordinator needs to find creators, evaluate them in 5 seconds per card, and present the best ones to a creative strategist. Every feature should be judged by: "Does this help the coordinator make a faster, better decision?"

## WHAT THE COORDINATOR NEEDS PER CARD
1. Profile picture — instant vibe check
2. Clickable handle → opens their actual TikTok/IG
3. Real follower count
4. 2-3 niche tags
5. Email or contact method
6. Estimated rate

## PROJECT
- **GitHub:** https://github.com/shmuel-hash/creator-engine
- **Live:** https://creator-engine-production.up.railway.app
- **Stack:** Python 3.12, FastAPI, PostgreSQL (Railway), Serper.dev, Anthropic Claude, Apify
- **Frontend:** Single index.html (React JSX + Babel), Warm Studio design

## WHAT WORKS
- Discovery: natural language search → AI intent parsing → Serper web search → AI analysis/scoring → results
- Enrichment: Apify profile scrape (real followers, bio, avatar) → email search → saves to DB
- "Save & Enrich All" button — batch saves + enriches all results
- Dedup against existing DB
- Category filters (Creator Type + Content Niche)
- Slide-out detail panel
- Grid + List view
- Profile pictures (from Apify), clickable handles, email quality indicator
- Bulk delete (clear test data)
- URL validation, fake email filtering, quality scoring gates

## API KEYS (Railway env vars)
- ANTHROPIC_API_KEY ✅
- SERPER_API_KEY ✅
- APIFY_API_TOKEN ✅
- CLICKUP_API_TOKEN ✅
- DATABASE_URL ✅

## ARCHITECTURE
```
app/services/
├── discovery_engine.py — search intent → web search → AI analysis → scoring → storage
├── enrichment_service.py — Apify profile scrape → email search → save (2 steps, fast)
├── apify_service.py — TikTok + Instagram profile/hashtag scraping via Apify API
├── import_service.py, clickup_service.py, gmail_service.py
```

## ENRICHMENT PIPELINE (2 steps, ~15-30 seconds)
1. Apify profile scrape — real followers, bio, avatar URL, email, website
2. Email search — web search fallback if Apify didn't find email
(Content analysis and outreach strategy removed for speed — can be added as separate buttons)

## KEY DESIGN DECISIONS
- Discovery is FAST (~2 min) — uses Google search snippets, AI extracts what it can
- Enrichment fills in the gaps — Apify gets real platform data
- "Save & Enrich All" is the primary workflow — not one-at-a-time
- Cards saved this session stay visible (not grayed as "In DB")
- Scoring penalizes incomplete data: no handle = max 25, no handle + no followers = skip

## WHAT TO BUILD NEXT

### High Priority
1. **Doctor Discovery Mode** — specialized search queries for finding medical professionals with content presence. Search by credential + topic, not just "doctor creator". Target: Doximity profiles, podcast guest lists, LinkedIn, supplement-adjacent content.
2. **Profile pics during discovery** — currently only shows after enrichment. Could construct TikTok/IG avatar URL directly from handle without Apify call.
3. **Content samples** — show 1-2 recent video thumbnails or post images on the card
4. **Country filter** — let coordinator filter by US/international

### Medium Priority
5. **Outreach strategy as separate button** — "Generate Outreach" on enriched creators
6. **ClickUp Push to Pipeline** — send vetted creators to ClickUp
7. **Gmail OAuth** — send outreach emails from the app
8. **Apify hashtag search** — search TikTok by hashtag to find creators by content topic
9. **Better card layout** — show estimated rate, engagement rate when available

### Future
10. **Odyssey Scraper integration** — their Airtable base has a TikTok content scraper (videos + transcripts + engagement). Could wire up same approach.
11. **Creator comparison view** — side-by-side for presenting to creative strategist
12. **Bulk outreach** — send templated emails to multiple creators at once
