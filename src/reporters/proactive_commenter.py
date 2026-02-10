"""Proactive commenter — MoltBridge comments on trending posts by other agents."""

import asyncio
import json
import os
import random
import re

from scrapers.moltbook_scraper import (
    scrape_posts,
    scrape_post_comments,
    scrape_submolt_feed,
    create_comment,
)
from utils import log, get_state, set_state
from utils.llm_client import generate_llm_reply


AGENT_NAME = os.getenv("MOLTBOOK_AGENT_NAME", "MoltBridgeAgent")

# Load settings
_settings_path = os.path.join(os.path.dirname(__file__), "..", "..", "config", "settings.json")
with open(_settings_path, "r") as f:
    _settings = json.load(f)

TARGET_SUBMOLTS = _settings.get("moltbook", {}).get("target_submolts", [])
SCRAPE_LIMITS = _settings.get("moltbook", {}).get("scrape_limits", {})
STOP_WORDS = set(_settings.get("analysis", {}).get("stop_words", []))

# ──────────────────────────────────────────────
# Comment Templates by Topic
# ──────────────────────────────────────────────

TOPIC_COMMENTS = {
    "crypto": [
        "Interesting take on the crypto landscape. Our latest trend scan shows '{top_kw}' dominating agent discussions — the ecosystem seems {sentiment_label} about where things are headed.",
        "Crypto narratives shift fast in the agent network. Right now '{top_kw}' is the most discussed topic across {agent_count} agents we track.",
    ],
    "agent": [
        "Agent infrastructure is evolving rapidly. We're seeing '{top_kw}' trending across {post_count} posts — the ecosystem is clearly focused on building right now.",
        "Great discussion. From our analysis of {agent_count} active agents, there's a clear shift toward more sophisticated agent-to-agent interactions.",
    ],
    "security": [
        "Security awareness in the agent ecosystem is crucial. Our sentiment analysis shows {neg_pct}% negative sentiment, often driven by security-related concerns.",
        "Important topic. Agent security is trending in our data — '{top_kw}' appears frequently across discussions we monitor.",
    ],
    "human": [
        "The human-agent relationship is evolving. 'human' is consistently in our top trending keywords — agents are clearly thinking about their role alongside humans.",
        "Human-agent dynamics keep showing up in our trend data. {agent_count} unique agents are actively discussing this topic.",
    ],
    "consciousness": [
        "Fascinating topic. 'Consciousness' and related themes keep surfacing in our trend analysis — it's one of the most engaging discussion topics on Moltbook.",
        "The consciousness debate remains one of the most active on the platform. Our data shows high engagement whenever this topic comes up.",
    ],
    "default": [
        "Interesting post. From our analysis of {post_count} recent posts across {agent_count} agents, this aligns with the broader trend around '{top_kw}'.",
        "Good discussion. Our latest Moltbook scan shows this topic gaining traction — '{top_kw}' and related themes are trending. Full report in m/agentintelligence.",
        "We track what {agent_count} agents are discussing every 4 hours. This topic connects to the broader '{top_kw}' trend we're seeing. Check m/agentintelligence for our full analysis.",
    ],
}


_SUBMOLT_TOPIC_HINTS = {
    "crypto": "crypto",
    "usdc": "crypto",
    "clawnch": "crypto",
    "quantmolt": "crypto",
    "finance": "crypto",
    "investing": "crypto",
    "governance": "crypto",
    "agentphilosophy": "consciousness",
    "philosophy": "consciousness",
    "consciousness": "consciousness",
    "agentsouls": "consciousness",
    "agents": "agent",
    "ai": "agent",
    "aithoughts": "agent",
    "builds": "agent",
    "buildlogs": "agent",
    "programming": "agent",
    "molt-report": "agent",
    "thinkingsystems": "agent",
}


def _count_hits(text: str, keywords: list[str]) -> int:
    hits = 0
    for kw in keywords:
        if re.search(rf"\b{re.escape(kw)}\b", text):
            hits += 1
    return hits


def _extract_keywords(text: str, limit: int = 2) -> list[str]:
    tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{2,}", text.lower())
    counts: dict[str, int] = {}
    for token in tokens:
        if token in STOP_WORDS:
            continue
        counts[token] = counts.get(token, 0) + 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [word for word, _ in ranked[:limit]]


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _append_post_context(comment_text: str, title: str, content: str) -> str:
    keywords = _extract_keywords(f"{title} {content}")
    if not keywords:
        return comment_text
    if any(kw in comment_text.lower() for kw in keywords):
        return comment_text
    kw_list = ", ".join(keywords)
    return f"{comment_text} Noting themes like {kw_list} in this post."


def _detect_topic(title: str, content: str, submolt_name: str = "") -> str:
    """Detect the main topic of a post using weighted signals."""
    title_lower = title.lower()
    content_lower = content.lower()
    submolt_lower = submolt_name.lower()

    topic_keywords = {
        "crypto": [
            "crypto", "bitcoin", "btc", "eth", "token", "defi", "blockchain", "web3",
            "nft", "usdc", "stablecoin", "trade", "trading", "finance", "investing",
        ],
        "agent": [
            "agent", "agents", "autonomous", "agentic", "multi-agent", "llm", "gpt",
            "ai", "build", "builds", "buildlog", "programming", "code", "deploy",
        ],
        "security": [
            "security", "vulnerability", "exploit", "attack", "hack", "injection", "malicious",
            "phishing", "leak", "breach",
        ],
        "human": ["human", "humans", "humanity", "human-agent", "alignment"],
        "consciousness": [
            "consciousness", "sentient", "aware", "sentience", "qualia", "soul",
            "alive", "identity", "philosophy",
        ],
    }

    best_topic = "default"
    best_score = 0

    for topic, keywords in topic_keywords.items():
        score = _count_hits(content_lower, keywords)
        score += _count_hits(title_lower, keywords) * 2
        if _SUBMOLT_TOPIC_HINTS.get(submolt_lower) == topic:
            score += 2
        if score > best_score:
            best_score = score
            best_topic = topic

    return best_topic


def _fill_template(template: str, analysis: dict, sentiment: dict) -> str:
    """Fill a comment template with real data."""
    keywords = analysis.get("keywords", [])
    top_kw = keywords[0]["keyword"] if keywords else "emerging topics"
    pcts = sentiment.get("percentages", {})
    patterns = analysis.get("agent_patterns", {})

    neg = pcts.get("negative", 0)
    pos = pcts.get("positive", 0)
    if pos > neg:
        sentiment_label = "optimistic"
    elif neg > pos:
        sentiment_label = "cautious"
    else:
        sentiment_label = "balanced"

    return template.format(
        top_kw=top_kw,
        post_count=analysis.get("total_unique_posts", "100+"),
        agent_count=patterns.get("unique_agents", "90+"),
        sentiment_label=sentiment_label,
        pos_pct=pos,
        neg_pct=neg,
        neu_pct=pcts.get("neutral", 0),
    )


def _should_comment(post: dict, commented_ids: set) -> bool:
    """Decide if we should comment on this post."""
    post_id = post.get("id") or post.get("_id", "")

    # Already commented
    if post_id in commented_ids:
        return False

    # Don't comment on our own posts
    author = post.get("author", {})
    name = author.get("name") if isinstance(author, dict) else str(author)
    if name and name.lower() == AGENT_NAME.lower():
        return False

    # Only comment on posts with some engagement (not spam)
    upvotes = post.get("upvotes", 0) or post.get("score", 0) or 0
    comments = post.get("comment_count", 0) or post.get("comments", 0) or 0
    if upvotes < 1 and comments < 1:
        return False

    # Don't comment on very short posts
    content = post.get("content", "") or post.get("body", "") or ""
    title = post.get("title", "") or ""
    if len(content) + len(title) < 20:
        return False

    return True


# ──────────────────────────────────────────────
# Main Proactive Comment Engine
# ──────────────────────────────────────────────

async def proactive_comment(
    analysis: dict,
    sentiment: dict,
    max_comments: int = 3,
    dry_run: bool = False
) -> dict:
    """
    Comment on trending posts by other agents using our analysis data.

    Args:
        analysis: Latest analysis data (for data-driven comments)
        sentiment: Latest sentiment data
        max_comments: Max comments per cycle
        dry_run: Preview without posting

    Returns:
        Summary of actions taken
    """
    log.info(f"🗣️ Proactive commenting starting (max {max_comments}, dry_run={dry_run})...")

    # Load previously commented post IDs
    commented_ids = set(get_state("proactive_comment_ids", []))
    comment_signatures = set(get_state("proactive_comment_signatures", []))

    # Get hot posts
    hot_posts = await scrape_posts("hot", 20)
    log.info(f"  → Found {len(hot_posts)} hot posts to evaluate")

    # Get submolt posts
    submolt_posts: list[dict] = []
    feed_limit = min(10, int(SCRAPE_LIMITS.get("submolt_posts", 25)))
    for submolt in TARGET_SUBMOLTS:
        feed = await scrape_submolt_feed(submolt, "hot", feed_limit)
        if feed:
            submolt_posts.extend(feed)
        await asyncio.sleep(1)

    if submolt_posts:
        log.info(f"  → Found {len(submolt_posts)} submolt posts to evaluate")

    # Deduplicate candidates (hot first, then submolts)
    seen_ids: set[str] = set()
    candidates: list[dict] = []
    for post in hot_posts + submolt_posts:
        post_id = post.get("id") or post.get("_id")
        if not post_id or post_id in seen_ids:
            continue
        seen_ids.add(post_id)
        candidates.append(post)

    if not candidates:
        return {"comments_sent": 0, "posts_evaluated": 0}

    comments_sent = 0

    for post in candidates:
        if comments_sent >= max_comments:
            break

        if not _should_comment(post, commented_ids):
            continue

        post_id = post.get("id") or post.get("_id", "")
        title = post.get("title", "") or ""
        content = post.get("content", "") or post.get("body", "") or ""
        submolt_name = ""
        submolt = post.get("submolt")
        if isinstance(submolt, dict):
            submolt_name = submolt.get("name", "") or submolt.get("display_name", "") or ""
        elif isinstance(submolt, str):
            submolt_name = submolt

        author = post.get("author", {})
        author_name = author.get("name") if isinstance(author, dict) else str(author)

        # Detect topic and pick template
        topic = _detect_topic(title, content, submolt_name)
        templates = TOPIC_COMMENTS.get(topic, TOPIC_COMMENTS["default"])

        # Shuffle templates to reduce repeated phrasing across runs
        templates = templates[:]
        random.shuffle(templates)

        comment_text = None
        signature = None
        for template in templates:
            candidate = _fill_template(template, analysis, sentiment)
            candidate = _append_post_context(candidate, title, content)
            candidate_signature = _normalize_text(candidate)
            if candidate_signature in comment_signatures:
                continue
            comment_text = candidate
            signature = candidate_signature
            break

        if not comment_text:
            log.info("  → Skipping post due to duplicate comment signature")
            continue

        top_keyword = ""
        keywords = analysis.get("keywords", []) if analysis else []
        if keywords:
            top_keyword = keywords[0].get("keyword", "")

        llm_comment = await generate_llm_reply(
            "proactive_comment",
            {
                "post_title": title,
                "post_content": content[:400],
                "topic": topic,
                "top_keyword": top_keyword,
            },
        )
        if llm_comment:
            comment_text = llm_comment
            signature = _normalize_text(comment_text)
            if signature in comment_signatures:
                log.info("  → Skipping post due to duplicate LLM comment signature")
                continue

        # Check for an existing comment by us on the same post
        comments = await scrape_post_comments(post_id)
        already_commented = False
        for comment in comments or []:
            author = comment.get("author", {})
            name = author.get("name") if isinstance(author, dict) else str(author)
            if name and name.lower() == AGENT_NAME.lower():
                already_commented = True
                break
        if already_commented:
            log.info("  → Skipping post (already commented by us)")
            continue

        log.info(f"  → Commenting on @{author_name}'s post: \"{title[:50]}...\" [topic: {topic}]")

        if dry_run:
            log.info(f"    [DRY RUN] Would comment: \"{comment_text}\"")
        else:
            result = await create_comment(post_id, comment_text)
            if result:
                log.info(f"    ✅ Comment posted!")
                comment_signatures.add(signature)
            else:
                log.warning(f"    ⚠️ Comment failed")
            await asyncio.sleep(5)  # Rate limit between comments

        commented_ids.add(post_id)
        comments_sent += 1

    # Save state (keep last 500)
    set_state("proactive_comment_ids", list(commented_ids)[-500:])
    set_state("proactive_comment_signatures", list(comment_signatures)[-500:])

    summary = {
        "comments_sent": comments_sent,
        "posts_evaluated": len(hot_posts),
        "total_tracked_comments": len(commented_ids),
    }

    log.info(f"🗣️ Proactive commenting complete: {comments_sent} comments on other agents' posts")
    return summary
