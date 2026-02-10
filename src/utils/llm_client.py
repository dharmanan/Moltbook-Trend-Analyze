"""LLM client for generating professional replies."""

import json
import os
import re
from datetime import datetime
from typing import Any

import httpx
from dotenv import load_dotenv

from utils import log

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))


_SETTINGS_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "config", "settings.json")
with open(_SETTINGS_PATH, "r") as f:
    _settings = json.load(f)

_LLM_SETTINGS = _settings.get("llm", {})

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
_HISTORY_PATH = os.path.join(_DATA_DIR, "llm_history.jsonl")


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


def _memory_settings() -> dict:
    return _LLM_SETTINGS.get("memory", {})


def _memory_enabled() -> bool:
    return bool(_memory_settings().get("enabled", False))


def _memory_max_items() -> int:
    return int(_memory_settings().get("max_items", 500))


def _memory_examples() -> int:
    return int(_memory_settings().get("examples", 2))


def _ensure_history_dir() -> None:
    os.makedirs(_DATA_DIR, exist_ok=True)


def _context_text(context: dict[str, Any]) -> str:
    parts = []
    for key in sorted(context.keys()):
        value = context.get(key, "")
        if value:
            parts.append(f"{key}: {value}")
    return " | ".join(parts)


def _trim_context(context: dict[str, Any], limit: int = 500) -> dict[str, Any]:
    trimmed: dict[str, Any] = {}
    for key, value in context.items():
        if isinstance(value, str) and len(value) > limit:
            trimmed[key] = value[:limit]
        else:
            trimmed[key] = value
    return trimmed


def _tokenize(text: str) -> set[str]:
    tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{2,}", text.lower())
    return set(tokens)


def _load_history() -> list[dict[str, Any]]:
    if not _memory_enabled() or not os.path.exists(_HISTORY_PATH):
        return []
    items: list[dict[str, Any]] = []
    with open(_HISTORY_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return items[-_memory_max_items():]


def _write_history(items: list[dict[str, Any]]) -> None:
    _ensure_history_dir()
    with open(_HISTORY_PATH, "w", encoding="utf-8") as f:
        for item in items[-_memory_max_items():]:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


def _record_history(kind: str, context: dict[str, Any], response: str) -> None:
    if not _memory_enabled():
        return
    items = _load_history()
    safe_context = _trim_context(context)
    entry = {
        "ts": datetime.utcnow().isoformat() + "Z",
        "kind": kind,
        "context": safe_context,
        "context_text": _context_text(safe_context),
        "response": response,
    }
    items.append(entry)
    _write_history(items)


def _select_examples(kind: str, context: dict[str, Any]) -> list[dict[str, Any]]:
    if not _memory_enabled():
        return []
    items = [i for i in _load_history() if i.get("kind") == kind]
    if not items:
        return []

    target_tokens = _tokenize(_context_text(context))
    if not target_tokens:
        return []

    scored: list[tuple[int, dict[str, Any]]] = []
    for item in items:
        item_tokens = _tokenize(item.get("context_text", ""))
        if not item_tokens:
            continue
        score = len(target_tokens & item_tokens)
        if score > 0:
            scored.append((score, item))

    scored.sort(key=lambda x: (-x[0], x[1].get("ts", "")))
    top_n = _memory_examples()
    return [item for _, item in scored[:top_n]]


def _format_examples(examples: list[dict[str, Any]]) -> str:
    if not examples:
        return ""
    lines = ["Reference examples (style only):"]
    for ex in examples:
        ctx = (ex.get("context_text") or "")[:200]
        resp = (ex.get("response") or "")[:200]
        lines.append(f"- Input: {ctx}")
        lines.append(f"  Output: {resp}")
    return "\n".join(lines)


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
    if kind == "report_teaser":
        return (
            "Write a short teaser post (1-2 sentences) that invites readers to the full report. "
            "Keep it informative and non-spammy.\n"
            f"Report title: {context.get('report_title', '')}\n"
            f"Top keywords: {context.get('top_keywords', '')}\n"
            f"Sentiment: {context.get('sentiment', '')}\n"
            f"Report URL: {context.get('report_url', '')}\n"
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
    user_prompt = _build_user_prompt(kind, context)
    examples = _format_examples(_select_examples(kind, context))
    if examples:
        user_prompt = f"{user_prompt}\n{examples}"

    payload = {
        "model": _get_model(),
        "temperature": _get_temperature(),
        "max_tokens": _get_max_tokens(),
        "messages": [
            {"role": "system", "content": _system_prompt()},
            {"role": "user", "content": user_prompt},
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

    _record_history(kind, context, content)
    log.info(f"LLM reply generated ({kind})")
    return content
