import tests._path  # noqa: F401
import os
import sqlite3
import tempfile
import unittest

from ctk.providers.crush import CrushAdapter


class TestCrushFixture(unittest.TestCase):
    """Validates iter_sessions against a synthetic `messages` table mirroring
    the documented Crush shape (session id + role + text columns)."""

    def _make_db(self, rows):
        fd, p = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        conn = sqlite3.connect(p)
        conn.execute(
            "CREATE TABLE messages ("
            "id INTEGER PRIMARY KEY, session_id TEXT, role TEXT, content TEXT, "
            "created_at INTEGER)"
        )
        conn.executemany(
            "INSERT INTO messages (id, session_id, role, content, created_at) "
            "VALUES (?,?,?,?,?)",
            rows,
        )
        conn.commit()
        conn.close()
        return p

    def test_groups_rows_into_sessions(self):
        rows = [
            (1, "s1", "user", "How do I cache big Float32 arrays?", 1775030850),
            (2, "s1", "assistant", "Use OPFS over IndexedDB for large numeric blobs.", 1775030851),
            (3, "s2", "user", "key sk-ABCDEF0123456789ABCDEF0123", 1775030852),
            # noise role -> dropped
            (4, "s1", "tool", "<file dump>", 1775030853),
        ]
        p = self._make_db(rows)
        try:
            sessions = sorted(CrushAdapter([p]).parse(p), key=lambda s: s.session_id)
            self.assertEqual(len(sessions), 2)
            a = sessions[0]
            self.assertEqual(a.provider, "crush")
            self.assertEqual(a.session_id, "s1")
            self.assertEqual([t.role for t in a.turns], ["user", "assistant"])
            joined = "\n".join(t.text for t in a.turns)
            self.assertIn("OPFS", joined)
            self.assertNotIn("file dump", joined)
            # clean() masks the secret in s2
            b = sessions[1]
            self.assertNotIn("sk-ABCDEF0123456789", "\n".join(t.text for t in b.turns))
        finally:
            os.unlink(p)

    def test_missing_table_yields_nothing(self):
        fd, p = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        conn = sqlite3.connect(p)
        conn.execute("CREATE TABLE other (id INTEGER PRIMARY KEY, x TEXT)")
        conn.commit()
        conn.close()
        try:
            self.assertEqual(list(CrushAdapter([p]).parse(p)), [])
        finally:
            os.unlink(p)

    def test_missing_db_skipped(self):
        self.assertEqual(CrushAdapter([]).detect(), [])


REAL_DB = os.path.expanduser(os.path.join("~", ".crush", "crush.db"))


@unittest.skipUnless(os.path.exists(REAL_DB), "no real ~/.crush/crush.db present")
class TestCrushLive(unittest.TestCase):
    def test_real_db_does_not_crash(self):
        # read-only smoke test; just ensure no exception
        list(CrushAdapter().parse(REAL_DB))


if __name__ == "__main__":
    unittest.main()
