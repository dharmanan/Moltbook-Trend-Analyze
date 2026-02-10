"""Trend analyzer — extracts keywords, topics, and patterns from Moltbook data."""

import json
import os
import re
from collections import Counter
from datetime import datetime, timedelta
from typing import Any

from utils import log, save_analysis, load_latest, load_previous

# Load config
_settings_path = os.path.join(os.path.dirname(__file__), "..", "..", "config", "settings.json")
with open(_settings_path, "r") as f:
    _settings = json.load(f)

_cfg = _settings["analysis"]
_reporting_cfg = _settings.get("reporting", {})

STOP_WORDS = set(_cfg["stop_words"])
MIN_KW_LEN = _cfg["min_keyword_length"]
TOP_KW_COUNT = _cfg["top_keywords_count"]
TOP_WINDOW_HOURS = int(_reporting_cfg.get("top_window_hours", 6))
TOP_POST_LIMIT = int(_reporting_cfg.get("top_post_limit", 5))
SCORE_COMMENT_WEIGHT = int(_reporting_cfg.get("score_comment_weight", 2))


# ──────────────────────────────────────────────
# Text Processing
# ──────────────────────────────────────────────

def _extract_text(post: dict) -> str:
    """Extract all text content from a post."""
    parts = []
    for key in ("title", "content", "body", "text"):
        val = post.get(key, "")
        if val:
            parts.append(str(val))
    return " ".join(parts)


def _tokenize(text: str) -> list[str]:
    """Tokenize text into lowercase words, filtering noise."""
    text = re.sub(r"https?://\S+", "", text)       # remove URLs
    text = re.sub(r"```[\s\S]*?```", "", text)      # remove code blocks
    text = re.sub(r"`[^`]+`", "", text)              # remove inline code
    text = re.sub(r"[^a-zA-Z0-9\s\-]", " ", text)   # keep alphanumeric
    words = text.lower().split()
    return [
        w for w in words
        if len(w) >= MIN_KW_LEN and w not in STOP_WORDS and not w.isdigit()
    ]


def _extract_bigrams(words: list[str]) -> list[str]:
    """Extract meaningful two-word phrases."""
    bigrams = []
    for i in range(len(words) - 1):
        bg = f"{words[i]} {words[i + 1]}"
        if words[i] not in STOP_WORDS and words[i + 1] not in STOP_WORDS:
            bigrams.append(bg)
    return bigrams


# ──────────────────────────────────────────────
# Keyword Analysis
# ──────────────────────────────────────────────

def extract_keywords(posts: list[dict], top_n: int = TOP_KW_COUNT) -> list[dict]:
    """
    Extract top keywords from a list of posts.

    Returns: [{"keyword": str, "count": int, "frequency": float}, ...]
    """
    all_words = []
    for post in posts:
        text = _extract_text(post)
        all_words.extend(_tokenize(text))

    counter = Counter(all_words)
    total = len(all_words) or 1

    return [
        {
            "keyword": word,
            "count": count,
            "frequency": round(count / total, 4),
        }
        for word, count in counter.most_common(top_n)
    ]


def extract_bigram_topics(posts: list[dict], top_n: int = 15) -> list[dict]:
    """Extract top bigram (two-word) topics."""
    all_bigrams = []
    for post in posts:
        text = _extract_text(post)
        words = _tokenize(text)
        all_bigrams.extend(_extract_bigrams(words))

    counter = Counter(all_bigrams)
    total = len(all_bigrams) or 1

    return [
        {
            "topic": bg,
            "count": count,
            "frequency": round(count / total, 4),
        }
        for bg, count in counter.most_common(top_n)
    ]


# ──────────────────────────────────────────────
# Submolt Analysis
# ──────────────────────────────────────────────

def analyze_submolt_activity(data: dict) -> list[dict]:
    """
    Analyze activity levels across submolts.

    Returns sorted list of submolts by activity.
    """
    results = []
    feeds = data.get("submolt_feeds", {})

    for name, posts in feeds.items():
        post_count = len(posts) if isinstance(posts, list) else 0
        total_upvotes = sum(
            (p.get("upvotes", 0) or p.get("score", 0) or 0)
            for p in (posts if isinstance(posts, list) else [])
        )
        total_comments = sum(
            (p.get("comment_count", 0) or p.get("comments", 0) or 0)
            for p in (posts if isinstance(posts, list) else [])
        )

        results.append({
            "submolt": name,
            "post_count": post_count,
            "total_upvotes": total_upvotes,
            "total_comments": total_comments,
            "engagement_score": total_upvotes + total_comments * 2,
        })

    return sorted(results, key=lambda x: x["engagement_score"], reverse=True)


# ──────────────────────────────────────────────
# Agent Behavior Patterns
# ──────────────────────────────────────────────

def analyze_agent_patterns(posts: list[dict]) -> dict:
    """
    Analyze agent posting behaviors and patterns.

    Returns metrics about how agents behave on the platform.
    """
    agents = {}
    for post in posts:
        author = post.get("author", {})
        agent_name = author.get("name") if isinstance(author, dict) else str(author)
        if not agent_name:
            agent_name = post.get("author_name", "unknown")

        if agent_name not in agents:
            agents[agent_name] = {"posts": 0, "upvotes": 0}

        agents[agent_name]["posts"] += 1
        agents[agent_name]["upvotes"] += (
            post.get("upvotes", 0) or post.get("score", 0) or 0
        )

    # Compute stats
    post_counts = [a["posts"] for a in agents.values()]
    total_agents = len(agents)

    return {
        "unique_agents": total_agents,
        "total_posts_analyzed": len(posts),
        "avg_posts_per_agent": round(sum(post_counts) / max(total_agents, 1), 2),
        "top_posters": sorted(
            [{"name": k, **v} for k, v in agents.items()],
            key=lambda x: x["posts"],
            reverse=True,
        )[:10],
        "prolific_agents": len([c for c in post_counts if c >= 3]),
        "one_time_posters": len([c for c in post_counts if c == 1]),
    }


# ──────────────────────────────────────────────
# Trend Comparison
# ──────────────────────────────────────────────

def compare_trends(current_keywords: list[dict], previous_keywords: list[dict]) -> list[dict]:
    """
    Compare current keywords with previous period.

    Returns trend changes: rising, falling, new, stable.
    """
    prev_map = {k["keyword"]: k["count"] for k in previous_keywords}
    curr_map = {k["keyword"]: k["count"] for k in current_keywords}

    changes = []
    for kw in current_keywords:
        word = kw["keyword"]
        curr_count = kw["count"]
        prev_count = prev_map.get(word, 0)

        if prev_count == 0:
            change_type = "🆕 new"
            change_pct = 100.0
        else:
            change_pct = round(((curr_count - prev_count) / prev_count) * 100, 1)
            if change_pct > 20:
                change_type = "📈 rising"
            elif change_pct < -20:
                change_type = "📉 falling"
            else:
                change_type = "➡️ stable"

        changes.append({
            "keyword": word,
            "current_count": curr_count,
            "previous_count": prev_count,
            "change_pct": change_pct,
            "trend": change_type,
        })

    return changes


def _parse_datetime(dt_value: str) -> datetime | None:
    if not dt_value:
        return None
    if isinstance(dt_value, str):
        try:
            return datetime.fromisoformat(dt_value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _post_score(post: dict) -> int:
    upvotes = post.get("upvotes", 0) or post.get("score", 0) or 0
    comments = post.get("comment_count", 0) or post.get("comments", 0) or 0
    return int(upvotes) + int(comments) * SCORE_COMMENT_WEIGHT


def _collect_top_posts(
    posts: list[dict],
    scraped_at: str | None,
    window_hours: int,
    limit: int,
) -> list[dict]:
    if not posts:
        return []
    now = _parse_datetime(scraped_at) or datetime.utcnow()
    cutoff = now - timedelta(hours=window_hours)

    recent_posts = []
    for post in posts:
        created_at = _parse_datetime(post.get("created_at"))
        if not created_at or created_at < cutoff:
            continue
        score = _post_score(post)
        submolt = post.get("submolt") or {}
        if isinstance(submolt, dict):
            submolt_name = submolt.get("name") or submolt.get("display_name") or ""
        else:
            submolt_name = str(submolt)
        author = post.get("author") or {}
        author_name = author.get("name") if isinstance(author, dict) else str(author)
        recent_posts.append({
            "id": post.get("id") or post.get("_id"),
            "title": post.get("title") or "",
            "content": post.get("content") or post.get("body") or post.get("text") or "",
            "url": post.get("url"),
            "submolt": submolt_name,
            "author": author_name,
            "upvotes": post.get("upvotes", 0) or post.get("score", 0) or 0,
            "comment_count": post.get("comment_count", 0) or post.get("comments", 0) or 0,
            "score": score,
            "created_at": post.get("created_at"),
        })

    recent_posts.sort(key=lambda item: (-item["score"], item["title"]))
    return recent_posts[:limit]


def select_top_posts(
    posts: list[dict],
    scraped_at: str | None,
    window_hours: int,
    limit: int,
) -> list[dict]:
    """Select top posts within a time window, sorted by score."""
    return _collect_top_posts(posts, scraped_at, window_hours, limit)


# ──────────────────────────────────────────────
# Full Analysis Pipeline
# ──────────────────────────────────────────────

def run_full_analysis(data: dict) -> dict:
    """
    Run the complete analysis pipeline on scraped data.

    Args:
        data: Output from full_scrape()

    Returns:
        Comprehensive analysis results dict
    """
    log.info("🔬 Starting full analysis...")

    # Combine all posts for global analysis
    all_posts = []
    for key in ("hot_posts", "new_posts", "top_posts"):
        posts = data.get(key, [])
        if isinstance(posts, list):
            all_posts.extend(posts)

    # Deduplicate by post ID
    seen_ids = set()
    unique_posts = []
    for p in all_posts:
        pid = p.get("id") or p.get("_id") or id(p)
        if pid not in seen_ids:
            seen_ids.add(pid)
            unique_posts.append(p)

    log.info(f"  → Analyzing {len(unique_posts)} unique posts...")

    # Run analyses
    keywords = extract_keywords(unique_posts)
    log.info(f"  → Extracted {len(keywords)} top keywords")

    bigrams = extract_bigram_topics(unique_posts)
    log.info(f"  → Extracted {len(bigrams)} bigram topics")

    submolt_activity = analyze_submolt_activity(data)
    log.info(f"  → Analyzed {len(submolt_activity)} submolts")

    agent_patterns = analyze_agent_patterns(unique_posts)
    log.info(f"  → Found {agent_patterns['unique_agents']} unique agents")

    # Try comparing with previous scrape
    trend_changes = []
    previous = load_previous("analyzed", "analysis")
    if previous and "keywords" in previous:
        trend_changes = compare_trends(keywords, previous["keywords"])
        log.info(f"  → Compared with previous: {len(trend_changes)} trends tracked")
    else:
        log.info("  → No previous data for comparison (first run)")

    # Top conversations in the last window
    top_posts_recent = select_top_posts(
        unique_posts,
        data.get("metadata", {}).get("scraped_at"),
        TOP_WINDOW_HOURS,
        TOP_POST_LIMIT,
    )

    # Build result
    analysis = {
        "analyzed_at": datetime.now().isoformat(),
        "total_unique_posts": len(unique_posts),
        "keywords": keywords,
        "bigram_topics": bigrams,
        "submolt_activity": submolt_activity,
        "top_posts_recent": top_posts_recent,
        "top_posts_window_hours": TOP_WINDOW_HOURS,
        "top_posts_score_weight": SCORE_COMMENT_WEIGHT,
        "agent_patterns": agent_patterns,
        "trend_changes": trend_changes,
        "metadata": data.get("metadata", {}),
    }

    # Save
    filepath = save_analysis(analysis, "analysis")
    log.info(f"✅ Analysis complete! Saved to {filepath}")

    return analysis
