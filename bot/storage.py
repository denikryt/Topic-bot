"""Storage helpers for the topics bot.

This module centralizes safe JSON reading and writing for the guild registry
and per-guild topic lists. All operations are asynchronous-friendly but use
standard file IO since the dataset is small.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

BASE_DIR = Path(__file__).resolve().parent
TOPICS_DIR = BASE_DIR / "topics"
GUILDS_FILE = BASE_DIR / "guilds.json"


def _atomic_write(path: Path, data: Any) -> None:
    """Write JSON data atomically to the given path.

    Uses a temporary file in the same directory then replaces the destination to
    reduce risk of corruption if the process exits mid-write.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
    tmp_path.replace(path)


def _safe_read(path: Path, default: Any) -> Any:
    """Safely read JSON content, returning *default* if missing or invalid."""
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        return default
    except json.JSONDecodeError:
        return default


def load_guild_registry() -> Dict[str, Dict[str, str]]:
    """Return the guilds registry, falling back to an empty mapping."""
    return _safe_read(GUILDS_FILE, default={})


def save_guild_registry(registry: Dict[str, Dict[str, str]]) -> None:
    """Persist the guilds registry to disk."""
    _atomic_write(GUILDS_FILE, registry)


def ensure_topics_file(guild_id: int) -> Path:
    """Ensure a topics file exists for *guild_id* and return its path."""
    path = TOPICS_DIR / f"{guild_id}.json"
    if not path.exists():
        _atomic_write(path, [])
    return path


def load_topics(guild_id: int) -> List[Dict[str, Any]]:
    """Load the topics list for *guild_id*, creating the file if missing."""
    path = ensure_topics_file(guild_id)
    return _safe_read(path, default=[])


def save_topics(guild_id: int, topics: List[Dict[str, Any]]) -> None:
    """Persist the topics list for *guild_id*."""
    path = ensure_topics_file(guild_id)
    _atomic_write(path, topics)


def delete_topics_file(guild_id: int) -> None:
    """Delete the topics file for *guild_id* if it exists."""
    path = TOPICS_DIR / f"{guild_id}.json"
    try:
        path.unlink()
    except FileNotFoundError:
        return
