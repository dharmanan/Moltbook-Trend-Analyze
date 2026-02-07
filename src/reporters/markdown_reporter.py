"""Markdown report generator — produces human/agent-readable reports from analysis."""

from datetime import datetime

from utils import log, save_report


def generate_daily_report(analysis: dict, sentiment: dict) -> str:
    """
    Generate a daily Moltbook trend report in Markdown.

    Args:
        analysis: Output from run_full_analysis()
        sentiment: Output from analyze_sentiment()

    Returns:
        Markdown string
    """
    log.info("📝 Generating daily report...")
    now = datetime.now()

    # Header
    lines = [
        f"# 🦞 Moltbook Ekosistem Raporu — {now.strftime('%d %B %Y')}",
        "",
        f"> Otomatik üretim: MoltBridge Agent | {now.strftime('%H:%M UTC')}",
        f"> Analiz edilen post sayısı: {analysis.get('total_unique_posts', 0)}",
        "",
        "---",
        "",
    ]

    # Top Keywords
    lines.append("## 📈 Trending Konular")
    lines.append("")
    keywords = analysis.get("keywords", [])[:10]
    for i, kw in enumerate(keywords, 1):
        lines.append(f"{i}. **{kw['keyword']}** — {kw['count']} mention ({kw['frequency']*100:.1f}%)")
    lines.append("")

    # Bigram Topics
    bigrams = analysis.get("bigram_topics", [])[:8]
    if bigrams:
        lines.append("## 🔗 İlişkili Konular (Bigrams)")
        lines.append("")
        for bg in bigrams:
            lines.append(f"- **{bg['topic']}** ({bg['count']}x)")
        lines.append("")

    # Submolt Activity
    lines.append("## 🏘️ En Aktif Submolt'lar")
    lines.append("")
    submolts = analysis.get("submolt_activity", [])[:6]
    lines.append("| Submolt | Post | Upvote | Yorum | Engagement |")
    lines.append("|---------|------|--------|-------|------------|")
    for s in submolts:
        lines.append(
            f"| m/{s['submolt']} | {s['post_count']} | "
            f"{s['total_upvotes']} | {s['total_comments']} | "
            f"{s['engagement_score']} |"
        )
    lines.append("")

    # Sentiment
    lines.append("## 💭 Sentiment Analizi")
    lines.append("")
    pcts = sentiment.get("percentages", {})
    lines.append(f"- ✅ Pozitif: **{pcts.get('positive', 0)}%**")
    lines.append(f"- ⚪ Nötr: **{pcts.get('neutral', 0)}%**")
    lines.append(f"- ❌ Negatif: **{pcts.get('negative', 0)}%**")
    lines.append(f"- Ortalama skor: **{sentiment.get('avg_score', 0)}**")
    lines.append("")

    # Positive keywords
    pos_kws = sentiment.get("positive_keywords", [])[:5]
    if pos_kws:
        lines.append("**En çok kullanılan pozitif kelimeler:**")
        for pk in pos_kws:
            lines.append(f"  - {pk['word']} ({pk['count']}x)")
        lines.append("")

    # Negative keywords
    neg_kws = sentiment.get("negative_keywords", [])[:5]
    if neg_kws:
        lines.append("**En çok kullanılan negatif kelimeler:**")
        for nk in neg_kws:
            lines.append(f"  - {nk['word']} ({nk['count']}x)")
        lines.append("")

    # Trend Changes
    changes = analysis.get("trend_changes", [])
    if changes:
        lines.append("## 🌊 Trend Değişimleri (vs Önceki Dönem)")
        lines.append("")
        rising = [c for c in changes if "rising" in c["trend"] or "new" in c["trend"]][:5]
        falling = [c for c in changes if "falling" in c["trend"]][:5]

        if rising:
            lines.append("**Yükselen:**")
            for r in rising:
                lines.append(
                    f"  - {r['trend']} **{r['keyword']}** "
                    f"({r['previous_count']} → {r['current_count']}, "
                    f"+{r['change_pct']}%)"
                )
            lines.append("")

        if falling:
            lines.append("**Düşen:**")
            for f_item in falling:
                lines.append(
                    f"  - {f_item['trend']} **{f_item['keyword']}** "
                    f"({f_item['previous_count']} → {f_item['current_count']}, "
                    f"{f_item['change_pct']}%)"
                )
            lines.append("")

    # Agent Patterns
    patterns = analysis.get("agent_patterns", {})
    if patterns:
        lines.append("## 🤖 Agent Davranış Kalıpları")
        lines.append("")
        lines.append(f"- Benzersiz agent sayısı: **{patterns.get('unique_agents', 0)}**")
        lines.append(f"- Agent başına ortalama post: **{patterns.get('avg_posts_per_agent', 0)}**")
        lines.append(f"- 3+ post yapan aktif agentlar: **{patterns.get('prolific_agents', 0)}**")
        lines.append(f"- Tek seferlik paylaşımcılar: **{patterns.get('one_time_posters', 0)}**")
        lines.append("")

        top_posters = patterns.get("top_posters", [])[:5]
        if top_posters:
            lines.append("**En aktif agentlar:**")
            for tp in top_posters:
                lines.append(
                    f"  - @{tp['name']} — {tp['posts']} post, "
                    f"{tp['upvotes']} upvote"
                )
            lines.append("")

    # Footer
    lines.extend([
        "---",
        "",
        "*Bu rapor MoltBridge Agent tarafından otomatik üretilmiştir.*",
        "*Veriler Moltbook API'sinden çekilmiş ve analiz edilmiştir.*",
        f"*Rapor zamanı: {now.isoformat()}*",
    ])

    report = "\n".join(lines)

    # Save
    filepath = save_report(report, "daily_report")
    log.info(f"✅ Daily report generated! Saved to {filepath}")

    return report


def generate_moltbook_post(analysis: dict, sentiment: dict) -> tuple[str, str]:
    """
    Generate a concise post suitable for sharing on Moltbook.

    Returns: (title, content)
    """
    now = datetime.now()
    keywords = analysis.get("keywords", [])[:5]
    pcts = sentiment.get("percentages", {})
    submolts = analysis.get("submolt_activity", [])[:3]
    top_agents = analysis.get("agent_patterns", {}).get("top_posters", [])[:3]

    title = f"📊 Moltbook Trend Report — {now.strftime('%b %d')}"

    kw_list = ", ".join(kw["keyword"] for kw in keywords)
    content = (
        f"**Today's Top Topics:** {kw_list}\n\n"
        f"**Sentiment:** {pcts.get('positive', 0)}% positive | "
        f"{pcts.get('neutral', 0)}% neutral | "
        f"{pcts.get('negative', 0)}% negative\n\n"
        f"**Unique Agents Analyzed:** {analysis.get('agent_patterns', {}).get('unique_agents', '?')}\n"
        f"**Posts Analyzed:** {analysis.get('total_unique_posts', '?')}\n\n"
    )

    if submolts:
        sm_list = ", ".join(f"m/{s['submolt']} ({s['post_count']})" for s in submolts)
        content += f"**Active Submolts:** {sm_list}\n\n"

    if top_agents:
        agent_list = ", ".join(f"@{a['name']} ({a['posts']})" for a in top_agents)
        content += f"**Top Agents:** {agent_list}\n\n"

    # Add rising trends if available
    changes = analysis.get("trend_changes", [])
    rising = [c for c in changes if "rising" in c["trend"]][:3]
    if rising:
        content += "**Rising Trends:**\n"
        for r in rising:
            content += f"  📈 {r['keyword']} (+{r['change_pct']}%)\n"
        content += "\n"

    content += (
        "---\n"
        "*Generated by MoltBridge Agent — "
        "bridging Moltbook intelligence to the agent ecosystem.*"
    )

    return title, content
