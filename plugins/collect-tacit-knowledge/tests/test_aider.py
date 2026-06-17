import tests._path  # noqa: F401
import os
import unittest

from ctk.providers.aider import AiderAdapter

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "aider.chat.history.md")


class TestAider(unittest.TestCase):
    def test_parses_alternating_turns(self):
        sessions = list(AiderAdapter().parse(FIXTURE))
        self.assertEqual(len(sessions), 1)
        s = sessions[0]
        self.assertEqual(s.provider, "aider")
        # user (two #### lines merged), assistant, user, assistant
        self.assertEqual([t.role for t in s.turns], ["user", "assistant", "user", "assistant"])

    def test_secret_masked_code_and_noise_dropped(self):
        s = list(AiderAdapter().parse(FIXTURE))[0]
        joined = "\n".join(t.text for t in s.turns)
        # planted secret masked
        self.assertNotIn("sk-ABCDEF0123456789", joined)
        # long fenced code block reduced
        self.assertIn("[code omitted]", joined)
        self.assertNotIn("x = 1\n    x = 1", joined)
        # `>` command echoes / tool output dropped
        self.assertNotIn("Applied edit to file.py", joined)
        self.assertNotIn("Repo-map", joined)
        self.assertIn("OPFS", joined)


if __name__ == "__main__":
    unittest.main()
