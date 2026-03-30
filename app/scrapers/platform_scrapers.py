"""
Platform Scrapers

Specialized scrapers for finding creators across platforms.
These work by using web search to find profiles, then parsing
publicly available profile data.

Strategy per platform:
  - TikTok: Search for profiles via web, parse bio/stats from public pages
  - Instagram: Search for profiles via web, parse public profile data
  - YouTube: Use YouTube Data API (free tier: 10K units/day)
  - UGC Marketplaces: Scrape Collabstr, Billo, JoinBrands search results
  - Twitter/X: Search for profiles via web search
"""

import re
import json
import logging
from typing import Optional
from datetime import datetime

import httpx
from bs4 import BeautifulSoup

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def searchapi_search(query: str, num_results: int = 10) -> list[dict]:
    """Shared SearchAPI.io search utility for all platform scrapers."""
    if not settings.serper_api_key:
        logger.warning("No SearchAPI key — skipping web search")
        return []

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.get(
                "https://www.searchapi.io/api/v1/search",
                params={"q": query, "engine": "google", "num": num_results},
                headers={
                    "Authorization": f"Bearer {settings.serper_api_key}",
                    "Accept": "application/json",
                },
            )
            if response.status_code != 200:
                logger.error(f"SearchAPI error {response.status_code}: {response.text[:200]}")
                return []

            data = response.json()
            return [
                {
                    "url": item.get("link", ""),
                    "title": item.get("title", ""),
                    "snippet": item.get("snippet", ""),
                    "position": item.get("position", 0),
                }
                for item in data.get("organic_results", [])
            ]
        except Exception as e:
            logger.error(f"SearchAPI request failed: {e}")
            return []


class TikTokScraper:
    """
    Finds TikTok creators through web search and public profile parsing.

    Since TikTok doesn't have a public creator search API, we use:
    1. Web search (Brave/Google) with site:tiktok.com queries
    2. Public profile page parsing for bio, followers, engagement
    3. Hashtag research to find creators using relevant tags
    """

    def __init__(self, search_api_key: Optional[str] = None):
        self.client = httpx.AsyncClient(
            timeout=30,
            headers={"User-Agent": "Mozilla/5.0 (compatible; CreatorBot/1.0)"},
            follow_redirects=True,
        )
        self.search_api_key = search_api_key

    async def search_creators(
        self,
        query: str,
        niche: str = "",
        max_results: int = 20,
    ) -> list[dict]:
        """
        Search for TikTok creators matching criteria.
        Uses web search with site:tiktok.com to find profiles.
        """
        search_queries = [
            f'site:tiktok.com "{query}" creator',
            f'site:tiktok.com {query} {niche} bio',
            f'tiktok {query} {niche} influencer content creator',
            f'tiktok {query} creator review 2025 2026',
            f'best {query} tiktok accounts to follow',
        ]

        results = []
        for sq in search_queries:
            try:
                web_results = await self._web_search(sq)
                for r in web_results:
                    parsed = self._parse_search_result(r)
                    if parsed:
                        results.append(parsed)
            except Exception as e:
                logger.warning(f"TikTok search failed for '{sq}': {e}")

        # Deduplicate by handle
        seen = set()
        unique = []
        for r in results:
            handle = r.get("handle", "").lower()
            if handle and handle not in seen:
                seen.add(handle)
                unique.append(r)

        return unique[:max_results]

    async def get_profile_data(self, username: str) -> Optional[dict]:
        """
        Get public profile data for a TikTok user.
        Parses the public profile page for bio, stats, etc.
        """
        url = f"https://www.tiktok.com/@{username}"
        try:
            response = await self.client.get(url)
            if response.status_code != 200:
                return None

            # TikTok embeds profile data in a script tag
            soup = BeautifulSoup(response.text, "lxml")

            # Try to find the SIGI_STATE or __UNIVERSAL_DATA script
            for script in soup.find_all("script", {"id": "__UNIVERSAL_DATA_FOR_REHYDRATION__"}):
                try:
                    data = json.loads(script.string)
                    user_data = (
                        data.get("__DEFAULT_SCOPE__", {})
                        .get("webapp.user-detail", {})
                        .get("userInfo", {})
                    )
                    if user_data:
                        user = user_data.get("user", {})
                        stats = user_data.get("stats", {})
                        return {
                            "platform": "tiktok",
                            "handle": f"@{user.get('uniqueId', username)}",
                            "name": user.get("nickname", ""),
                            "bio": user.get("signature", ""),
                            "followers": stats.get("followerCount", 0),
                            "following": stats.get("followingCount", 0),
                            "likes": stats.get("heartCount", 0),
                            "videos": stats.get("videoCount", 0),
                            "verified": user.get("verified", False),
                            "profile_url": url,
                        }
                except (json.JSONDecodeError, AttributeError):
                    pass

            return None

        except Exception as e:
            logger.error(f"Failed to get TikTok profile @{username}: {e}")
            return None

    async def _web_search(self, query: str) -> list[dict]:
        """Execute web search via Serper.dev."""
        return await searchapi_search(query, num_results=10)

    def _parse_search_result(self, result: dict) -> Optional[dict]:
        """Parse a web search result into a TikTok creator record."""
        url = result.get("url", "")
        title = result.get("title", "")
        snippet = result.get("snippet", "")

        # Extract handle from TikTok URL
        match = re.search(r"tiktok\.com/@([\w.]+)", url)
        if not match:
            return None

        handle = match.group(1)
        return {
            "platform": "tiktok",
            "handle": f"@{handle}",
            "name": title.split("|")[0].strip() if "|" in title else title.split("(@")[0].strip(),
            "bio": snippet[:200],
            "profile_url": f"https://www.tiktok.com/@{handle}",
            "source": "web_search",
        }


class InstagramScraper:
    """
    Finds Instagram creators through web search.
    Instagram's API is restricted, so we use web search to discover profiles
    and parse publicly available information.
    """

    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=30,
            headers={"User-Agent": "Mozilla/5.0 (compatible; CreatorBot/1.0)"},
        )

    async def search_creators(
        self,
        query: str,
        niche: str = "",
        max_results: int = 20,
    ) -> list[dict]:
        """Search for Instagram creators via web search."""
        search_queries = [
            f'site:instagram.com "{query}" {niche}',
            f'instagram {query} {niche} creator influencer',
            f'best {query} instagram accounts 2025 2026',
            f'{query} {niche} content creator instagram bio',
        ]

        results = []
        for sq in search_queries:
            try:
                web_results = await self._web_search(sq)
                for r in web_results:
                    parsed = self._parse_search_result(r)
                    if parsed:
                        results.append(parsed)
            except Exception as e:
                logger.warning(f"Instagram search failed: {e}")

        seen = set()
        unique = []
        for r in results:
            handle = r.get("handle", "").lower()
            if handle and handle not in seen:
                seen.add(handle)
                unique.append(r)

        return unique[:max_results]

    async def _web_search(self, query: str) -> list[dict]:
        """Execute web search via Serper.dev."""
        return await searchapi_search(query, num_results=10)

    def _parse_search_result(self, result: dict) -> Optional[dict]:
        url = result.get("url", "")
        title = result.get("title", "")
        snippet = result.get("snippet", "")

        match = re.search(r"instagram\.com/([\w.]+)", url)
        if not match:
            return None

        handle = match.group(1)
        # Skip non-profile pages
        if handle in ("p", "reel", "stories", "explore", "accounts", "about"):
            return None

        return {
            "platform": "instagram",
            "handle": f"@{handle}",
            "name": title.split("(")[0].strip() if "(" in title else title.split("|")[0].strip(),
            "bio": snippet[:200],
            "profile_url": f"https://www.instagram.com/{handle}",
            "source": "web_search",
        }


class YouTubeScraper:
    """
    Finds YouTube creators using the YouTube Data API.
    Free tier: 10,000 units/day (search costs 100 units, so ~100 searches/day).
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.client = httpx.AsyncClient(timeout=30)
        self.base_url = "https://www.googleapis.com/youtube/v3"

    async def search_creators(
        self,
        query: str,
        max_results: int = 20,
    ) -> list[dict]:
        """Search for YouTube channels matching criteria."""
        if not self.api_key:
            # Fall back to web search
            return await self._web_search_fallback(query, max_results)

        try:
            response = await self.client.get(
                f"{self.base_url}/search",
                params={
                    "key": self.api_key,
                    "q": query,
                    "type": "channel",
                    "maxResults": min(max_results, 50),
                    "part": "snippet",
                    "order": "relevance",
                }
            )

            if response.status_code != 200:
                logger.error(f"YouTube API error: {response.status_code}")
                return []

            data = response.json()
            results = []

            for item in data.get("items", []):
                snippet = item.get("snippet", {})
                channel_id = item.get("id", {}).get("channelId", "")
                results.append({
                    "platform": "youtube",
                    "handle": f"@{snippet.get('channelTitle', '')}",
                    "name": snippet.get("channelTitle", ""),
                    "bio": snippet.get("description", "")[:200],
                    "profile_url": f"https://www.youtube.com/channel/{channel_id}",
                    "channel_id": channel_id,
                    "source": "youtube_api",
                })

            return results

        except Exception as e:
            logger.error(f"YouTube search failed: {e}")
            return []

    async def get_channel_stats(self, channel_id: str) -> Optional[dict]:
        """Get detailed channel statistics."""
        if not self.api_key:
            return None

        try:
            response = await self.client.get(
                f"{self.base_url}/channels",
                params={
                    "key": self.api_key,
                    "id": channel_id,
                    "part": "statistics,snippet,brandingSettings",
                }
            )

            if response.status_code != 200:
                return None

            items = response.json().get("items", [])
            if not items:
                return None

            channel = items[0]
            stats = channel.get("statistics", {})
            snippet = channel.get("snippet", {})

            return {
                "subscribers": int(stats.get("subscriberCount", 0)),
                "total_views": int(stats.get("viewCount", 0)),
                "video_count": int(stats.get("videoCount", 0)),
                "description": snippet.get("description", ""),
                "country": snippet.get("country", ""),
                "custom_url": snippet.get("customUrl", ""),
            }

        except Exception as e:
            logger.error(f"Failed to get channel stats: {e}")
            return None

    async def _web_search_fallback(self, query: str, max_results: int) -> list[dict]:
        """Fallback to Serper web search when no YouTube API key is available."""
        search_queries = [
            f'site:youtube.com {query} channel creator',
            f'youtube {query} creator influencer subscribe',
        ]
        all_results = []
        for sq in search_queries:
            results = await searchapi_search(sq, num_results=max_results)
            for r in results:
                url = r.get("url", "")
                # Extract channel info from YouTube URLs
                match = re.search(r"youtube\.com/(?:@|channel/|c/)([\w-]+)", url)
                if match:
                    handle = match.group(1)
                    all_results.append({
                        "platform": "youtube",
                        "handle": f"@{handle}",
                        "name": r.get("title", "").split(" - YouTube")[0].strip(),
                        "bio": r.get("snippet", "")[:200],
                        "profile_url": url,
                        "source": "serper_web_search",
                    })
        # Deduplicate
        seen = set()
        unique = []
        for r in all_results:
            h = r.get("handle", "").lower()
            if h and h not in seen:
                seen.add(h)
                unique.append(r)
        return unique[:max_results]


class UGCMarketplaceScraper:
    """
    Scrapes UGC creator marketplaces for available creators.
    Targets: Collabstr, Billo, JoinBrands, Insense, Hashtag Paid
    """

    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=30,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            },
            follow_redirects=True,
        )

    async def search_collabstr(
        self,
        category: str = "health-wellness",
        platform: str = "tiktok",
        max_results: int = 20,
    ) -> list[dict]:
        """
        Search Collabstr for creators.
        Collabstr has public search pages we can parse.
        """
        url = f"https://collabstr.com/search/{platform}-influencers/{category}"
        try:
            response = await self.client.get(url)
            if response.status_code != 200:
                return []

            soup = BeautifulSoup(response.text, "lxml")
            results = []

            # Parse creator cards from search results
            # (Structure depends on current Collabstr HTML — may need updating)
            creator_cards = soup.select("[class*='creator'], [class*='influencer'], [class*='card']")

            for card in creator_cards[:max_results]:
                name_el = card.select_one("[class*='name'], h3, h4")
                handle_el = card.select_one("[class*='handle'], [class*='username']")
                price_el = card.select_one("[class*='price'], [class*='rate']")
                link_el = card.select_one("a[href*='/creator/']")

                if name_el:
                    results.append({
                        "platform": platform,
                        "name": name_el.get_text(strip=True),
                        "handle": handle_el.get_text(strip=True) if handle_el else "",
                        "rate": price_el.get_text(strip=True) if price_el else "",
                        "profile_url": f"https://collabstr.com{link_el['href']}" if link_el else "",
                        "source": "collabstr",
                        "category": category,
                    })

            return results

        except Exception as e:
            logger.error(f"Collabstr scrape failed: {e}")
            return []

    async def search_all_marketplaces(
        self,
        query: str,
        max_results: int = 30,
    ) -> list[dict]:
        """Search across all UGC marketplaces via Serper."""
        marketplace_queries = [
            f'site:collabstr.com {query} creator',
            f'site:billo.app {query}',
            f'site:joinbrands.com {query} creator',
            f'site:insense.pro {query}',
            f'{query} ugc creator marketplace profile',
        ]

        all_results = []
        for mq in marketplace_queries:
            try:
                results = await searchapi_search(mq, num_results=10)
                for r in results:
                    url = r.get("url", "")
                    # Determine which marketplace this is from
                    marketplace = "unknown"
                    for mp in ["collabstr", "billo", "joinbrands", "insense", "hashtagpaid"]:
                        if mp in url.lower():
                            marketplace = mp
                            break

                    all_results.append({
                        "platform": "ugc_marketplace",
                        "marketplace": marketplace,
                        "name": r.get("title", "").split("|")[0].split("-")[0].strip(),
                        "bio": r.get("snippet", "")[:200],
                        "profile_url": url,
                        "source": f"serper_{marketplace}",
                    })
            except Exception as e:
                logger.warning(f"Marketplace search failed for '{mq}': {e}")

        return all_results[:max_results]


class CreatorEnricher:
    """
    Enriches a basic creator profile with data from multiple platforms.
    Given a handle or URL, it attempts to find the same person across
    platforms and aggregate their data.
    """

    def __init__(self):
        self.tiktok = TikTokScraper()
        self.instagram = InstagramScraper()
        self.youtube = YouTubeScraper()

    async def enrich_profile(self, creator_data: dict) -> dict:
        """
        Take a basic creator profile and enrich it with cross-platform data.
        """
        enriched = {**creator_data}

        handle = creator_data.get("handle", "").strip("@")
        if not handle:
            return enriched

        # Try to find on TikTok
        if not creator_data.get("tiktok_url"):
            tiktok_data = await self.tiktok.get_profile_data(handle)
            if tiktok_data:
                enriched["tiktok_url"] = tiktok_data.get("profile_url")
                enriched["tiktok_handle"] = tiktok_data.get("handle")
                enriched["tiktok_followers"] = tiktok_data.get("followers")
                if not enriched.get("bio"):
                    enriched["bio"] = tiktok_data.get("bio")

        # Calculate total followers
        total = 0
        for key in ["tiktok_followers", "instagram_followers", "youtube_subscribers", "twitter_followers"]:
            val = enriched.get(key)
            if val and isinstance(val, (int, float)):
                total += int(val)
        enriched["total_followers"] = total

        return enriched

    async def close(self):
        await self.tiktok.client.aclose()
        await self.instagram.client.aclose()
        await self.youtube.client.aclose()
