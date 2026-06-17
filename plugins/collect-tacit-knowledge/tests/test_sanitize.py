import tests._path  # noqa: F401
import unittest
from ctk.sanitize import find_leaks, mask_report


class TestSanitize(unittest.TestCase):
    def test_finds_email_key_ip(self):
        text = "contact a@b.com via 10.0.0.5 with sk-ABCDEF0123456789ABCDEF0123"
        kinds = {f["kind"] for f in find_leaks(text)}
        self.assertIn("email", kinds)
        self.assertIn("ip", kinds)
        self.assertIn("secret", kinds)

    def test_known_names_flagged(self):
        text = "We used the AcmeCorp internal API."
        kinds = {f["kind"] for f in find_leaks(text, known_names=["AcmeCorp"])}
        self.assertIn("known-name", kinds)

    def test_mask_replaces_all(self):
        text = "a@b.com and AcmeCorp"
        masked = mask_report(text, known_names=["AcmeCorp"])
        self.assertNotIn("a@b.com", masked)
        self.assertNotIn("AcmeCorp", masked)
        self.assertEqual(find_leaks(masked, known_names=["AcmeCorp"]), [])

    def test_clean_report_has_no_findings(self):
        self.assertEqual(find_leaks("Use OPFS for big numeric caches."), [])

    def test_finds_and_masks_ipv6(self):
        text = "host fe80::1ff:fe23:4567:890a here"
        findings = find_leaks(text)
        self.assertIn("ip", {f["kind"] for f in findings})
        masked = mask_report(text)
        self.assertNotIn("fe80::1ff:fe23:4567:890a", masked)
        self.assertEqual(find_leaks(masked), [])


if __name__ == "__main__":
    unittest.main()
