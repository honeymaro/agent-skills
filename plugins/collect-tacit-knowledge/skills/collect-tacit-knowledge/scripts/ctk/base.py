from __future__ import annotations
import json
import sqlite3
from pathlib import Path
from typing import Iterable, Optional
from ctk.model import NormalizedSession, Turn


class ProviderAdapter:
    name: str = "base"

    def detect(self) -> list:
        """Return session file/db paths that exist for this tool ([] if not installed)."""
        raise NotImplementedError

    def parse(self, path) -> Iterable[NormalizedSession]:
        raise NotImplementedError

    def project_of(self, session: NormalizedSession) -> Optional[str]:
        return session.project

    def supported(self) -> bool:
        """False for encrypted/undocumented providers that should be skipped."""
        return True


class JsonlFileSessionAdapter(ProviderAdapter):
    """One .jsonl file == one session. Each line is a record; subclasses map records."""

    def session_files(self) -> list:
        raise NotImplementedError

    def detect(self) -> list:
        return list(self.session_files())

    def parse(self, path) -> Iterable[NormalizedSession]:
        path = Path(path)
        turns = []
        first = None
        meta = None
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except (ValueError, json.JSONDecodeError):
                continue
            if first is None:
                first = rec
            if meta is None and self.has_meta(rec):
                meta = rec
            turn = self.turn_of(rec)
            if turn is not None and turn.text and turn.text.strip():
                turns.append(turn)
        if not turns:
            return
        # Metadata (project/session_id/started_at) is read from the first record
        # that actually carries it (has_meta), since many tools prefix a session
        # file with header records that lack cwd/timestamp. Falls back to `first`.
        meta = meta if meta is not None else first
        yield NormalizedSession(
            provider=self.name,
            session_id=self.session_id(path, meta),
            project=self.project_path(path, meta),
            started_at=self.started_at(path, meta),
            turns=turns,
        )

    # ---- hooks for subclasses ----
    def has_meta(self, rec) -> bool:
        """True if `rec` carries the metadata (cwd/session id/timestamp) that the
        metadata hooks read. Default: the first record. Override when a tool
        prefixes the file with header records lacking that metadata."""
        return True

    def turn_of(self, rec) -> Optional[Turn]:
        raise NotImplementedError

    def session_id(self, path, first) -> str:
        return Path(path).stem

    def project_path(self, path, first) -> Optional[str]:
        return None

    def started_at(self, path, first) -> Optional[str]:
        return None


class JsonFileSessionAdapter(ProviderAdapter):
    """One whole .json file == one session.

    Mirrors JsonlFileSessionAdapter but json.load()s the entire file and iterates
    a message array obtained from messages_of(data). Subclasses map each message
    record to a Turn via turn_of(rec)."""

    def session_files(self) -> list:
        raise NotImplementedError

    def detect(self) -> list:
        return list(self.session_files())

    def parse(self, path) -> Iterable[NormalizedSession]:
        path = Path(path)
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return
        try:
            data = json.loads(raw)
        except (ValueError, json.JSONDecodeError):
            return
        messages = self.messages_of(data)
        if not isinstance(messages, list):
            return
        turns = []
        for rec in messages:
            turn = self.turn_of(rec)
            if turn is not None and turn.text and turn.text.strip():
                turns.append(turn)
        if not turns:
            return
        yield NormalizedSession(
            provider=self.name,
            session_id=self.session_id(path, data),
            project=self.project_path(path, data),
            started_at=self.started_at(path, data),
            turns=turns,
        )

    # ---- hooks for subclasses ----
    def messages_of(self, data) -> list:
        """Return the list of message records from the loaded JSON.

        Default handles both a bare top-level array and an object carrying the
        array under a "messages" key."""
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            msgs = data.get("messages")
            if isinstance(msgs, list):
                return msgs
        return []

    def turn_of(self, rec) -> Optional[Turn]:
        raise NotImplementedError

    def session_id(self, path, data) -> str:
        return Path(path).stem

    def project_path(self, path, data) -> Optional[str]:
        return None

    def started_at(self, path, data) -> Optional[str]:
        return None


class SqliteAdapter(ProviderAdapter):
    """Sessions stored in a SQLite DB. Subclasses implement iter_sessions()."""

    def db_paths(self) -> list:
        raise NotImplementedError

    def detect(self) -> list:
        return [p for p in self.db_paths() if Path(p).exists()]

    def parse(self, path) -> Iterable[NormalizedSession]:
        try:
            conn = sqlite3.connect(f"file:{Path(path)}?mode=ro", uri=True)
        except sqlite3.Error:
            return
        try:
            yield from self.iter_sessions(conn, Path(path))
        except sqlite3.Error:
            return
        finally:
            conn.close()

    def iter_sessions(self, conn, path) -> Iterable[NormalizedSession]:
        raise NotImplementedError

    def make_session(self, session_id, turns, project=None, started_at=None) -> NormalizedSession:
        return NormalizedSession(
            provider=self.name,
            session_id=str(session_id),
            project=project,
            started_at=started_at,
            turns=list(turns),
        )


class FlexibleMessageSqliteAdapter(SqliteAdapter):
    """SQLite adapters whose conversations live in a `messages` table with
    version-varying column names. Discovers session-id/role/text/order columns
    defensively via PRAGMA table_info, groups rows into sessions, and applies
    clean(). Subclasses only set `name` and `db_paths()`.

    Yields nothing (rather than raising) if the message table or required
    role/text columns are absent."""

    _MESSAGE_TABLE = "messages"
    _SID_COLS = ("session_id", "sessionId", "thread_id", "conversation_id", "chat_id")
    _ROLE_COLS = ("role", "author", "sender", "type")
    _TEXT_COLS = ("content", "text", "body", "message", "parts")
    _ORDER_COLS = ("created_at", "createdAt", "timestamp", "ts", "id", "rowid")
    _ROLE_MAP = {
        "user": "user",
        "human": "user",
        "assistant": "assistant",
        "model": "assistant",
        "ai": "assistant",
    }

    def __init__(self, paths=None):
        self._paths = paths

    def _tables(self, conn) -> set:
        return {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }

    def _columns(self, conn, table) -> list:
        return [row[1] for row in conn.execute('PRAGMA table_info("{}")'.format(table))]

    @staticmethod
    def _pick(candidates, columns):
        cset = set(columns)
        for c in candidates:
            if c in cset:
                return c
        return None

    def iter_sessions(self, conn, path) -> Iterable[NormalizedSession]:
        from ctk.text import extract_text, clean

        if self._MESSAGE_TABLE not in self._tables(conn):
            return
        cols = self._columns(conn, self._MESSAGE_TABLE)
        role_col = self._pick(self._ROLE_COLS, cols)
        text_col = self._pick(self._TEXT_COLS, cols)
        if not role_col or not text_col:
            return
        sid_col = self._pick(self._SID_COLS, cols)
        order_col = self._pick(self._ORDER_COLS, cols) or "rowid"

        select = [role_col, text_col]
        if sid_col:
            select.append(sid_col)
        rows = conn.execute(
            'SELECT {} FROM "{}" ORDER BY {}'.format(
                ", ".join('"{}"'.format(c) for c in select), self._MESSAGE_TABLE, order_col
            )
        ).fetchall()

        by_sid = {}
        order = []
        for row in rows:
            raw_role, raw_text = row[0], row[1]
            sid = row[2] if sid_col else "default"
            role = self._ROLE_MAP.get(str(raw_role).lower()) if raw_role is not None else None
            if role is None:
                continue
            text = clean(extract_text(raw_text))
            if not text.strip():
                continue
            if sid not in by_sid:
                by_sid[sid] = []
                order.append(sid)
            by_sid[sid].append(Turn(role=role, text=text))

        for sid in order:
            turns = by_sid[sid]
            if turns:
                yield self.make_session(sid, turns)
