import tests._path  # noqa: F401
import os
import sqlite3
import tempfile
import unittest

from ctk.providers.codex import CodexAdapter, CodexLegacyAdapter

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "codex_rollout.jsonl")


class TestCodexRollout(unittest.TestCase):
    def test_rollout_parses_text_turns(self):
        s = list(CodexAdapter().parse(FIXTURE))[0]
        self.assertEqual(s.provider, "codex")
        self.assertEqual([t.role for t in s.turns], ["user", "assistant", "assistant"])
        joined = "\n".join(t.text for t in s.turns)
        self.assertIn("OPFS", joined)
        self.assertEqual(s.project, "/home/u/projects/demo")
        self.assertEqual(s.started_at, "2026-06-17T09:00:00Z")

    def test_rollout_masks_secret_and_drops_noise(self):
        s = list(CodexAdapter().parse(FIXTURE))[0]
        joined = "\n".join(t.text for t in s.turns)
        # secret masked by clean()
        self.assertNotIn("sk-ABCDEF0123456789", joined)
        # function_call / function_call_output / reasoning dropped
        self.assertNotIn("file dump", joined)
        self.assertNotIn("chain of thought", joined)
        self.assertNotIn("ls", [t.text for t in s.turns])


class TestCodexLegacyFixture(unittest.TestCase):
    """Proves iter_sessions logic on a synthetic `logs` table that mirrors the
    REAL columns found on this machine
    (id, ts, ts_nanos, level, target, feedback_log_body, module_path, file,
    line, thread_id, process_uuid, estimated_bytes), plus the role/text columns
    the mapping reads when present."""

    def _make_db(self, rows):
        fd, p = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        conn = sqlite3.connect(p)
        conn.execute(
            "CREATE TABLE logs ("
            "id INTEGER PRIMARY KEY, ts INTEGER, ts_nanos INTEGER, level TEXT, "
            "target TEXT, feedback_log_body TEXT, module_path TEXT, file TEXT, "
            "line INTEGER, thread_id TEXT, process_uuid TEXT, estimated_bytes INTEGER, "
            "role TEXT, text TEXT)"
        )
        conn.executemany(
            "INSERT INTO logs (id, ts, level, target, feedback_log_body, "
            "thread_id, role, text) VALUES (?,?,?,?,?,?,?,?)",
            rows,
        )
        conn.commit()
        conn.close()
        return p

    def test_groups_rows_into_sessions_by_thread_id(self):
        rows = [
            # id, ts, level, target, feedback_log_body, thread_id, role, text
            (1, 1775030850, "INFO", "conv", None, "thread-A", "user", "How do I cache arrays?"),
            (2, 1775030851, "INFO", "conv", None, "thread-A", "assistant", "Use OPFS for blobs."),
            (3, 1775030852, "INFO", "conv", None, "thread-B", "user", "key sk-ABCDEF0123456789ABCDEF0123"),
            # diagnostic-only row with no role/text -> skipped
            (4, 1775030853, "WARN", "codex_core::shell_snapshot", "Failed to create shell snapshot", "thread-A", None, None),
        ]
        p = self._make_db(rows)
        try:
            sessions = sorted(CodexLegacyAdapter([p]).parse(p), key=lambda s: s.session_id)
            self.assertEqual(len(sessions), 2)
            a = sessions[0]
            self.assertEqual(a.provider, "codex-legacy")
            self.assertEqual(a.session_id, "thread-A")
            self.assertEqual([t.role for t in a.turns], ["user", "assistant"])
            self.assertIn("OPFS", "\n".join(t.text for t in a.turns))
            # clean() applied: secret masked in thread-B
            b = sessions[1]
            self.assertNotIn("sk-ABCDEF0123456789", "\n".join(t.text for t in b.turns))
        finally:
            os.unlink(p)

    def test_no_conversation_rows_yields_nothing(self):
        rows = [
            (1, 1775030850, "WARN", "codex_core::shell_snapshot", "diag", "thread-A", None, None),
        ]
        p = self._make_db(rows)
        try:
            self.assertEqual(list(CodexLegacyAdapter([p]).parse(p)), [])
        finally:
            os.unlink(p)


REAL_LEGACY_DB = os.path.expanduser(os.path.join("~", ".codex", "logs_1.sqlite"))


@unittest.skipUnless(os.path.exists(REAL_LEGACY_DB), "no real ~/.codex/logs_*.sqlite present")
@unittest.skip(
    "codex legacy schema: real ~/.codex/logs_*.sqlite `logs` table is a Rust "
    "tracing/diagnostics log (level/target/feedback_log_body), not a conversation "
    "store; it has no role/text turns, so no clean conversation can be extracted. "
    "iter_sessions logic is validated by TestCodexLegacyFixture instead."
)
class TestCodexLegacyLive(unittest.TestCase):
    def test_real_db_yields_clean_turns(self):
        sessions = list(CodexLegacyAdapter().parse(REAL_LEGACY_DB))
        self.assertTrue(sessions)


if __name__ == "__main__":
    unittest.main()
