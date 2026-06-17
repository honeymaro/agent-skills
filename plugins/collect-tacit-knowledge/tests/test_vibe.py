import tests._path  # noqa: F401
import os
import unittest
from ctk.providers.vibe import VibeAdapter

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "vibe_session.jsonl")


class TestVibe(unittest.TestCase):
    def test_parses_only_text_turns(self):
        sessions = list(VibeAdapter().parse(FIXTURE))
        self.assertEqual(len(sessions), 1)
        s = sessions[0]
        self.assertEqual(s.provider, "vibe")
        self.assertEqual(s.project, "/home/u/projects/demo")
        self.assertEqual(s.started_at, "2026-06-17T09:00:00Z")
        self.assertEqual([t.role for t in s.turns], ["user", "assistant"])

    def test_secret_is_masked_and_no_tool_noise(self):
        s = list(VibeAdapter().parse(FIXTURE))[0]
        joined = "\n".join(t.text for t in s.turns)
        self.assertNotIn("sk-ABCDEF0123456789", joined)
        self.assertNotIn("file dump", joined)
        self.assertIn("OPFS", joined)


if __name__ == "__main__":
    unittest.main()
