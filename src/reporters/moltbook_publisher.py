"""Moltbook publisher — posts analysis reports back to Moltbook."""

import asyncio
import json
import os

from scrapers.moltbook_scraper import create_post
from reporters.markdown_reporter import generate_moltbook_post
from utils import log, get_state, set_state

# Load settings
_settings_path = os.path.join(os.path.dirname(__file__), "..", "..", "config", "settings.json")
with open(_settings_path, "r") as f:
    _settings = json.load(f)

REPORT_SUBMOLT = _settings["moltbook"].get("report_submolt", "general")


async def publish_report(analysis: dict, sentiment: dict) -> dict | None:
    """
    Generate and publish a trend report to Moltbook.

    Args:
        analysis: Output from run_full_analysis()
        sentiment: Output from analyze_sentiment()

    Returns:
        API response or None
    """
    title, content = generate_moltbook_post(analysis, sentiment)
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
    else:
        log.warning(f"⚠️ Failed to publish report: {result}")

    return result
