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


if __name__ == "__main__":
    unittest.main()
