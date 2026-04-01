"""
Creator Discovery Engine — AI-Powered Search Orchestrator

This is the brain of the system. It takes a natural language query like
"find doctors who talk about heart health on TikTok" and:

1. Uses Claude to parse the intent and build a search strategy
2. Fans out across multiple search sources (web, Reddit, UGC marketplaces)
3. Deduplicates and enriches raw results
4. Uses Claude to analyze and score each creator for relevance
5. Returns ranked, structured creator profiles

Architecture:
  DiscoveryEngine (orchestrator)
    ├── IntentParser (Claude) — understands what you're looking for
    ├── SearchFanout — runs searches in parallel across sources
    │   ├── WebSearchProvider — general web search for profiles
    │   ├── RedditSearchProvider — scrapes relevant subreddits
    │   ├── UGCMarketplaceProvider — searches creator marketplaces
    │   └── HashtagResearchProvider — platform hashtag analysis
    ├── ResultDeduplicator — merges results about the same person
    └── AIAnalyzer (Claude) — scores and enriches each result
"""

import asyncio
import json
import re
import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

import httpx
from anthropic import AsyncAnthropic
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import get_settings
from app.models.models import (
    DiscoverySearch, DiscoveryResult, Creator, CreatorSource
)

logger = logging.getLogger(__name__)
settings = get_settings()


def detect_platform(result_data: dict) -> str:
    """Detect platform from result data, falling back to URL-based detection."""
    platform = result_data.get("platform")
    if platform:
        return platform
    profile_url = (result_data.get("profile_url") or "").lower()
    if "linkedin.com" in profile_url:
        return "linkedin"
    if "tiktok.com" in profile_url:
        return "tiktok"
    if "instagram.com" in profile_url:
        return "instagram"
    if "youtube.com" in profile_url or "youtu.be" in profile_url:
        return "youtube"
    if "twitter.com" in profile_url or "x.com" in profile_url:
        return "twitter"
    if "reddit.com" in profile_url:
        return "reddit"
    if "facebook.com" in profile_url:
        return "facebook"
    return "unknown"


def extract_json(text: str):
    """
    Robustly extract a JSON object or array from Claude's response.

    Handles common issues:
    - Markdown ```json fences
    - Preamble text before the JSON ("Here's the analysis:\n{...}")
    - Trailing text after the JSON
    - Multiple JSON blocks (takes the first valid one)
    """
    # Strip markdown fences
    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*", "", text)
    text = text.strip()

    # Try direct parse first (happy path)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Use raw_decode: finds valid JSON starting at a given position,
    # ignoring trailing text. Try every [ or { as a candidate start.
    decoder = json.JSONDecoder()

    # Collect all candidate start positions, prefer [ before { at same pos
    # so arrays aren't swallowed as inner objects
    candidates = []
    for i, ch in enumerate(text):
        if ch == "[":
            candidates.append(i)
        elif ch == "{":
            candidates.append(i)

    for pos in candidates:
        try:
            result, end_idx = decoder.raw_decode(text, pos)
            return result
        except json.JSONDecodeError:
            continue

    raise json.JSONDecodeError("No valid JSON found in response", text, 0)


# ─── INTENT PARSER ───

# ─── DOCTOR DISCOVERY MODE ───

DOCTOR_INTENT_PARSER_PROMPT = """You are a specialized medical professional discovery assistant for Luma Nutrition, a DTC supplement brand.
Your job is to find REAL DOCTORS AND MEDICAL PROFESSIONALS who also create content — NOT celebrity doctors or mega-influencers.

This is DOCTOR DISCOVERY MODE. The coordinator is specifically looking for medical professionals (MDs, DOs, NPs, PAs, RDs, PharmDs, PhDs) who:
1. Have real medical credentials
2. Create content on social media (even small audiences)
3. Would be accessible for a $200-$3,000 partnership

Luma's products: Heart Health Bundle, Gut Health Protocol, Longevity Protocol, Sleep/Mood, Blood Sugar, NAD+, Berberine, NAC, Probiotic.

WHO WE'RE LOOKING FOR (in order of priority):
1. **Micro-doctor creators** (5K-300K followers) — real MDs, DOs who make health content on TikTok/IG/YouTube
2. **Nurse practitioners & PAs with content** — NPs and PAs who review supplements, share health tips
3. **Registered Dietitians (RDs)** — nutrition professionals who create content about gut health, supplements
4. **PharmDs with social presence** — pharmacists who review supplements and medications on social
5. **Naturopathic doctors (NDs)** — naturopaths who discuss supplements and natural health
6. **Medical researchers/PhDs** — scientists who translate research for lay audiences

WHO TO EXPLICITLY EXCLUDE:
- Celebrity doctors: Andrew Huberman, Peter Attia, Rhonda Patrick, Dr. Berg, Dr. Oz, Mark Hyman, Dr. Mike Varshavski, Dr. Eric Berg
- Anyone with 1M+ followers
- Hospital/institutional accounts
- Doctors who only post about cosmetic/plastic surgery (unless they also do wellness)
- Medical news aggregator accounts

SEARCH STRATEGY — DOCTOR-SPECIFIC QUERIES:
Generate 12-18 search queries using these PROVEN strategies for finding micro-doctor creators:

1. CREDENTIAL + PLATFORM + TOPIC (highest signal):
   - "MD" OR "DO" tiktok [TOPIC] creator "business inquiries"
   - "nurse practitioner" instagram [TOPIC] "link in bio"
   - "registered dietitian" tiktok supplements gut health
   - "PharmD" OR "pharmacist" tiktok supplement review
   - "board certified" [SPECIALTY] tiktok OR instagram creator

2. PROFESSIONAL DIRECTORIES + SOCIAL CROSSREF:
   - site:doximity.com [SPECIALTY] [TOPIC] social media
   - site:linkedin.com "MD" OR "DO" "content creator" OR "health influencer" [TOPIC]
   - "doctor" "content creator" [TOPIC] portfolio OR collab

3. PODCAST GUEST LISTS (doctors who do podcasts are content-ready):
   - "[TOPIC] podcast" guest "MD" OR "DO" OR "doctor" 2025 2026
   - "health podcast" guest list doctor [TOPIC] supplement
   - "interviewed" "doctor" [TOPIC] podcast episode

4. MEDICAL CONFERENCE SPEAKERS (with social presence):
   - "[TOPIC] conference" speaker "MD" tiktok OR instagram OR youtube
   - "functional medicine" conference speaker social media

5. DOCTOR LISTICLES & ROUNDUPS:
   - "doctors on tiktok" [TOPIC] 2025 2026 follow
   - "medical professionals" social media [TOPIC] "micro influencer"
   - "best doctor" creators tiktok instagram [TOPIC] "small" OR "underrated"
   - "doctor influencer" [TOPIC] list 2025 2026

6. SUPPLEMENT-ADJACENT DOCTORS:
   - "doctor" "supplement review" youtube OR tiktok [TOPIC]
   - "MD reviews" supplements [TOPIC]
   - "doctor recommends" [TOPIC] supplements tiktok

7. NICHE MEDICAL SPECIALTIES → LUMA PRODUCTS:
   - For Heart Health: "cardiologist" OR "cardiology" tiktok instagram creator
   - For Gut Health: "gastroenterologist" OR "GI doctor" tiktok content
   - For Longevity: "anti-aging" OR "longevity" doctor creator tiktok
   - For Sleep: "sleep medicine" doctor tiktok OR instagram
   - For Blood Sugar: "endocrinologist" OR "diabetes" doctor tiktok creator

Replace [TOPIC] with the actual topic from the user's query. If no topic specified, use Luma's core areas.

Given the search query, return a JSON object with:
{
  "primary_niche": "the medical specialty or focus area",
  "sub_niches": ["specific medical sub-specialties to search"],
  "topics": ["specific health topics they'd discuss"],
  "platforms": ["prioritized platforms"],
  "search_queries": ["12-18 specific web search queries using the strategies above"],
  "medical_specialties": ["specific specialties to target: cardiology, gastroenterology, etc."],
  "credential_types": ["MD", "DO", "NP", "RD", "PharmD", etc.],
  "hashtags": ["relevant medical creator hashtags"],
  "subreddits": ["relevant medical/health subreddits"],
  "ugc_search_terms": ["terms for finding doctor UGC"],
  "credential_signals": ["board certified", "fellowship trained", "residency at...", etc.],
  "follower_range": {"min": 5000, "max": 500000},
  "content_fit_signals": ["supplement reviews", "evidence-based", "patient education"],
  "reasoning": "brief explanation of your search strategy"
}

Return ONLY the JSON, no other text."""

DOCTOR_ANALYZER_PROMPT = """You are analyzing raw web search results to extract MEDICAL PROFESSIONALS who create content, for Luma Nutrition.
Luma is a US-based DTC supplement brand selling: Heart Health Bundle, Gut Health Protocol, Longevity Protocol.

THIS IS DOCTOR DISCOVERY MODE. You are specifically looking for credentialed medical professionals.

YOUR CORE JOB: Extract INDIVIDUAL DOCTORS/MEDICAL PROFESSIONALS from these search results who:
1. Have REAL medical credentials (MD, DO, NP, PA, RD, PharmD, PhD, ND)
2. Create content on social media (even small accounts)
3. Would realistically partner with a DTC supplement brand at $200-$3,000 per deliverable

CRITICAL — CREDENTIAL VERIFICATION:
- Look for credential signals: "MD", "DO", "Dr.", "NP", "PA-C", "RD", "RDN", "PharmD", "PhD", "ND", "DACM"
- Look for specialty signals: "board certified", "fellowship", "residency", specific hospital/clinic names
- If someone claims to be a "health coach" or "wellness expert" without medical credentials, they are NOT a doctor — still include but set creator_type to "Health Influencer" not "Doctor/Medical"
- Naturopathic doctors (ND) should be flagged as such — they're valid but different from MDs

SCORING FOR DOCTORS (credential weight is HIGH):
- 90-100: Verified credential (MD/DO) + social handle + followers + relevant topic + partnership signals
- 80-89: Verified credential + social handle + relevant topic (missing followers or contact)
- 70-79: Likely credentialed (Dr. title) + social presence + relevant topic
- 60-69: Allied health (NP, RD, PharmD) + social presence + relevant topic
- 50-59: Credential unclear but health professional with social presence
- 40-49: Found on professional directory but no visible social presence
- Below 30: Celebrity doctor, no credentials found, or institutional account

DATA QUALITY — SAME RULES APPLY:
- No social handle → max score 30 (doctors without social are useless for partnerships)
- No handle AND no followers → skip
- Must be a real individual, not a hospital or practice account

AUTOMATICALLY SCORE LOW (below 30):
- Celebrity doctors: Huberman, Attia, Rhonda Patrick, Dr. Berg, Dr. Oz, Mark Hyman, Dr. Mike, etc.
- Anyone with 1M+ followers
- Hospital/institutional accounts
- Medical news aggregators

For each person, extract:
1. **Identity**: Full name, credentials (MD, DO, NP, etc.), social handle(s)
2. **Profile URLs**: Links to TikTok, Instagram, YouTube, LinkedIn, Doximity
3. **Medical credentials**: Specific degree, specialty, board certifications
4. **Practice info**: Hospital/clinic affiliation, specialty area
5. **Content focus**: What health topics they create about
6. **Audience**: Follower counts on each platform
7. **Contact**: Email, business inquiry links, clinic contact
8. **Partnership signals**: Brand collabs, "DM for partnerships", supplement mentions
9. **Country/Region**: Where they practice/are based
10. **Estimated rate**: Based on follower count + credential premium (doctors can charge more)
11. **Creator type**: "Doctor/Medical", "Nutritionist/Dietitian", or "Health Influencer" (if no medical credential)
12. **Content niches**: From ["Heart Health", "Gut Health", "Longevity", "Supplements", "Nutrition", "Fitness", "General Wellness", "Weight Loss", "Mental Health", "Biohacking", "Women's Health", "Men's Health", "Sleep", "Blood Sugar"]

Return JSON array:
[
  {
    "name": "Dr. Jane Smith",
    "handle": "@drjanesmith",
    "platform": "tiktok",
    "profile_url": "https://tiktok.com/@drjanesmith",
    "other_profiles": {"instagram": "@drjanesmith", "linkedin": "url"},
    "bio": "Board-certified cardiologist. Heart health tips...",
    "email": "jane@drjanesmith.com",
    "estimated_followers": 45000,
    "estimated_engagement_rate": null,
    "creator_type": "Doctor/Medical",
    "content_niches": ["Heart Health", "Supplements"],
    "categories": ["Doctor", "Cardiologist", "Heart Health"],
    "credentials": ["MD", "Board Certified Cardiologist", "FACC"],
    "medical_specialty": "Cardiology",
    "practice_affiliation": "City Medical Center",
    "past_partnerships": ["Brand X supplement"],
    "country": "US",
    "language": "English",
    "estimated_rate": "$500-$1000",
    "relevance_score": 88,
    "content_fit_reasoning": "Board-certified cardiologist with 45K TikTok. Reviews supplements, evidence-based. Perfect for Heart Health Bundle. Credential premium justifies $500-$1000 rate.",
    "red_flags": [],
    "recommended_action": "save",
    "source_urls": ["url where found"]
  }
]

IMPORTANT RULES:
- Credential quality > follower count. A 10K-follower MD is more valuable than a 200K-follower wellness coach.
- Extract SPECIFIC credentials, not just "doctor" — we need to know MD vs DO vs NP vs RD
- If found on Doximity/LinkedIn, try to cross-reference with social media handles from other results
- Don't pad the list — 8 credentialed doctors with handles > 20 vague entries
- In content_fit_reasoning, mention their SPECIFIC credential and how it maps to Luma products

LANGUAGE FILTERING (CRITICAL):
- Luma needs creators who make content in ENGLISH or SPANISH only.
- Look for language signals: bio language, content titles, country of practice, name ethnicity + country combo
- If creator's content appears to be in a non-English/non-Spanish language, set recommended_action to "skip" and add "Non-English/Spanish content" to red_flags
- If uncertain about language, note it in red_flags as "Language uncertain — verify content language"
- Country clues: India, Middle East, East Asia, Brazil (Portuguese), France, Germany, etc. → check if they create content in English despite being from that country (many do)

PARTNERSHIP EXTRACTION (IMPORTANT):
- ACTIVELY look for partnership signals in every snippet: brand names mentioned, "#ad", "#sponsored", "#gifted", "partnered with", "ambassador for", "collab with"
- Check for common supplement/health brand partnerships: Athletic Greens, Seed, Ritual, Thorne, Garden of Life, NOW Foods, Nature Made
- If they're on a talent agency roster, note the agency name
- "No partnerships found" is useful info — include empty array, don't omit the field

Return ONLY the JSON array, no other text."""

INTENT_PARSER_PROMPT = """You are a creator discovery assistant for Luma Nutrition, a DTC supplement brand.
Your job is to find ACCESSIBLE, PARTNERSHIP-READY creators — NOT celebrities or mega-influencers.

Luma's products: Heart Health Bundle, Gut Health Protocol, Longevity Protocol, Sleep/Mood, Blood Sugar, NAD+, Berberine, NAC, Probiotic.

WHO WE'RE LOOKING FOR (in order of priority):
1. **UGC creators** — people who make content-for-hire, typically $200-$1000/video. They may not even have huge followings. Search UGC marketplaces, UGC-specific hashtags, and creator directories.
2. **Micro/mid-tier doctor creators** (5K-500K followers) — real MDs, DOs, NPs, RDs who make health content but are NOT famous. Think: a family medicine doctor with 30K TikTok followers who does supplement reviews. NOT Andrew Huberman, Dr. Berg, Dr. Mark Hyman, etc.
3. **Niche wellness creators** (10K-300K followers) — gut health, heart health, longevity, biohacking creators who actively do brand partnerships at accessible rates ($500-$3000/post).
4. **Gen Z health/wellness creators** — younger creators building audiences around health, supplements, nutrition. Typically 10K-200K followers.
5. **Mom/parenting health creators** — moms who talk about family health, supplements, nutrition. Typically open to partnerships.

WHO TO EXPLICITLY EXCLUDE:
- Anyone with 1M+ followers (too expensive, won't respond)
- Celebrity doctors (Huberman, Dr. Berg, Dr. Oz, Dr. Mark Hyman, Dr. Eric Berg, Peter Attia, Rhonda Patrick, etc.)
- Major podcasters (unless they're small/mid-tier)
- Anyone who clearly only works with Fortune 500 brands
- Pure entertainment accounts that don't do health content

BUDGET CONTEXT: Luma's per-creator budget is $200-$3000. Creators charging $5K+ per post are generally out of range unless they're a perfect strategic fit.

Given the search query, return a JSON object with:
{
  "primary_niche": "the main type of creator",
  "sub_niches": ["more specific niches to search"],
  "topics": ["specific topics they'd talk about"],
  "platforms": ["prioritized platforms to search"],
  "search_queries": ["10-15 specific web search queries - see strategy notes below"],
  "hashtags": ["relevant platform hashtags to research"],
  "subreddits": ["relevant subreddits to search"],
  "ugc_search_terms": ["terms for UGC marketplace search"],
  "credential_signals": ["things to look for in bios that confirm they're legit"],
  "follower_range": {"min": null, "max": null},
  "content_fit_signals": ["what would make their content a good fit for Luma products"],
  "reasoning": "brief explanation of your search strategy"
}

CRITICAL — SEARCH QUERY STRATEGY:
Generate 10-15 diverse, specific search queries designed to find SMALL-TO-MID creators, NOT celebrities:

1. UGC-FOCUSED (highest priority):
   - site:collabstr.com health supplement UGC creator
   - site:billo.app health wellness creator
   - site:joinbrands.com supplement nutrition creator
   - "ugc creator" "health" OR "supplements" OR "wellness" email
   - "ugc" "supplement review" tiktok OR instagram

2. MICRO-CREATOR DISCOVERY (explicitly targeting small accounts):
   - "heart health" tiktok creator "business inquiries" -huberman -berg
   - "gut health creator" "50k" OR "30k" OR "20k" followers collab
   - "doctor tiktok" "supplement" small creator
   - "MD" OR "NP" OR "RD" tiktok health tips "link in bio" -million

3. LIST/ROUNDUP ARTICLES:
   - "micro influencers" health wellness 2025 2026 list
   - "underrated" health creators tiktok instagram to follow
   - "small" OR "micro" doctor creators social media

4. CREATOR PLATFORMS & DIRECTORIES:
   - site:linkedin.com "health creator" OR "UGC creator" "open to collaborations"
   - "health" "brand ambassador" "apply" supplement

5. COMMUNITY DISCOVERY:
   - site:reddit.com "small" health creators recommend tiktok
   - site:reddit.com UGC creator health supplements

6. CONTACT-READY SIGNALS:
   - "health creator" "DM for collabs" OR "business inquiries" OR "partnerships"
   - "supplement review" creator "PR" OR "gifted" OR "collab" email

The goal is to find ACCESSIBLE creators who would realistically work with a DTC supplement brand at $200-$3000 per deliverable. Skip the famous ones — we want the hidden gems.

Return ONLY the JSON, no other text."""


async def parse_search_intent(query: str, platforms: list[str], search_mode: str = "general") -> dict:
    """Use Claude to parse a natural language query into a structured search strategy."""
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    # Pick prompt based on search mode
    system_prompt = DOCTOR_INTENT_PARSER_PROMPT if search_mode == "doctor" else INTENT_PARSER_PROMPT

    response = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": f"Search query: {query}\nPreferred platforms: {', '.join(platforms)}"
        }],
        system=system_prompt,
    )

    text = response.content[0].text

    try:
        return extract_json(text)
    except json.JSONDecodeError:
        logger.error(f"Failed to parse intent response: {text[:200]}")
        # Fallback: basic parsing
        return {
            "primary_niche": query.split()[0] if query else "creator",
            "search_queries": [
                f"{query} TikTok creator",
                f"{query} Instagram influencer",
                f"{query} content creator",
            ],
            "hashtags": [],
            "subreddits": ["r/UGCcreators"],
            "credential_signals": [],
            "reasoning": "Fallback parsing",
        }


# ─── SEARCH PROVIDERS ───

class WebSearchProvider:
    """
    Web search provider — supports Serper.dev (preferred) and SearchAPI.io (fallback).

    Serper.dev: https://serper.dev
    - POST https://google.serper.dev/search
    - Auth: X-API-KEY header
    - 2,500 free searches/month

    SearchAPI.io: https://www.searchapi.io
    - GET https://www.searchapi.io/api/v1/search
    - Auth: Bearer token
    """

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30)
        self.api_key = settings.serper_api_key  # env var name kept for compat
        # Auto-detect provider: Serper keys are shorter and don't start with V
        self._use_serper = bool(self.api_key and not self.api_key.startswith("V"))

    async def search(self, queries: list[str], max_results_per_query: int = 10) -> list[dict]:
        """Run multiple search queries and aggregate results."""
        all_results = []

        for query in queries:
            try:
                if self._use_serper:
                    results = await self._serper_search(query, max_results_per_query)
                else:
                    results = await self._searchapi_search(query, max_results_per_query)
                all_results.extend(results)
            except Exception as e:
                logger.error(f"Web search failed for '{query}': {e}")

        return all_results

    async def _serper_search(self, query: str, num_results: int) -> list[dict]:
        """Execute a search via Serper.dev (Google SERP API)."""
        if not self.api_key:
            logger.warning("No Serper API key configured — skipping web search")
            return []

        try:
            response = await self.client.post(
                "https://google.serper.dev/search",
                json={
                    "q": query,
                    "num": min(num_results, 100),
                },
                headers={
                    "X-API-KEY": self.api_key,
                    "Content-Type": "application/json",
                },
            )

            if response.status_code != 200:
                logger.error(f"Serper error {response.status_code}: {response.text[:200]}")
                return []

            data = response.json()
            results = []

            # Parse organic results
            for item in data.get("organic", []):
                results.append({
                    "url": item.get("link", ""),
                    "title": item.get("title", ""),
                    "snippet": item.get("snippet", ""),
                    "position": item.get("position", 0),
                    "source": "serper",
                    "query": query,
                })

            # Knowledge graph
            kg = data.get("knowledgeGraph", {})
            if kg.get("title"):
                results.append({
                    "url": kg.get("website", ""),
                    "title": kg.get("title", ""),
                    "snippet": kg.get("description", ""),
                    "position": 0,
                    "source": "serper_knowledge_graph",
                    "query": query,
                })

            # People also ask — can surface creator names
            for paa in data.get("peopleAlsoAsk", [])[:3]:
                if paa.get("snippet"):
                    results.append({
                        "url": paa.get("link", ""),
                        "title": paa.get("question", ""),
                        "snippet": paa.get("snippet", ""),
                        "position": 99,
                        "source": "serper_paa",
                        "query": query,
                    })

            logger.info(f"Serper: '{query}' → {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"Serper request failed: {e}")
            return []

    async def _searchapi_search(self, query: str, num_results: int) -> list[dict]:
        """Execute a search via SearchAPI.io (legacy fallback)."""
        if not self.api_key:
            return []

        try:
            response = await self.client.get(
                "https://www.searchapi.io/api/v1/search",
                params={
                    "q": query,
                    "engine": "google",
                    "num": min(num_results, 100),
                },
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Accept": "application/json",
                },
            )

            if response.status_code != 200:
                logger.error(f"SearchAPI error {response.status_code}: {response.text[:200]}")
                return []

            data = response.json()
            results = []

            for item in data.get("organic_results", []):
                results.append({
                    "url": item.get("link", ""),
                    "title": item.get("title", ""),
                    "snippet": item.get("snippet", ""),
                    "position": item.get("position", 0),
                    "source": "searchapi",
                    "query": query,
                })

            kg = data.get("knowledge_graph", {})
            if kg.get("title"):
                results.append({
                    "url": kg.get("website", ""),
                    "title": kg.get("title", ""),
                    "snippet": kg.get("description", ""),
                    "position": 0,
                    "source": "searchapi_knowledge_graph",
                    "query": query,
                })

            logger.info(f"SearchAPI: '{query}' → {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"SearchAPI request failed: {e}")
            return []

class RedditSearchProvider:
    """
    Searches Reddit for creator self-promotion posts and recommendations.
    Key subreddits for UGC/creator discovery:
    - r/UGCcreators, r/ugc, r/influencermarketing
    - Niche subs: r/Supplements, r/fitness, r/SkincareAddiction, etc.
    """

    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=30,
            headers={"User-Agent": "CreatorDiscoveryBot/1.0"}
        )
        self.base_url = "https://www.reddit.com"

    async def search(self, subreddits: list[str], search_terms: list[str], limit: int = 25) -> list[dict]:
        """Search across multiple subreddits for creator posts."""
        all_results = []

        for subreddit in subreddits:
            for term in search_terms[:3]:  # Limit queries per sub
                try:
                    results = await self._search_subreddit(subreddit, term, limit)
                    all_results.extend(results)
                except Exception as e:
                    logger.error(f"Reddit search failed for {subreddit}/{term}: {e}")

        return all_results

    async def _search_subreddit(self, subreddit: str, query: str, limit: int) -> list[dict]:
        """Search a specific subreddit."""
        sub = subreddit.replace("r/", "")
        url = f"{self.base_url}/r/{sub}/search.json"

        try:
            response = await self.client.get(url, params={
                "q": query,
                "restrict_sr": "on",
                "sort": "relevance",
                "t": "year",
                "limit": min(limit, 25),
            })

            if response.status_code != 200:
                return []

            data = response.json()
            posts = data.get("data", {}).get("children", [])

            results = []
            for post in posts:
                p = post.get("data", {})
                results.append({
                    "source": "reddit",
                    "subreddit": sub,
                    "title": p.get("title", ""),
                    "body": p.get("selftext", "")[:1000],
                    "url": f"https://reddit.com{p.get('permalink', '')}",
                    "author": p.get("author", ""),
                    "score": p.get("score", 0),
                    "created_utc": p.get("created_utc", 0),
                })

            return results

        except Exception as e:
            logger.error(f"Reddit API error: {e}")
            return []


class UGCMarketplaceProvider:
    """
    Searches UGC creator marketplaces and directories via web search.
    Targets: Collabstr, Billo, JoinBrands, Insense, etc.
    """

    def __init__(self):
        self.web = WebSearchProvider()

    MARKETPLACES = [
        {"name": "Collabstr", "domain": "collabstr.com"},
        {"name": "Billo", "domain": "billo.app"},
        {"name": "JoinBrands", "domain": "joinbrands.com"},
        {"name": "Insense", "domain": "insense.pro"},
        {"name": "Hashtag Paid", "domain": "hashtagpaid.com"},
    ]

    async def search(self, search_terms: list[str]) -> list[dict]:
        """Search across UGC marketplaces using real web search."""
        queries = []
        for marketplace in self.MARKETPLACES[:3]:  # top 3 to save API credits
            for term in search_terms[:2]:
                queries.append(f"site:{marketplace['domain']} {term} creator")

        if not queries:
            return []

        return await self.web.search(queries, max_results_per_query=5)


class HashtagResearchProvider:
    """
    Researches relevant hashtags on platforms to find creators via web search.
    """

    def __init__(self):
        self.web = WebSearchProvider()

    async def search(self, hashtags: list[str], platforms: list[str]) -> list[dict]:
        """Find creators through hashtag research using real web search."""
        queries = []
        for platform in platforms[:3]:
            for hashtag in hashtags[:3]:
                tag = hashtag.replace("#", "")
                queries.append(f"top {platform} creators #{tag} 2025 2026 influencer")

        if not queries:
            return []

        return await self.web.search(queries, max_results_per_query=5)


# ─── AI ANALYZER ───

ANALYZER_PROMPT = """You are analyzing raw web search results to extract individual creator/influencer profiles for Luma Nutrition.
Luma is a US-based DTC supplement brand selling: Heart Health Bundle, Gut Health Protocol, Longevity Protocol.

YOUR CORE JOB: Extract INDIVIDUAL PEOPLE from these search results who would realistically partner with a DTC supplement brand at $200-$3,000 per deliverable.

CRITICAL — DATA QUALITY REQUIREMENTS:
A creator is ONLY useful if we have ENOUGH information to actually reach out. Before scoring, check:
- Do we have at least ONE social media handle or profile URL? If NO → score max 25, flag "No direct social handle found"
- Do we have follower count on any platform? If NO → subtract 20 points from score
- Do we have BOTH no handle AND no follower count? → score max 15, set recommended_action to "skip"
- Do we have a way to contact them (email, DM, linktree)? If NO → subtract 10 points
- Is the person clearly a real individual (not a brand, agency listing, or directory entry)? If NO → score 0, skip them

DO NOT include people who are just LISTED on a talent directory or marketplace without any additional info. If all you know is "Name + talent agency URL", that's not enough — score 0, skip them.

CRITICAL BUSINESS CONTEXT — WHO IS AND ISN'T VIABLE:

IDEAL CREATORS (score 70-100, but only if data is complete):
- UGC creators who make content-for-hire ($200-$1000/video) — must have portfolio or social handle
- Micro doctors (5K-300K followers) — real MDs/DOs/NPs with visible social media presence
- Niche wellness creators (10K-300K) who actively partner with supplement/health brands
- Gen Z health creators building audiences, open to gifted/paid partnerships
- Mom/parenting health creators who review products

AUTOMATICALLY SCORE LOW (below 30):
- Celebrity doctors: Andrew Huberman, Peter Attia, Rhonda Patrick, Dr. Berg, Dr. Oz, Mark Hyman, Dr. Mike, or anyone clearly famous
- Anyone with 1M+ followers
- Major podcast hosts with millions of listeners
- Pure entertainment accounts that don't discuss health/wellness
- Generic health news sites, hospitals, or institutional accounts

GEOGRAPHIC PRIORITY:
- US-based creators are strongly preferred (Luma ships primarily in the US)
- Canada, UK, Australia are acceptable but note the country
- Other countries: score -10 and flag as "non-US creator"
- Extract country/region whenever possible from bio, location, domain (.au = Australia, .uk = UK, etc.)

SCORING (data completeness is a HARD requirement):
- 90-100: Has social handle + follower count + email/contact + relevant niche + partnership signals. Perfect fit.
- 70-89: Has social handle + either followers or contact info + relevant niche. Strong fit.
- 50-69: Has social handle but missing followers/contact. OR right niche but missing key data.
- 30-49: Name only, no handle, or only found via directory listing. Needs more research.
- Below 30: Celebrity, no useful data, wrong niche, or institutional.

For each person you identify, extract:

1. **Identity**: Full name, social handle(s), platform(s)
2. **Profile URLs**: Actual links to TikTok, Instagram, YouTube, Twitter, LinkedIn
3. **Contact**: Email, business inquiry links, linktree, management/agency
4. **Credentials**: MD, DO, NP, RD, PhD, certified trainer, etc.
5. **Content focus**: What topics they create about
6. **Audience signals**: Follower counts (extract from text like "500K followers" → 500000)
7. **Brand partnerships**: Brands they work with — especially DTC/supplement brands
8. **Partnership signals**: "business inquiries", "PR friendly", "DM for collabs", UGC in bio
9. **Country/Region**: Where they're based (extract from bio, location, URL domains)
10. **Estimated rate**: Based on follower count (micro: $200-$800, mid: $800-$3000)
11. **Creator type**: Pick ONE from this exact list: "Doctor/Medical", "UGC Creator", "Health Influencer", "Fitness Creator", "Mom/Parenting", "Wellness/Lifestyle", "Nutritionist/Dietitian", "Podcaster", "Other"
12. **Content niches**: Pick 1-3 from this exact list: "Heart Health", "Gut Health", "Longevity", "Supplements", "Nutrition", "Fitness", "General Wellness", "Weight Loss", "Mental Health", "Biohacking", "Women's Health", "Men's Health"

Return a JSON array:
[
  {
    "name": "Dr. Jane Smith",
    "handle": "@drjanesmith",
    "platform": "tiktok",
    "profile_url": "https://tiktok.com/@drjanesmith",
    "other_profiles": {"instagram": "@drjanesmith"},
    "bio": "Family medicine doc sharing heart health tips...",
    "email": "jane@drjanesmith.com",
    "estimated_followers": 45000,
    "estimated_engagement_rate": null,
    "creator_type": "Doctor/Medical",
    "content_niches": ["Heart Health", "Supplements"],
    "categories": ["Doctor", "Family Medicine", "Heart Health"],
    "credentials": ["MD"],
    "past_partnerships": ["Brand X supplement"],
    "country": "US",
    "relevance_score": 85,
    "content_fit_reasoning": "Micro-doctor with 45K TikTok followers who reviews supplements. Has done paid partnerships with 2 supplement brands. Likely rate: $500-$800/video. Perfect for Luma Heart Health.",
    "red_flags": [],
    "recommended_action": "save",
    "source_urls": ["url where found"]
  }
]

IMPORTANT RULES:
- If you can't find a social handle or profile URL, set recommended_action to "skip" unless they have exceptional credentials
- Don't pad the list with low-quality entries — 8 solid creators with handles > 20 names from talent directories
- In content_fit_reasoning, be specific about WHY and include estimated rate
- Always extract country when possible

EXTRACTION — BE THOROUGH WITH THE DATA YOU HAVE:
- URLs contain handles: tiktok.com/@drheartdoc → handle is @drheartdoc, platform is tiktok
- Snippets contain emails: look for anything@domain.com patterns in every snippet
- Snippets contain follower counts: "50K followers", "250,000 subscribers", "500k on TikTok" → extract the number
- Snippets contain bios: "Family medicine doctor sharing..." → use as bio
- If a creator appears in multiple search results, MERGE all the data into one entry
- Look for "linktree", "linktr.ee", "beacons.ai" URLs — these often have email + all social links
- Look for "business inquiries", "collabs", "partnerships", "PR", "booking" in snippets — these indicate accessibility
- List articles ("Top 10 doctors on TikTok") should yield 10 separate entries, each with whatever handle/URL the article mentions
- If you find an Instagram handle but the search was for TikTok, still include it — put it in other_profiles

YOUR OUTPUT QUALITY IS JUDGED BY: how many creators have BOTH a social handle AND enough info (followers, bio, or email) to make an outreach decision. Empty cards with just a name are useless.

LANGUAGE FILTERING (CRITICAL):
- Luma needs creators who make content in ENGLISH or SPANISH only.
- If creator's content appears to be in a non-English/non-Spanish language, set recommended_action to "skip" and add "Non-English/Spanish content" to red_flags
- Include a "language" field in your output: "English", "Spanish", or the detected language
- Country clues: India, Middle East, East Asia, Brazil, France, Germany → check if they create in English despite location

PARTNERSHIP EXTRACTION:
- ACTIVELY look for brand partnerships in every snippet: brand names, "#ad", "#sponsored", "ambassador for"
- Include "past_partnerships" array even if empty — this is valuable info for the coordinator

Return ONLY the JSON array, no other text."""


async def analyze_results(
    raw_results: list[dict],
    search_intent: dict,
    original_query: str,
    search_mode: str = "general"
) -> list[dict]:
    """Use Claude to analyze and score raw search results."""
    if not raw_results:
        return []

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    # Pick prompt based on search mode
    system_prompt = DOCTOR_ANALYZER_PROMPT if search_mode == "doctor" else ANALYZER_PROMPT

    # Batch results into chunks for analysis (avoid token limits)
    chunk_size = 10
    all_analyzed = []

    for i in range(0, len(raw_results), chunk_size):
        chunk = raw_results[i:i + chunk_size]

        context = json.dumps({
            "original_query": original_query,
            "search_intent": search_intent,
            "raw_results": chunk,
        }, indent=2, default=str)

        try:
            response = await client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4000,
                messages=[{
                    "role": "user",
                    "content": f"Analyze these search results:\n\n{context}"
                }],
                system=system_prompt,
            )

            text = response.content[0].text

            analyzed = extract_json(text)
            if isinstance(analyzed, list):
                all_analyzed.extend(analyzed)
            elif isinstance(analyzed, dict):
                all_analyzed.append(analyzed)

        except Exception as e:
            logger.error(f"AI analysis failed for chunk {i}: {e}")

    # In doctor mode, classify credential tiers
    if search_mode == "doctor":
        for result in all_analyzed:
            result["credential_tier"] = classify_credential_tier(result)

    return all_analyzed


# ─── DEDUPLICATION ───

# ─── CREDENTIAL TIER CLASSIFICATION ───

def classify_credential_tier(result: dict) -> str:
    """
    Classify a doctor/medical professional into credential tiers for filtering.
    Returns: "physician" (MD/DO), "allied" (NP/PA/RD/PharmD), or "other_medical" (ND, coaches with certs, etc.)
    """
    credentials = [c.upper() for c in result.get("credentials", [])]
    creator_type = (result.get("creator_type") or "").lower()
    name = (result.get("name") or "").lower()
    bio = (result.get("bio") or "").lower()

    # Combine all text signals
    all_text = " ".join(credentials) + " " + creator_type + " " + name + " " + bio

    # Tier 1: Physicians (MD, DO)
    physician_signals = ["MD", "DO", "M.D.", "D.O.", "PHYSICIAN", "SURGEON", "FELLOW"]
    if any(sig in all_text.upper() for sig in physician_signals):
        return "physician"

    # Tier 2: Allied health professionals
    allied_signals = ["NP", "PA-C", "PA ", "NURSE PRACTITIONER", "PHYSICIAN ASSISTANT",
                      "RD", "RDN", "REGISTERED DIETITIAN", "PHARMD", "PHARM.D",
                      "PHARMACIST", "PHD", "PH.D", "DNP", "APRN"]
    if any(sig in all_text.upper() for sig in allied_signals):
        return "allied"

    # Tier 3: Other medical (naturopaths, chiropractors, etc.)
    other_signals = ["ND", "N.D.", "NATUROPATH", "DC", "D.C.", "CHIROPRACT",
                     "DACM", "ACUPUNCTUR", "AYURVED", "FUNCTIONAL MEDICINE",
                     "LAC", "L.AC", "DOM"]
    if any(sig in all_text.upper() for sig in other_signals):
        return "other_medical"

    # If creator_type says Doctor/Medical but we couldn't classify, default to physician
    if "doctor" in creator_type or "medical" in creator_type:
        return "physician"

    # Check for "Dr." in name
    if result.get("name", "").startswith("Dr.") or result.get("name", "").startswith("Dr "):
        return "physician"

    return "other_medical"


# ─── DEEP SEARCH (LAYERS 3-5) ───

DEEP_SEARCH_QUERIES_PROMPT = """You are generating ADVANCED search queries to find hidden-gem doctor creators for Luma Nutrition.

The coordinator already ran a surface-level search and found some doctors. Now they want to GO DEEPER.

Your job is to generate 10-15 CREATIVE, NON-OBVIOUS search queries that find doctors through INDIRECT signals:

LAYER 3 — LINKEDIN SIGNAL MINING:
Find LinkedIn posts where brand founders/marketers talk about working with doctor creators.
- site:linkedin.com "doctor creator" OR "physician influencer" "worked with" OR "partnered with" supplement
- site:linkedin.com "medical influencer" campaign results "our brand"
- site:linkedin.com "doctor" "UGC" OR "content creator" looking hire health
- site:linkedin.com "medical professional" "brand deal" OR "partnership" supplement health

LAYER 4 — TALENT MARKETPLACES & AGENCIES:
Find intermediaries who sell access to doctor creators.
- "medical influencer agency" OR "doctor talent" roster health wellness
- "healthcare creator" marketplace OR platform OR network sign up
- "physician" "brand ambassador" program supplement health apply
- "medical professional" "influencer network" health supplement join

LAYER 5 — REDDIT & COMMUNITY:
Find doctors discussing side income through content creation.
- site:reddit.com "doctor" OR "physician" OR "resident" "content creation" income OR "side hustle"
- site:reddit.com "MD" "social media" supplement review paid OR sponsored
- site:reddit.com medical professional UGC creator experience
- site:reddit.com "as a doctor" tiktok instagram started creating content

ADDITIONAL CREATIVE APPROACHES:
- "[TOPIC] summit" OR "conference" speaker doctor social media 2025 2026
- "doctor reviews" [LUMA_PRODUCT_TOPIC] supplement youtube tiktok small channel
- "[SPECIALTY]" "my practice" tiktok OR instagram "link in bio"

The original search query was: {query}
The topic/specialty focus is: {topic}

Return ONLY a JSON object:
{{
  "deep_search_queries": ["query1", "query2", ...],
  "reasoning": "brief explanation of strategy"
}}"""


async def generate_deep_search_queries(original_query: str, topic: str) -> list[str]:
    """Generate Layer 3-5 deep search queries using AI."""
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    try:
        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            messages=[{
                "role": "user",
                "content": f"Original search: {original_query}\nTopic focus: {topic}"
            }],
            system=DEEP_SEARCH_QUERIES_PROMPT.format(query=original_query, topic=topic),
        )

        result = extract_json(response.content[0].text)
        return result.get("deep_search_queries", [])
    except Exception as e:
        logger.error(f"Deep search query generation failed: {e}")
        # Fallback deep queries
        return [
            f'site:linkedin.com "doctor" "content creator" {topic} supplement',
            f'site:reddit.com "doctor" OR "physician" "content creation" {topic}',
            f'"medical influencer" agency {topic} health roster',
            f'"doctor reviews" {topic} supplement youtube tiktok',
            f'site:reddit.com "MD" social media {topic} sponsored',
        ]


def deduplicate_results(results: list[dict]) -> list[dict]:
    """
    Merge results that refer to the same creator.
    Deduplicates by handle, email, or profile URL similarity.
    """
    seen = {}
    deduplicated = []

    for result in results:
        # Build dedup keys
        keys = []
        if result.get("handle"):
            keys.append(result["handle"].lower().strip("@"))
        if result.get("email"):
            keys.append(result["email"].lower())
        if result.get("profile_url"):
            # Extract handle from URL
            url = result["profile_url"].lower()
            for pattern in [r"/@([^/?\s]+)", r"/([^/?\s]+)/?$"]:
                m = re.search(pattern, url)
                if m:
                    keys.append(m.group(1))
                    break

        # Check for existing match
        matched_key = None
        for key in keys:
            if key in seen:
                matched_key = key
                break

        if matched_key:
            # Merge into existing result
            existing = seen[matched_key]
            # Keep higher relevance score
            if (result.get("relevance_score") or 0) > (existing.get("relevance_score") or 0):
                existing["relevance_score"] = result["relevance_score"]
            # Merge categories
            existing_cats = set(existing.get("categories", []))
            existing_cats.update(result.get("categories", []))
            existing["categories"] = list(existing_cats)
            # Add source URLs
            existing.setdefault("source_urls", [])
            existing["source_urls"].extend(result.get("source_urls", []))
        else:
            # New result
            for key in keys:
                seen[key] = result
            deduplicated.append(result)

    return deduplicated


# ─── MAIN DISCOVERY ENGINE ───

class DiscoveryEngine:
    """
    Main orchestrator. Takes a search query, runs the full discovery pipeline.
    """

    def __init__(self):
        self.web_search = WebSearchProvider()
        self.reddit_search = RedditSearchProvider()
        self.ugc_search = UGCMarketplaceProvider()
        self.hashtag_search = HashtagResearchProvider()

    async def discover(
        self,
        query: str,
        platforms: list[str],
        filters: dict,
        db: AsyncSession,
        max_results: int = 20,
    ) -> DiscoverySearch:
        """
        Run a full discovery search.

        1. Parse intent with AI
        2. Fan out searches across providers
        3. Aggregate and deduplicate
        4. Analyze and score with AI
        5. Store results in database
        """

        # Create search record
        search = DiscoverySearch(
            query=query,
            platforms_searched=platforms,
            filters=filters,
            status="parsing_intent",
        )
        db.add(search)
        await db.flush()

        try:
            # Step 1: Parse intent
            logger.info(f"[Discovery] Parsing intent: {query}")
            intent = await parse_search_intent(query, platforms)
            search.parsed_intent = intent
            search.status = "searching"
            await db.flush()

            # Step 2: Fan out searches in parallel
            logger.info(f"[Discovery] Running parallel searches...")
            search_tasks = []

            # Web search (primary)
            web_queries = intent.get("search_queries", [])
            if web_queries:
                search_tasks.append(self.web_search.search(web_queries))

            # Reddit search
            subreddits = intent.get("subreddits", [])
            if subreddits:
                reddit_terms = intent.get("topics", [query])
                search_tasks.append(self.reddit_search.search(subreddits, reddit_terms))

            # UGC marketplace search
            ugc_terms = intent.get("ugc_search_terms", [])
            if ugc_terms:
                search_tasks.append(self.ugc_search.search(ugc_terms))

            # Hashtag research
            hashtags = intent.get("hashtags", [])
            if hashtags:
                search_tasks.append(self.hashtag_search.search(hashtags, platforms))

            # Run all searches in parallel
            raw_results_groups = await asyncio.gather(*search_tasks, return_exceptions=True)

            # Flatten results
            raw_results = []
            for group in raw_results_groups:
                if isinstance(group, list):
                    raw_results.extend(group)
                elif isinstance(group, Exception):
                    logger.error(f"Search task failed: {group}")

            logger.info(f"[Discovery] Got {len(raw_results)} raw results")
            search.status = "analyzing"
            await db.flush()

            # Step 3: AI Analysis
            analyzed = await analyze_results(raw_results, intent, query)
            logger.info(f"[Discovery] AI analyzed {len(analyzed)} results")

            # Step 4: Deduplicate
            unique = deduplicate_results(analyzed)
            logger.info(f"[Discovery] {len(unique)} unique creators after dedup")

            # Step 5: Sort by relevance and limit
            unique.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
            final = unique[:max_results]

            # ─── VALIDATION & CLEANUP before storing ───
            LEGIT_DOMAINS = {'tiktok.com','instagram.com','youtube.com','twitter.com','x.com','linkedin.com','facebook.com','threads.net'}
            JUNK_DOMAINS = {'twstalker','tweetdeck','nitter','socialblade','social-searcher','hootsuite','sproutsocial','followerwonk','thetalentnet'}
            FAKE_EMAILS = {'available upon request','email upon request','available on request','contact via','dm for','upon request','n/a','none','not available','tbd','pending'}

            def clean_profile_url(url):
                """Only keep URLs that point to actual social platforms."""
                if not url:
                    return None
                url_lower = url.lower()
                # Check against junk domains
                if any(junk in url_lower for junk in JUNK_DOMAINS):
                    return None
                # Check if it's a real platform URL
                if any(domain in url_lower for domain in LEGIT_DOMAINS):
                    return url
                # Allow linktree, linktr.ee, bio links
                if 'linktr' in url_lower or 'bio' in url_lower:
                    return url
                return None

            def clean_email(email):
                """Filter out fake/placeholder emails."""
                if not email:
                    return None
                email_lower = email.lower().strip()
                if any(fake in email_lower for fake in FAKE_EMAILS):
                    return None
                if '@' not in email_lower:
                    return None
                if len(email_lower) < 5:
                    return None
                return email

            for rd in final:
                # Clean profile URL
                rd["profile_url"] = clean_profile_url(rd.get("profile_url"))
                # Clean email
                rd["email"] = clean_email(rd.get("email"))
                # Clean other profile URLs
                if rd.get("other_profiles"):
                    cleaned = {}
                    for plat, val in rd["other_profiles"].items():
                        if isinstance(val, str) and val.startswith('http'):
                            cleaned_url = clean_profile_url(val)
                            if cleaned_url:
                                cleaned[plat] = cleaned_url
                        elif isinstance(val, str) and val.startswith('@'):
                            cleaned[plat] = val  # Handle is fine
                        elif isinstance(val, str) and len(val) > 2:
                            cleaned[plat] = val  # Username is fine
                    rd["other_profiles"] = cleaned

            # Step 6: Store results (filter out junk)
            stored_count = 0
            for result_data in final:
                # Skip results with recommended_action = "skip" or score below 25
                if result_data.get("recommended_action") == "skip":
                    continue
                if (result_data.get("relevance_score") or 0) < 25:
                    continue
                # Skip results with no name or only a first name and no handle
                name = result_data.get("name", "")
                handle = result_data.get("handle")
                if not name or name == "Unknown":
                    continue
                # If only first name (no space) AND no handle AND no profile URL, skip
                if ' ' not in name and not handle and not result_data.get("profile_url"):
                    continue

                result = DiscoveryResult(
                    search_id=search.id,
                    name=result_data.get("name", "Unknown"),
                    handle=result_data.get("handle"),
                    platform=detect_platform(result_data),
                    profile_url=result_data.get("profile_url"),
                    bio=result_data.get("bio"),
                    email=result_data.get("email"),
                    followers=result_data.get("estimated_followers"),
                    engagement_rate=result_data.get("estimated_engagement_rate"),
                    relevance_score=result_data.get("relevance_score"),
                    categories=result_data.get("categories", []),
                    ai_analysis={
                        "credentials": result_data.get("credentials", []),
                        "content_fit": result_data.get("content_fit_reasoning"),
                        "red_flags": result_data.get("red_flags", []),
                        "recommended_action": result_data.get("recommended_action"),
                        "other_profiles": result_data.get("other_profiles", {}),
                        "past_partnerships": result_data.get("past_partnerships", []),
                        "source_urls": result_data.get("source_urls", []),
                        "country": result_data.get("country"),
                        "estimated_rate": result_data.get("estimated_rate"),
                        "creator_type": result_data.get("creator_type"),
                        "content_niches": result_data.get("content_niches", []),
                    },
                    source_type=result_data.get("source", "web_search"),
                    source_url=result_data.get("source_urls", [None])[0] if result_data.get("source_urls") else None,
                    raw_data=result_data,
                )
                db.add(result)
                stored_count += 1

            # Update search record
            search.results_count = stored_count
            search.status = "complete"
            search.completed_at = datetime.utcnow()
            await db.commit()

            # Reload with results
            await db.refresh(search)
            return search

        except Exception as e:
            logger.error(f"[Discovery] Search failed: {e}")
            search.status = "failed"
            search.error = str(e)
            await db.commit()
            raise

    async def save_result_as_creator(
        self,
        result_id: UUID,
        db: AsyncSession,
    ) -> Creator:
        """Save a discovery result as a creator in the database."""
        result = await db.get(DiscoveryResult, result_id)
        if not result:
            raise ValueError(f"Discovery result {result_id} not found")

        # Check for existing creator with same email
        if result.email:
            existing = await db.execute(
                select(Creator).where(Creator.email == result.email)
            )
            if existing.scalar_one_or_none():
                raise ValueError(f"Creator with email {result.email} already exists")

        # Create creator from result
        creator = Creator(
            name=result.name,
            email=result.email,
            bio=result.bio,
            categories=result.categories or [],
            relevance_score=result.relevance_score,
            engagement_rate=result.engagement_rate,
            total_followers=result.followers,
            ai_analysis=result.ai_analysis,
            source=CreatorSource.AI_DISCOVERY,
            source_details={
                "search_id": str(result.search_id),
                "platform": result.platform,
                "source_type": result.source_type,
            },
            pipeline_stage="discovered",
        )

        # Map platform-specific fields
        platform = result.platform
        if platform == "tiktok":
            creator.tiktok_url = result.profile_url
            creator.tiktok_handle = result.handle
            creator.tiktok_followers = result.followers
        elif platform == "instagram":
            creator.instagram_url = result.profile_url
            creator.instagram_handle = result.handle
            creator.instagram_followers = result.followers
        elif platform == "youtube":
            creator.youtube_url = result.profile_url
            creator.youtube_handle = result.handle
            creator.youtube_subscribers = result.followers
        elif platform == "twitter":
            creator.twitter_url = result.profile_url
            creator.twitter_handle = result.handle
            creator.twitter_followers = result.followers

        db.add(creator)

        # Link result to creator
        result.creator_id = creator.id
        result.saved_at = datetime.utcnow()

        await db.commit()
        await db.refresh(creator)
        return creator
