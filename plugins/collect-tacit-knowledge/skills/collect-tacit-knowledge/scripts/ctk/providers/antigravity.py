from __future__ import annotations
import os
from pathlib import Path
from typing import Optional
from ctk.base import JsonlFileSessionAdapter
from ctk.model import Turn
from ctk.text import extract_text, clean

# Google Antigravity is Gemini CLI's successor (deprecated 2026-06-18). It is a
# VS Code fork; documented conversation transcripts are JSONL under
#   <appDataDir>/Antigravity/brain/<conversation-id>/.system_generated/logs/*.jsonl
# NOTE: not yet verified against real local data (no Antigravity conversations on
# this machine — the editor's state.vscdb chat index was empty). Implemented
# defensively against a role/content message shape and validated by a synthetic
# fixture (tests/test_antigravity.py). Detection returns [] gracefully when absent.

_ROLE_MAP = {
    "user": "user",
    "human": "user",
    "assistant": "assistant",
    "model": "assistant",
    "ai": "assistant",
    "agent": "assistant",
    "gemini": "assistant",
}


def _appdata_dirs() -> list:
    dirs = []
    appdata = os.environ.get("APPDATA")
    if appdata:
        dirs.append(Path(appdata) / "Antigravity")              # Windows
    home = Path.home()
    dirs.append(home / "Library" / "Application Support" / "Antigravity")  # macOS
    dirs.append(home / ".config" / "Antigravity")               # Linux
    return dirs


def _content_of(rec):
    for field in ("content", "text", "message", "parts", "body"):
        if field in rec:
            return rec[field]
    return None


def _to_text(val) -> str:
    """Resolve Antigravity content into plain text defensively (string, block
    list, or {parts:[...]} / {text:...} shapes)."""
    if val is None:
        return ""
    if isinstance(val, str):
        return val
    if isinstance(val, list):
        out = []
        for b in val:
            if isinstance(b, str):
                out.append(b)
            elif isinstance(b, dict):
                if isinstance(b.get("text"), str):
                    out.append(b["text"])
                elif b.get("type") in ("text", "input_text", "output_text") and isinstance(b.get("content"), str):
                    out.append(b["content"])
        return "\n".join(o for o in out if o)
    if isinstance(val, dict):
        if isinstance(val.get("text"), str):
            return val["text"]
        if isinstance(val.get("parts"), list):
            return _to_text(val["parts"])
    return extract_text(val)


class AntigravityAdapter(JsonlFileSessionAdapter):
    """Google Antigravity (Gemini CLI successor). JSONL transcripts under
    <appData>/Antigravity/brain/<conversation-id>/.system_generated/logs/.
    Documented-format / fixture-validated (no real local data to verify yet)."""

    name = "antigravity"

    def session_files(self) -> list:
        files = []
        for base in _appdata_dirs():
            brain = base / "brain"
            if brain.exists():
                files += list(brain.glob("**/*.jsonl"))
        return sorted(files)

    def turn_of(self, rec) -> Optional[Turn]:
        if not isinstance(rec, dict):
            return None
        raw_role = rec.get("role") or rec.get("type") or rec.get("author")
        role = _ROLE_MAP.get(str(raw_role).lower()) if raw_role is not None else None
        if role is None:
            return None
        text = clean(_to_text(_content_of(rec)))
        if not text.strip():
            return None
        return Turn(role=role, text=text)
