import io
import json
import tempfile
import unittest
from pathlib import Path

from app import RULE_LABELS, create_app
from detector import inspect_text, redact_text


class DetectorTests(unittest.TestCase):
    def test_finds_email_and_phone(self):
        findings = inspect_text("Contact priya@example.com or (415) 555-0138")
        self.assertEqual([item["type"] for item in findings], ["Email address", "Phone number"])

    def test_redaction_replaces_matches(self):
        text = "Send to priya@example.com"
        self.assertEqual(redact_text(text, inspect_text(text)), "Send to [REDACTED: Email address]")

    def test_credit_card_requires_luhn_check(self):
        self.assertFalse(any(f["type"] == "Credit card number" for f in inspect_text("4111 1111 1111 1112")))
        self.assertTrue(any(f["type"] == "Credit card number" for f in inspect_text("4111 1111 1111 1111")))

    def test_enabled_rules_and_custom_keywords(self):
        findings = inspect_text("Mail team@example.com about Project Aurora", set(), ["Aurora"])
        self.assertEqual([f["type"] for f in findings], ["Custom keyword"])

    def test_private_key_redaction_covers_the_entire_block(self):
        key = "-----BEGIN PRIVATE KEY-----\nFAKE-KEY-MATERIAL\n-----END PRIVATE KEY-----"
        finding = inspect_text(key)
        self.assertEqual(len(finding), 1)
        self.assertEqual(redact_text(key, finding), "[REDACTED: Private key]")


class AppTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmp.name) / "test.sqlite3")
        self.app = create_app({"TESTING": True, "DATABASE": self.db})
        self.client = self.app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def scan(self, text, policy="warn", **extra):
        return self.client.post("/api/scan", json={"content": text, "policy": policy, **extra})

    def test_health_and_default_settings(self):
        self.assertEqual(self.client.get("/api/health").json["status"], "ok")
        settings = self.client.get("/api/settings").json
        self.assertEqual(settings["policy"], "warn")
        self.assertEqual(len(settings["enabled_detectors"]), len(RULE_LABELS))

    def test_homepage_serves_the_backend_connected_ui(self):
        page = self.client.get("/")
        self.assertEqual(page.status_code, 200)
        script = self.client.get("/static/app.js")
        self.assertIn(b"/api/scan", script.data)
        script.close()
        self.assertIn(b"PROTECT THE", page.data)

    def test_warn_records_metadata_without_submitted_content(self):
        response = self.scan("Send to cust-458@example.com")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["outcome"], "Warning")
        audit = self.client.get("/api/audit").json[0]
        self.assertEqual(audit["finding_types"], ["Email address"])
        self.assertNotIn("cust-458@example.com", json.dumps(audit))

    def test_redact_returns_sanitized_text(self):
        response = self.scan("Send to user-123@example.com", "redact")
        self.assertEqual(response.json["outcome"], "Redacted")
        self.assertEqual(response.json["sanitized_text"], "Send to [REDACTED: Email address]")

    def test_block_does_not_return_submitted_content(self):
        response = self.scan("Private cust-199@confidential.invalid", "block")
        self.assertEqual(response.json["outcome"], "Blocked")
        self.assertNotIn("cust-199@confidential.invalid", json.dumps(response.json))

    def test_saved_policy_and_custom_keyword_are_used(self):
        saved = self.client.put("/api/settings", json={
            "policy": "block", "enabled_detectors": [], "custom_keywords": ["Project Nightfall"]
        })
        self.assertEqual(saved.status_code, 200)
        response = self.client.post("/api/scan", json={"content": "Notes on Project Nightfall"})
        self.assertEqual(response.json["outcome"], "Blocked")
        self.assertEqual(response.json["findings"][0]["type"], "Custom keyword")

    def test_settings_persist_after_app_restarts(self):
        self.client.put("/api/settings", json={"policy": "redact", "enabled_detectors": [], "custom_keywords": ["Nightingale"]})
        restarted = create_app({"TESTING": True, "DATABASE": self.db}).test_client()
        self.assertEqual(restarted.get("/api/settings").json["policy"], "redact")
        response = restarted.post("/api/scan", json={"content": "Nightingale plan"})
        self.assertEqual(response.json["outcome"], "Redacted")

    def test_scan_accepts_disabled_detector_list(self):
        response = self.scan("team@example.com", enabled_detectors=[], custom_keywords=[])
        self.assertEqual(response.json["outcome"], "Allowed")

    def test_upload_text_file(self):
        response = self.client.post("/api/scan-file", data={
            "file": (io.BytesIO(b"Contact alex@example.com"), "notes.txt")
        }, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["file_name"], "notes.txt")
        self.assertEqual(response.json["outcome"], "Warning")

    def test_upload_rejects_non_text_files(self):
        response = self.client.post("/api/scan-file", data={
            "file": (io.BytesIO(b"secret"), "notes.pdf")
        }, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 400)

    def test_audit_export_and_clear(self):
        self.scan("No sensitive values here")
        export = self.client.get("/api/audit/export.csv")
        self.assertEqual(export.status_code, 200)
        self.assertIn(b"timestamp_utc,policy,outcome", export.data)
        self.assertEqual(self.client.delete("/api/audit").json, {"cleared": True})
        self.assertEqual(self.client.get("/api/audit").json, [])
        self.assertEqual(self.client.get("/api/stats").json["scan_count"], 0)

    def test_invalid_policy_and_empty_content_are_rejected(self):
        self.assertEqual(self.scan("abc", "destroy").status_code, 400)
        self.assertEqual(self.scan("   ").status_code, 400)


if __name__ == "__main__":
    unittest.main()
