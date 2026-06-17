from __future__ import annotations
from pathlib import Path
from typing import Optional
from ctk.base import JsonlFileSessionAdapter
from ctk.model import Turn
from ctk.text import extract_text, clean

_ROLE_MAP = {
    "user": "user",
    "human": "user",
    "assistant": "assistant",
    "model": "assistant",
    "ai": "assistant",
}


def _content_of(rec):
    """OpenCode message records vary; try common content fields."""
    for key in ("content", "text", "parts", "message"):
        if key in rec:
            return rec[key]
    return None


class OpenCodeAdapter(JsonlFileSessionAdapter):
    """OpenCode: JSONL under ~/.local/share/opencode/storage/**/*.jsonl.

    The user-data store is JSONL (not SQLite), so this subclasses the JSONL
    base: one file == one session, each line a record. Only user/assistant
    records carry transcript text; other event lines are dropped. Text is
    cleaned via clean(extract_text(...))."""

    name = "opencode"

    def session_files(self) -> list:
        base = Path.home() / ".local" / "share" / "opencode" / "storage"
        if not base.exists():
            return []
        return sorted(base.glob("**/*.jsonl"))

    def turn_of(self, rec) -> Optional[Turn]:
        if not isinstance(rec, dict):
            return None
        role = _ROLE_MAP.get(str(rec.get("role")).lower())
        if role is None:
            return None
        text = clean(extract_text(_content_of(rec)))
        if not text.strip():
            return None
        return Turn(role=role, text=text)

    def project_path(self, path, first) -> Optional[str]:
        return (first or {}).get("cwd") or (first or {}).get("directory")

    def started_at(self, path, first) -> Optional[str]:
        return (first or {}).get("timestamp") or (first or {}).get("time")
