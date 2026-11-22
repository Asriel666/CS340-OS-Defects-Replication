"""Regressions for the root-level Week 2 compatibility entry.

The subprocess help check is unmocked. The full runpy entry check mocks only
acquisition/records so fresh checkouts need neither the network nor an ignored
data cache; it performs all statistical calculations and file writes normally.
Pinned-payload rejection is covered by test_rq1.SourceIntegrityTests.
"""
import contextlib
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "run_weekend_02.py"
sys.path.insert(0, str(ROOT / "src"))

from osdefects import data
from osdefects.common import OS_ORDER, semantic_digest

validate_output_directory = runpy.run_path(str(ENTRY))["validate_output_directory"]


def fixture_records():
    records = []
    for os_name in OS_ORDER:
        for index in range(500):
            record = {"os": os_name, "bug_id": str(index), "line_changes": 1,
                      "involved_functions": 1, "modified_files": 1}
            record.update({field: [values[0]] if field == "code_level" else values[0]
                           for field, values in data.CANONICAL_CATEGORIES.items()})
            records.append(record)
    return records


class Weekend02EntryTests(unittest.TestCase):
    def test_help_runs_from_external_cwd_with_all_supported_flags(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, str(ENTRY), "--help"], cwd=directory,
                                    capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        for flag in ("--offline", "--runs", "--output-dir", "--no-plots"):
            self.assertIn(flag, result.stdout)

    def test_real_entry_uses_repository_paths_and_external_output_with_no_plots(self):
        reference_path = ROOT / "paper_baselines_weekend_02.json"
        original_reference = json.loads(reference_path.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            output = directory / "clean-output"
            invocation = [str(ENTRY), "--offline", "--no-plots", "--output-dir", "clean-output"]
            original_cwd = Path.cwd()
            try:
                os.chdir(directory)
                with patch.object(sys, "argv", invocation), contextlib.redirect_stdout(io.StringIO()) as stdout, \
                     patch.object(data, "fetch_source", return_value={"source_sha256_lf": data.SOURCE_SHA256_LF}) as fetch, \
                     patch.object(data, "load_records", side_effect=lambda source: fixture_records()) as load, \
                     patch.dict(sys.modules, {"osdefects.plots": None}):
                    runpy.run_path(str(ENTRY), run_name="__main__")
            finally:
                os.chdir(original_cwd)
            fetch.assert_called_once_with(ROOT / "data/raw/index.html", offline=True)
            self.assertEqual(load.call_count, 3)
            for call in load.call_args_list:
                self.assertEqual(call.args, (ROOT / "data/raw/index.html",))
            summary = json.loads(stdout.getvalue())
            self.assertEqual(summary["table_ii_cells"], 114)
            self.assertEqual(summary["runs"], 3)
            self.assertEqual(summary["reference_file"], "paper_baselines_weekend_02.json")
            self.assertEqual(summary["source_sha256_lf"], data.SOURCE_SHA256_LF)
            self.assertEqual(summary["figures"], 0)
            self.assertEqual(json.loads((output / "stage_summary.json").read_text(encoding="utf-8")), summary)
            self.assertEqual(json.loads((output / "figure_manifest.json").read_text(encoding="utf-8")), [])
            self.assertFalse((output / "figures").exists())
            self.assertFalse((directory / "data").exists())
            with (output / "tables/table_ii.csv").open(encoding="utf-8", newline="") as stream:
                table = list(csv.DictReader(stream))
            self.assertEqual(len(table), 114)
            for row in table:
                spec = original_reference["dimensions"][row["dimension"]]
                category_index = spec["categories"].index(row["category"])
                self.assertEqual(float(row["paper_percent"]), spec["table_ii_percent"][row["os"]][category_index])
            digests = []
            for index in range(1, 4):
                run = output / "runs" / f"run_{index:02d}"
                result = json.loads((run / "results.json").read_text(encoding="utf-8"))
                log = json.loads((run / "run_log.json").read_text(encoding="utf-8"))
                self.assertEqual(log["semantic_result_sha256"], semantic_digest(result))
                digests.append(log["semantic_result_sha256"])
                self.assertEqual(log["records"], 1500)
                for filename in ("table_ii.csv", "repair_distributions.csv", "repair_claim_checks.csv"):
                    self.assertEqual((run / "tables" / filename).read_bytes(), (output / "tables" / filename).read_bytes())
            self.assertEqual(len(set(digests)), 1)
            environment = json.loads((output / "environment.json").read_text(encoding="utf-8"))
            for path in (ENTRY, reference_path):
                expected_hash = hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
                self.assertEqual(environment["files_sha256"][path.name], expected_hash)

    def test_insufficient_runs_fail_before_data_access(self):
        with tempfile.TemporaryDirectory() as directory:
            completed = subprocess.run([sys.executable, str(ENTRY), "--runs", "2", "--offline", "--no-plots"],
                                       cwd=directory, capture_output=True, text=True, timeout=30)
            self.assertEqual(completed.returncode, 2)
            self.assertIn("at least 3", completed.stderr)
            self.assertFalse(list(Path(directory).iterdir()))

    def test_output_guard_accepts_new_empty_and_own_output_directories(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            new = root / "new"
            empty = root / "empty"
            empty.mkdir()
            own = root / "own"
            own.mkdir()
            marker = own / "stage_summary.json"
            marker.write_text('{"analysis":"weekend_02","status":"running"}', encoding="utf-8")
            sentinel = own / "notes.txt"
            sentinel.write_bytes(b"student notes")
            for target in (new, empty, own):
                self.assertEqual(validate_output_directory(target, root), target.resolve())
            self.assertFalse(new.exists())
            self.assertEqual(sentinel.read_bytes(), b"student notes")

    def test_output_guard_rejects_nonempty_unknown_and_incompatible_markers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index, content in enumerate((None, "not json", "[]", '{"analysis":"all"}')):
                with self.subTest(marker=content):
                    target = root / str(index)
                    target.mkdir()
                    (target / "keep.txt").write_bytes(b"original content")
                    if content is not None:
                        (target / "stage_summary.json").write_text(content, encoding="utf-8")
                    original = {p.name: p.read_bytes() for p in target.iterdir()}
                    with self.assertRaises(ValueError):
                        validate_output_directory(target, root)
                    self.assertEqual({p.name: p.read_bytes() for p in target.iterdir()}, original)
            file_target = root / "file.txt"
            file_target.write_bytes(b"original file")
            with self.assertRaisesRegex(ValueError, "directory"):
                validate_output_directory(file_target, root)
            self.assertEqual(file_target.read_bytes(), b"original file")

    def test_output_guard_protects_sources_history_core_and_nested_other_results(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in (".", "src", "src/new", "scripts/new", "tests/new", "reference/new",
                             "data/new", "docs/new", "weekend_02", "weekend_02/new", "results/full",
                             "results/full/new"):
                with self.subTest(path=relative), self.assertRaisesRegex(ValueError, "protected"):
                    validate_output_directory(root / relative, root)
            other = root / "results/other"
            other.mkdir(parents=True)
            (other / "stage_summary.json").write_text('{"analysis":"rq1"}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "another analysis"):
                validate_output_directory(other / "empty/new", root)
            self.assertFalse((other / "empty").exists())

    def test_real_entry_rejects_unknown_output_before_fetch_or_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "existing"
            output.mkdir()
            sentinel = output / "results.json"
            sentinel.write_bytes(b"valuable previous analysis")
            invocation = [str(ENTRY), "--offline", "--no-plots", "--output-dir", str(output)]
            with patch.object(sys, "argv", invocation), patch.object(data, "fetch_source") as fetch:
                with self.assertRaisesRegex(ValueError, "lacks a Week 2 marker"):
                    runpy.run_path(str(ENTRY), run_name="__main__")
            fetch.assert_not_called()
            self.assertEqual(list(output.iterdir()), [sentinel])
            self.assertEqual(sentinel.read_bytes(), b"valuable previous analysis")


if __name__ == "__main__":
    unittest.main()
