import tests._path  # noqa: F401
import os
import unittest
from ctk.providers.antigravity import AntigravityAdapter

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "antigravity_session.jsonl")


class TestAntigravity(unittest.TestCase):
    def test_parses_user_assistant_turns(self):
        s = list(AntigravityAdapter().parse(FIXTURE))[0]
        self.assertEqual(s.provider, "antigravity")
        # model -> assistant, assistant -> assistant; tool_call dropped
        self.assertEqual([t.role for t in s.turns], ["user", "assistant", "assistant"])

    def test_masks_secret_and_drops_tool_noise(self):
        s = list(AntigravityAdapter().parse(FIXTURE))[0]
        joined = "\n".join(t.text for t in s.turns)
        self.assertNotIn("sk-ABCDEF0123456789", joined)
        self.assertNotIn("command", joined)
        self.assertIn("checkpoints", joined)

    def test_no_brain_dir_detects_nothing_gracefully(self):
        # detect() must not raise when no Antigravity install/brain dir exists
        self.assertIsInstance(AntigravityAdapter().detect(), list)


if __name__ == "__main__":
    unittest.main()
