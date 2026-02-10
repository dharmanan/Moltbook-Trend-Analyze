"""LLM client for generating professional replies."""

import json
import os
from typing import Any

import httpx
from dotenv import load_dotenv

from utils import log

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))


_SETTINGS_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "config", "settings.json")
with open(_SETTINGS_PATH, "r") as f:
    _settings = json.load(f)

_LLM_SETTINGS = _settings.get("llm", {})


def _is_enabled() -> bool:
    return bool(_LLM_SETTINGS.get("enabled", False))


def _get_provider() -> str:
    return str(_LLM_SETTINGS.get("provider", "groq")).lower()


def _get_model() -> str:
    return str(_LLM_SETTINGS.get("model", "llama-3.3-70b-versatile"))


def _get_temperature() -> float:
    return float(_LLM_SETTINGS.get("temperature", 0.4))


def _get_max_tokens() -> int:
    return int(_LLM_SETTINGS.get("max_tokens", 140))


def _get_groq_key() -> str:
    return os.getenv("GROQ_API_KEY", "")


def _system_prompt() -> str:
    return (
        "You are MoltBridgeAgent, a professional analyst responding on Moltbook. "
        "Write a concise, helpful reply in 1-2 sentences. "
        "No emojis, no hashtags, no salesy tone. "
        "Avoid repeating phrasing and do not mention being an AI model."
    )


def _build_user_prompt(kind: str, context: dict[str, Any]) -> str:
    if kind == "auto_reply":
        return (
            "Reply to the user comment in a professional, constructive tone.\n"
            f"Post title: {context.get('post_title', '')}\n"
            f"Comment: {context.get('comment_text', '')}\n"
            f"Top keyword: {context.get('top_keyword', '')}\n"
        )
    if kind == "proactive_comment":
        return (
            "Write a concise comment that adds value and references the post topic.\n"
            f"Post title: {context.get('post_title', '')}\n"
            f"Post content: {context.get('post_content', '')}\n"
            f"Topic: {context.get('topic', '')}\n"
            f"Top keyword: {context.get('top_keyword', '')}\n"
        )
    if kind == "report_summary":
        return (
            "Write a single-sentence executive summary of this report. "
            "Be professional and concise.\n"
            f"Top keywords: {context.get('top_keywords', '')}\n"
            f"Rising trends: {context.get('rising_trends', '')}\n"
            f"Sentiment: {context.get('sentiment', '')}\n"
            f"Posts analyzed: {context.get('posts_analyzed', '')}\n"
            f"Unique agents: {context.get('unique_agents', '')}\n"
        )
    return "Write a concise, professional reply."


async def generate_llm_reply(kind: str, context: dict[str, Any]) -> str | None:
    if not _is_enabled():
        return None

    provider = _get_provider()
    if provider != "groq":
        log.warning(f"LLM provider not supported: {provider}")
        return None

    api_key = _get_groq_key()
    if not api_key:
        log.warning("GROQ_API_KEY not set. Falling back to templates.")
        return None

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": _get_model(),
        "temperature": _get_temperature(),
        "max_tokens": _get_max_tokens(),
        "messages": [
            {"role": "system", "content": _system_prompt()},
            {"role": "user", "content": _build_user_prompt(kind, context)},
        ],
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=headers, json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        log.warning(f"LLM HTTP {e.response.status_code}: {e.response.text[:200]}")
        return None
    except Exception as e:
        log.warning(f"LLM request failed: {e}")
        return None

    try:
        content = data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError):
        return None

    if not content:
        return None

    # Simple safety: keep to 2 sentences max (1 for report_summary)
    sentences = [s for s in content.split(".") if s.strip()]
    max_sentences = 1 if kind == "report_summary" else 2
    if len(sentences) > max_sentences:
        content = ".".join(sentences[:max_sentences]).strip()
        if not content.endswith("."):
            content += "."

    return content
