"""JSON-based storage for scraped data, analysis results, and reports."""

import json
import os
from datetime import datetime
from typing import Any


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")


def _ensure_dir(subdir: str) -> str:
    """Ensure a data subdirectory exists and return its path."""
    path = os.path.join(DATA_DIR, subdir)
    os.makedirs(path, exist_ok=True)
    return path


def save_raw(data: dict, label: str = "scrape") -> str:
    """Save raw scraped data with timestamp."""
    dir_path = _ensure_dir("raw")
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    filename = f"{label}_{timestamp}.json"
    filepath = os.path.join(dir_path, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)

    return filepath


def save_analysis(data: dict, label: str = "analysis") -> str:
    """Save analysis results."""
    dir_path = _ensure_dir("analyzed")
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    filename = f"{label}_{timestamp}.json"
    filepath = os.path.join(dir_path, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)

    return filepath


def save_report(content: str, label: str = "report") -> str:
    """Save a markdown report."""
    dir_path = _ensure_dir("reports")
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    filename = f"{label}_{timestamp}.md"
    filepath = os.path.join(dir_path, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    return filepath


def load_latest(subdir: str, prefix: str = "") -> dict | None:
    """Load the most recent file from a subdirectory."""
    dir_path = os.path.join(DATA_DIR, subdir)
    if not os.path.exists(dir_path):
        return None

    files = sorted(
        [f for f in os.listdir(dir_path) if f.startswith(prefix)],
        reverse=True,
    )
    if not files:
        return None

    filepath = os.path.join(dir_path, files[0])
    with open(filepath, "r", encoding="utf-8") as f:
        if filepath.endswith(".json"):
            return json.load(f)
        return {"content": f.read(), "filename": files[0]}


def load_previous(subdir: str, prefix: str = "", skip: int = 1) -> dict | None:
    """Load a previous file (for comparison). skip=1 means second most recent."""
    dir_path = os.path.join(DATA_DIR, subdir)
    if not os.path.exists(dir_path):
        return None

    files = sorted(
        [f for f in os.listdir(dir_path) if f.startswith(prefix)],
        reverse=True,
    )
    if len(files) <= skip:
        return None

    filepath = os.path.join(dir_path, files[skip])
    with open(filepath, "r", encoding="utf-8") as f:
        if filepath.endswith(".json"):
            return json.load(f)
        return {"content": f.read(), "filename": files[skip]}


def get_state(key: str, default: Any = None) -> Any:
    """Get a persistent state value."""
    state_file = os.path.join(_ensure_dir("state"), "agent_state.json")
    if not os.path.exists(state_file):
        return default

    with open(state_file, "r") as f:
        state = json.load(f)
    return state.get(key, default)


def set_state(key: str, value: Any) -> None:
    """Set a persistent state value."""
    state_file = os.path.join(_ensure_dir("state"), "agent_state.json")

    state = {}
    if os.path.exists(state_file):
        with open(state_file, "r") as f:
            state = json.load(f)

    state[key] = value
    with open(state_file, "w") as f:
        json.dump(state, f, indent=2, default=str)
