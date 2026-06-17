from __future__ import annotations
from pathlib import Path
from typing import Optional
from ctk.base import JsonlFileSessionAdapter
from ctk.model import Turn
from ctk.text import extract_text, clean

# Assumed line shape: {"role": "human"|"ai"|"user"|"assistant", "message": <str> | [{"type":"text","text"}], ...};
# non-message lines (role "event", etc.) are dropped.

_ROLE_MAP = {"user": "user", "human": "user", "assistant": "assistant", "model": "assistant", "ai": "assistant"}


def _content_of(rec):
    for key in ("message", "content", "text"):
        if key in rec:
            return rec[key]
    return None


class OpenClawAdapter(JsonlFileSessionAdapter):
    """OpenClaw: ~/.openclaw/agents/<agent>/sessions/<id>.jsonl. One file == one session."""

    name = "openclaw"

    def session_files(self) -> list:
        base = Path.home() / ".openclaw" / "agents"
        if not base.exists():
            return []
        return sorted(base.glob("*/sessions/*.jsonl"))

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
