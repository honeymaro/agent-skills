import tests._path  # noqa: F401  (puts scripts/ on sys.path)
import unittest
from ctk.model import Turn, NormalizedSession


class TestModel(unittest.TestCase):
    def test_to_dict_roundtrips_turns(self):
        s = NormalizedSession(
            provider="claude-code",
            session_id="abc",
            project="/home/u/proj",
            started_at="2026-06-17T00:00:00Z",
            turns=[Turn(role="user", text="hi"), Turn(role="assistant", text="yo")],
        )
        d = s.to_dict()
        self.assertEqual(d["provider"], "claude-code")
        self.assertEqual(d["turns"], [
            {"role": "user", "text": "hi"},
            {"role": "assistant", "text": "yo"},
        ])

    def test_defaults_empty_turns(self):
        s = NormalizedSession(provider="x", session_id="y", project=None, started_at=None)
        self.assertEqual(s.turns, [])


if __name__ == "__main__":
    unittest.main()
