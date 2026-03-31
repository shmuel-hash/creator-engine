"""
Apify integration for real creator profile data.

Supports:
- TikTok profile scraping (followers, bio, avatar, recent videos)
- Instagram profile scraping (followers, bio, avatar, email, website)
- TikTok keyword/hashtag search (find creators by content topic)

Uses Apify's REST API to run actors and fetch results synchronously.
"""

import asyncio
import logging
import httpx
from typing import Optional
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

APIFY_BASE = "https://api.apify.com/v2"

# Actor IDs
TIKTOK_PROFILE_ACTOR = "clockworks/tiktok-profile-scraper"
TIKTOK_SCRAPER_ACTOR = "clockworks/tiktok-scraper"  # For hashtag/keyword search
INSTAGRAM_PROFILE_ACTOR = "apify/instagram-profile-scraper"
INSTAGRAM_SEARCH_ACTOR = "apify/instagram-search-scraper"


async def _run_actor_sync(actor_id: str, input_data: dict, timeout: int = 120) -> list[dict]:
    """
    Run an Apify actor synchronously and return dataset items.
    Uses the run-sync-get-dataset-items endpoint for simplicity.
    """
    token = settings.apify_api_token
    if not token:
        logger.warning("[Apify] No API token configured")
        return []

    url = f"{APIFY_BASE}/acts/{actor_id}/run-sync-get-dataset-items"
    params = {"token": token}

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            logger.info(f"[Apify] Running actor {actor_id} with input: {input_data}")
            resp = await client.post(url, json=input_data, params=params)

            if resp.status_code == 200:
                items = resp.json()
                logger.info(f"[Apify] Actor {actor_id} returned {len(items)} items")
                return items
            elif resp.status_code == 402:
                logger.error("[Apify] Insufficient credits — check your Apify plan")
                return []
            else:
                logger.error(f"[Apify] Actor {actor_id} failed: {resp.status_code} — {resp.text[:300]}")
                return []

    except httpx.TimeoutException:
        logger.error(f"[Apify] Actor {actor_id} timed out after {timeout}s")
        return []
    except Exception as e:
        logger.error(f"[Apify] Actor {actor_id} error: {e}")
        return []


# ─── TIKTOK ───

async def scrape_tiktok_profile(username: str) -> Optional[dict]:
    """
    Scrape a single TikTok profile by username.
    Returns structured profile data or None.
    """
    username = username.lstrip("@").strip()
    if not username:
        return None

    items = await _run_actor_sync(
        TIKTOK_PROFILE_ACTOR,
        {
            "profiles": [username],
            "resultsPerPage": 1,
            "profileScrapeSections": [],  # Profile only, no videos
        },
        timeout=60,
    )

    if not items:
        return None

    # The profile scraper returns video items with authorMeta
    # Or if profileScrapeSections is empty, it may return profile data directly
    item = items[0]

    # Extract profile data — handle different response formats
    author = item.get("authorMeta") or item
    profile = {
        "username": author.get("name") or author.get("uniqueId") or username,
        "display_name": author.get("nickName") or author.get("nickname") or author.get("name"),
        "bio": author.get("signature") or author.get("bio") or "",
        "followers": author.get("fans") or author.get("followers") or author.get("followerCount"),
        "following": author.get("following") or author.get("followingCount"),
        "likes": author.get("heart") or author.get("likes") or author.get("heartCount"),
        "videos": author.get("video") or author.get("videoCount"),
        "verified": author.get("verified", False),
        "avatar_url": author.get("avatar") or author.get("avatarLarger") or author.get("avatarMedium"),
        "profile_url": f"https://www.tiktok.com/@{username}",
        "platform": "tiktok",
        "bio_link": author.get("bioLink") or author.get("link"),
        "region": author.get("region"),
        "source": "apify_tiktok",
    }

    # Clean up None values for follower counts
    for key in ["followers", "following", "likes", "videos"]:
        if isinstance(profile[key], str):
            try:
                profile[key] = int(profile[key].replace(",", ""))
            except (ValueError, AttributeError):
                profile[key] = None

    return profile


async def search_tiktok_by_hashtag(hashtag: str, max_results: int = 20) -> list[dict]:
    """
    Search TikTok for videos by hashtag and extract unique creators.
    Returns list of creator profiles found.
    """
    tag = hashtag.lstrip("#").strip()
    if not tag:
        return []

    items = await _run_actor_sync(
        TIKTOK_SCRAPER_ACTOR,
        {
            "hashtags": [tag],
            "resultsPerPage": min(max_results * 2, 50),  # Get more to deduplicate
        },
        timeout=90,
    )

    # Deduplicate by author username
    seen = set()
    creators = []
    for item in items:
        author = item.get("authorMeta", {})
        username = author.get("name") or author.get("uniqueId")
        if not username or username in seen:
            continue
        seen.add(username)

        creators.append({
            "username": username,
            "display_name": author.get("nickName") or author.get("nickname"),
            "bio": author.get("signature") or "",
            "followers": author.get("fans") or author.get("followers"),
            "verified": author.get("verified", False),
            "avatar_url": author.get("avatar"),
            "profile_url": f"https://www.tiktok.com/@{username}",
            "platform": "tiktok",
            "source": "apify_tiktok_hashtag",
            "sample_video": {
                "text": item.get("text"),
                "views": item.get("playCount") or item.get("plays"),
                "likes": item.get("diggCount") or item.get("likes"),
                "comments": item.get("commentCount") or item.get("comments"),
                "shares": item.get("shareCount") or item.get("shares"),
                "url": item.get("webVideoUrl") or f"https://www.tiktok.com/@{username}/video/{item.get('id')}",
            },
        })

        if len(creators) >= max_results:
            break

    return creators


# ─── INSTAGRAM ───

async def scrape_instagram_profile(username: str) -> Optional[dict]:
    """
    Scrape a single Instagram profile by username.
    Returns structured profile data or None.
    """
    username = username.lstrip("@").strip()
    if not username:
        return None

    items = await _run_actor_sync(
        INSTAGRAM_PROFILE_ACTOR,
        {
            "usernames": [username],
        },
        timeout=60,
    )

    if not items:
        return None

    item = items[0]

    profile = {
        "username": item.get("username") or username,
        "display_name": item.get("fullName") or item.get("full_name") or "",
        "bio": item.get("biography") or item.get("bio") or "",
        "followers": item.get("followersCount") or item.get("follower_count") or item.get("followers"),
        "following": item.get("followsCount") or item.get("following_count") or item.get("following"),
        "posts": item.get("postsCount") or item.get("media_count") or item.get("posts"),
        "verified": item.get("verified", False),
        "is_business": item.get("isBusinessAccount") or item.get("is_business_account", False),
        "category": item.get("businessCategoryName") or item.get("category_name"),
        "avatar_url": item.get("profilePicUrl") or item.get("profilePicUrlHD") or item.get("profile_pic_url"),
        "profile_url": f"https://www.instagram.com/{username}/",
        "platform": "instagram",
        "website": item.get("externalUrl") or item.get("external_url"),
        "email": item.get("businessEmail") or item.get("public_email"),
        "phone": item.get("businessPhoneNumber") or item.get("public_phone_number"),
        "region": item.get("igtvVideoCount"),  # Not a region, placeholder
        "source": "apify_instagram",
    }

    # Extract bio link/email from bio text
    bio = profile["bio"] or ""
    if not profile["email"]:
        import re
        email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', bio)
        if email_match:
            profile["email"] = email_match.group()

    return profile


async def search_instagram_by_keyword(keyword: str, max_results: int = 20) -> list[dict]:
    """
    Search Instagram for users matching a keyword.
    Returns list of user profiles found.
    """
    if not keyword.strip():
        return []

    items = await _run_actor_sync(
        INSTAGRAM_SEARCH_ACTOR,
        {
            "search": keyword,
            "searchType": "user",
            "resultsLimit": max_results,
        },
        timeout=60,
    )

    creators = []
    for item in items:
        username = item.get("username") or item.get("slug")
        if not username:
            continue

        creators.append({
            "username": username,
            "display_name": item.get("fullName") or item.get("full_name") or item.get("name") or "",
            "bio": item.get("biography") or item.get("bio") or "",
            "followers": item.get("followersCount") or item.get("follower_count"),
            "verified": item.get("verified", False),
            "is_business": item.get("isBusinessAccount", False),
            "category": item.get("businessCategoryName") or item.get("category_name"),
            "avatar_url": item.get("profilePicUrl") or item.get("profile_pic_url"),
            "profile_url": f"https://www.instagram.com/{username}/",
            "platform": "instagram",
            "website": item.get("externalUrl") or item.get("external_url"),
            "email": item.get("businessEmail") or item.get("public_email"),
            "source": "apify_instagram_search",
        })

    return creators


# ─── MULTI-PLATFORM PROFILE ENRICHMENT ───

async def enrich_profile(handle: str, platform: str) -> Optional[dict]:
    """
    Enrich a creator profile using Apify.
    Routes to the appropriate platform scraper.

    Returns structured profile data or None.
    """
    handle = handle.lstrip("@").strip()
    if not handle:
        return None

    if not settings.apify_api_token:
        logger.info("[Apify] No API token — skipping profile enrichment")
        return None

    platform = platform.lower()
    if platform == "tiktok":
        return await scrape_tiktok_profile(handle)
    elif platform in ("instagram", "ig"):
        return await scrape_instagram_profile(handle)
    else:
        # Try TikTok first, then Instagram
        result = await scrape_tiktok_profile(handle)
        if result and result.get("followers"):
            return result
        result = await scrape_instagram_profile(handle)
        if result and result.get("followers"):
            return result
        return result


async def check_apify_status() -> dict:
    """Check if Apify API is configured and working."""


async def batch_scrape_avatars(handles: list[dict], timeout: int = 45) -> dict:
    """
    Batch-scrape profile pictures and real follower counts for discovery results.

    Args:
        handles: list of {"handle": "@username", "platform": "tiktok"|"instagram"}
        timeout: max seconds for each platform batch

    Returns:
        dict mapping lowercase handle → {"avatar_url": ..., "followers": ..., "bio": ...}
    """
    if not settings.apify_api_token:
        logger.info("[Apify] No API token — skipping batch avatar scrape")
        return {}

    # Group by platform
    tiktok_handles = []
    ig_handles = []
    for h in handles:
        clean = (h.get("handle") or "").lstrip("@").strip().lower()
        if not clean:
            continue
        platform = (h.get("platform") or "").lower()
        if platform == "tiktok":
            tiktok_handles.append(clean)
        elif platform in ("instagram", "ig"):
            ig_handles.append(clean)
        else:
            # Guess from URL if available
            url = (h.get("url") or "").lower()
            if "tiktok.com" in url:
                tiktok_handles.append(clean)
            elif "instagram.com" in url:
                ig_handles.append(clean)
            else:
                # Default: try TikTok (more common in discovery)
                tiktok_handles.append(clean)

    # Deduplicate
    tiktok_handles = list(dict.fromkeys(tiktok_handles))
    ig_handles = list(dict.fromkeys(ig_handles))

    results = {}
    tasks = []

    if tiktok_handles:
        logger.info(f"[Apify] Batch avatar scrape: {len(tiktok_handles)} TikTok profiles")
        tasks.append(_batch_tiktok(tiktok_handles, timeout))

    if ig_handles:
        logger.info(f"[Apify] Batch avatar scrape: {len(ig_handles)} Instagram profiles")
        tasks.append(_batch_instagram(ig_handles, timeout))

    if not tasks:
        return {}

    try:
        batch_results = await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=timeout + 10,
        )
        for batch in batch_results:
            if isinstance(batch, dict):
                results.update(batch)
            elif isinstance(batch, Exception):
                logger.error(f"[Apify] Batch avatar error: {batch}")
    except asyncio.TimeoutError:
        logger.warning("[Apify] Batch avatar scrape timed out — continuing without avatars")
    except Exception as e:
        logger.error(f"[Apify] Batch avatar scrape failed: {e}")

    logger.info(f"[Apify] Batch avatar scrape got {len(results)} profiles")
    return results


async def _batch_tiktok(handles: list[str], timeout: int) -> dict:
    """Scrape multiple TikTok profiles in one actor run."""
    items = await _run_actor_sync(
        TIKTOK_PROFILE_ACTOR,
        {"profiles": handles, "resultsPerPage": 1, "profileScrapeSections": []},
        timeout=timeout,
    )
    results = {}
    for item in items:
        author = item.get("authorMeta") or item
        username = (author.get("name") or author.get("uniqueId") or "").lower()
        if username:
            results[username] = {
                "avatar_url": author.get("avatar") or author.get("avatarLarger") or author.get("avatarMedium"),
                "followers": author.get("fans") or author.get("followers") or author.get("followerCount"),
                "bio": author.get("signature") or author.get("bio") or "",
                "platform": "tiktok",
            }
    return results


async def _batch_instagram(handles: list[str], timeout: int) -> dict:
    """Scrape multiple Instagram profiles in one actor run."""
    items = await _run_actor_sync(
        INSTAGRAM_PROFILE_ACTOR,
        {"usernames": handles},
        timeout=timeout,
    )
    results = {}
    for item in items:
        username = (item.get("username") or "").lower()
        if username:
            results[username] = {
                "avatar_url": item.get("profilePicUrl") or item.get("profilePicUrlHD") or item.get("profile_pic_url"),
                "followers": item.get("followersCount") or item.get("follower_count") or item.get("followers"),
                "bio": item.get("biography") or item.get("bio") or "",
                "platform": "instagram",
            }
    return results
    token = settings.apify_api_token
    if not token:
        return {"configured": False, "error": "No APIFY_API_TOKEN set"}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{APIFY_BASE}/users/me",
                params={"token": token},
            )
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "configured": True,
                    "username": data.get("data", {}).get("username"),
                    "plan": data.get("data", {}).get("plan", {}).get("id"),
                    "credits": data.get("data", {}).get("plan", {}).get("usageCreditsUsd"),
                }
            else:
                return {"configured": False, "error": f"API returned {resp.status_code}"}
    except Exception as e:
        return {"configured": False, "error": str(e)}
