from __future__ import annotations
from pathlib import Path
from typing import Optional
from ctk.base import JsonlFileSessionAdapter
from ctk.model import Turn
from ctk.text import extract_text, clean


class ClaudeCodeAdapter(JsonlFileSessionAdapter):
    name = "claude-code"

    def session_files(self) -> list:
        base = Path.home() / ".claude" / "projects"
        if not base.exists():
            return []
        return sorted(base.glob("*/*.jsonl"))

    def has_meta(self, rec) -> bool:
        # Claude Code prefixes sessions with last-prompt/mode/permission-mode
        # records that carry sessionId but NOT cwd; cwd appears on user/assistant
        # records. Pick the first record bearing cwd (it also has sessionId+timestamp).
        return isinstance(rec, dict) and bool(rec.get("cwd"))

    def turn_of(self, rec) -> Optional[Turn]:
        if rec.get("type") not in ("user", "assistant"):
            return None
        msg = rec.get("message")
        if not isinstance(msg, dict):
            return None
        role = msg.get("role")
        if role not in ("user", "assistant"):
            return None
        text = clean(extract_text(msg.get("content")))
        if not text.strip():
            return None
        return Turn(role=role, text=text)

    def session_id(self, path, first) -> str:
        sid = (first or {}).get("sessionId")
        return sid or Path(path).stem

    def project_path(self, path, first) -> Optional[str]:
        return (first or {}).get("cwd")

    def started_at(self, path, first) -> Optional[str]:
        return (first or {}).get("timestamp")
