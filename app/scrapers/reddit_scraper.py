"""
Reddit Creator Scraper

Specialized scraper for finding creators through Reddit.
Reddit is a goldmine for discovering micro-influencers and niche creators
because:
  1. Creators self-promote in subreddits like r/UGCcreators
  2. Niche communities recommend creators organically
  3. "Looking for" and "for hire" posts reveal active creators
  4. Comment history reveals authentic engagement patterns

This scraper targets:
  - UGC/creator subreddits (self-promotion, portfolios)
  - Health/wellness subreddits (finding doctor creators)
  - Niche interest subreddits (matching Luma product categories)
  - Creator marketplace subreddits
"""

import re
import logging
from datetime import datetime, timedelta
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


# ─── SUBREDDIT MAPS ───
# Organized by niche so the discovery engine can pick the right ones

SUBREDDIT_MAP = {
    # UGC / Creator communities
    "ugc": [
        "UGCcreators", "ugc", "UGC_marketplace", "influencermarketing",
        "ContentCreators", "NewTubers", "TikTokCreators",
        "InstagramMarketing", "youtubers",
    ],

    # Health / Medical (for finding doctor creators)
    "doctor": [
        "medicine", "medicalschool", "Residency", "physicians",
        "doctorsUK", "healthIT", "publichealth",
    ],
    "health": [
        "health", "HealthyFood", "nutrition", "Supplements",
        "Nootropics", "longevity", "Biohackers",
    ],
    "heart_health": [
        "HeartHealth", "cardiovascular", "health", "Supplements",
    ],
    "gut_health": [
        "GutHealth", "Microbiome", "Probiotics", "IBS",
        "SIBO", "fermentation",
    ],

    # Fitness
    "fitness": [
        "fitness", "bodybuilding", "xxfitness", "GYM",
        "CrossFit", "yoga", "running",
    ],

    # Lifestyle / Demographics
    "mom": [
        "Mommit", "beyondthebump", "Parenting", "workingmoms",
        "MomInfluencers",
    ],
    "gen_z": [
        "GenZ", "GenZedong", "teenagers", "college",
    ],
    "beauty": [
        "beauty", "SkincareAddiction", "MakeupAddiction",
        "AsianBeauty", "Skincare_Addiction",
    ],
    "pets": [
        "dogs", "cats", "pets", "aww", "dogpictures",
    ],
    "food": [
        "food", "Cooking", "MealPrepSunday", "EatCheapAndHealthy",
        "recipes", "FoodPorn",
    ],
    "comedy": [
        "funny", "TikTokCringe", "ContagiousLaughter",
    ],
    "wellness": [
        "Meditation", "selfimprovement", "DecidingToBeBetter",
        "getdisciplined", "Wellness",
    ],
}

# Post patterns that indicate a creator or creator recommendation
CREATOR_SIGNAL_PATTERNS = [
    r"(?i)\b(portfolio|my\s+work|hire\s+me|for\s+hire|creator\s+for)\b",
    r"(?i)\b(check\s+out\s+my|follow\s+me|my\s+channel|my\s+page)\b",
    r"(?i)\b(ugc\s+creator|content\s+creator|influencer)\b",
    r"(?i)\b(collab|collaboration|brand\s+deal|sponsored)\b",
    r"(?i)\b(tiktok\.com|instagram\.com|youtube\.com)/@?\w+",
    r"(?i)\b(@\w{3,})\b",  # @handles
    r"(?i)\b(dm\s+me|email\s+me|reach\s+out)\b",
    r"(?i)\b(rates|pricing|packages)\b",
]

# Patterns for extracting contact info from posts
CONTACT_PATTERNS = {
    "email": r"[\w.+-]+@[\w-]+\.[\w.]+",
    "tiktok": r"(?:tiktok\.com/@?|@)([\w.]+)",
    "instagram": r"(?:instagram\.com/|@)([\w.]+)",
    "youtube": r"youtube\.com/(?:@|c/|channel/)([\w-]+)",
    "website": r"https?://[\w.-]+\.\w+(?:/\S*)?",
}


class RedditScraper:
    """
    Scrapes Reddit for creator discovery.
    Uses Reddit's public JSON API (no auth required for basic access).
    For higher rate limits, configure Reddit OAuth in settings.
    """

    def __init__(self, user_agent: str = "CreatorDiscoveryEngine/1.0"):
        self.client = httpx.AsyncClient(
            timeout=30,
            headers={"User-Agent": user_agent},
            follow_redirects=True,
        )
        self.base_url = "https://www.reddit.com"

    async def find_creators_in_niche(
        self,
        niche: str,
        search_terms: list[str] = None,
        time_filter: str = "year",
        max_results: int = 50,
    ) -> list[dict]:
        """
        Find creators in a specific niche by scanning relevant subreddits.

        Args:
            niche: Key from SUBREDDIT_MAP (e.g. "doctor", "fitness", "ugc")
            search_terms: Additional search terms to use
            time_filter: "hour", "day", "week", "month", "year", "all"
            max_results: Maximum total results across all subreddits
        """
        subreddits = SUBREDDIT_MAP.get(niche, SUBREDDIT_MAP.get("ugc", []))
        all_results = []

        # Default search terms if none provided
        if not search_terms:
            search_terms = ["creator", "ugc", "influencer", "content creator"]

        for sub in subreddits:
            if len(all_results) >= max_results:
                break

            # Search for creator-related posts
            for term in search_terms[:2]:
                try:
                    posts = await self._search_subreddit(sub, term, time_filter, limit=10)
                    for post in posts:
                        parsed = self._parse_creator_post(post, sub)
                        if parsed and parsed.get("creator_signals", 0) > 0:
                            all_results.append(parsed)
                except Exception as e:
                    logger.warning(f"Failed to search r/{sub} for '{term}': {e}")

            # Also check "hot" and "new" posts for self-promotion
            try:
                hot_posts = await self._get_posts(sub, "hot", limit=10)
                for post in hot_posts:
                    parsed = self._parse_creator_post(post, sub)
                    if parsed and parsed.get("creator_signals", 0) >= 2:
                        all_results.append(parsed)
            except Exception as e:
                logger.warning(f"Failed to get hot posts from r/{sub}: {e}")

        # Deduplicate by author
        seen_authors = set()
        unique = []
        for r in all_results:
            author = r.get("reddit_author", "").lower()
            if author and author not in seen_authors and author != "[deleted]":
                seen_authors.add(author)
                unique.append(r)

        # Sort by signal strength
        unique.sort(key=lambda x: x.get("creator_signals", 0), reverse=True)

        return unique[:max_results]

    async def find_creator_recommendations(
        self,
        topic: str,
        max_results: int = 20,
    ) -> list[dict]:
        """
        Find posts where people RECOMMEND creators in a topic area.
        These are organic endorsements — gold for finding hidden gems.
        """
        search_queries = [
            f"best {topic} creator",
            f"recommend {topic} influencer",
            f"favorite {topic} tiktoker",
            f"who to follow {topic}",
            f"underrated {topic} creator",
        ]

        all_results = []
        for query in search_queries:
            try:
                # Search across all of Reddit
                posts = await self._search_all(query, time_filter="year", limit=10)
                for post in posts:
                    # Look for creator mentions in post body and comments
                    mentions = self._extract_creator_mentions(post)
                    all_results.extend(mentions)
            except Exception as e:
                logger.warning(f"Recommendation search failed for '{query}': {e}")

        return all_results[:max_results]

    async def scan_ugc_subreddits(self, max_results: int = 50) -> list[dict]:
        """
        Dedicated scan of UGC creator subreddits.
        These are where creators actively self-promote and share portfolios.
        """
        ugc_subs = SUBREDDIT_MAP["ugc"]
        results = []

        for sub in ugc_subs:
            try:
                # Get recent "for hire" and portfolio posts
                posts = await self._search_subreddit(
                    sub, "for hire OR portfolio OR rates", "month", limit=15
                )
                for post in posts:
                    parsed = self._parse_creator_post(post, sub)
                    if parsed:
                        # UGC sub posts are almost always from creators
                        parsed["creator_signals"] = max(parsed.get("creator_signals", 0), 3)
                        results.append(parsed)

                # Also get recent posts
                new_posts = await self._get_posts(sub, "new", limit=10)
                for post in new_posts:
                    parsed = self._parse_creator_post(post, sub)
                    if parsed:
                        parsed["creator_signals"] = max(parsed.get("creator_signals", 0), 2)
                        results.append(parsed)

            except Exception as e:
                logger.warning(f"UGC scan failed for r/{sub}: {e}")

        # Deduplicate
        seen = set()
        unique = []
        for r in results:
            key = r.get("reddit_author", "").lower()
            if key and key not in seen and key != "[deleted]":
                seen.add(key)
                unique.append(r)

        return unique[:max_results]

    # ─── INTERNAL METHODS ───

    async def _search_subreddit(
        self, subreddit: str, query: str, time_filter: str, limit: int = 25
    ) -> list[dict]:
        """Search within a specific subreddit."""
        url = f"{self.base_url}/r/{subreddit}/search.json"
        params = {
            "q": query,
            "restrict_sr": "on",
            "sort": "relevance",
            "t": time_filter,
            "limit": min(limit, 100),
        }

        response = await self.client.get(url, params=params)
        if response.status_code != 200:
            return []

        data = response.json()
        return [child["data"] for child in data.get("data", {}).get("children", [])]

    async def _search_all(
        self, query: str, time_filter: str, limit: int = 25
    ) -> list[dict]:
        """Search across all of Reddit."""
        url = f"{self.base_url}/search.json"
        params = {
            "q": query,
            "sort": "relevance",
            "t": time_filter,
            "limit": min(limit, 100),
        }

        response = await self.client.get(url, params=params)
        if response.status_code != 200:
            return []

        data = response.json()
        return [child["data"] for child in data.get("data", {}).get("children", [])]

    async def _get_posts(
        self, subreddit: str, sort: str = "hot", limit: int = 25
    ) -> list[dict]:
        """Get posts from a subreddit by sort type."""
        url = f"{self.base_url}/r/{subreddit}/{sort}.json"
        params = {"limit": min(limit, 100)}

        response = await self.client.get(url, params=params)
        if response.status_code != 200:
            return []

        data = response.json()
        return [child["data"] for child in data.get("data", {}).get("children", [])]

    def _parse_creator_post(self, post: dict, subreddit: str) -> Optional[dict]:
        """Parse a Reddit post for creator signals and extract info."""
        title = post.get("title", "")
        body = post.get("selftext", "")
        author = post.get("author", "")
        full_text = f"{title} {body}"

        if not author or author == "[deleted]":
            return None

        # Count creator signals
        signals = 0
        for pattern in CREATOR_SIGNAL_PATTERNS:
            if re.search(pattern, full_text):
                signals += 1

        # Extract contact info
        contacts = {}
        for contact_type, pattern in CONTACT_PATTERNS.items():
            matches = re.findall(pattern, full_text)
            if matches:
                contacts[contact_type] = matches[0] if isinstance(matches[0], str) else matches[0]

        # Extract categories/niches mentioned
        niche_keywords = [
            "health", "wellness", "fitness", "beauty", "skincare",
            "food", "cooking", "mom", "parenting", "doctor", "medical",
            "supplement", "nutrition", "lifestyle", "comedy", "pets",
            "ugc", "gen z", "millennial",
        ]
        found_niches = [n for n in niche_keywords if n.lower() in full_text.lower()]

        return {
            "source": "reddit",
            "reddit_author": author,
            "reddit_url": f"https://reddit.com{post.get('permalink', '')}",
            "subreddit": subreddit,
            "title": title[:200],
            "body_snippet": body[:500],
            "score": post.get("score", 0),
            "created_utc": post.get("created_utc", 0),
            "creator_signals": signals,
            "contacts": contacts,
            "niches": found_niches,
            "has_email": bool(contacts.get("email")),
            "has_social": bool(contacts.get("tiktok") or contacts.get("instagram") or contacts.get("youtube")),
            "flair": post.get("link_flair_text", ""),
        }

    def _extract_creator_mentions(self, post: dict) -> list[dict]:
        """Extract mentions of other creators from a post (recommendations)."""
        body = post.get("selftext", "")
        title = post.get("title", "")
        full_text = f"{title} {body}"

        mentions = []

        # Find @handles
        handles = re.findall(r"@([\w.]{3,30})", full_text)
        for handle in handles:
            mentions.append({
                "source": "reddit_recommendation",
                "handle": f"@{handle}",
                "context": f"Mentioned in r/{post.get('subreddit', 'unknown')}: {title[:100]}",
                "reddit_url": f"https://reddit.com{post.get('permalink', '')}",
                "post_score": post.get("score", 0),
            })

        # Find platform URLs
        for platform, pattern in [
            ("tiktok", r"tiktok\.com/@?([\w.]+)"),
            ("instagram", r"instagram\.com/([\w.]+)"),
            ("youtube", r"youtube\.com/(?:@|c/)([\w-]+)"),
        ]:
            found = re.findall(pattern, full_text)
            for handle in found:
                mentions.append({
                    "source": "reddit_recommendation",
                    "handle": f"@{handle}",
                    "platform": platform,
                    "profile_url": f"https://{'tiktok.com' if platform == 'tiktok' else 'instagram.com' if platform == 'instagram' else 'youtube.com'}/@{handle}",
                    "context": f"Recommended in r/{post.get('subreddit', 'unknown')}: {title[:100]}",
                    "reddit_url": f"https://reddit.com{post.get('permalink', '')}",
                    "post_score": post.get("score", 0),
                })

        return mentions

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
