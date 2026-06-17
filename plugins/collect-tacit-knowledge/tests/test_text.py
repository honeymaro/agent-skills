import tests._path  # noqa: F401
import unittest
from ctk.text import extract_text, strip_code_blocks, mask_secrets, clean


class TestText(unittest.TestCase):
    def test_extract_from_string(self):
        self.assertEqual(extract_text("hello"), "hello")

    def test_extract_from_blocks_keeps_only_text(self):
        content = [
            {"type": "text", "text": "do the thing"},
            {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}},
            {"type": "tool_result", "content": "huge file dump"},
            {"type": "thinking", "thinking": "secret reasoning"},
        ]
        self.assertEqual(extract_text(content), "do the thing")

    def test_strip_long_code_block(self):
        code = "```python\n" + ("x = 1\n" * 50) + "```"
        out = strip_code_blocks(code, max_chars=40)
        self.assertIn("[code omitted]", out)
        self.assertNotIn("x = 1", out)

    def test_keep_short_inline_snippet(self):
        text = "use `pnpm i` to install"
        self.assertEqual(strip_code_blocks(text, max_chars=40), text)

    def test_mask_api_key(self):
        out = mask_secrets("key sk-ABCDEF0123456789ABCDEF0123 done")
        self.assertNotIn("ABCDEF0123456789", out)
        self.assertIn("[redacted]", out)

    def test_mask_env_assignment(self):
        out = mask_secrets("SECRET_TOKEN=hunter2supersecretvalue")
        self.assertNotIn("hunter2supersecretvalue", out)

    def test_clean_composes_strip_and_mask(self):
        # code block must exceed clean()'s default 200-char threshold to be omitted
        text = "AWS_SECRET=abcd1234abcd1234abcd\n```\n" + ("y\n" * 200) + "```"
        out = clean(text)
        self.assertNotIn("abcd1234abcd1234abcd", out)
        self.assertIn("[code omitted]", out)

    def test_mask_github_pat(self):
        out = mask_secrets("token github_pat_" + "A" * 40 + " end")
        self.assertNotIn("AAAAAAAA", out)
        self.assertIn("[redacted]", out)

    def test_mask_json_style_secret(self):
        out = mask_secrets('{"password": "hunter2supersecretvalue"}')
        self.assertNotIn("hunter2supersecretvalue", out)

    def test_mask_connection_string_credentials(self):
        out = mask_secrets("db at postgres://admin:hunter2pw@host:5432/app")
        self.assertNotIn("hunter2pw", out)
        self.assertNotIn("admin:hunter2pw", out)


if __name__ == "__main__":
    unittest.main()
