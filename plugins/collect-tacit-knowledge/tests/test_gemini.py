import tests._path  # noqa: F401
import glob
import os
import unittest

from ctk.providers.gemini import GeminiAdapter

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "gemini_checkpoint.json")


class TestGemini(unittest.TestCase):
    def test_parses_checkpoint_array(self):
        sessions = list(GeminiAdapter().parse(FIXTURE))
        self.assertEqual(len(sessions), 1)
        s = sessions[0]
        self.assertEqual(s.provider, "gemini")
        # role user/model/user; model -> assistant
        self.assertEqual([t.role for t in s.turns], ["user", "assistant", "user"])

    def test_secret_masked_and_code_noise_dropped(self):
        s = list(GeminiAdapter().parse(FIXTURE))[0]
        joined = "\n".join(t.text for t in s.turns)
        # planted secret masked
        self.assertNotIn("sk-ABCDEF0123456789", joined)
        # long code fence dropped by clean()
        self.assertIn("[code omitted]", joined)
        self.assertNotIn("x = 1\nx = 1", joined)
        # functionCall part dropped (no shell command leaks)
        self.assertNotIn("run_shell", joined)
        self.assertIn("OPFS", joined)


REAL_GEMINI = sorted(
    glob.glob(os.path.expanduser(os.path.join("~", ".gemini", "tmp", "*", "checkpoint*.json")))
    + glob.glob(os.path.expanduser(os.path.join("~", ".gemini", "tmp", "*", "chats", "session-*.json")))
)


@unittest.skipUnless(REAL_GEMINI, "no real ~/.gemini checkpoint/session json present")
class TestGeminiLive(unittest.TestCase):
    def test_real_data_parses_without_crash(self):
        a = GeminiAdapter()
        total = 0
        for f in REAL_GEMINI:
            for s in a.parse(f):
                self.assertEqual(s.provider, "gemini")
                self.assertTrue(all(t.role in ("user", "assistant") for t in s.turns))
                total += len(s.turns)
        # real session files on this machine carry at least one turn
        self.assertGreater(total, 0)


if __name__ == "__main__":
    unittest.main()
