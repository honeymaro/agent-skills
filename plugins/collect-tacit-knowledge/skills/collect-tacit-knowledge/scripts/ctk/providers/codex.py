from __future__ import annotations
import os
from pathlib import Path
from typing import Iterable, Optional
from ctk.base import JsonlFileSessionAdapter, SqliteAdapter
from ctk.model import Turn
from ctk.text import extract_text, clean


def _codex_text(content) -> str:
    """Codex content blocks use input_text/output_text rather than "text"."""
    if isinstance(content, list):
        parts = []
        for b in content:
            if isinstance(b, dict) and b.get("type") in ("input_text", "output_text", "text"):
                parts.append(str(b.get("text", "")))
        return "\n".join(p for p in parts if p)
    return extract_text(content)


class CodexAdapter(JsonlFileSessionAdapter):
    """Current Codex format: ~/.codex/sessions/Y/M/D/rollout-*.jsonl.

    One file == one session. Each line is a JSON record; only `message` records
    with role user/assistant carry transcript text (function_call /
    function_call_output / reasoning records are dropped)."""

    name = "codex"

    def session_files(self) -> list:
        base = Path.home() / ".codex" / "sessions"
        return sorted(base.glob("**/rollout-*.jsonl")) if base.exists() else []

    def has_meta(self, rec) -> bool:
        # Pick the first record bearing cwd (a rollout may start with header
        # records that lack it); falls back to the first record otherwise.
        return isinstance(rec, dict) and bool(rec.get("cwd"))

    def turn_of(self, rec) -> Optional[Turn]:
        if rec.get("type") != "message":
            return None
        role = rec.get("role")
        if role not in ("user", "assistant"):
            return None
        text = clean(_codex_text(rec.get("content")))
        if not text.strip():
            return None
        return Turn(role=role, text=text)

    def project_path(self, path, first) -> Optional[str]:
        return (first or {}).get("cwd")

    def started_at(self, path, first) -> Optional[str]:
        return (first or {}).get("timestamp")


class CodexLegacyAdapter(SqliteAdapter):
    """Legacy Codex store: ~/.codex/logs_*.sqlite (table `logs`).

    NOTE on the real schema: on machines running recent Codex, the `logs` table
    is a Rust tracing/diagnostics log
    (id, ts, ts_nanos, level, target, feedback_log_body, module_path, file,
    line, thread_id, process_uuid, estimated_bytes) -- it stores log lines, not
    conversation turns, so it cannot yield clean role/text turns. The live test
    is therefore skipped. iter_sessions() is written best-effort: it reads
    role/text columns when the table carries them and groups rows into sessions
    by thread_id (the conversation identifier), applying clean(). This logic is
    validated against a synthetic `logs` table mirroring the real columns in
    tests/test_codex.py::TestCodexLegacyFixture."""

    name = "codex-legacy"

    def __init__(self, paths=None):
        self._paths = paths

    def db_paths(self) -> list:
        if self._paths is not None:
            return list(self._paths)
        base = Path.home() / ".codex"
        return sorted(str(p) for p in base.glob("logs_*.sqlite")) if base.exists() else []

    def _columns(self, conn) -> set:
        return {row[1] for row in conn.execute("PRAGMA table_info(logs)")}

    def iter_sessions(self, conn, path) -> Iterable:
        cols = self._columns(conn)
        # Conversation turns require role + text columns. The real diagnostics
        # schema lacks them -> nothing to extract.
        if not ({"role", "text"} <= cols):
            return
        sid_col = "thread_id" if "thread_id" in cols else None
        order_col = "id" if "id" in cols else "rowid"
        select_cols = ["role", "text"]
        if sid_col:
            select_cols.append(sid_col)
        rows = conn.execute(
            "SELECT {} FROM logs ORDER BY {}".format(", ".join(select_cols), order_col)
        ).fetchall()

        by_sid = {}
        order = []
        for row in rows:
            role, text = row[0], row[1]
            sid = row[2] if sid_col else "default"
            if role not in ("user", "assistant"):
                continue
            cleaned = clean(text or "")
            if not cleaned.strip():
                continue
            if sid not in by_sid:
                by_sid[sid] = []
                order.append(sid)
            by_sid[sid].append(Turn(role=role, text=cleaned))

        for sid in order:
            turns = by_sid[sid]
            if turns:
                yield self.make_session(sid, turns)
