"""Offline regressions for the weekly RQ1 deliverable.

Run with: py -3.11 -m unittest discover -s tests -v
All source acquisitions are mocked; these tests never need the author website.
"""

import copy
import csv
import hashlib
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from osdefects import data
from osdefects.univariate import OS_ORDER, analyze_univariate, distribution


def example_records(per_os=500):
    """Structurally valid synthetic records, with IDs scoped to each OS."""
    records = []
    for os_name in OS_ORDER:
        for index in range(per_os):
            record = {
                "os": os_name,
                "bug_id": str(index),
                "patch": "https://example.invalid/patch/" + str(index),
                "line_deletions": 0,
                "line_additions": 1,
                "line_changes": 1,
                "involved_functions": 1,
                "modified_files": 1,
            }
            for field, categories in data.CANONICAL_CATEGORIES.items():
                record[field] = [categories[0]] if field == "code_level" else categories[0]
            records.append(record)
    return records


def example_reference():
    """A complete synthetic baseline whose mass is in the first category."""
    dimensions = {}
    for field, categories in data.CANONICAL_CATEGORIES.items():
        dimensions[field] = {
            "categories": list(categories),
            "multilabel": field == "code_level",
            "table_ii_percent": {
                os_name: [100.0] + [0.0] * (len(categories) - 1)
                for os_name in OS_ORDER
            },
        }
    return {"dimensions": dimensions}


class SourceIntegrityTests(unittest.TestCase):
    def test_pinned_hash_is_for_the_unmodified_author_source(self):
        # Regression: the old digest described an extra trailing newline.
        self.assertEqual(
            data.SOURCE_SHA256_LF,
            "3794ff8c39e975ff457f264cb863f6e191297614dc0273f04c09ac654962eed5",
        )

    def test_fresh_lf_and_crlf_downloads_have_the_same_verified_digest(self):
        canonical = b"first line\nlast line"
        digest = hashlib.sha256(canonical).hexdigest()
        for payload in (canonical, canonical.replace(b"\n", b"\r\n")):
            with self.subTest(payload=payload), tempfile.TemporaryDirectory() as directory:
                target = Path(directory) / "source.js"
                with patch.object(data, "SOURCE_SHA256_LF", digest), patch.object(
                    data, "urlopen", return_value=io.BytesIO(payload)
                ) as network:
                    metadata = data.fetch_source(target)
                self.assertEqual(target.read_bytes(), canonical)
                self.assertEqual(metadata["source_sha256_lf"], digest)
                self.assertEqual(metadata["acquisition_mode"], "downloaded")
                self.assertIsNotNone(metadata["retrieved_at_utc"])
                network.assert_called_once()

    def test_corruption_and_extra_trailing_newline_are_rejected_before_caching(self):
        canonical = b"first line\nlast line"
        digest = hashlib.sha256(canonical).hexdigest()
        for payload in (b"changed source", canonical + b"\n"):
            with self.subTest(payload=payload), tempfile.TemporaryDirectory() as directory:
                target = Path(directory) / "source.js"
                with patch.object(data, "SOURCE_SHA256_LF", digest), patch.object(
                    data, "urlopen", return_value=io.BytesIO(payload)
                ), self.assertRaisesRegex(ValueError, "checksum mismatch"):
                    data.fetch_source(target)
                self.assertFalse(target.exists())
                self.assertFalse(target.with_suffix(".provenance.json").exists())

    def test_offline_cache_is_verified_without_inventing_a_download_timestamp(self):
        canonical = b"first line\nlast line"
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "source.js"
            target.write_bytes(canonical)
            with patch.object(data, "SOURCE_SHA256_LF", hashlib.sha256(canonical).hexdigest()), patch.object(
                data, "urlopen"
            ) as network:
                metadata = data.fetch_source(target, offline=True)
                self.assertEqual(metadata["acquisition_mode"], "verified_cache")
                self.assertIsNone(metadata["retrieved_at_utc"])
                target.write_bytes(canonical + b"\n")
                with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                    data.fetch_source(target, offline=True)
                network.assert_not_called()

    def test_missing_offline_cache_never_attempts_a_download(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(data, "urlopen") as network:
            with self.assertRaises(FileNotFoundError):
                data.fetch_source(Path(directory) / "missing.js", offline=True)
            network.assert_not_called()


class DatasetValidationTests(unittest.TestCase):
    def test_ids_are_unique_within_each_os(self):
        records = example_records()
        result = data.validate_records(records)
        self.assertEqual(result["record_count"], 1500)
        self.assertEqual(result["unique_os_bug_ids"], 1500)
        # The same text ID in different OSes is legitimate; a duplicate in one is not.
        records[1]["bug_id"] = records[0]["bug_id"]
        with self.assertRaisesRegex(ValueError, "Duplicate OS/bug ID"):
            data.validate_records(records)

    def test_unknown_single_and_multi_label_categories_are_rejected(self):
        for field, value in (("os_layer", "UnpublishedLayer"), ("code_level", ["UnpublishedCode"])):
            with self.subTest(field=field):
                records = example_records()
                records[0][field] = value
                with self.assertRaises(ValueError):
                    data.validate_records(records)

    def test_missing_os_record_is_rejected(self):
        records = example_records()
        records.pop()
        with self.assertRaisesRegex(ValueError, "500 records per OS"):
            data.validate_records(records)


class DistributionTests(unittest.TestCase):
    def test_multilabel_denominator_is_defects_not_number_of_labels(self):
        records = [{"code_level": ["Call", "If"]}, {"code_level": ["Call"]}]
        counts, percentages = distribution(records, "code_level", ["Call", "If", "Loop"], multilabel=True)
        self.assertEqual(counts, [2, 1, 0])
        self.assertEqual(percentages, [100.0, 50.0, 0.0])
        self.assertEqual(sum(percentages), 150.0)

    def test_repeated_label_cannot_double_count_one_defect(self):
        with self.assertRaises(ValueError):
            distribution([{"code_level": ["Call", "Call"]}], "code_level", ["Call"], multilabel=True)


class ReferenceValidationTests(unittest.TestCase):
    def assert_reference_rejected(self, reference):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                analyze_univariate(example_records(per_os=1), reference, directory)
            self.assertFalse((Path(directory) / "table_ii.csv").exists())

    def test_complete_reference_preserves_all_114_cells_including_zeroes(self):
        with tempfile.TemporaryDirectory() as directory:
            result = analyze_univariate(example_records(per_os=1), example_reference(), directory)
            self.assertEqual(result["cell_count"], 114)
            self.assertEqual(result["matched_cells"], 114)
            self.assertEqual(result["mismatches"], [])
            with (Path(directory) / "table_ii.csv").open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 114)
            self.assertTrue(any(float(row["paper_percent"]) == 0 for row in rows))

    def test_short_or_long_reference_vector_cannot_be_silently_truncated_by_zip(self):
        for extra in (-1, 1):
            with self.subTest(extra=extra):
                reference = example_reference()
                percentages = reference["dimensions"]["os_layer"]["table_ii_percent"]["Android"]
                if extra == -1:
                    percentages.pop()
                else:
                    percentages.append(0.0)
                self.assert_reference_rejected(reference)

    def test_missing_os_vector_is_rejected(self):
        reference = example_reference()
        del reference["dimensions"]["os_layer"]["table_ii_percent"]["Linux"]
        self.assert_reference_rejected(reference)

    def test_missing_unknown_and_reordered_categories_are_rejected(self):
        original = example_reference()
        for defect in ("missing", "unknown", "reordered"):
            with self.subTest(defect=defect):
                reference = copy.deepcopy(original)
                spec = reference["dimensions"]["os_layer"]
                if defect == "missing":
                    spec["categories"].pop()
                    for percentages in spec["table_ii_percent"].values():
                        percentages.pop()
                elif defect == "unknown":
                    spec["categories"][-1] = "UnpublishedLayer"
                else:
                    spec["categories"].reverse()
                self.assert_reference_rejected(reference)

    def test_multilabel_policy_cannot_change_the_denominator_or_field_type(self):
        for field, invalid in (("code_level", False), ("os_layer", True), ("code_level", "true")):
            with self.subTest(field=field, invalid=invalid):
                reference = example_reference()
                reference["dimensions"][field]["multilabel"] = invalid
                self.assert_reference_rejected(reference)

    def test_nonfinite_percentages_are_rejected(self):
        for invalid in (float("nan"), float("inf")):
            with self.subTest(invalid=invalid):
                reference = example_reference()
                reference["dimensions"]["os_layer"]["table_ii_percent"]["Android"][0] = invalid
                self.assert_reference_rejected(reference)


class CommandLineTests(unittest.TestCase):
    def run_cli(self, *arguments):
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "run_stage.py"), *arguments],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )

    def test_help_exposes_rq1_and_retains_stage_entry(self):
        result = self.run_cli("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        for flag in ("--analysis", "rq1", "--stage", "--offline", "--no-plots"):
            self.assertIn(flag, result.stdout)

    def test_invalid_or_ambiguous_scope_fails_before_any_run(self):
        for arguments in (
            ("--analysis", "rq2"),
            ("--analysis", "rq1", "--runs", "0"),
            ("--analysis", "rq1", "--stage", "1"),
        ):
            with self.subTest(arguments=arguments):
                result = self.run_cli(*arguments)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertIn("error:", result.stderr)
                self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
