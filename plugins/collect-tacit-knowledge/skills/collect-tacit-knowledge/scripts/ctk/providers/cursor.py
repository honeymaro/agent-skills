from __future__ import annotations
import json
import os
from glob import glob
from pathlib import Path
from typing import Iterable, Optional
from ctk.base import SqliteAdapter
from ctk.model import Turn
from ctk.text import extract_text, clean

_ROLE_MAP = {
    "user": "user",
    "human": "user",
    "assistant": "assistant",
    "model": "assistant",
    "ai": "assistant",
    1: "user",       # some VS Code chat blobs encode role as int (1=user, 2=ai)
    2: "assistant",
    "1": "user",
    "2": "assistant",
}

# ItemTable keys that plausibly hold chat data (best-effort; the real key path
# is uncertain across Cursor versions, so match broadly on substrings).
_CHAT_KEY_HINTS = ("chat", "composer", "aichat", "aiservice", "conversation", "prompt")


def _looks_chatty(key: str) -> bool:
    k = key.lower()
    return any(h in k for h in _CHAT_KEY_HINTS)


def _role_of(node) -> Optional[str]:
    for field in ("role", "author", "type", "sender", "speaker"):
        if field in node:
            mapped = _ROLE_MAP.get(node[field])
            if mapped is None and isinstance(node[field], str):
                mapped = _ROLE_MAP.get(node[field].lower())
            if mapped:
                return mapped
    # Cursor often uses isUser/fromUser booleans instead of a role string.
    for field in ("isUser", "fromUser", "isFromUser"):
        if field in node:
            return "user" if node[field] else "assistant"
    return None


def _text_of(node) -> str:
    for field in ("text", "content", "message", "richText", "body"):
        if field in node:
            val = node[field]
            extracted = extract_text(val)
            if extracted and extracted.strip():
                return extracted
            if isinstance(val, str) and val.strip():
                return val
    return ""


def _walk_messages(obj, depth=0):
    """Yield (role, text) for any message-like dict found anywhere in the blob.

    Bounded depth guards against deeply nested / adversarial blobs triggering
    RecursionError."""
    if depth > 50:
        return
    if isinstance(obj, dict):
        role = _role_of(obj)
        text = _text_of(obj)
        if role and text.strip():
            yield role, text
        for v in obj.values():
            yield from _walk_messages(v, depth + 1)
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk_messages(item, depth + 1)


class CursorAdapter(SqliteAdapter):
    """Cursor (VS Code fork): state.vscdb SQLite.

    On Windows: %APPDATA%\\Cursor\\User\\**\\state.vscdb plus the
    globalStorage\\state.vscdb. Chat data lives in an `ItemTable`
    (columns key, value) where some `value` cells are JSON blobs containing
    messages. This is the MOST format-fragile adapter: the exact key path
    varies across Cursor versions, so iter_sessions reads every chat-looking
    key, json.loads the value, and walks the structure best-effort to collect
    role/text message pairs. If ItemTable is absent or no chat keys parse, it
    yields nothing rather than raising.

    The synthetic-fixture test (tests/test_cursor.py) validates this walker
    against a plausible blob shape; a LIVE-only assertion is skipped because no
    real state.vscdb is available to confirm the exact key path."""

    name = "cursor"

    def __init__(self, paths=None):
        self._paths = paths

    def db_paths(self) -> list:
        if self._paths is not None:
            return list(self._paths)
        appdata = os.environ.get("APPDATA")
        if not appdata:
            return []
        base = os.path.join(appdata, "Cursor", "User")
        if not os.path.isdir(base):
            return []
        found = set()
        found.update(glob(os.path.join(base, "**", "state.vscdb"), recursive=True))
        return sorted(found)

    def _tables(self, conn) -> set:
        return {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }

    def iter_sessions(self, conn, path) -> Iterable:
        if "ItemTable" not in self._tables(conn):
            return
        cols = {row[1] for row in conn.execute('PRAGMA table_info("ItemTable")')}
        if not ({"key", "value"} <= cols):
            return
        rows = conn.execute('SELECT key, value FROM "ItemTable"').fetchall()
        for key, value in rows:
            if not isinstance(key, str) or not _looks_chatty(key):
                continue
            if not isinstance(value, (str, bytes, bytearray)):
                continue
            try:
                blob = json.loads(value)
            except (ValueError, TypeError):
                continue
            turns = []
            for role, text in _walk_messages(blob):
                cleaned = clean(text)
                if cleaned.strip():
                    turns.append(Turn(role=role, text=cleaned))
            if turns:
                yield self.make_session(key, turns)
