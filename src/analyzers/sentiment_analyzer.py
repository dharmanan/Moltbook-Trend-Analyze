"""Sentiment analyzer — lightweight keyword-based sentiment scoring."""

import json
import os
import re
from collections import Counter

from utils import log

# Load config
_settings_path = os.path.join(os.path.dirname(__file__), "..", "..", "config", "settings.json")
with open(_settings_path, "r") as f:
    _cfg = json.load(f)["analysis"]["sentiment_keywords"]

POS_WORDS = set(_cfg["positive"])
NEG_WORDS = set(_cfg["negative"])


def _clean_text(text: str) -> str:
    """Basic text cleaning."""
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"[^a-zA-Z\s]", " ", text)
    return text.lower()


def score_text(text: str) -> dict:
    """
    Score a piece of text for sentiment.

    Returns: {"positive": int, "negative": int, "score": float, "label": str}
    """
    words = _clean_text(text).split()
    pos_count = sum(1 for w in words if w in POS_WORDS)
    neg_count = sum(1 for w in words if w in NEG_WORDS)
    total = pos_count + neg_count

    if total == 0:
        return {"positive": 0, "negative": 0, "score": 0.0, "label": "neutral"}

    score = (pos_count - neg_count) / total
    if score > 0.2:
        label = "positive"
    elif score < -0.2:
        label = "negative"
    else:
        label = "neutral"

    return {
        "positive": pos_count,
        "negative": neg_count,
        "score": round(score, 3),
        "label": label,
    }


def analyze_sentiment(posts: list[dict]) -> dict:
    """
    Analyze sentiment across all posts.

    Returns:
    {
        "distribution": {"positive": N, "negative": N, "neutral": N},
        "percentages": {"positive": X%, "negative": X%, "neutral": X%},
        "avg_score": float,
        "top_positive_posts": [...],
        "top_negative_posts": [...],
        "positive_keywords": [...],
        "negative_keywords": [...]
    }
    """
    log.info("💭 Running sentiment analysis...")

    results = []
    pos_keywords_all = []
    neg_keywords_all = []

    for post in posts:
        text_parts = []
        for key in ("title", "content", "body", "text"):
            val = post.get(key, "")
            if val:
                text_parts.append(str(val))
        full_text = " ".join(text_parts)

        sent = score_text(full_text)
        sent["post_title"] = post.get("title", "")[:80]
        sent["post_id"] = post.get("id") or post.get("_id", "")
        results.append(sent)

        # Collect sentiment keywords found
        words = _clean_text(full_text).split()
        pos_keywords_all.extend([w for w in words if w in POS_WORDS])
        neg_keywords_all.extend([w for w in words if w in NEG_WORDS])

    # Distribution
    dist = Counter(r["label"] for r in results)
    total = len(results) or 1
    pcts = {k: round(v / total * 100, 1) for k, v in dist.items()}

    # Average score
    scores = [r["score"] for r in results]
    avg_score = round(sum(scores) / max(len(scores), 1), 3)

    # Top posts
    sorted_by_score = sorted(results, key=lambda x: x["score"])
    top_positive = [
        {"title": r["post_title"], "score": r["score"]}
        for r in sorted_by_score[-5:][::-1]
        if r["score"] > 0
    ]
    top_negative = [
        {"title": r["post_title"], "score": r["score"]}
        for r in sorted_by_score[:5]
        if r["score"] < 0
    ]

    # Top sentiment keywords
    pos_kw_counts = Counter(pos_keywords_all).most_common(10)
    neg_kw_counts = Counter(neg_keywords_all).most_common(10)

    analysis = {
        "distribution": dict(dist),
        "percentages": pcts,
        "avg_score": avg_score,
        "total_analyzed": len(results),
        "top_positive_posts": top_positive,
        "top_negative_posts": top_negative,
        "positive_keywords": [{"word": w, "count": c} for w, c in pos_kw_counts],
        "negative_keywords": [{"word": w, "count": c} for w, c in neg_kw_counts],
    }

    log.info(
        f"  → Sentiment: {pcts.get('positive', 0)}% pos | "
        f"{pcts.get('neutral', 0)}% neutral | "
        f"{pcts.get('negative', 0)}% neg"
    )

    return analysis
