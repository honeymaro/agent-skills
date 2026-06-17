import tests._path  # noqa: F401
import unittest
from ctk.model import NormalizedSession, Turn
from ctk.collect import (
    filter_by_mode,
    filter_by_contains,
    list_projects,
    output_dict,
    session_summary,
)


def _s(provider, project):
    return NormalizedSession(provider, "id", project, None, [Turn("user", "x")])


class TestCollect(unittest.TestCase):
    def test_all_mode_keeps_everything(self):
        sessions = [_s("a", "/p1"), _s("b", "/p2")]
        self.assertEqual(len(filter_by_mode(sessions, "all", None)), 2)

    def test_current_mode_matches_cwd(self):
        sessions = [_s("a", "/home/u/p1"), _s("b", "/home/u/p2")]
        out = filter_by_mode(sessions, "current", "/home/u/p1")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].project, "/home/u/p1")

    def test_selected_mode_matches_project(self):
        sessions = [_s("a", "/p1"), _s("b", "/p2")]
        out = filter_by_mode(sessions, "selected", "/p2")
        self.assertEqual(len(out), 1)

    def test_list_projects_dedups(self):
        sessions = [_s("a", "/p1"), _s("b", "/p1"), _s("c", "/p2")]
        self.assertEqual(sorted(list_projects(sessions)), ["/p1", "/p2"])

    def test_output_dict_uses_project_leaf_not_full_path(self):
        # Username + full path (PII) dropped; product/repo leaf name kept for context.
        s = _s("claude-code", "/home/dev/projects/acme-web")
        d = output_dict(s)
        self.assertEqual(d["project"], "acme-web")
        self.assertNotIn("dev", d["project"])

    def test_output_dict_leaf_handles_windows_paths(self):
        s = _s("claude-code", "C:\\Users\\dev\\projects\\acme\\app")
        self.assertEqual(output_dict(s)["project"], "app")

    def test_output_dict_none_project_stays_none(self):
        self.assertIsNone(output_dict(_s("x", None))["project"])

    def test_session_summary_fields(self):
        s = NormalizedSession(
            "claude-code", "sid", "/home/dev/projects/acme-web", "2026-03-20T00:00:00Z",
            [Turn("user", "x"), Turn("assistant", "y")],
        )
        m = session_summary(s, "claude-code__sid.json", 123)
        self.assertEqual(m["file"], "claude-code__sid.json")
        self.assertEqual(m["provider"], "claude-code")
        self.assertEqual(m["project"], "acme-web")  # aliased leaf, no path/username
        self.assertEqual(m["started_at"], "2026-03-20T00:00:00Z")
        self.assertEqual(m["turns"], 2)
        self.assertEqual(m["bytes"], 123)

    def test_filter_by_contains(self):
        sessions = [
            _s("a", "C:\\Users\\dev\\projects\\acme\\web"),
            _s("b", "C:\\Users\\dev\\projects\\personal\\toy"),
            _s("c", "C:\\Users\\dev\\projects\\acme\\api"),
        ]
        out = filter_by_contains(sessions, "acme")
        self.assertEqual(len(out), 2)
        # case-insensitive
        self.assertEqual(len(filter_by_contains(sessions, "ACME")), 2)
        # empty substring keeps everything
        self.assertEqual(len(filter_by_contains(sessions, "")), 3)


if __name__ == "__main__":
    unittest.main()
