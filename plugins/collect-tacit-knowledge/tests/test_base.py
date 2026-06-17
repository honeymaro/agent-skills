import tests._path  # noqa: F401
import os
import tempfile
import unittest
from ctk.base import JsonlFileSessionAdapter
from ctk.model import Turn


class _FakeAdapter(JsonlFileSessionAdapter):
    name = "fake"

    def __init__(self, files):
        self._files = files

    def session_files(self):
        return self._files

    def turn_of(self, rec):
        if rec.get("role") in ("user", "assistant"):
            return Turn(role=rec["role"], text=rec.get("text", ""))
        return None

    def project_path(self, path, first):
        return (first or {}).get("cwd")


class TestJsonlBase(unittest.TestCase):
    def _write(self, lines):
        fd, p = tempfile.mkstemp(suffix=".jsonl")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return p

    def test_parses_turns_and_skips_noise_and_bad_lines(self):
        p = self._write([
            '{"role": "user", "text": "hi", "cwd": "/proj"}',
            'NOT JSON',
            '{"role": "system", "text": "ignore me"}',
            '{"role": "assistant", "text": "hello"}',
            '',
        ])
        adapter = _FakeAdapter([p])
        sessions = list(adapter.parse(p))
        self.assertEqual(len(sessions), 1)
        s = sessions[0]
        self.assertEqual([t.role for t in s.turns], ["user", "assistant"])
        self.assertEqual(s.project, "/proj")
        os.unlink(p)

    def test_empty_session_yields_nothing(self):
        p = self._write(['{"role": "system", "text": "x"}'])
        self.assertEqual(list(_FakeAdapter([p]).parse(p)), [])
        os.unlink(p)


if __name__ == "__main__":
    unittest.main()
