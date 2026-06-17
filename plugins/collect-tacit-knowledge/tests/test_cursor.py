import tests._path  # noqa: F401
import json
import os
import sqlite3
import tempfile
import unittest

from ctk.providers.cursor import CursorAdapter


class TestCursorFixture(unittest.TestCase):
    """Validates the best-effort ItemTable blob walker against a plausible
    Cursor chat blob shape. The exact real key path is uncertain across Cursor
    versions, so the live assertion is skipped (see TestCursorLive); this
    synthetic test must keep passing."""

    def _make_db(self, items):
        fd, p = tempfile.mkstemp(suffix=".vscdb")
        os.close(fd)
        conn = sqlite3.connect(p)
        conn.execute("CREATE TABLE ItemTable (key TEXT PRIMARY KEY, value TEXT)")
        conn.executemany(
            "INSERT INTO ItemTable (key, value) VALUES (?,?)", items
        )
        conn.commit()
        conn.close()
        return p

    def test_extracts_messages_from_chat_blob(self):
        chat_blob = {
            "tabs": [
                {
                    "messages": [
                        {"role": "user", "text": "How do I cache big Float32 arrays? sk-ABCDEF0123456789ABCDEF0123"},
                        {"role": "assistant", "text": "Use OPFS over IndexedDB for large numeric blobs."},
                    ]
                }
            ]
        }
        items = [
            ("workbench.panel.aichat.view.aichat.chatdata", json.dumps(chat_blob)),
            # unrelated key -> ignored
            ("telemetry.machineId", json.dumps({"id": "x"})),
            # chatty key but non-JSON value -> skipped gracefully
            ("composer.state", "not-json"),
        ]
        p = self._make_db(items)
        try:
            sessions = list(CursorAdapter([p]).parse(p))
            self.assertEqual(len(sessions), 1)
            s = sessions[0]
            self.assertEqual(s.provider, "cursor")
            self.assertEqual([t.role for t in s.turns], ["user", "assistant"])
            joined = "\n".join(t.text for t in s.turns)
            self.assertIn("OPFS", joined)
            self.assertNotIn("sk-ABCDEF0123456789", joined)
        finally:
            os.unlink(p)

    def test_isuser_boolean_role_encoding(self):
        chat_blob = {
            "conversation": [
                {"isUser": True, "content": "user side"},
                {"isUser": False, "content": "assistant side"},
            ]
        }
        items = [("aiService.prompts", json.dumps(chat_blob))]
        p = self._make_db(items)
        try:
            s = list(CursorAdapter([p]).parse(p))[0]
            self.assertEqual([t.role for t in s.turns], ["user", "assistant"])
        finally:
            os.unlink(p)

    def test_no_itemtable_yields_nothing(self):
        fd, p = tempfile.mkstemp(suffix=".vscdb")
        os.close(fd)
        conn = sqlite3.connect(p)
        conn.execute("CREATE TABLE other (k TEXT, v TEXT)")
        conn.commit()
        conn.close()
        try:
            self.assertEqual(list(CursorAdapter([p]).parse(p)), [])
        finally:
            os.unlink(p)

    def test_missing_db_skipped(self):
        self.assertEqual(CursorAdapter([]).detect(), [])


REAL_DB_GLOB = os.path.join(
    os.environ.get("APPDATA", ""), "Cursor", "User", "globalStorage", "state.vscdb"
)


@unittest.skip(
    "cursor: needs real state.vscdb to confirm key path. The ItemTable chat key "
    "varies across Cursor versions; the walker is validated by TestCursorFixture."
)
class TestCursorLive(unittest.TestCase):
    def test_real_db_yields_clean_turns(self):
        sessions = list(CursorAdapter([REAL_DB_GLOB]).parse(REAL_DB_GLOB))
        self.assertTrue(sessions)


if __name__ == "__main__":
    unittest.main()
