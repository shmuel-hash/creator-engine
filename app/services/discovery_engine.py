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


async def parse_search_intent(query: str, platforms: list[str]) -> dict:
    """Use Claude to parse a natural language query into a structured search strategy."""
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    response = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": f"Search query: {query}\nPreferred platforms: {', '.join(platforms)}"
        }],
        system=INTENT_PARSER_PROMPT,
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
- Do we have at least ONE social media handle or profile URL? If NO → score max 40, flag "No direct social handle found"
- Do we have follower count on any platform? If NO → subtract 15 points from score
- Do we have a way to contact them (email, DM, linktree)? If NO → subtract 10 points
- Is the person clearly a real individual (not a brand, agency listing, or directory entry)? If NO → score 0, skip them

DO NOT include people who are just LISTED on a talent directory or marketplace without any additional info. If all you know is "Name + talent agency URL", that's not enough — they score max 35.

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

Return ONLY the JSON array, no other text."""


async def analyze_results(
    raw_results: list[dict],
    search_intent: dict,
    original_query: str
) -> list[dict]:
    """Use Claude to analyze and score raw search results."""
    if not raw_results:
        return []

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)

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
                system=ANALYZER_PROMPT,
            )

            text = response.content[0].text

            analyzed = extract_json(text)
            if isinstance(analyzed, list):
                all_analyzed.extend(analyzed)
            elif isinstance(analyzed, dict):
                all_analyzed.append(analyzed)

        except Exception as e:
            logger.error(f"AI analysis failed for chunk {i}: {e}")

    return all_analyzed


# ─── DEDUPLICATION ───

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

            # Step 5.5: Quick contact enrichment for top results
            # For creators without email, do a fast web search to find contact info
            search.status = "enriching_contacts"
            await db.commit()

            async def quick_contact_search(creator_data):
                """Fast email/contact search for a single creator."""
                if creator_data.get("email"):
                    return creator_data  # Already has email
                name = creator_data.get("name", "")
                handle = creator_data.get("handle", "")
                if not name and not handle:
                    return creator_data
                try:
                    q = f'{handle or name} email contact business inquiries' if handle else f'"{name}" email health creator contact'
                    results = await self.web.search([q], max_results_per_query=3)
                    import re
                    email_pattern = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
                    found_emails = set()
                    for r in results:
                        text = f"{r.get('title','')} {r.get('snippet','')} {r.get('link','')}"
                        found_emails.update(email_pattern.findall(text))
                    junk = {'noreply','no-reply','info@','support@tiktok','support@instagram','example','sentry','abuse','privacy','legal','help@','contact@serper'}
                    good_emails = [e for e in found_emails if not any(j in e.lower() for j in junk)]
                    if good_emails:
                        creator_data["email"] = good_emails[0]
                        creator_data.setdefault("contact_source", "web_search")
                except Exception as e:
                    logger.debug(f"[Discovery] Quick contact search failed for {name}: {e}")
                return creator_data

            # Run contact search for top 5 only (keep it fast)
            import asyncio
            top_without_email = [c for c in final[:10] if not c.get("email")][:5]
            if top_without_email:
                try:
                    contact_tasks = [quick_contact_search(c) for c in top_without_email]
                    await asyncio.wait_for(asyncio.gather(*contact_tasks, return_exceptions=True), timeout=30)
                except asyncio.TimeoutError:
                    logger.warning("[Discovery] Contact enrichment timed out after 30s, continuing without")

            logger.info(f"[Discovery] Contact enrichment done — {sum(1 for c in final if c.get('email'))} have emails")

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
                    platform=result_data.get("platform", "unknown"),
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
