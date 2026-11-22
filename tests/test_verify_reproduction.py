"""Verifier regressions run without network access or published result files."""
import csv
import hashlib
import json
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest

ENTRY = Path(__file__).resolve().parents[1] / "scripts/verify_reproduction.py"
VERIFY = runpy.run_path(str(ENTRY))


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def table_rows():
    return [{"dimension": "dimension", "os": "Android", "category": str(index),
             "count": 5, "n": 500, "paper_percent": 1, "ours_percent": 1,
             "difference_pp": 0, "status": "match"} for index in range(114)]


def write_table(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


class SourceSnapshotTests(unittest.TestCase):
    def test_opt_in_reports_changes_but_requires_exact_current_copy(self):
        previous = {"src/changed.py": "old", "tests/deleted.py": "removed", "src/same.py": "same"}
        current = {"src/changed.py": "new", "tests/added.py": "added", "src/same.py": "same"}
        check = VERIFY["check_source_snapshot"]
        with self.assertRaisesRegex(AssertionError, "allow-source-changes"):
            check(previous, current, current)
        differences = check(previous, current, current, True)
        self.assertEqual(differences, {
            "changed": {"src/changed.py": {"published": "old", "current": "new"}},
            "new": {"tests/added.py": "added"}, "missing": {"tests/deleted.py": "removed"}})
        with self.assertRaisesRegex(AssertionError, "Isolated source hashes differ"):
            check(previous, current, previous, True)
        self.assertEqual(check(current, current, current), {"changed": {}, "new": {}, "missing": {}})

    def test_opt_in_cannot_waive_reference_changes_additions_or_deletions(self):
        check = VERIFY["check_source_snapshot"]
        for previous, current in (({"reference/paper.json": "old"}, {"reference/paper.json": "new"}),
                                  ({}, {"reference/paper.json": "new"}),
                                  ({"reference/paper.json": "old"}, {})):
            with self.subTest(current=current), self.assertRaisesRegex(AssertionError, "cannot waive reference"):
                check(previous, current, current, True)

    def test_copy_includes_root_entries_and_references_but_not_cache_or_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root, copied = Path(directory) / "root", Path(directory) / "copy"
            root.mkdir()
            copied.mkdir()
            for folder in ("src", "scripts", "tests", "reference"):
                (root / folder).mkdir()
            files = {"src/example.py": b"one\r\ntwo\r\n", "scripts/run.py": b"pass\n",
                     "tests/test_example.py": b"pass\n", "reference/paper.json": b"{}\n",
                     "requirements.txt": b"", "SUBMISSION.json": b"{}\n", "SNAPSHOT.json": b"{}\n",
                     "run_weekend_02.py": b"pass\n", "export_contributions.py": b"pass\n",
                     "paper_baselines_weekend_02.json": b"{}\n"}
            for relative, content in files.items():
                (root / relative).write_bytes(content)
            for excluded in ("data/raw/index.html", "results/full/stage_summary.json", "src/__pycache__/cached.pyc"):
                path = root / excluded
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"must not copy")
            VERIFY["copy_project_inputs"](root, copied)
            hashes = VERIFY["source_hashes"](root, True)
            self.assertEqual(hashes, VERIFY["source_hashes"](copied, True))
            self.assertEqual(hashes["src/example.py"], hashlib.sha256(b"one\ntwo\n").hexdigest())
            self.assertEqual(set(hashes), set(files))
            self.assertNotIn("run_weekend_02.py", VERIFY["source_hashes"](root))
            for excluded in ("data", "results", "src/__pycache__"):
                self.assertFalse((copied / excluded).exists())

    def test_help_explains_opt_in_and_output_directory_from_external_cwd(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, str(ENTRY), "--help"], cwd=directory,
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(list(Path(directory).iterdir()))
        for expected in ("--output-dir", "--allow-source-changes", "current source", "remain strict"):
            self.assertIn(expected, " ".join(result.stdout.split()))


class WeekendResultVerificationTests(unittest.TestCase):
    def test_table_rejects_missing_duplicate_and_nonmatching_comparisons(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "table.csv"
            rows = table_rows()
            write_table(path, rows)
            expected = VERIFY["table_ii_values"](path)
            write_table(path, list(reversed(rows)))
            self.assertEqual(VERIFY["table_ii_values"](path), expected)
            duplicate = [*rows[:-1], rows[0]]
            mismatch = [dict(row) for row in rows]
            mismatch[0]["status"] = "mismatch"
            for broken in (rows[:-1], duplicate, mismatch):
                with self.subTest(kind=len(broken)):
                    write_table(path, broken)
                    with self.assertRaises(AssertionError):
                        VERIFY["table_ii_values"](path)

    def test_verifier_checks_actual_run_values_digests_tables_and_input(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            result = {"univariate": {"example": 114}, "repairs": {"example": 5}}
            digest = VERIFY["digest"](result)
            summary = {"analysis": "weekend_02", "status": "computationally_complete", "runs": 3,
                       "table_ii_cells": 114, "table_ii_matches": 114,
                       "repeatability": {"semantic_result_sha256": digest, "identical_semantic_outputs": True}}
            write_json(output / "stage_summary.json", summary)
            write_json(output / "source_provenance.json", {"source_sha256_lf": "pinned", "acquisition_mode": "downloaded"})
            write_json(output / "figure_manifest.json", [])
            write_table(output / "tables/table_ii.csv", table_rows())
            expected_table = VERIFY["table_ii_values"](output / "tables/table_ii.csv")
            log = {"semantic_result_sha256": digest, "records": 1500, "source_sha256_lf": "pinned"}
            for index in range(1, 4):
                run = output / "runs" / f"run_{index:02d}"
                write_json(run / "results.json", result)
                write_json(run / "run_log.json", log)
                write_table(run / "tables/table_ii.csv", table_rows())
                for filename in ("repair_distributions.csv", "repair_claim_checks.csv"):
                    (run / "tables" / filename).write_bytes(b"same repair values\n")
                    (output / "tables" / filename).write_bytes(b"same repair values\n")
            inspect = lambda: VERIFY["inspect_weekend_output"](output, expected_table, result, "pinned", "downloaded")
            self.assertTrue(inspect()["matches_published_core_table_ii"])
            second = output / "runs/run_02"
            write_json(second / "results.json", {"univariate": {"changed": 1}})
            with self.assertRaisesRegex(AssertionError, "per-run values"):
                inspect()
            write_json(second / "results.json", result)
            for field, invalid in (("semantic_result_sha256", "incorrect"), ("records", 1499), ("source_sha256_lf", "different")):
                with self.subTest(field=field):
                    write_json(second / "run_log.json", {**log, field: invalid})
                    with self.assertRaises(AssertionError):
                        inspect()
            write_json(second / "run_log.json", log)
            changed_rows = table_rows()
            changed_rows[0]["count"] = 6
            write_table(second / "tables/table_ii.csv", changed_rows)
            with self.assertRaisesRegex(AssertionError, "per-run Table II"):
                inspect()


if __name__ == "__main__":
    unittest.main()
