from __future__ import annotations
from pathlib import Path
from typing import Optional
from ctk.base import JsonFileSessionAdapter
from ctk.model import Turn
from ctk.text import extract_text, clean


def _qwen_text(rec) -> str:
    """Pull text out of a Qwen message record, defensively.

    Qwen Code is a Gemini-CLI fork, so the message shape mirrors Gemini's:
    either {"content": "<text>"|[blocks]} or {"parts": [{"text": ...}]}."""
    parts = rec.get("parts")
    if isinstance(parts, list):
        out = []
        for p in parts:
            if isinstance(p, dict) and isinstance(p.get("text"), str):
                out.append(p["text"])
            elif isinstance(p, str):
                out.append(p)
        return "\n".join(t for t in out if t)
    return extract_text(rec.get("content"))


class QwenAdapter(JsonFileSessionAdapter):
    """Qwen Code: ~/.qwen/tmp/*/chats/session-*.json (JSON).

    Qwen Code is a Gemini-CLI derivative; the session file is a JSON object with
    a "messages" array (or a bare array). Each message carries a role under
    "role" or "type" (user->user, assistant/model/qwen->assistant) and text
    under "content" or "parts[].text". Implemented defensively against both
    shapes; text is clean()'d. No real Qwen sample available on this machine, so
    correctness is proven by the synthetic fixture test."""

    name = "qwen"

    def session_files(self) -> list:
        base = Path.home() / ".qwen" / "tmp"
        if not base.exists():
            return []
        return sorted(base.glob("*/chats/session-*.json"))

    def turn_of(self, rec) -> Optional[Turn]:
        if not isinstance(rec, dict):
            return None
        raw_role = rec.get("role") or rec.get("type")
        if raw_role in ("user",):
            role = "user"
        elif raw_role in ("assistant", "model", "qwen", "gemini"):
            role = "assistant"
        else:
            return None
        text = clean(_qwen_text(rec))
        if not text.strip():
            return None
        return Turn(role=role, text=text)

    def session_id(self, path, data) -> str:
        if isinstance(data, dict):
            sid = data.get("sessionId") or data.get("session_id")
            if sid:
                return str(sid)
        return Path(path).stem

    def project_path(self, path, data) -> Optional[str]:
        if isinstance(data, dict):
            return data.get("projectHash") or data.get("project")
        return None

    def started_at(self, path, data) -> Optional[str]:
        if isinstance(data, dict):
            return data.get("startTime") or data.get("started_at")
        return None
