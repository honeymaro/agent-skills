import tests._path  # noqa: F401
import unittest
from ctk.registry import all_adapters, supported_adapters
from ctk.providers.claude_code import ClaudeCodeAdapter


class TestRegistry(unittest.TestCase):
    def test_includes_claude_code(self):
        names = {a.name for a in all_adapters()}
        self.assertIn("claude-code", names)

    def test_supported_excludes_unsupported(self):
        for a in supported_adapters():
            self.assertTrue(a.supported())


if __name__ == "__main__":
    unittest.main()
