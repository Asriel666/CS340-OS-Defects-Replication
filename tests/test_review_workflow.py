import csv
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from osdefects.common import write_csv
from osdefects.data import CANONICAL_CATEGORIES
from osdefects.review_workflow import FIELDS, FORM_FIELDS, prepare_review_materials, read_rows, validate_review_sample, validate_reviews


def sample():
    return [{"os": os_name, "bug_id": str(index), "patch": "https://example.org/" + os_name + str(index),
             **{"paper_" + field: CANONICAL_CATEGORIES[field][0] for field in FIELDS}}
            for os_name in ("Android", "Linux", "HarmonyOS") for index in range(4)]


class ReviewPreparationTests(unittest.TestCase):
    def test_blind_forms_have_no_answers_and_reruns_preserve_written_work(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_csv(root / "evidence.csv", sample())
            prepare_review_materials(root / "evidence.csv", root)
            form = root / "blind/reviewer_A.csv"
            rows = read_rows(form)
            self.assertEqual(set(rows[0]), set(FORM_FIELDS))
            self.assertFalse(any("paper" in key or "fill_after" in key for key in rows[0]))
            rows[0]["notes"] = "A student's ongoing notes must survive reruns."
            write_csv(form, rows)
            before = form.read_bytes()
            prepare_review_materials(root / "evidence.csv", root)
            self.assertEqual(form.read_bytes(), before)
            self.assertEqual(len(read_rows(root / "coordinator/author_labels.csv")), 12)

    def test_different_existing_sample_is_rejected_before_any_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_csv(root / "evidence.csv", sample())
            prepare_review_materials(root / "evidence.csv", root)
            changed = sample()
            changed[0]["bug_id"] = "different"
            write_csv(root / "evidence.csv", changed)
            with self.assertRaises(ValueError):
                prepare_review_materials(root / "evidence.csv", root)


class ReviewInputTests(unittest.TestCase):
    def test_duplicate_headers_are_rejected_before_dictreader_can_discard_a_value(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "duplicate.csv"
            with path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.writer(stream)
                writer.writerow(["your_os_layer", "os", "bug_id", "your_os_layer"])
                writer.writerow(["INVALID_SHOULD_NOT_DISAPPEAR", "Android", "one", "Kernel"])
            with self.assertRaisesRegex(ValueError, "headers"):
                read_rows(path)

    def test_blank_whitespace_or_absent_headers_and_ragged_rows_are_rejected(self):
        payloads = ["", "os,,bug_id\nAndroid,x,one\n", "os, bug_id\nAndroid,one\n",
                    "os,bug_id\nAndroid\n", "os,bug_id\nAndroid,one,extra\n"]
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "invalid.csv"
            for payload in payloads:
                path.write_text(payload, encoding="utf-8")
                with self.subTest(payload=payload), self.assertRaises(ValueError):
                    read_rows(path)

    def test_sample_and_patch_must_match_original_evidence(self):
        source = sample()
        cases = [{"os": row["os"], "bug_id": row["bug_id"], "patch_url": row["patch"]} for row in source]
        validate_review_sample(cases, source)
        validate_review_sample(list(reversed(cases)), source)
        variants = [cases[1:]]
        for field, value in (("bug_id", "substituted"), ("patch_url", "https://example.org/changed"), ("answer", "Kernel")):
            changed = copy.deepcopy(cases)
            changed[0][field] = value
            variants.append(changed)
        for changed in variants:
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                validate_review_sample(changed, source)
        with self.assertRaisesRegex(ValueError, "four sampled defects"):
            validate_review_sample(cases[1:], source[1:])

    def test_cli_rejects_jointly_shrunken_cases_and_forms_without_overwriting_status(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            evidence = root / "evidence.csv"
            write_csv(evidence, sample())
            prepare_review_materials(evidence, root)
            status = root / "status.json"
            command = [sys.executable, str(Path(__file__).resolve().parents[1] / "scripts/manage_review.py"),
                       "check", "--materials", str(root), "--evidence", str(evidence), "--output", str(status)]
            completed = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(json.loads(status.read_text(encoding="utf-8"))["sample_size"], 12)
            before = status.read_bytes()
            for name in ("cases.csv", "reviewer_A.csv", "reviewer_B.csv"):
                path = root / "blind" / name
                write_csv(path, read_rows(path)[1:])
            completed = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("original twelve-case", completed.stderr)
            self.assertEqual(status.read_bytes(), before)


class ReviewValidationTests(unittest.TestCase):
    def setUp(self):
        self.cases = [{"os": "Android", "bug_id": "one", "patch_url": "https://example.org/patch"}]
        self.forms = {reviewer: [{**dict.fromkeys(FORM_FIELDS, ""), **self.cases[0], "reviewer": reviewer}]
                      for reviewer in ("A", "B")}

    def check(self):
        return validate_reviews(self.cases, self.forms["A"], self.forms["B"])

    def fill(self):
        for reviewer, rows in self.forms.items():
            rows[0].update(reviewer_name="Person " + reviewer, reviewed_on="2026-11-14",
                           evidence_urls="https://example.org/evidence", notes="Observed in the patch.")
            rows[0].update({"your_" + field: CANONICAL_CATEGORIES[field][0] for field in FIELDS})

    def test_empty_forms_are_pending_with_undefined_agreement(self):
        result = self.check()
        self.assertEqual(result["status"], "pending_human_review")
        self.assertEqual(result["reviewers"]["A"]["submitted_cases"], 0)
        self.assertIsNone(result["agreement"]["os_layer"]["agreement_fraction"])

    def test_missing_evidence_does_not_count_as_submission(self):
        self.fill()
        self.forms["A"][0]["evidence_urls"] = ""
        self.assertEqual(self.check()["reviewers"]["A"]["submitted_cases"], 0)

    def test_malformed_evidence_urls_never_make_confirmed_judgments_eligible(self):
        self.fill()
        invalid = ["https://", "http://#fragment", "https:///path", "ftp://example.org/file",
                   "https://exa mple.org", "https://example.org:wrong/path", "https://example.org:99999/path",
                   "https://.example.org", "https://example..org", "https://-example.org"]
        for url in invalid:
            self.forms["A"][0]["evidence_urls"] = url
            with self.subTest(url=url):
                result = self.check()
                self.assertEqual(result["status"], "pending_human_review")
                self.assertEqual(result["reviewers"]["A"]["submitted_cases"], 0)
                self.assertEqual(result["agreement"]["os_layer"]["eligible_pairs"], 0)

    def test_multiple_well_formed_evidence_urls_are_accepted_without_network_claim(self):
        self.fill()
        self.forms["A"][0]["evidence_urls"] = "https://example.org/one; http://example.net:8080/two"
        result = self.check()
        self.assertEqual(result["status"], "ready_for_adjudication")
        self.assertEqual(result["agreement"]["os_layer"]["eligible_pairs"], 1)

    def test_all_unconfirmed_does_not_excuse_malformed_provided_url(self):
        self.fill()
        self.forms["A"][0].update({"your_" + field: "unconfirmed" for field in FIELDS})
        self.forms["A"][0]["evidence_urls"] = "https://"
        self.assertEqual(self.check()["reviewers"]["A"]["submitted_cases"], 0)

    def test_unconfirmed_excluded_and_disagreement_retained(self):
        self.fill()
        self.forms["B"][0]["your_trigger_scenario"] = "unconfirmed"
        self.forms["B"][0]["your_os_layer"] = CANONICAL_CATEGORIES["os_layer"][1]
        result = self.check()
        self.assertEqual(result["status"], "ready_for_adjudication")
        self.assertEqual(result["agreement"]["os_layer"]["agreement_fraction"], 0)
        self.assertIsNone(result["agreement"]["trigger_scenario"]["agreement_fraction"])
        self.assertEqual(len(result["disagreements"]), 1)
        self.assertFalse(result["adjudication_complete"])

    def test_all_unconfirmed_requires_reason_but_can_be_recorded_without_url(self):
        self.fill()
        for row in (self.forms["A"][0], self.forms["B"][0]):
            row.update({"your_" + field: "unconfirmed" for field in FIELDS})
            row["evidence_urls"] = ""
            row["notes"] = "URL was unavailable; no judgment made."
        result = self.check()
        self.assertEqual(result["status"], "ready_for_adjudication")
        self.assertEqual(result["reviewers"]["A"]["fully_confirmed_cases"], 0)

    def test_invalid_labels_duplicate_ids_and_same_person_are_rejected(self):
        self.fill()
        original = copy.deepcopy(self.forms)
        self.forms["A"][0]["your_os_layer"] = "Typo"
        with self.assertRaises(ValueError): self.check()
        self.forms = copy.deepcopy(original)
        self.forms["B"].append(copy.deepcopy(self.forms["B"][0]))
        with self.assertRaises(ValueError): self.check()
        self.forms = copy.deepcopy(original)
        self.forms["B"][0]["reviewer_name"] = "Person A"
        with self.assertRaises(ValueError): self.check()

    def test_answer_columns_cannot_be_silently_added_to_blind_forms(self):
        self.forms["A"][0]["paper_os_layer"] = "Kernel"
        with self.assertRaises(ValueError): self.check()


if __name__ == "__main__":
    unittest.main()
