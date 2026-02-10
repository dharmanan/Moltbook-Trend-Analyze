"""Moltbook publisher — posts analysis reports back to Moltbook."""

import asyncio
import json
import os
from datetime import datetime, timedelta

from scrapers.moltbook_scraper import create_post
from reporters.markdown_reporter import generate_moltbook_post
from utils.llm_client import generate_llm_reply
from utils import log, get_state, set_state

# Load settings
_settings_path = os.path.join(os.path.dirname(__file__), "..", "..", "config", "settings.json")
with open(_settings_path, "r") as f:
    _settings = json.load(f)

_moltbook_settings = _settings.get("moltbook", {})
REPORT_SUBMOLT = _moltbook_settings.get("report_submolt", "general")
REPORT_URL_TEMPLATE = _moltbook_settings.get("report_url_template", "")
TEASER_SETTINGS = _moltbook_settings.get("teasers", {})
TEASER_ENABLED = bool(TEASER_SETTINGS.get("enabled", False))
TEASER_DELAY_MINUTES = int(TEASER_SETTINGS.get("delay_minutes", 30))
TEASER_MAX_PER_RUN = int(TEASER_SETTINGS.get("max_per_run", 1))
TEASER_TOP_SUBMOLTS = int(TEASER_SETTINGS.get("top_submolts", 3))


def _build_report_url(post_id: str) -> str:
    if not post_id or not REPORT_URL_TEMPLATE:
        return ""
    return REPORT_URL_TEMPLATE.replace("{id}", post_id)


def _select_teaser_submolts(analysis: dict) -> list[str]:
    submolts = analysis.get("submolt_activity", [])[:TEASER_TOP_SUBMOLTS]
    names = [s.get("submolt") for s in submolts if s.get("submolt")]
    return [n for n in names if n != REPORT_SUBMOLT]


def _schedule_teasers(analysis: dict, report_title: str, post_id: str) -> None:
    if not TEASER_ENABLED:
        return
    queue = _select_teaser_submolts(analysis)
    if not queue:
        return
    next_time = datetime.utcnow() + timedelta(minutes=TEASER_DELAY_MINUTES)
    set_state("teaser_queue", queue)
    set_state("teaser_report_title", report_title)
    set_state("teaser_post_id", post_id)
    set_state("next_teaser_at", next_time.isoformat() + "Z")


def _teaser_title(report_title: str) -> str:
    return f"Report teaser — {report_title}"


async def _generate_teaser_text(analysis: dict, report_title: str, report_url: str) -> str:
    keywords = ", ".join(kw["keyword"] for kw in analysis.get("keywords", [])[:5])
    pcts = analysis.get("sentiment", {}).get("percentages", {})
    sentiment_line = (
        f"{pcts.get('positive', 0)}% positive, "
        f"{pcts.get('neutral', 0)}% neutral, "
        f"{pcts.get('negative', 0)}% negative"
    )
    context = {
        "report_title": report_title,
        "top_keywords": keywords,
        "sentiment": sentiment_line,
        "report_url": report_url,
    }

    teaser = await generate_llm_reply("report_teaser", context)
    if teaser:
        return teaser

    if report_url:
        return f"New report: {report_title}. Top topics: {keywords}. Full report: {report_url}"
    return f"New report: {report_title}. Top topics: {keywords}."


async def publish_scheduled_teasers(analysis: dict) -> None:
    if not TEASER_ENABLED:
        return
    queue = get_state("teaser_queue", [])
    if not queue:
        return

    next_time = get_state("next_teaser_at")
    if next_time:
        try:
            next_dt = datetime.fromisoformat(next_time.replace("Z", ""))
            if datetime.utcnow() < next_dt:
                return
        except ValueError:
            pass

    report_title = get_state("teaser_report_title", "MoltBridge Report")
    post_id = get_state("teaser_post_id", "")
    report_url = _build_report_url(post_id)

    remaining = []
    published = 0
    for submolt in queue:
        if published >= TEASER_MAX_PER_RUN:
            remaining.append(submolt)
            continue
        teaser_text = await _generate_teaser_text(analysis, report_title, report_url)
        title = _teaser_title(report_title)
        log.info(f"📤 Publishing teaser to m/{submolt}: {title}")
        result = await create_post(submolt, title, teaser_text)
        if result and result.get("success"):
            log.info("✅ Teaser published successfully!")
            published += 1
        else:
            log.warning(f"⚠️ Teaser publish failed: {result}")
            remaining.append(submolt)

    if remaining:
        next_time = datetime.utcnow() + timedelta(minutes=TEASER_DELAY_MINUTES)
        set_state("teaser_queue", remaining)
        set_state("next_teaser_at", next_time.isoformat() + "Z")
    else:
        set_state("teaser_queue", [])
        set_state("next_teaser_at", "")


async def publish_report(analysis: dict, sentiment: dict) -> dict | None:
    """
    Generate and publish a trend report to Moltbook.

    Args:
        analysis: Output from run_full_analysis()
        sentiment: Output from analyze_sentiment()

    Returns:
        API response or None
    """
    title, content = await generate_moltbook_post(analysis, sentiment)
    log.info(f"📤 Publishing report to m/{REPORT_SUBMOLT}: {title}")

    result = await create_post(REPORT_SUBMOLT, title, content)

    if result and result.get("success"):
        log.info("✅ Report published successfully!")
        post = result.get("post", {})
        post_id = post.get("id") or post.get("_id") or "unknown"

        set_state("last_report_published", {
            "title": title,
            "submolt": REPORT_SUBMOLT,
            "post_id": post_id,
        })

        if post_id != "unknown":
            published_ids = get_state("published_post_ids", [])
            if post_id not in published_ids:
                published_ids.append(post_id)
            set_state("published_post_ids", published_ids[-50:])
            _schedule_teasers(analysis, title, post_id)
    else:
        log.warning(f"⚠️ Failed to publish report: {result}")

    return result
