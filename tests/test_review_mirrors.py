"""Offline integrity tests for mirror evidence; no network access."""
import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location("check_review_mirrors", Path(__file__).resolve().parents[1] / "scripts/check_review_mirrors.py")
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


class MirrorEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.sha = "a" * 40
        self.patch_body = (f"From {self.sha} Mon Sep 17 00:00:00 2001\n"
                           "Subject: example\n\ndiff --git a/x.c b/x.c\nindex 1234567..abcdef0 100644\n"
                           "--- a/x.c\n+++ b/x.c\n@@ -1 +1,2 @@ fn()\n-old\n+new\n+next\n-- \n2.0\n").encode()
        self.patch = audit.parse_patch(self.patch_body)
        self.commit = {"sha": self.sha, "parents": [{"sha": "b" * 40}],
                       "files": [{"filename": "x.c", "additions": 2, "deletions": 1}]}
        self.blobs = [{"current_sha_matches_api": True, "current_sha_matches_patch": True, "parent_sha_matches_patch": True}]

    def verify(self, requested=None):
        return audit.verify_identity(requested or self.sha, self.commit, self.patch, self.blobs)

    def test_git_blob_hash_uses_object_framing(self):
        self.assertEqual(audit.git_blob_sha(b""), "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391")

    def test_full_sha_patch_and_blob_checks(self):
        self.assertEqual(self.verify()["identity_level"], "full_original_sha")
        self.assertEqual((self.patch["additions"], self.patch["deletions"], self.patch["hunks"]), (2, 1, 1))

    def test_abbreviation_is_disclosed(self):
        self.assertEqual(self.verify(self.sha[:12])["identity_level"], "original_prefix_resolved")

    def test_mismatching_original_sha_rejected(self):
        self.assertEqual(self.verify("c" * 40)["status"], "unconfirmed")

    def test_login_page_is_not_patch(self):
        self.patch = audit.parse_patch(b"<html><title>Sign in</title></html>")
        self.assertEqual(self.verify()["status"], "unconfirmed")

    def test_other_commit_patch_rejected(self):
        self.patch["from_sha"] = "c" * 40
        self.assertEqual(self.verify()["status"], "unconfirmed")

    def test_file_mismatch_rejected(self):
        self.patch["files"] = ["other.c"]
        self.assertEqual(self.verify()["status"], "unconfirmed")

    def test_missing_parent_or_blobs_rejected(self):
        self.commit["parents"] = []
        self.assertEqual(self.verify()["status"], "unconfirmed")
        self.commit["parents"] = [{"sha": "b" * 40}]
        self.blobs = []
        self.assertEqual(self.verify()["status"], "unconfirmed")

    def test_bad_parent_blob_rejected(self):
        self.blobs[0]["parent_sha_matches_patch"] = False
        self.assertEqual(self.verify()["status"], "unconfirmed")

    def test_statistics_disagreement_rejected(self):
        self.patch["additions"] = 3
        self.assertEqual(self.verify()["status"], "unconfirmed")


if __name__ == "__main__":
    unittest.main()
