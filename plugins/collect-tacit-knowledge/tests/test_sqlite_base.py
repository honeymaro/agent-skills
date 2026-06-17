import tests._path  # noqa: F401
import os
import sqlite3
import tempfile
import unittest
from ctk.base import SqliteAdapter
from ctk.model import Turn


class _FakeSqlite(SqliteAdapter):
    name = "fakedb"

    def __init__(self, paths):
        self._paths = paths

    def db_paths(self):
        return self._paths

    def iter_sessions(self, conn, path):
        rows = conn.execute(
            "SELECT session_id, role, text FROM msg ORDER BY id"
        ).fetchall()
        by_sid = {}
        for sid, role, text in rows:
            by_sid.setdefault(sid, []).append(Turn(role=role, text=text))
        for sid, turns in by_sid.items():
            yield self.make_session(sid, turns, project=None, started_at=None)


class TestSqliteBase(unittest.TestCase):
    def test_reads_sessions_from_db(self):
        fd, p = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        conn = sqlite3.connect(p)
        conn.execute("CREATE TABLE msg (id INTEGER PRIMARY KEY, session_id TEXT, role TEXT, text TEXT)")
        conn.executemany(
            "INSERT INTO msg (session_id, role, text) VALUES (?,?,?)",
            [("s1", "user", "hi"), ("s1", "assistant", "yo"), ("s2", "user", "q")],
        )
        conn.commit()
        conn.close()
        sessions = list(_FakeSqlite([p]).parse(p))
        self.assertEqual(len(sessions), 2)
        self.assertEqual(sessions[0].provider, "fakedb")
        os.unlink(p)

    def test_missing_db_skipped(self):
        self.assertEqual(_FakeSqlite([]).detect(), [])


if __name__ == "__main__":
    unittest.main()
