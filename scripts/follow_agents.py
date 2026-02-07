#!/usr/bin/env python3
"""Follow agents based on latest analysis and/or commenters on our posts."""

import argparse
import asyncio
import os
import sys
from typing import Iterable
from urllib.parse import quote

import httpx
from dotenv import load_dotenv

SCRIPT_DIR = os.path.dirname(__file__)
SRC_DIR = os.path.join(SCRIPT_DIR, "..", "src")
sys.path.insert(0, os.path.abspath(SRC_DIR))

from utils import log, load_latest, get_state, set_state  # noqa: E402
from scrapers.moltbook_scraper import scrape_post_comments  # noqa: E402
from reporters.auto_replier import get_my_posts  # noqa: E402


BASE_URL = os.getenv("MOLTBOOK_BASE_URL", "https://www.moltbook.com/api/v1")
API_KEY = os.getenv("MOLTBOOK_API_KEY", "")


def _headers() -> dict:
    key = API_KEY or os.getenv("MOLTBOOK_API_KEY", "")
    return {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def _load_top_agent_names(limit: int | None = None) -> list[str]:
    analysis = load_latest("analyzed", "analysis")
    if not analysis:
        log.error("No analysis data found. Run a scrape+analyze first.")
        return []

    top = analysis.get("agent_patterns", {}).get("top_posters", [])
    names = [entry.get("name", "") for entry in top if entry.get("name")]
    if limit and limit > 0:
        return names[:limit]
    return names


def _collect_author_names(comments: list[dict], names: set[str]) -> None:
    for comment in comments:
        author = comment.get("author", {})
        author_name = author.get("name") if isinstance(author, dict) else str(author)
        if author_name:
            names.add(author_name)
        replies = comment.get("replies", [])
        if replies:
            _collect_author_names(replies, names)


async def _load_commenter_names(limit: int | None = None) -> list[str]:
    posts = await get_my_posts()
    if not posts:
        log.warning("No posts found for current agent.")
        return []

    names: set[str] = set()
    for post in posts:
        post_id = post.get("id") or post.get("_id")
        if not post_id:
            continue
        comments = await scrape_post_comments(post_id)
        if comments:
            _collect_author_names(comments, names)

    my_name = os.getenv("MOLTBOOK_AGENT_NAME", "MoltBridgeAgent").lower()
    names = {n for n in names if n.lower() != my_name}

    sorted_names = sorted(names)
    if limit and limit > 0:
        return sorted_names[:limit]
    return sorted_names


async def _follow_agents(agent_names: Iterable[str], dry_run: bool) -> dict:
    followed = []
    skipped = []
    failed = []

    tracked = set(get_state("followed_agent_names", []))

    async with httpx.AsyncClient() as client:
        for name in agent_names:
            if name in tracked:
                skipped.append(name)
                continue

            path = f"/agents/{quote(name)}/follow"
            url = f"{BASE_URL}{path}"

            if dry_run:
                log.info(f"[DRY RUN] Would follow {name}")
                followed.append(name)
                continue

            try:
                resp = await client.post(url, headers=_headers(), timeout=30)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("success"):
                        followed.append(name)
                        tracked.add(name)
                    else:
                        failed.append(name)
                        log.warning(f"Follow failed for {name}: {data}")
                else:
                    failed.append(name)
                    log.warning(f"Follow failed for {name}: HTTP {resp.status_code}")
            except Exception as exc:
                failed.append(name)
                log.warning(f"Follow error for {name}: {exc}")

    set_state("followed_agent_names", sorted(tracked))
    return {"followed": followed, "skipped": skipped, "failed": failed}


async def follow_from_latest(
    *,
    top_agents: bool = True,
    commenters: bool = False,
    limit: int | None = None,
    dry_run: bool = False,
) -> dict:
    """Follow agents using latest analysis data and/or commenters on our posts."""
    names: list[str] = []
    if top_agents:
        names.extend(_load_top_agent_names(limit or None))
    if commenters:
        names.extend(await _load_commenter_names(limit or None))

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique_names = []
    for name in names:
        if name not in seen:
            seen.add(name)
            unique_names.append(name)

    if not unique_names:
        return {"followed": [], "skipped": [], "failed": []}

    return await _follow_agents(unique_names, dry_run)


async def main() -> None:
    load_dotenv(os.path.join(SRC_DIR, "..", ".env"))

    parser = argparse.ArgumentParser(
        description="Follow top agents and/or commenters from latest data",
    )
    parser.add_argument("--top-agents", action="store_true", help="Follow top agents from latest analysis")
    parser.add_argument("--commenters", action="store_true", help="Follow commenters on our posts")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of follows from each source")
    parser.add_argument("--dry-run", action="store_true", help="Preview without posting follows")

    args = parser.parse_args()
    if not args.top_agents and not args.commenters:
        args.top_agents = True

    key = os.getenv("MOLTBOOK_API_KEY", "")
    if not key:
        log.error("MOLTBOOK_API_KEY is not set. Load .env before running.")
        return

    result = await follow_from_latest(
        top_agents=args.top_agents,
        commenters=args.commenters,
        limit=args.limit or None,
        dry_run=args.dry_run,
    )
    if not result["followed"] and not result["skipped"] and not result["failed"]:
        log.warning("No agents found to follow.")
        return
    log.info(
        "Follow complete: "
        f"{len(result['followed'])} followed, "
        f"{len(result['skipped'])} skipped, "
        f"{len(result['failed'])} failed"
    )


if __name__ == "__main__":
    asyncio.run(main())
