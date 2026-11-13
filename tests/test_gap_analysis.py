"""Offline checks for the three project-added gap analyses."""

import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from osdefects.gap_analysis import (
    analyze_gaps, explore_figure4c, explore_figure4d, pearson,
    repair_evidence, validate_gap_reference, _count_vectors, _groups,
)


def similarity_reference():
    return json.loads((ROOT / "reference" / "similarity_baselines.json").read_text(encoding="utf-8"))


def synthetic_records():
    """1500 minimal records: one label per dimension, no external input."""
    records = []
    for os_name in ("Android", "Linux", "HarmonyOS"):
        for index in range(500):
            records.append({
                "os": os_name, "bug_id": os_name[0] + str(index),
                "os_layer": "Kernel", "affected_function": "Mem/Res Mng",
                "trigger_scenario": "Bor Con", "severity": "High",
                "code_level": ["Call"],
                "patch": "https://example.test/patch/" + os_name[0] + str(index),
                "raw": {"Involved Functions": "1"}, "numeric_censored": [],
                "line_changes": 5, "line_deletions": 2, "line_additions": 3,
                "involved_functions": 1, "modified_files": 1,
            })
    return records


class CoefficientTests(unittest.TestCase):
    def test_pearson_of_identical_vectors_is_one(self):
        self.assertAlmostEqual(pearson([1, 2, 3, 4], [2, 4, 6, 8]), 1.0, places=12)

    def test_pearson_of_constant_vector_is_undefined(self):
        self.assertIsNone(pearson([3, 3, 3], [1, 2, 3]))

    def test_bad_reference_is_rejected(self):
        broken = similarity_reference()
        broken["excluded"]["overall"]["status"] = "confirmed"
        with self.assertRaises(ValueError):
            validate_gap_reference(broken)
        validate_gap_reference(similarity_reference())

    def test_single_category_after_dropping_zeros_does_not_crash(self):
        groups = _groups(synthetic_records())
        counts, categories = _count_vectors(groups, "trigger_scenario", "drop_all_zero_categories")
        self.assertEqual(len(categories), 1)
        summary, rows = explore_figure4c(groups, similarity_reference())
        self.assertEqual(summary["enumeration_count"], 144)
        self.assertTrue(any(row["ours_rho"] == "" or row["ours_rho"] is None for row in rows))


class ExplorationTests(unittest.TestCase):
    def test_figure_4d_has_all_candidate_rows_and_stays_unconfirmed(self):
        summary, rows = explore_figure4d(_groups(synthetic_records()), similarity_reference())
        self.assertEqual(summary["candidate_count"], 42)
        self.assertEqual(len(rows), 42)
        self.assertEqual({row["status"] for row in rows}, {"unconfirmed_candidate"})
        self.assertEqual(set(summary["published_values"].values()), {-0.11, 0.05, -0.04})

    def test_end_to_end_writes_all_four_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            result = analyze_gaps(synthetic_records(), similarity_reference(), Path(directory) / "out")
            outdir = Path(directory) / "out"
            for name in ("figure_4c_exploration.csv", "figure_4d_candidates.csv",
                         "repair_anomaly_evidence.csv", "gap_analysis_summary.json"):
                self.assertTrue((outdir / name).exists(), name)
            self.assertEqual(result["figure_4c"]["enumeration_count"], 144)
            self.assertEqual(result["figure_4d"]["candidate_count"], 42)

    def test_in_memory_mode_writes_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            result = analyze_gaps(synthetic_records(), similarity_reference(), write_outputs=False)
            self.assertEqual(list(Path(directory).iterdir()), [])
            self.assertIn("figure_4c", result)


class RepairEvidenceTests(unittest.TestCase):
    def test_zero_and_censored_records_are_exported_with_blank_review_columns(self):
        records = synthetic_records()
        records[0]["involved_functions"] = 0
        records[0]["raw"] = {"Involved Functions": "0"}
        records[1]["involved_functions"] = 10
        records[1]["numeric_censored"] = ["involved_functions"]
        records[1]["raw"] = {"Involved Functions": "10+"}
        stats, rows = repair_evidence(records)
        self.assertEqual(stats["zero_function_records"], 1)
        self.assertEqual(stats["censored_records"], 1)
        self.assertEqual(len(rows), 2)
        reasons = {row["bug_id"]: row["anomaly_reasons"] for row in rows}
        self.assertIn("zero_involved_functions", reasons[records[0]["bug_id"]])
        self.assertIn("censored_lower_bound", reasons[records[1]["bug_id"]])
        for row in rows:
            self.assertEqual(row["evidence_status"], "pending_manual_patch_review")
            self.assertEqual(row["verified_function_count"], "")
            self.assertEqual(row["patch_host"], "example.test")

    def test_no_patch_fetching_or_value_changes(self):
        records = synthetic_records()
        before = [record["involved_functions"] for record in records]
        repair_evidence(records)
        self.assertEqual([record["involved_functions"] for record in records], before)


if __name__ == "__main__":
    unittest.main()
