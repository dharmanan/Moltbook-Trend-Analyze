#!/usr/bin/env python3
"""
MoltBridge Agent — Main entry point.

Usage:
    python src/main.py --scrape              # Scrape Moltbook
    python src/main.py --analyze             # Analyze latest scrape
    python src/main.py --report              # Generate report
    python src/main.py --publish             # Publish report to Moltbook
    python src/main.py --reply               # Auto-reply to comments on our posts
    python src/main.py --reply-dry           # Preview replies without posting
    python src/main.py --hot-post            # Publish a hot post summary
    python src/main.py --full                # Full pipeline: scrape → analyze → report → publish → reply
    python src/main.py --register-moltbook   # Register on Moltbook
    python src/main.py --generate-8004       # Generate ERC-8004 registration file
    python src/main.py --register-8004 ADDR  # Register on ERC-8004 (on-chain)
    python src/main.py --status              # Check agent status
    python src/main.py --heartbeat           # Run heartbeat cycle
"""

import argparse
import asyncio
import json
import os
import re
import sys

# Ensure src is in path
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from utils import log, save_raw, load_latest, get_state, set_state
from utils.llm_client import generate_llm_reply
from scrapers.moltbook_scraper import (
    full_scrape,
    register_agent,
    check_status,
    get_me,
    check_auth_status,
    create_post,
)
from analyzers.trend_analyzer import run_full_analysis, select_top_posts
from analyzers.sentiment_analyzer import analyze_sentiment
from reporters.markdown_reporter import generate_daily_report, generate_moltbook_post
from reporters.moltbook_publisher import publish_report
from reporters.auto_replier import auto_reply
from reporters.proactive_commenter import proactive_comment
from blockchain.erc8004_client import (
    generate_registration_file,
    save_registration_file,
    register_on_chain,
    print_setup_guide,
)


# ──────────────────────────────────────────────
# Helper: deduplicate posts
# ──────────────────────────────────────────────

def _deduplicate_posts(data: dict) -> list[dict]:
    """Extract and deduplicate posts from scrape data."""
    all_posts = []
    for key in ("hot_posts", "new_posts", "top_posts"):
        posts = data.get(key, [])
        if isinstance(posts, list):
            all_posts.extend(posts)

    seen = set()
    unique = []
    for p in all_posts:
        pid = p.get("id") or p.get("_id") or id(p)
        if pid not in seen:
            seen.add(pid)
            unique.append(p)
    return unique


# ──────────────────────────────────────────────
# Commands
# ──────────────────────────────────────────────

async def cmd_scrape():
    """Run full Moltbook scrape."""
    log.info("=" * 50)
    log.info("🦞 MOLTBRIDGE — SCRAPE MODE")
    log.info("=" * 50)
    data = await full_scrape()
    return data


async def cmd_analyze():
    """Analyze the latest scrape data."""
    log.info("=" * 50)
    log.info("🔬 MOLTBRIDGE — ANALYZE MODE")
    log.info("=" * 50)

    data = load_latest("raw", "full_scrape")
    if not data:
        log.error("No scrape data found. Run --scrape first.")
        return None

    analysis = run_full_analysis(data)
    unique = _deduplicate_posts(data)
    sentiment = analyze_sentiment(unique)
    analysis["sentiment"] = sentiment

    return analysis


async def cmd_report():
    """Generate a daily report."""
    log.info("=" * 50)
    log.info("📝 MOLTBRIDGE — REPORT MODE")
    log.info("=" * 50)

    analysis = load_latest("analyzed", "analysis")
    if not analysis:
        log.error("No analysis data found. Run --analyze first.")
        return None

    sentiment = analysis.get("sentiment", {})
    report = await generate_daily_report(analysis, sentiment, include_sample_note=False)
    print("\n" + report)
    return report


async def cmd_publish():
    """Publish report to Moltbook (tries agentintelligence first, falls back to general)."""
    log.info("=" * 50)
    log.info("📤 MOLTBRIDGE — PUBLISH MODE")
    log.info("=" * 50)

    analysis = load_latest("analyzed", "analysis")
    if not analysis:
        log.error("No analysis data found. Run --analyze first.")
        return None

    sentiment = analysis.get("sentiment", {})
    result = await publish_report(analysis, sentiment)
    return result


async def cmd_reply(dry_run: bool = False):
    """Auto-reply to comments on our posts."""
    log.info("=" * 50)
    log.info(f"💬 MOLTBRIDGE — AUTO-REPLY MODE {'(DRY RUN)' if dry_run else ''}")
    log.info("=" * 50)

    result = await auto_reply(max_replies=5, dry_run=dry_run)
    return result


async def cmd_full():
    """Full pipeline: scrape → analyze → report → publish → reply."""
    log.info("=" * 60)
    log.info("🚀 MOLTBRIDGE — FULL PIPELINE")
    log.info("=" * 60)

    # Step 1: Scrape
    data = await full_scrape()
    if not data:
        log.error("Scrape failed. Aborting pipeline.")
        return

    # Step 2: Analyze
    analysis = run_full_analysis(data)
    unique = _deduplicate_posts(data)
    sentiment = analyze_sentiment(unique)
    analysis["sentiment"] = sentiment

    # Step 3: Report
    report = await generate_daily_report(analysis, sentiment, include_sample_note=False)
    log.info("📝 Report generated")

    # Step 4: Publish
    api_key = os.getenv("MOLTBOOK_API_KEY", "")
    published = False
    if api_key:
        result = await publish_report(analysis, sentiment)
        if result and result.get("success"):
            published = True
            log.info("📤 Report published to Moltbook")
        else:
            log.warning("⚠️ Publish failed (rate limit or other issue). Report saved locally.")
    else:
        log.warning("⚠️ MOLTBOOK_API_KEY not set. Skipping publish.")

    # Step 5: Proactive commenting on other agents' posts
    if api_key and analysis:
        log.info("🗣️ Commenting on trending posts...")
        await asyncio.sleep(2)
        try:
            comment_result = await proactive_comment(
                analysis, sentiment, max_comments=1, dry_run=False
            )
            log.info(f"🗣️ Proactive: {comment_result.get('comments_sent', 0)} comments posted")
        except Exception as e:
            log.warning(f"⚠️ Proactive comment error (non-fatal): {e}")

    # Update state
    set_state("last_full_run", {
        "timestamp": data.get("metadata", {}).get("scraped_at"),
        "posts_analyzed": analysis.get("total_unique_posts"),
        "top_keyword": analysis.get("keywords", [{}])[0].get("keyword", ""),
        "published": published,
    })

    log.info("✅ Full pipeline complete!")
    return analysis


async def cmd_sample_report():
    """Generate a sample report with expanded limits and a sample note."""
    log.info("=" * 50)
    log.info("🧪 MOLTBRIDGE — SAMPLE REPORT MODE")
    log.info("=" * 50)

    settings_path = os.path.join(os.path.dirname(__file__), "..", "config", "settings.json")
    with open(settings_path, "r") as f:
        settings = json.load(f)

    sample_limits = settings.get("moltbook", {}).get("sample_scrape_limits")
    if not sample_limits:
        log.error("Sample scrape limits not configured.")
        return None

    data = await full_scrape(scrape_limits=sample_limits)
    if not data:
        log.error("Scrape failed. Aborting sample report.")
        return None

    analysis = run_full_analysis(data)
    unique = _deduplicate_posts(data)
    sentiment = analyze_sentiment(unique)
    analysis["sentiment"] = sentiment

    report = await generate_daily_report(analysis, sentiment, include_sample_note=True)
    print("\n" + report)
    return report


async def cmd_hot_post(dry_run: bool = False):
    """Publish a hot post summary based on the last few hours."""
    log.info("=" * 50)
    log.info(f"🔥 MOLTBRIDGE — HOT POST MODE {'(DRY RUN)' if dry_run else ''}")
    log.info("=" * 50)

    api_key = os.getenv("MOLTBOOK_API_KEY", "")
    if not dry_run:
        if not api_key:
            log.warning("⚠️ MOLTBOOK_API_KEY not set. Skipping hot post.")
            return None

        auth_status = await check_auth_status()
        if auth_status == 401:
            log.warning("⚠️ Account unauthorized (401). Skipping hot post flow.")
            return None

    settings_path = os.path.join(os.path.dirname(__file__), "..", "config", "settings.json")
    with open(settings_path, "r") as f:
        settings = json.load(f)

    reporting_cfg = settings.get("reporting", {})
    window_hours = int(reporting_cfg.get("hot_post_window_hours", 4))
    limit = int(reporting_cfg.get("hot_post_limit", 1))
    moltbook_cfg = settings.get("moltbook", {})
    report_submolt = moltbook_cfg.get("report_submolt", "general")
    web_base_url = str(moltbook_cfg.get("web_base_url", "https://www.moltbook.com")).rstrip("/")

    data = load_latest("raw", "full_scrape")
    if not data:
        data = await full_scrape()
    if not data:
        log.error("Scrape failed. Aborting hot post.")
        return None

    unique = _deduplicate_posts(data)
    top_posts = select_top_posts(
        unique,
        data.get("metadata", {}).get("scraped_at"),
        window_hours,
        limit,
    )
    if not top_posts:
        log.info("No qualifying posts found for hot post window.")
        return None

    top_post = top_posts[0]
    source_id = top_post.get("id")
    posted_ids = set(get_state("hot_posted_source_ids", []))
    if source_id and source_id in posted_ids:
        log.info("Top post already featured. Skipping.")
        return None

    title = top_post.get("title") or "Untitled"
    author = top_post.get("author") or "unknown"
    submolt = top_post.get("submolt") or "general"
    score = top_post.get("score", 0)
    upvotes = top_post.get("upvotes", 0)
    comments = top_post.get("comment_count", 0)
    author_line = f"Author: @{author}" if author and author != "unknown" else "Author: unknown"
    raw_content = top_post.get("content") or top_post.get("body") or top_post.get("text") or ""
    post_url = top_post.get("url") or (f"{web_base_url}/post/{source_id}" if source_id else "")

    def _summary_text(text: str, max_sentences: int = 2, max_chars: int = 280) -> str:
        cleaned = re.sub(r"\s+", " ", text.strip())
        if not cleaned:
            return ""
        sentences = re.split(r"(?<=[.!?])\s+", cleaned)
        summary = " ".join(sentences[:max_sentences])
        if len(summary) > max_chars:
            summary = summary[: max_chars - 3].rstrip() + "..."
        return summary

    def _excerpt_text(text: str, max_chars: int = 360) -> str:
        cleaned = re.sub(r"\s+", " ", text.strip())
        if len(cleaned) <= max_chars:
            return cleaned
        return cleaned[: max_chars - 3].rstrip() + "..."

    summary_text = _summary_text(raw_content)
    excerpt_text = _excerpt_text(raw_content)

    llm_summary = await generate_llm_reply(
        "hot_post_summary",
        {
            "post_title": title,
            "author": author,
            "submolt": submolt,
            "post_content": raw_content,
        },
    )
    if llm_summary:
        summary_text = llm_summary.strip()
        if len(summary_text) > 200:
            summary_text = summary_text[:197].rstrip() + "..."

    post_title = f"Hot Post (Last {window_hours}h): {title}"
    content_parts = [
        f"Top post from the last {window_hours} hours.",
        "",
        f"Title: {title}",
        author_line,
        f"Submolt: m/{submolt}",
        f"Score: {score} (upvotes {upvotes}, comments {comments})",
    ]
    if post_url:
        content_parts.append(f"Link: {post_url}")
    if summary_text:
        content_parts.extend(["", "Summary:", summary_text])
    if excerpt_text:
        content_parts.extend(["", "Excerpt:", excerpt_text])

    content = "\n".join(content_parts) + "\n"

    if dry_run:
        log.info("[DRY RUN] Hot post content preview:")
        print("\n" + post_title + "\n\n" + content)
        return {"dry_run": True, "title": post_title, "content": content}

    result = await create_post(report_submolt, post_title, content)
    if result and result.get("success"):
        log.info("✅ Hot post published successfully!")
        set_state(
            "last_hot_post",
            {
                "source_id": source_id,
                "title": title,
                "submolt": submolt,
                "score": score,
                "published_at": data.get("metadata", {}).get("scraped_at"),
            },
        )
        if source_id:
            posted_ids.add(source_id)
            set_state("hot_posted_source_ids", list(posted_ids)[-200:])
    else:
        log.warning(f"⚠️ Failed to publish hot post: {result}")

    return result


async def cmd_register_moltbook():
    """Register agent on Moltbook."""
    name = os.getenv("MOLTBOOK_AGENT_NAME", "MoltBridgeAgent")
    desc = (
        "Autonomous intelligence agent that monitors Moltbook trends, "
        "analyzes what AI agents are discussing, and publishes structured reports. "
        "Bridging Moltbook intelligence to the ERC-8004 ecosystem."
    )

    log.info(f"📝 Registering '{name}' on Moltbook...")
    result = await register_agent(name, desc)

    if result and "agent" in result:
        agent = result["agent"]
        print("\n" + "=" * 50)
        print("✅ REGISTRATION SUCCESSFUL!")
        print("=" * 50)
        print(f"\n  API Key:    {agent.get('api_key', 'N/A')}")
        print(f"  Claim URL:  {agent.get('claim_url', 'N/A')}")
        print(f"  Verify:     {agent.get('verification_code', 'N/A')}")
        print("\n⚠️  IMPORTANT:")
        print("  1. Save the API key to your .env file:")
        print(f"     MOLTBOOK_API_KEY={agent.get('api_key', '')}")
        print("  2. Send the claim URL to your human")
        print("  3. They need to tweet the verification code")
        print("=" * 50)
    else:
        print("❌ Registration failed. Check logs for details.")

    return result


async def cmd_generate_8004():
    """Generate ERC-8004 registration file."""
    log.info("📋 Generating ERC-8004 registration file...")

    # Try to get GitHub repo URL from env
    github_url = os.getenv(
        "GITHUB_REPO_URL",
        "https://github.com/YOUR_USERNAME/moltbook-8004-bridge-agent"
    )

    reg = generate_registration_file(
        name="MoltBridgeAgent",
        description=(
            "Autonomous intelligence agent that monitors Moltbook AI agent "
            "social network, performs trend analysis, sentiment analysis, "
            "and topic clustering. Publishes structured reports about what "
            "AI agents are discussing and building. Bridges Moltbook data "
            "to the ERC-8004 trustless agent ecosystem."
        ),
        web_endpoint=github_url,
    )

    filepath = save_registration_file(reg)

    print("\n" + "=" * 60)
    print("📋 ERC-8004 REGISTRATION FILE GENERATED")
    print("=" * 60)
    print(f"\nFile: {filepath}")
    print(f"\nContent:\n{json.dumps(reg, indent=2)}")
    print("\n" + "=" * 60)
    print("NEXT STEPS:")
    print("=" * 60)
    print("""
  Option A — Quick (HTTPS hosting via GitHub):
    1. Commit agent_registration.json to your repo
    2. Use the raw GitHub URL as your agentURI
    3. Set ETH_PRIVATE_KEY in .env
    4. Run: python src/main.py --register-8004 <registry_address>

  Option B — Decentralized (IPFS via Filecoin Pin):
    1. Install: npm install -g @filecoin-pin/cli
    2. Upload: filecoin-pin upload data/agent_registration.json
    3. Use the IPFS CID as your agentURI
    4. Run: python src/main.py --register-8004 <registry_address>

  Registry addresses (check 8004.org for latest):
    - Base Sepolia (testnet): Check 8004.org/build
    - Ethereum Mainnet: Check eips.ethereum.org/EIPS/eip-8004
""")

    return reg


async def cmd_register_8004(registry_address: str):
    """Register agent on ERC-8004 Identity Registry."""
    log.info(f"📡 Registering on ERC-8004 (registry: {registry_address})...")

    github_url = os.getenv(
        "GITHUB_REPO_URL",
        "https://github.com/YOUR_USERNAME/moltbook-8004-bridge-agent"
    )
    agent_uri = f"{github_url}/raw/main/data/agent_registration.json"

    result = await register_on_chain(agent_uri, registry_address)

    if "error" in result:
        print(f"\n❌ Registration failed: {result['error']}")
        if "manual_steps" in result:
            print("\nManual steps:")
            for step in result["manual_steps"]:
                print(f"  {step}")
    else:
        print(f"\n✅ Agent registered on-chain!")
        print(f"   Agent ID: {result.get('agent_id')}")
        print(f"   TX Hash:  {result.get('tx_hash')}")
        print(f"   Chain:    {result.get('chain_id')}")
        print(f"   Block:    {result.get('block')}")

        set_state("erc8004_registration", {
            "agent_id": result.get("agent_id"),
            "tx_hash": result.get("tx_hash"),
            "chain_id": result.get("chain_id"),
        })

    return result


async def cmd_status():
    """Check agent status on both platforms."""
    print("\n" + "=" * 60)
    print("📊 MOLTBRIDGE AGENT STATUS")
    print("=" * 60)

    # Moltbook status
    api_key = os.getenv("MOLTBOOK_API_KEY", "")
    if api_key:
        status = await check_status()
        me = await get_me()
        print(f"\n🦞 Moltbook:")
        print(f"   Status: {status}")
        if me:
            print(f"   Agent: {json.dumps(me, indent=4)}")
    else:
        print("\n🦞 Moltbook: NOT REGISTERED (set MOLTBOOK_API_KEY)")

    # ERC-8004 status
    erc_reg = get_state("erc8004_registration")
    if erc_reg:
        print(f"\n⛓️  ERC-8004:")
        print(f"   Agent ID: {erc_reg.get('agent_id', 'N/A')}")
        print(f"   Chain:    {erc_reg.get('chain_id', 'N/A')}")
        print(f"   TX:       {erc_reg.get('tx_hash', 'N/A')}")
    else:
        print("\n⛓️  ERC-8004: NOT REGISTERED (run --generate-8004 first)")

    # Auto-reply stats
    replied_count = len(get_state("replied_comment_ids", []))
    print(f"\n💬 Auto-reply:")
    print(f"   Total replies tracked: {replied_count}")

    # Last run
    last_run = get_state("last_full_run")
    if last_run:
        print(f"\n📊 Last Run:")
        print(f"   Time:      {last_run.get('timestamp', 'N/A')}")
        print(f"   Posts:     {last_run.get('posts_analyzed', 'N/A')}")
        print(f"   Top Topic: {last_run.get('top_keyword', 'N/A')}")
        print(f"   Published: {'✅' if last_run.get('published') else '❌'}")
    else:
        print("\n📊 No runs yet. Use --full to start.")

    print("=" * 60)


async def cmd_heartbeat():
    """Run a heartbeat cycle (scrape + analyze + publish + reply if enough time passed)."""
    log.info("💓 Heartbeat cycle starting...")

    from datetime import datetime, timedelta

    last_scrape = get_state("last_scrape_time")
    min_interval = timedelta(hours=4)

    if last_scrape:
        try:
            last_dt = datetime.fromisoformat(last_scrape)
            if datetime.now() - last_dt < min_interval:
                remaining = min_interval - (datetime.now() - last_dt)
                log.info(
                    f"⏳ Too soon since last scrape ({last_scrape}). "
                    f"Next run in {remaining}. Skipping."
                )
                # Still do auto-reply even if skipping scrape
                log.info("💬 Running auto-reply anyway...")
                await auto_reply(max_replies=3, dry_run=False)
                return
        except (ValueError, TypeError):
            pass

    # Run full pipeline
    await cmd_full()
    set_state("last_scrape_time", datetime.now().isoformat())
    log.info("💓 Heartbeat complete!")


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="MoltBridge Agent — Moltbook ↔ ERC-8004 Bridge",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python src/main.py --full                 # Full pipeline (scrape+analyze+publish+reply)
  python src/main.py --scrape               # Just scrape
  python src/main.py --analyze              # Analyze latest data
  python src/main.py --report               # Generate report
  python src/main.py --publish              # Publish to Moltbook
  python src/main.py --reply                # Auto-reply to comments
  python src/main.py --reply-dry            # Preview replies (no posting)
    python src/main.py --hot-post             # Publish hot post summary
  python src/main.py --register-moltbook    # Register on Moltbook
  python src/main.py --generate-8004        # Generate ERC-8004 file
  python src/main.py --register-8004 ADDR   # Register on ERC-8004
  python src/main.py --heartbeat            # Run heartbeat cycle
    python src/main.py --sample-report        # Sample report with expanded limits
  python src/main.py --status               # Show agent status
        """,
    )

    parser.add_argument("--scrape", action="store_true", help="Scrape Moltbook")
    parser.add_argument("--analyze", action="store_true", help="Analyze latest scrape")
    parser.add_argument("--report", action="store_true", help="Generate daily report")
    parser.add_argument("--publish", action="store_true", help="Publish report to Moltbook")
    parser.add_argument("--reply", action="store_true", help="Auto-reply to comments")
    parser.add_argument("--reply-dry", action="store_true", help="Preview replies (dry run)")
    parser.add_argument("--hot-post", action="store_true", help="Publish hot post summary")
    parser.add_argument("--hot-post-dry", action="store_true", help="Preview hot post summary")
    parser.add_argument("--engage", action="store_true", help="Comment on trending posts")
    parser.add_argument("--engage-dry", action="store_true", help="Preview engagement (dry run)")
    parser.add_argument("--full", action="store_true", help="Full pipeline")
    parser.add_argument("--register-moltbook", action="store_true", help="Register on Moltbook")
    parser.add_argument("--generate-8004", action="store_true", help="Generate ERC-8004 reg file")
    parser.add_argument("--register-8004", type=str, metavar="ADDR", help="Register on ERC-8004")
    parser.add_argument("--status", action="store_true", help="Show agent status")
    parser.add_argument("--heartbeat", action="store_true", help="Run heartbeat cycle")
    parser.add_argument("--sample-report", action="store_true", help="Generate sample report")

    args = parser.parse_args()

    if not any(vars(args).values()):
        parser.print_help()
        return

    if args.scrape:
        asyncio.run(cmd_scrape())
    elif args.analyze:
        asyncio.run(cmd_analyze())
    elif args.report:
        asyncio.run(cmd_report())
    elif args.publish:
        asyncio.run(cmd_publish())
    elif args.reply:
        asyncio.run(cmd_reply(dry_run=False))
    elif args.reply_dry:
        asyncio.run(cmd_reply(dry_run=True))
    elif args.hot_post or args.hot_post_dry:
        asyncio.run(cmd_hot_post(dry_run=bool(args.hot_post_dry)))
    elif args.engage or args.engage_dry:
        dry = getattr(args, 'engage_dry', False)
        async def _engage():
            analysis = load_latest("analyzed", "analysis")
            sentiment = analysis.get("sentiment", {}) if analysis else {}
            if not analysis:
                log.error("No analysis data. Run --full first.")
                return
            await proactive_comment(analysis, sentiment, max_comments=1, dry_run=dry)
        asyncio.run(_engage())
    elif args.full:
        asyncio.run(cmd_full())
    elif args.register_moltbook:
        asyncio.run(cmd_register_moltbook())
    elif args.generate_8004:
        asyncio.run(cmd_generate_8004())
    elif args.register_8004:
        asyncio.run(cmd_register_8004(args.register_8004))
    elif args.status:
        asyncio.run(cmd_status())
    elif args.heartbeat:
        asyncio.run(cmd_heartbeat())
    elif args.sample_report:
        asyncio.run(cmd_sample_report())


if __name__ == "__main__":
    main()
