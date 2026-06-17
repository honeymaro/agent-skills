from __future__ import annotations
from pathlib import Path
from typing import Optional
from ctk.base import JsonlFileSessionAdapter
from ctk.model import Turn
from ctk.text import extract_text, clean

# Assumed line shape: {"role": "user"|"assistant", "content": <str | [{"type":"text","text"}] >, ...};
# non-message event lines (tool_call, etc.) lack a user/assistant role and are dropped.

_ROLE_MAP = {"user": "user", "human": "user", "assistant": "assistant", "model": "assistant", "ai": "assistant"}


def _content_of(rec):
    for key in ("content", "text", "message"):
        if key in rec:
            return rec[key]
    return None


class CopilotCliAdapter(JsonlFileSessionAdapter):
    """GitHub Copilot CLI: ~/.copilot/session-state/<id>/events.jsonl
    (+ legacy ~/.copilot/history-session-state/<id>/events.jsonl).
    One events.jsonl == one session; session_id is the parent directory name."""

    name = "copilot-cli"

    def session_files(self) -> list:
        base = Path.home() / ".copilot"
        if not base.exists():
            return []
        files = []
        files.extend(base.glob("session-state/*/events.jsonl"))
        files.extend(base.glob("history-session-state/*/events.jsonl"))
        return sorted(files)

    def turn_of(self, rec) -> Optional[Turn]:
        role = _ROLE_MAP.get(rec.get("role"))
        if role is None:
            return None
        text = clean(extract_text(_content_of(rec)))
        if not text.strip():
            return None
        return Turn(role=role, text=text)

    def session_id(self, path, first) -> str:
        return Path(path).parent.name or Path(path).stem

    def project_path(self, path, first) -> Optional[str]:
        return (first or {}).get("cwd")

    def started_at(self, path, first) -> Optional[str]:
        return (first or {}).get("timestamp")
