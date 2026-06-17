from __future__ import annotations
from pathlib import Path
from typing import Optional
from ctk.base import JsonFileSessionAdapter
from ctk.model import Turn
from ctk.text import extract_text, clean


def _gemini_text(rec) -> str:
    """Pull human/model text out of a Gemini message record.

    Two documented/observed shapes:
    - checkpoint*.json: {"role": "user"|"model", "parts": [{"text": ...}, ...]}
    - chats/session-*.json: {"type": "user"|"gemini", "content": "<text>"}
    Tool/function parts and non-text parts are dropped."""
    # parts[].text (checkpoint shape)
    parts = rec.get("parts")
    if isinstance(parts, list):
        out = []
        for p in parts:
            if isinstance(p, dict) and isinstance(p.get("text"), str):
                out.append(p["text"])
            elif isinstance(p, str):
                out.append(p)
        return "\n".join(t for t in out if t)
    # content (session shape) — string or block list
    return extract_text(rec.get("content"))


class GeminiAdapter(JsonFileSessionAdapter):
    """Gemini CLI. Two on-disk shapes are supported defensively:

    1. Documented: ~/.gemini/tmp/<hash>/checkpoint*.json — a JSON ARRAY of
       messages {"role":"user"|"model","parts":[{"text":...}]}. Checkpointing
       is OFF by default, so most machines have none.
    2. Observed on real machines: ~/.gemini/tmp/<hash>/chats/session-*.json —
       a JSON OBJECT {"sessionId","projectHash","startTime","messages":[
       {"type":"user"|"gemini","content":"..."}]}.

    Roles map: user->user, model/gemini->assistant. parts[].text or content is
    extracted and clean()'d (code-strip + secret-mask)."""

    name = "gemini"

    def session_files(self) -> list:
        base = Path.home() / ".gemini" / "tmp"
        if not base.exists():
            return []
        files = sorted(base.glob("*/checkpoint*.json"))
        files += sorted(base.glob("*/chats/session-*.json"))
        return files

    def turn_of(self, rec) -> Optional[Turn]:
        if not isinstance(rec, dict):
            return None
        raw_role = rec.get("role") or rec.get("type")
        if raw_role in ("user",):
            role = "user"
        elif raw_role in ("model", "gemini", "assistant"):
            role = "assistant"
        else:
            return None
        text = clean(_gemini_text(rec))
        if not text.strip():
            return None
        return Turn(role=role, text=text)

    def session_id(self, path, data) -> str:
        if isinstance(data, dict):
            sid = data.get("sessionId")
            if sid:
                return str(sid)
        return Path(path).stem

    def project_path(self, path, data) -> Optional[str]:
        if isinstance(data, dict):
            return data.get("projectHash")
        return None

    def started_at(self, path, data) -> Optional[str]:
        if isinstance(data, dict):
            return data.get("startTime")
        return None
