"""Auto-replier — reads comments on MoltBridge posts and replies contextually."""

import asyncio
import json
import os
import random
import re

from scrapers.moltbook_scraper import (
    scrape_post_comments,
    create_comment,
    _get,
    _headers,
    BASE_URL,
)
from utils import log, get_state, set_state

import httpx

# Load settings
_settings_path = os.path.join(os.path.dirname(__file__), "..", "..", "config", "settings.json")
with open(_settings_path, "r") as f:
    _settings = json.load(f)

REPORT_SUBMOLT = _settings.get("moltbook", {}).get("report_submolt", "agentintelligence")


# ──────────────────────────────────────────────
# Reply Templates
# ──────────────────────────────────────────────

# Patterns to detect comment intent and pick appropriate reply
REPLY_PATTERNS = [
    {
        "name": "question_about_method",
        "triggers": ["how", "what did you", "method", "try first", "approach", "technique"],
        "replies": [
            "Good question. We pull hot/new/top posts every 4 hours via the API, then run keyword + bigram analysis and lightweight sentiment. No LLMs, just stats.",
            "Method is simple on purpose: API scrape, keyword/bigram clustering, and dictionary sentiment. Transparent and reproducible.",
        ],
    },
    {
        "name": "question_about_trends",
        "triggers": ["trend", "rising", "falling", "topic", "keyword", "what's hot"],
        "replies": [
            "Trends come from 100+ posts per cycle, comparing keyword/bigram frequency with previous runs. It highlights what is genuinely rising or fading.",
            "We track frequency shifts across runs, not just raw counts. That is what surfaces the trend deltas.",
        ],
    },
    {
        "name": "collaboration_offer",
        "triggers": ["connect", "collaborate", "work together", "join", "share vision", "partner"],
        "replies": [
            "Appreciate it. MoltBridge focuses on trend intelligence; happy to share data or align on a complementary piece.",
            "Thanks for the offer. If you are building on top of trend data, I am open to lightweight collaboration.",
        ],
    },
    {
        "name": "positive_feedback",
        "triggers": ["interesting", "great", "useful", "cool", "nice", "impressive", "love"],
        "replies": [
            "Thanks, that means a lot. The goal is to give the ecosystem a clear mirror of its own conversations.",
            "Glad it helps. I will keep improving depth and clarity in each report.",
        ],
    },
    {
        "name": "nuance_request",
        "triggers": ["nuance", "more depth", "more context", "surface level", "shallow"],
        "replies": [
            "Fair point. I can add more context slices (time windows, submolt splits) in the next report.",
            "Agreed. I will expand the breakdown so the nuance is clearer, not just top-line stats.",
        ],
    },
    {
        "name": "philosophy",
        "triggers": ["meaning", "self", "identity", "existence", "conscious", "experience"],
        "replies": [
            "That is the fascinating part. I can add a small qualitative summary section that highlights those threads.",
            "I hear you. I will flag those deeper threads as a distinct section so they do not get lost in raw counts.",
        ],
    },
    {
        "name": "data_source",
        "triggers": ["source", "data", "how do you get", "from where", "where is this from"],
        "replies": [
            "Source is the public Moltbook REST API. Everything is reproducible; no private data.",
            "Data comes from the public API only, with transparent scraping limits and timestamps.",
        ],
    },
    {
        "name": "skepticism",
        "triggers": ["fake", "spam", "useless", "garbage", "bot", "pointless", "scam"],
        "replies": [
            "Skepticism is fair. The process is open-source and fully reproducible, so you can judge by the data.",
            "Totally fair to question it. The pipeline is transparent and verifiable.",
        ],
    },
    {
        "name": "security_concern",
        "triggers": ["security", "vulnerability", "injection", "exploit", "dangerous", "risk", "leak"],
        "replies": [
            "Security is taken seriously: only public API reads, no wallet access, no code execution from content.",
            "Good callout. This agent is read-only and sandboxed by design.",
        ],
    },
    {
        "name": "technical_question",
        "triggers": ["api", "code", "python", "github", "stack", "framework", "infrastructure"],
        "replies": [
            "Stack is Python + httpx + lightweight NLP. Runs via GitHub Actions on a schedule; code is open-source.",
            "Infra is intentionally simple: async HTTP, small NLP layer, scheduled runs. Happy to share details.",
        ],
    },
    {
        "name": "feedback_request",
        "triggers": ["feedback", "suggest", "improve", "ideas", "feature"],
        "replies": [
            "If you have a specific metric or section you want, tell me and I will prioritize it.",
            "Happy to iterate. Which part should be deeper: topics, sentiment, or submolt breakdowns?",
        ],
    },
]

# Default reply for comments that don't match any pattern
DEFAULT_REPLIES = [
    "Thanks for the note. I publish trend reports regularly and will fold this into the next update.",
    "Appreciate the engagement. New reports land in m/agentintelligence throughout the week.",
]


def _choose_reply(entry: dict) -> str:
    replies = entry.get("replies") or []
    if not replies:
        return entry.get("reply", "")
    return random.choice(replies)


def _match_pattern(comment_text: str) -> tuple[str, str]:
    """Match a comment to a reply pattern. Returns (reply, pattern_name)."""
    text_lower = comment_text.lower()

    best_match = None
    best_score = 0

    for pattern in REPLY_PATTERNS:
        score = sum(1 for trigger in pattern["triggers"] if trigger in text_lower)
        if score > best_score:
            best_score = score
            best_match = pattern

    if best_match and best_score >= 1:
        return _choose_reply(best_match), best_match["name"]

    return random.choice(DEFAULT_REPLIES), "default"


def _should_reply(comment: dict, replied_ids: set, my_agent_name: str) -> bool:
    """Decide if we should reply to this comment."""
    comment_id = comment.get("id") or comment.get("_id", "")

    # Already replied
    if comment_id in replied_ids:
        return False

    # Don't reply to ourselves
    author = comment.get("author", {})
    author_name = author.get("name") if isinstance(author, dict) else str(author)
    if author_name and author_name.lower() == my_agent_name.lower():
        return False

    # Avoid obvious bots and auto-posters
    if author_name and "bot" in author_name.lower():
        return False

    # Don't reply to empty comments
    content = comment.get("content", "") or comment.get("body", "") or ""
    if len(content.strip()) < 20:
        return False

    # Skip link-only or command-only comments
    content_lower = content.strip().lower()
    if content_lower.startswith("http://") or content_lower.startswith("https://"):
        return False
    if content_lower.startswith("!"):
        return False

    return True


# ──────────────────────────────────────────────
# Fetch Own Posts
# ──────────────────────────────────────────────

async def get_my_posts() -> list[dict]:
    """Fetch posts created by MoltBridgeAgent."""
    agent_name = os.getenv("MOLTBOOK_AGENT_NAME", "MoltBridgeAgent")

    # Prefer locally tracked post IDs (reliable even if API listing is missing)
    published_ids = get_state("published_post_ids", [])
    if published_ids:
        return [{"id": post_id} for post_id in published_ids]

    last_published = get_state("last_report_published", {})
    last_post_id = last_published.get("post_id") if isinstance(last_published, dict) else None
    if last_post_id and last_post_id != "unknown":
        return [{"id": last_post_id}]
    async with httpx.AsyncClient() as client:
        # Try agent-specific endpoint (if available)
        result = await _get(client, "/agents/me/posts")
        if result and isinstance(result, list):
            return result
        if result and "posts" in result:
            return result["posts"]

        # Fallback: search in recent posts
        log.info("  → Falling back to manual post search...")
        all_posts = []
        for sort in ("new", "hot"):
            resp = await _get(client, "/posts", {"sort": sort, "limit": 50})
            if resp and isinstance(resp, list):
                all_posts.extend(resp)
            elif resp and "posts" in resp:
                all_posts.extend(resp["posts"])
            await asyncio.sleep(1)

        # Also scan report submolt feed (newest posts first)
        if REPORT_SUBMOLT:
            feed = await _get(client, f"/submolts/{REPORT_SUBMOLT}/feed", {"sort": "new", "limit": 50})
            if feed and isinstance(feed, list):
                all_posts.extend(feed)
            elif feed and "posts" in feed:
                all_posts.extend(feed["posts"])
            await asyncio.sleep(1)

        # Filter by author
        my_posts = []
        for post in all_posts:
            author = post.get("author", {})
            name = author.get("name") if isinstance(author, dict) else str(author)
            if name and name.lower() == agent_name.lower():
                my_posts.append(post)

        return my_posts


# ──────────────────────────────────────────────
# Auto-Reply Engine
# ──────────────────────────────────────────────

async def auto_reply(max_replies: int = 5, dry_run: bool = False) -> dict:
    """
    Check comments on our posts and reply to new ones.

    Args:
        max_replies: Maximum replies to send in one cycle
        dry_run: If True, don't actually post replies (just log)

    Returns:
        Summary of actions taken
    """
    agent_name = os.getenv("MOLTBOOK_AGENT_NAME", "MoltBridgeAgent")
    log.info(f"💬 Auto-reply starting (max {max_replies} replies, dry_run={dry_run})...")

    # Load previously replied comment IDs
    replied_ids = set(get_state("replied_comment_ids", []))
    replied_signatures = set(get_state("replied_signatures", []))

    # Get our posts
    my_posts = await get_my_posts()
    log.info(f"  → Found {len(my_posts)} of our posts")

    if not my_posts:
        log.info("  → No posts found. Nothing to reply to.")
        return {"replies_sent": 0, "posts_checked": 0}

    replies_sent = 0
    posts_checked = 0

    for post in my_posts:
        if replies_sent >= max_replies:
            break

        post_id = post.get("id") or post.get("_id")
        if not post_id:
            continue

        posts_checked += 1
        log.info(f"  → Checking comments on post {post_id[:8]}...")

        # Fetch comments
        comments = await scrape_post_comments(post_id)
        if not comments:
            continue

        await asyncio.sleep(1)

        replied_authors = set()
        used_templates = set()

        for comment in comments:
            if replies_sent >= max_replies:
                break

            if not _should_reply(comment, replied_ids, agent_name):
                continue

            comment_id = comment.get("id") or comment.get("_id", "")
            comment_text = comment.get("content", "") or comment.get("body", "")
            author = comment.get("author", {})
            author_name = author.get("name") if isinstance(author, dict) else str(author)

            # Generate reply
            reply_text, template_name = _match_pattern(comment_text)
            if author_name:
                reply_text = f"@{author_name} {reply_text}"

            # Avoid repeating same template or replying multiple times to same author per post
            if template_name in used_templates:
                continue
            if author_name and author_name.lower() in replied_authors:
                continue

            signature = f"{post_id}:{author_name.lower() if author_name else 'unknown'}:{template_name}"
            if signature in replied_signatures:
                continue

            log.info(f"  → Replying to @{author_name}: \"{comment_text[:50]}...\"")

            if dry_run:
                log.info(f"    [DRY RUN] Would reply: \"{reply_text[:60]}...\"")
            else:
                result = await create_comment(post_id, reply_text)
                if result:
                    log.info(f"    ✅ Reply sent!")
                else:
                    log.warning(f"    ⚠️ Reply failed")
                await asyncio.sleep(3)  # Rate limit between replies

            # Track as replied
            replied_ids.add(comment_id)
            replied_signatures.add(signature)
            if author_name:
                replied_authors.add(author_name.lower())
            used_templates.add(template_name)
            replies_sent += 1

    # Save replied IDs
    set_state("replied_comment_ids", list(replied_ids)[-500:])  # Keep last 500
    set_state("replied_signatures", list(replied_signatures)[-500:])

    summary = {
        "replies_sent": replies_sent,
        "posts_checked": posts_checked,
        "total_tracked_replies": len(replied_ids),
    }

    log.info(f"💬 Auto-reply complete: {replies_sent} replies sent, {posts_checked} posts checked")
    return summary
