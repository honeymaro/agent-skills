import tests._path  # noqa: F401
import os
import sqlite3
import tempfile
import unittest

from ctk.providers.hermes import HermesAdapter


class TestHermesFixture(unittest.TestCase):
    """Validates iter_sessions against a synthetic `messages` table mirroring
    the documented Hermes shape (thread id + role + text columns)."""

    def _make_db(self, rows):
        fd, p = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        conn = sqlite3.connect(p)
        conn.execute(
            "CREATE TABLE messages ("
            "id INTEGER PRIMARY KEY, thread_id TEXT, role TEXT, text TEXT, "
            "timestamp TEXT)"
        )
        conn.executemany(
            "INSERT INTO messages (id, thread_id, role, text, timestamp) "
            "VALUES (?,?,?,?,?)",
            rows,
        )
        conn.commit()
        conn.close()
        return p

    def test_groups_rows_into_sessions(self):
        rows = [
            (1, "t1", "user", "How do I cache big Float32 arrays?", "2026-06-17T09:00:00Z"),
            (2, "t1", "assistant", "Use OPFS over IndexedDB for large numeric blobs.", "2026-06-17T09:00:01Z"),
            (3, "t2", "user", "AWS_SECRET=abcd1234abcd1234abcd", "2026-06-17T09:01:00Z"),
            (4, "t1", "system", "ignore me", "2026-06-17T09:00:02Z"),
        ]
        p = self._make_db(rows)
        try:
            sessions = sorted(HermesAdapter([p]).parse(p), key=lambda s: s.session_id)
            self.assertEqual(len(sessions), 2)
            a = sessions[0]
            self.assertEqual(a.provider, "hermes")
            self.assertEqual(a.session_id, "t1")
            self.assertEqual([t.role for t in a.turns], ["user", "assistant"])
            self.assertIn("OPFS", "\n".join(t.text for t in a.turns))
            b = sessions[1]
            self.assertNotIn("abcd1234abcd1234abcd", "\n".join(t.text for t in b.turns))
        finally:
            os.unlink(p)

    def test_missing_table_yields_nothing(self):
        fd, p = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        conn = sqlite3.connect(p)
        conn.execute("CREATE TABLE state (id INTEGER PRIMARY KEY, blob TEXT)")
        conn.commit()
        conn.close()
        try:
            self.assertEqual(list(HermesAdapter([p]).parse(p)), [])
        finally:
            os.unlink(p)

    def test_missing_db_skipped(self):
        self.assertEqual(HermesAdapter([]).detect(), [])


REAL_DB = os.path.expanduser(os.path.join("~", ".hermes", "state.db"))


@unittest.skipUnless(os.path.exists(REAL_DB), "no real ~/.hermes/state.db present")
class TestHermesLive(unittest.TestCase):
    def test_real_db_does_not_crash(self):
        list(HermesAdapter().parse(REAL_DB))


if __name__ == "__main__":
    unittest.main()
