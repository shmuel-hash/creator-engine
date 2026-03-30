"""
Creator Enrichment & Outreach Strategy Service

Takes a discovered creator profile and enriches it with:
1. Contact info (email from bio, linktree, website)
2. Recent content analysis (topics, style, engagement)
3. Partnership history (brands they've worked with)
4. AI-generated outreach strategy personalized to the creator

This is what transforms a "we found this person" into
"here's exactly how to approach them and why they'll say yes."
"""

import re
import json
import logging
from typing import Optional
from datetime import datetime

import httpx
from anthropic import AsyncAnthropic
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.models import Creator, CreatorNote
from app.services.discovery_engine import extract_json

logger = logging.getLogger(__name__)
settings = get_settings()


# ─── EMAIL EXTRACTION ───

# Common patterns for finding emails in bios and pages
EMAIL_PATTERNS = [
    r"[\w.+-]+@[\w-]+\.[\w.]+",
]

# Linktree and bio link patterns
BIO_LINK_PATTERNS = [
    r"linktr\.ee/([\w.-]+)",
    r"linkin\.bio/([\w.-]+)",
    r"beacons\.ai/([\w.-]+)",
    r"stan\.store/([\w.-]+)",
    r"bio\.site/([\w.-]+)",
    r"campsite\.bio/([\w.-]+)",
    r"hoo\.be/([\w.-]+)",
    r"tap\.bio/([\w.-]+)",
    r"linkpop\.com/([\w.-]+)",
    r"(?:https?://)?(?:www\.)?[\w-]+\.[\w]{2,}(?:/[\w.-]*)*",  # general URL
]


async def extract_email_from_url(url: str) -> list[str]:
    """Fetch a URL and extract email addresses from the page content."""
    if not url:
        return []

    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        try:
            response = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
            })
            if response.status_code != 200:
                return []

            text = response.text
            # Find all email addresses in the page
            emails = re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", text)
            # Filter out common false positives
            filtered = [
                e for e in emails
                if not any(skip in e.lower() for skip in [
                    "example.com", "email.com", "domain.com",
                    "wixpress", "sentry", "cloudflare", "schema.org",
                    ".png", ".jpg", ".svg", ".css", ".js",
                ])
            ]
            return list(set(filtered))

        except Exception as e:
            logger.debug(f"Failed to fetch {url}: {e}")
            return []


async def find_creator_email(
    handle: str,
    platform: str,
    bio: str = "",
    profile_url: str = "",
) -> dict:
    """
    Multi-step email finding:
    1. Check bio text directly for email
    2. Find linktree/bio link in bio, scrape that page
    3. Search for their business email via web search
    """
    found_emails = []
    sources = []

    # Step 1: Direct email in bio
    if bio:
        bio_emails = re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", bio)
        for e in bio_emails:
            if e not in found_emails:
                found_emails.append(e)
                sources.append("bio")

    # Step 2: Find and scrape linktree / bio link
    if bio:
        for pattern in BIO_LINK_PATTERNS[:8]:  # skip the generic URL pattern
            matches = re.findall(pattern, bio)
            for match in matches:
                if "linktr.ee" in pattern:
                    link_url = f"https://linktr.ee/{match}"
                elif "beacons.ai" in pattern:
                    link_url = f"https://beacons.ai/{match}"
                elif "stan.store" in pattern:
                    link_url = f"https://stan.store/{match}"
                else:
                    link_url = f"https://{match}" if not match.startswith("http") else match

                emails = await extract_email_from_url(link_url)
                for e in emails:
                    if e not in found_emails:
                        found_emails.append(e)
                        sources.append(f"linktree:{link_url}")

    # Step 3: Search for business email
    if not found_emails and settings.serper_api_key:
        clean_handle = handle.strip("@")
        search_queries = [
            f"{clean_handle} email contact business inquiry",
            f"{clean_handle} {platform} creator contact email collaboration",
        ]

        api_key = settings.serper_api_key
        use_serper = bool(api_key and not api_key.startswith("V"))

        async with httpx.AsyncClient(timeout=15) as client:
            for query in search_queries[:1]:  # limit to 1 search to save credits
                try:
                    if use_serper:
                        response = await client.post(
                            "https://google.serper.dev/search",
                            json={"q": query, "num": 5},
                            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
                        )
                        results_key = "organic"
                        link_key = "link"
                    else:
                        response = await client.get(
                            "https://www.searchapi.io/api/v1/search",
                            params={"q": query, "engine": "google", "num": 5},
                            headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
                        )
                        results_key = "organic_results"
                        link_key = "link"

                    if response.status_code == 200:
                        data = response.json()
                        for result in data.get(results_key, []):
                            snippet = result.get("snippet", "")
                            snippet_emails = re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", snippet)
                            for e in snippet_emails:
                                if e not in found_emails:
                                    found_emails.append(e)
                                    sources.append(f"web_search")

                            # Also try scraping the result page for email
                            if not found_emails:
                                page_emails = await extract_email_from_url(result.get(link_key, ""))
                                for e in page_emails[:2]:
                                    if e not in found_emails:
                                        found_emails.append(e)
                                        sources.append(f"web_page:{result.get(link_key, '')[:50]}")

                except Exception as e:
                    logger.debug(f"Email search failed: {e}")

    return {
        "emails": found_emails,
        "primary_email": found_emails[0] if found_emails else None,
        "sources": sources,
    }


# ─── CONTENT & PARTNERSHIP ANALYSIS ───

async def analyze_creator_content(
    handle: str,
    platform: str,
    profile_url: str = "",
) -> dict:
    """
    Search for and analyze a creator's recent content and brand partnerships.
    Uses web search to find their recent posts, sponsorships, and collaborations.
    """
    if not settings.serper_api_key:
        return {"error": "No search API key configured"}

    clean_handle = handle.strip("@")
    results_data = []

    # Search queries to find content and partnerships
    search_queries = [
        f'"{clean_handle}" {platform} sponsored partnership brand deal 2025 2026',
        f'"{clean_handle}" {platform} review unboxing collaboration',
        f'site:{_platform_domain(platform)} @{clean_handle}',
    ]

    async with httpx.AsyncClient(timeout=15) as client:
        api_key = settings.serper_api_key
        use_serper = bool(api_key and not api_key.startswith("V"))

        for query in search_queries:
            try:
                if use_serper:
                    response = await client.post(
                        "https://google.serper.dev/search",
                        json={"q": query, "num": 10},
                        headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
                    )
                    results_key = "organic"
                else:
                    response = await client.get(
                        "https://www.searchapi.io/api/v1/search",
                        params={"q": query, "engine": "google", "num": 10},
                        headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
                    )
                    results_key = "organic_results"

                if response.status_code == 200:
                    data = response.json()
                    for r in data.get(results_key, []):
                        results_data.append({
                            "title": r.get("title", ""),
                            "url": r.get("link", ""),
                            "snippet": r.get("snippet", ""),
                            "query": query,
                        })
            except Exception as e:
                logger.debug(f"Content search failed: {e}")

    return {
        "handle": handle,
        "platform": platform,
        "content_results": results_data,
        "total_found": len(results_data),
    }


def _platform_domain(platform: str) -> str:
    """Get domain for platform."""
    domains = {
        "tiktok": "tiktok.com",
        "instagram": "instagram.com",
        "youtube": "youtube.com",
        "twitter": "x.com",
    }
    return domains.get(platform, "")


# ─── AI OUTREACH STRATEGY GENERATOR ───

OUTREACH_STRATEGY_PROMPT = """You are an expert influencer marketing strategist for Luma Nutrition, a premium supplement brand.

Luma's products:
- Heart Health Bundle: CoQ10, Omega-3, Magnesium complex for cardiovascular support
- Gut Health Protocol: Probiotics, digestive enzymes, prebiotic fiber blend
- Longevity Protocol: NAD+, Resveratrol, NMN for cellular health
- Also: Sleep/Mood, Blood Sugar, Berberine, NAC, Probiotic

You're analyzing a creator to develop a personalized outreach strategy. Based on everything
we know about them, generate a comprehensive outreach plan.

Return a JSON object with:
{
  "creator_summary": "2-3 sentence summary of who they are and why they matter",
  "content_style": "How they create content (educational, entertainment, lifestyle, etc.)",
  "audience_profile": "Who follows them and why",
  "brand_fit_score": 1-10,
  "brand_fit_reasoning": "Why they're a good/bad fit for Luma specifically",
  "recommended_product": "Which Luma product to pitch (Heart Health / Gut Health / Longevity / etc.)",
  "product_reasoning": "Why this product matches their content and audience",
  "past_partnerships": ["List of brands/partnerships you identified from the content data"],
  "partnership_insights": "What we can learn from their past brand deals",
  "outreach_angle": "The specific angle/hook to use when reaching out",
  "personalization_hooks": ["3-5 specific things to mention that show we've done our homework"],
  "potential_objections": ["Likely concerns they'd have and how to address them"],
  "suggested_subject_line": "Email subject line",
  "suggested_email_body": "Full personalized outreach email (200-300 words)",
  "suggested_follow_up": "Follow-up email if no response (shorter, different angle)",
  "estimated_rate_range": "$X - $Y per video based on their tier",
  "content_ideas": ["3-5 specific content concepts they could create with Luma products"],
  "red_flags": ["Any concerns about working with this creator"],
  "priority_level": "high / medium / low",
  "priority_reasoning": "Why this priority level"
}

Be specific and actionable. The outreach email should feel like it was written by someone
who genuinely follows this creator, not a mass template. Reference their actual content.
Return ONLY the JSON, no other text."""


async def generate_outreach_strategy(
    creator_data: dict,
    content_analysis: dict,
) -> dict:
    """
    Use Claude to generate a personalized outreach strategy.

    Args:
        creator_data: Everything we know about the creator (profile, bio, stats)
        content_analysis: Results from analyze_creator_content
    """
    if not settings.anthropic_api_key:
        return {"error": "No Anthropic API key configured"}

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    context = json.dumps({
        "creator": creator_data,
        "content_analysis": content_analysis,
    }, indent=2, default=str)

    try:
        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            messages=[{
                "role": "user",
                "content": f"Analyze this creator and generate an outreach strategy:\n\n{context}"
            }],
            system=OUTREACH_STRATEGY_PROMPT,
        )

        text = response.content[0].text

        return extract_json(text)

    except json.JSONDecodeError:
        logger.error(f"Failed to parse outreach strategy response: {text[:200]}")
        return {"error": "Failed to parse AI response", "raw": text[:500]}
    except Exception as e:
        logger.error(f"Outreach strategy generation failed: {e}")
        return {"error": str(e)}


# ─── FULL ENRICHMENT PIPELINE ───

# In-memory enrichment status tracker (works for single-instance Railway)
_enrichment_jobs: dict[str, dict] = {}


def get_enrichment_status(creator_id: str) -> dict | None:
    """Get current enrichment status for a creator."""
    return _enrichment_jobs.get(creator_id)


def _update_status(creator_id: str, **kwargs):
    """Update enrichment status."""
    if creator_id not in _enrichment_jobs:
        _enrichment_jobs[creator_id] = {}
    _enrichment_jobs[creator_id].update(kwargs)


async def enrich_creator(
    creator: Creator,
    db: AsyncSession,
) -> dict:
    """
    Run the full enrichment pipeline on a creator:
    1. Find their email
    2. Analyze their content & partnerships
    3. Generate outreach strategy
    4. Update the database record

    Updates _enrichment_jobs in-memory so the frontend can poll for progress.
    """
    cid = str(creator.id)
    _update_status(cid,
        status="finding_email", step=1, total_steps=3,
        step_label="Finding email...",
        started_at=datetime.utcnow().isoformat(),
    )

    handle = (
        creator.tiktok_handle or
        creator.instagram_handle or
        creator.youtube_handle or
        creator.twitter_handle or
        creator.name
    )
    platform = (
        "tiktok" if creator.tiktok_url else
        "instagram" if creator.instagram_url else
        "youtube" if creator.youtube_url else
        "twitter" if creator.twitter_url else
        "unknown"
    )
    profile_url = (
        creator.tiktok_url or
        creator.instagram_url or
        creator.youtube_url or
        creator.twitter_url or
        ""
    )

    enrichment = {
        "handle": handle,
        "platform": platform,
        "enriched_at": datetime.utcnow().isoformat(),
    }

    # Step 1: Find email
    if not creator.email:
        logger.info(f"[Enrich] Finding email for {handle}...")
        email_result = await find_creator_email(
            handle=handle,
            platform=platform,
            bio=creator.bio or "",
            profile_url=profile_url,
        )
        enrichment["email_search"] = email_result

        if email_result.get("primary_email"):
            creator.email = email_result["primary_email"]
            note = CreatorNote(
                content=f"Email found: {email_result['primary_email']} (source: {', '.join(email_result.get('sources', []))})",
                note_type="ai_analysis",
            )
            creator.notes.append(note)
    else:
        enrichment["email_search"] = {"skipped": True, "reason": "email already exists"}

    # Step 2: Analyze content & partnerships
    _update_status(cid,
        status="analyzing_content", step=2,
        step_label="Analyzing content & partnerships...",
    )
    logger.info(f"[Enrich] Analyzing content for {handle}...")
    content_analysis = await analyze_creator_content(
        handle=handle,
        platform=platform,
        profile_url=profile_url,
    )
    enrichment["content_analysis"] = content_analysis

    # Step 3: Generate outreach strategy
    _update_status(cid,
        status="generating_strategy", step=3,
        step_label="Generating outreach strategy...",
    )
    logger.info(f"[Enrich] Generating outreach strategy for {handle}...")
    creator_data = {
        "name": creator.name,
        "handle": handle,
        "platform": platform,
        "bio": creator.bio,
        "categories": creator.categories,
        "followers": creator.total_followers,
        "engagement_rate": creator.engagement_rate,
        "email": creator.email,
        "profile_url": profile_url,
        "quality_tier": str(creator.quality_tier),
    }

    strategy = await generate_outreach_strategy(creator_data, content_analysis)
    enrichment["outreach_strategy"] = strategy

    # Step 4: Update creator record
    if not creator.ai_analysis:
        creator.ai_analysis = {}

    # Merge enrichment into ai_analysis
    existing = creator.ai_analysis if isinstance(creator.ai_analysis, dict) else {}
    existing["enrichment"] = enrichment
    existing["outreach_strategy"] = strategy
    existing["last_enriched"] = datetime.utcnow().isoformat()
    creator.ai_analysis = existing

    # Update relevance score based on strategy
    if strategy.get("brand_fit_score"):
        creator.relevance_score = strategy["brand_fit_score"] * 10  # Convert 1-10 to 0-100

    # Add enrichment note
    priority = strategy.get("priority_level", "unknown")
    product = strategy.get("recommended_product", "unknown")
    note = CreatorNote(
        content=f"Enrichment complete: Priority={priority}, Recommended product={product}, Brand fit={strategy.get('brand_fit_score', '?')}/10",
        note_type="ai_analysis",
    )
    creator.notes.append(note)

    await db.commit()
    await db.refresh(creator)

    _update_status(cid,
        status="complete", step=3,
        step_label="Enrichment complete",
        completed_at=datetime.utcnow().isoformat(),
        result=enrichment,
    )

    return enrichment
