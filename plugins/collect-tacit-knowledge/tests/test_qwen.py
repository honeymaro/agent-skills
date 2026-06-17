import tests._path  # noqa: F401
import os
import unittest

from ctk.providers.qwen import QwenAdapter

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "qwen_session.json")


class TestQwen(unittest.TestCase):
    def test_parses_session_messages(self):
        sessions = list(QwenAdapter().parse(FIXTURE))
        self.assertEqual(len(sessions), 1)
        s = sessions[0]
        self.assertEqual(s.provider, "qwen")
        self.assertEqual(s.session_id, "qwen-sess-42")
        self.assertEqual(s.started_at, "2026-06-17T09:00:00Z")
        # user/qwen->assistant/(tool dropped)/user
        self.assertEqual([t.role for t in s.turns], ["user", "assistant", "user"])

    def test_secret_masked_and_noise_dropped(self):
        s = list(QwenAdapter().parse(FIXTURE))[0]
        joined = "\n".join(t.text for t in s.turns)
        self.assertNotIn("abcd1234abcd1234abcd1234", joined)
        self.assertNotIn("file dump", joined)
        self.assertIn("[code omitted]", joined)
        self.assertNotIn("const a = 1;\nconst a = 1;", joined)
        self.assertIn("OPFS", joined)


if __name__ == "__main__":
    unittest.main()
