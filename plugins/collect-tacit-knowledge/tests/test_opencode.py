import tests._path  # noqa: F401
import os
import unittest
from ctk.providers.opencode import OpenCodeAdapter

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "opencode_session.jsonl")


class TestOpenCode(unittest.TestCase):
    def test_parses_only_text_turns(self):
        sessions = list(OpenCodeAdapter().parse(FIXTURE))
        self.assertEqual(len(sessions), 1)
        s = sessions[0]
        self.assertEqual(s.provider, "opencode")
        self.assertEqual(s.project, "/home/u/projects/demo")
        self.assertEqual(s.started_at, "2026-06-17T09:00:00Z")
        # user, assistant, user (plain-string content) -- tool line dropped
        self.assertEqual([t.role for t in s.turns], ["user", "assistant", "user"])

    def test_secret_is_masked_and_no_tool_noise(self):
        s = list(OpenCodeAdapter().parse(FIXTURE))[0]
        joined = "\n".join(t.text for t in s.turns)
        self.assertNotIn("sk-ABCDEF0123456789", joined)
        self.assertNotIn("file dump", joined)
        self.assertIn("OPFS", joined)


if __name__ == "__main__":
    unittest.main()
