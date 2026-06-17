from __future__ import annotations
from pathlib import Path
from typing import Optional
from ctk.base import JsonlFileSessionAdapter
from ctk.model import Turn
from ctk.text import extract_text, clean

# Assumed line shape: {"role": "user"|"assistant", "content": [{"type":"text","text"}] | <str>, ...};
# non-message lines (role "tool"/system, etc.) are dropped.

_ROLE_MAP = {"user": "user", "human": "user", "assistant": "assistant", "model": "assistant", "ai": "assistant"}


def _content_of(rec):
    for key in ("content", "text", "message"):
        if key in rec:
            return rec[key]
    return None


class FactoryAdapter(JsonlFileSessionAdapter):
    """Factory (Droid): ~/.factory/sessions/**/*.jsonl. One file == one session."""

    name = "factory"

    def session_files(self) -> list:
        base = Path.home() / ".factory" / "sessions"
        if not base.exists():
            return []
        return sorted(base.glob("**/*.jsonl"))

    def turn_of(self, rec) -> Optional[Turn]:
        role = _ROLE_MAP.get(rec.get("role"))
        if role is None:
            return None
        text = clean(extract_text(_content_of(rec)))
        if not text.strip():
            return None
        return Turn(role=role, text=text)

    def project_path(self, path, first) -> Optional[str]:
        return (first or {}).get("cwd")

    def started_at(self, path, first) -> Optional[str]:
        return (first or {}).get("timestamp")
