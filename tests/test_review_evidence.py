"""Regression checks for false-positive patch evidence and nested packaging."""
import base64
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/audit_review_evidence.py"
SPEC = importlib.util.spec_from_file_location("audit_review_evidence", SCRIPT)
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)

DIFF = b"--- a/file.c\n+++ b/file.c\n@@ -1 +1 @@ func\n-old\n+new\n"


class Response:
    def __init__(self, body, url="https://example.org/patch", content_type="text/plain"):
        self.body = body
        self.url = url
        self.status = 200
        self.headers = {"Content-Type": content_type}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size):
        return self.body[:size]


class EvidenceTests(unittest.TestCase):
    def row(self, url="https://example.org/patch", bug_id="case"):
        return {"os": "Linux", "bug_id": bug_id, "patch": url, "involved_functions": "0"}

    def test_gitiles_query_and_encoding(self):
        url, encoding = audit.retrieval_url("https://android.googlesource.com/repo/+/abc%5E%21/?x=1")
        self.assertIn("x=1&format=TEXT", url)
        self.assertEqual(encoding, "base64")
        self.assertEqual(audit.retrieval_url("https://example.org/patch"), ("https://example.org/patch", "identity"))

    def test_http_200_login_redirect_is_not_evidence(self):
        response = Response(b"<!DOCTYPE html><html><title>login</title></html>",
                            "https://gitee.com/login?redirect_to_url=patch", "text/html")
        with tempfile.TemporaryDirectory() as tmp, patch.object(audit, "urlopen", return_value=response):
            result = audit.fetch_one(self.row(), Path(tmp), 1)
        self.assertEqual(result["http_status"], 200)
        self.assertEqual(result["status"], "unconfirmed")
        self.assertEqual(result["content_kind"], "html_login_or_site_page")
        self.assertIn("/login", result["final_url"])

    def test_encoded_diff_hashes_both_transport_and_content(self):
        body = base64.b64encode(DIFF)
        with tempfile.TemporaryDirectory() as tmp, patch.object(audit, "urlopen", return_value=Response(body)):
            result = audit.fetch_one(self.row("https://android.googlesource.com/repo/+/abc%5E%21/"), Path(tmp), 1)
            self.assertEqual((Path(tmp) / "case.decoded").read_bytes(), DIFF)
        self.assertEqual(result["status"], "confirmed_diff")
        self.assertNotEqual(result["response_sha256"], result["decoded_sha256"])

    def test_corrupt_base64_cannot_be_marked_confirmed(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(audit, "urlopen", return_value=Response(b"invalid$$")):
            result = audit.fetch_one(self.row("https://android.googlesource.com/repo/+/abc%5E%21/"), Path(tmp), 1)
        self.assertEqual(result["status"], "unconfirmed")
        self.assertIn("decode failed", result["error"])

    def test_nested_diff_is_separate_from_packaging_hunks(self):
        body = b"--- a/debian/patches/fix\n+++ b/debian/patches/fix\n@@ -0,0 +1,5 @@\n+--- a/file.c\n++++ b/file.c\n+@@ -1 +1 @@\n+-old\n++new\n"
        result = audit.inspect_body(body)
        self.assertEqual(result["changed_files"], ["b/debian/patches/fix"])
        self.assertEqual(result["hunk_count"], 1)
        self.assertEqual(result["nested_changed_files"], ["b/file.c"])
        self.assertEqual(result["nested_hunk_count"], 1)

    def test_deleted_file_is_still_a_changed_file(self):
        result = audit.inspect_body(b"--- a/deleted.c\n+++ /dev/null\n@@ -1 +0,0 @@\n-old\n")
        self.assertEqual(result["changed_files"], ["a/deleted.c"])
        self.assertEqual(result["content_kind"], "unified_diff")

    def test_headers_without_hunks_are_unconfirmed(self):
        self.assertEqual(audit.inspect_body(b"--- a/a\n+++ b/a\n")["content_kind"], "unrecognized_text")

    def test_cve_rejection_retained_without_inventing_description(self):
        body = json.dumps({"cveMetadata": {"cveId": "CVE-2023-52756", "state": "REJECTED"},
                           "containers": {"cna": {"rejectedReasons": [{"lang": "en", "value": "Withdrawn"}]}}}).encode()
        with tempfile.TemporaryDirectory() as tmp, patch.object(audit, "urlopen", return_value=Response(body)):
            records = audit.fetch_cve_records([self.row(bug_id="CVE-2023-52756")], Path(tmp), 1)
        self.assertEqual(records[0]["cve_metadata"]["state"], "REJECTED")
        self.assertEqual(records[0]["title"], "")

    def test_wrong_cve_identifier_is_not_confirmed(self):
        body = json.dumps({"cveMetadata": {"cveId": "CVE-2023-0000"}}).encode()
        with tempfile.TemporaryDirectory() as tmp, patch.object(audit, "urlopen", return_value=Response(body)):
            records = audit.fetch_cve_records([self.row(bug_id="CVE-2023-52756")], Path(tmp), 1)
        self.assertEqual(records[0]["status"], "unconfirmed")


if __name__ == "__main__":
    unittest.main()
