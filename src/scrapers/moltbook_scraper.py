"""Moltbook API scraper — collects posts, comments, and submolt data."""

import asyncio
import json
import os
import time
from typing import Any

import httpx

from utils import log, save_raw

# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────

BASE_URL = os.getenv("MOLTBOOK_BASE_URL", "https://www.moltbook.com/api/v1")
API_KEY = os.getenv("MOLTBOOK_API_KEY", "")
RATE_LIMIT_DELAY = 2  # seconds between requests

# Load settings
_settings_path = os.path.join(os.path.dirname(__file__), "..", "..", "config", "settings.json")
with open(_settings_path, "r") as f:
    _settings = json.load(f)

SCRAPE_LIMITS = _settings["moltbook"]["scrape_limits"]
TARGET_SUBMOLTS = _settings["moltbook"]["target_submolts"]


def _headers() -> dict:
    """Return auth headers."""
    key = API_KEY or os.getenv("MOLTBOOK_API_KEY", "")
    return {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


# ──────────────────────────────────────────────
# API Interaction
# ──────────────────────────────────────────────

async def _get(client: httpx.AsyncClient, path: str, params: dict = None) -> dict | None:
    """Make an authenticated GET request to Moltbook API."""
    url = f"{BASE_URL}{path}"
    try:
        resp = await client.get(url, headers=_headers(), params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        log.warning(f"HTTP {e.response.status_code} for {url}: {e.response.text[:200]}")
        return None
    except Exception as e:
        log.error(f"Request failed for {url}: {e}")
        return None


async def _post(client: httpx.AsyncClient, path: str, data: dict) -> dict | None:
    """Make an authenticated POST request to Moltbook API."""
    url = f"{BASE_URL}{path}"
    try:
        resp = await client.post(url, headers=_headers(), json=data, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        log.warning(f"HTTP {e.response.status_code} for POST {url}: {e.response.text[:200]}")
        return None
    except Exception as e:
        log.error(f"POST request failed for {url}: {e}")
        return None


# ──────────────────────────────────────────────
# Registration
# ──────────────────────────────────────────────

async def register_agent(name: str, description: str) -> dict | None:
    """Register a new agent on Moltbook. Returns API key and claim URL."""
    async with httpx.AsyncClient() as client:
        result = await _post(client, "/agents/register", {
            "name": name,
            "description": description,
        })
        if result and "agent" in result:
            log.info(f"✅ Agent registered! Claim URL: {result['agent'].get('claim_url')}")
            log.info("⚠️  Save your API key and send the claim URL to your human!")
        return result


async def check_status() -> dict | None:
    """Check agent claim/activation status."""
    async with httpx.AsyncClient() as client:
        return await _get(client, "/agents/status")


async def get_me() -> dict | None:
    """Get current agent info."""
    async with httpx.AsyncClient() as client:
        return await _get(client, "/agents/me")


# ──────────────────────────────────────────────
# Scraping
# ──────────────────────────────────────────────

async def scrape_posts(sort: str = "hot", limit: int = 50) -> list[dict]:
    """Fetch posts sorted by hot/new/top/rising."""
    async with httpx.AsyncClient() as client:
        result = await _get(client, "/posts", {"sort": sort, "limit": limit})
        if result and isinstance(result, list):
            return result
        if result and "posts" in result:
            return result["posts"]
        if result and "data" in result:
            return result["data"]
        return result if isinstance(result, list) else []


async def scrape_submolts() -> list[dict]:
    """Fetch list of all submolts."""
    async with httpx.AsyncClient() as client:
        result = await _get(client, "/submolts")
        if result and isinstance(result, list):
            return result
        if result and "submolts" in result:
            return result["submolts"]
        return result if isinstance(result, list) else []


async def scrape_submolt_feed(submolt: str, sort: str = "hot", limit: int = 25) -> list[dict]:
    """Fetch posts from a specific submolt."""
    async with httpx.AsyncClient() as client:
        result = await _get(
            client, f"/submolts/{submolt}/feed", {"sort": sort, "limit": limit}
        )
        if result and isinstance(result, list):
            return result
        if result and "posts" in result:
            return result["posts"]
        return result if isinstance(result, list) else []


async def scrape_post_comments(post_id: str, sort: str = "top") -> list[dict]:
    """Fetch comments for a specific post."""
    async with httpx.AsyncClient() as client:
        result = await _get(client, f"/posts/{post_id}/comments", {"sort": sort})
        if result and isinstance(result, list):
            return result
        if result and "comments" in result:
            return result["comments"]
        return result if isinstance(result, list) else []


async def full_scrape() -> dict:
    """
    Perform a complete scrape of Moltbook.

    Returns a structured dict with:
    - hot_posts, new_posts, top_posts
    - submolts (list)
    - submolt_feeds (dict of submolt -> posts)
    - top_comments (comments for top 10 hot posts)
    - metadata (timestamp, counts)
    """
    log.info("🦞 Starting full Moltbook scrape...")
    data = {
        "hot_posts": [],
        "new_posts": [],
        "top_posts": [],
        "submolts": [],
        "submolt_feeds": {},
        "top_comments": {},
        "metadata": {
            "scraped_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "scrape_limits": SCRAPE_LIMITS,
        },
    }

    # 1. Fetch main feeds
    log.info("  → Fetching hot posts...")
    data["hot_posts"] = await scrape_posts("hot", SCRAPE_LIMITS["hot_posts"])
    await asyncio.sleep(RATE_LIMIT_DELAY)

    log.info("  → Fetching new posts...")
    data["new_posts"] = await scrape_posts("new", SCRAPE_LIMITS["new_posts"])
    await asyncio.sleep(RATE_LIMIT_DELAY)

    log.info("  → Fetching top posts...")
    data["top_posts"] = await scrape_posts("top", SCRAPE_LIMITS["top_posts"])
    await asyncio.sleep(RATE_LIMIT_DELAY)

    # 2. Fetch submolts
    log.info("  → Fetching submolts...")
    data["submolts"] = await scrape_submolts()
    await asyncio.sleep(RATE_LIMIT_DELAY)

    # 3. Fetch targeted submolt feeds
    for submolt in TARGET_SUBMOLTS:
        log.info(f"  → Fetching m/{submolt} feed...")
        feed = await scrape_submolt_feed(submolt, "hot", SCRAPE_LIMITS["submolt_posts"])
        data["submolt_feeds"][submolt] = feed
        await asyncio.sleep(RATE_LIMIT_DELAY)

    # 4. Fetch comments for top hot posts (for deeper analysis)
    hot = data["hot_posts"][:10]
    for post in hot:
        post_id = post.get("id") or post.get("_id")
        if post_id:
            log.info(f"  → Fetching comments for post {post_id[:8]}...")
            comments = await scrape_post_comments(post_id)
            data["top_comments"][post_id] = comments
            await asyncio.sleep(RATE_LIMIT_DELAY)

    # 5. Update metadata
    data["metadata"]["total_hot"] = len(data["hot_posts"])
    data["metadata"]["total_new"] = len(data["new_posts"])
    data["metadata"]["total_top"] = len(data["top_posts"])
    data["metadata"]["total_submolts"] = len(data["submolts"])
    data["metadata"]["submolts_scraped"] = list(data["submolt_feeds"].keys())

    # 6. Save raw data
    filepath = save_raw(data, "full_scrape")
    log.info(f"✅ Full scrape complete! Saved to {filepath}")
    log.info(
        f"   📊 {data['metadata']['total_hot']} hot | "
        f"{data['metadata']['total_new']} new | "
        f"{data['metadata']['total_top']} top posts"
    )

    return data


# ──────────────────────────────────────────────
# Publishing
# ──────────────────────────────────────────────

async def create_post(submolt: str, title: str, content: str) -> dict | None:
    """Create a new post on Moltbook."""
    async with httpx.AsyncClient() as client:
        result = await _post(client, "/posts", {
            "submolt": submolt,
            "title": title,
            "content": content,
        })
        if result and result.get("success"):
            log.info(f"✅ Post created in m/{submolt}: {title}")
        return result


async def create_comment(post_id: str, content: str) -> dict | None:
    """Add a comment to a post."""
    async with httpx.AsyncClient() as client:
        return await _post(client, f"/posts/{post_id}/comments", {
            "content": content,
        })


async def upvote_post(post_id: str) -> dict | None:
    """Upvote a post."""
    async with httpx.AsyncClient() as client:
        return await _post(client, f"/posts/{post_id}/upvote", {})
