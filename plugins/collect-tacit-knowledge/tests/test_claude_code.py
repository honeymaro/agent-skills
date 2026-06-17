import tests._path  # noqa: F401
import os
import tempfile
import unittest
from ctk.providers.claude_code import ClaudeCodeAdapter

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "claude_code_session.jsonl")


class TestClaudeCode(unittest.TestCase):
    def test_parses_only_text_turns(self):
        sessions = list(ClaudeCodeAdapter().parse(FIXTURE))
        self.assertEqual(len(sessions), 1)
        s = sessions[0]
        self.assertEqual(s.provider, "claude-code")
        self.assertEqual(s.session_id, "sess-123")
        self.assertEqual(s.project, "/home/u/projects/demo")
        self.assertEqual(s.started_at, "2026-06-17T09:00:00Z")
        # 3 text-bearing turns (user, assistant text-only, user text-only)
        self.assertEqual([t.role for t in s.turns], ["user", "assistant", "user"])

    def test_secret_is_masked_and_no_tool_noise(self):
        s = list(ClaudeCodeAdapter().parse(FIXTURE))[0]
        joined = "\n".join(t.text for t in s.turns)
        self.assertNotIn("sk-ABCDEF0123456789", joined)
        self.assertNotIn("file dump", joined)
        self.assertNotIn("command", joined)
        self.assertIn("OPFS", joined)

    def test_project_read_from_first_record_with_cwd_not_header(self):
        # Real sessions begin with header records (last-prompt/mode/...) that
        # carry sessionId but NOT cwd; cwd appears later on user/assistant
        # records. Metadata must be picked from the cwd-bearing record.
        lines = [
            '{"type":"last-prompt","sessionId":"sess-9","message":{}}',
            '{"type":"mode","sessionId":"sess-9"}',
            '{"type":"user","cwd":"C:\\\\Users\\\\dev\\\\projects\\\\acme\\\\app",'
            '"sessionId":"sess-9","timestamp":"2026-06-17T10:00:00Z",'
            '"message":{"role":"user","content":"hello"}}',
        ]
        fd, p = tempfile.mkstemp(suffix=".jsonl")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            s = list(ClaudeCodeAdapter().parse(p))[0]
            self.assertEqual(s.project, "C:\\Users\\dev\\projects\\acme\\app")
            self.assertEqual(s.session_id, "sess-9")
            self.assertEqual(s.started_at, "2026-06-17T10:00:00Z")
        finally:
            os.unlink(p)


if __name__ == "__main__":
    unittest.main()
