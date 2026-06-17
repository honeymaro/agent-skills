from __future__ import annotations
from pathlib import Path
from typing import Optional
from ctk.base import JsonlFileSessionAdapter
from ctk.model import Turn
from ctk.text import extract_text, clean

# Assumed line shape: {"role": "user"|"model"|"assistant", "text": <str> | [{"type":"text","text"}], ...};
# non-message lines (those without a user/assistant role, e.g. tool_result) are dropped.

_ROLE_MAP = {"user": "user", "human": "user", "assistant": "assistant", "model": "assistant", "ai": "assistant"}


def _content_of(rec):
    for key in ("text", "content", "message"):
        if key in rec:
            return rec[key]
    return None


class KimiAdapter(JsonlFileSessionAdapter):
    """Kimi Code: ~/.kimi/sessions/<a>/<b>/wire.jsonl. One wire.jsonl == one session."""

    name = "kimi"

    def session_files(self) -> list:
        base = Path.home() / ".kimi" / "sessions"
        if not base.exists():
            return []
        return sorted(base.glob("*/*/wire.jsonl"))

    def turn_of(self, rec) -> Optional[Turn]:
        role = _ROLE_MAP.get(rec.get("role"))
        if role is None:
            return None
        text = clean(extract_text(_content_of(rec)))
        if not text.strip():
            return None
        return Turn(role=role, text=text)

    def session_id(self, path, first) -> str:
        # wire.jsonl is nested; use the parent dir name as the session id.
        return Path(path).parent.name or Path(path).stem

    def project_path(self, path, first) -> Optional[str]:
        return (first or {}).get("cwd")

    def started_at(self, path, first) -> Optional[str]:
        return (first or {}).get("timestamp")
