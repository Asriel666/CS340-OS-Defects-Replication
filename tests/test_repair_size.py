"""Offline checks for Figure 2/3 binning-convention sensitivity analysis."""

import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from osdefects.repair_size import (
    CENSORED_METRIC, convention_configs, assign_bin, analyze_repair_size,
    bin_distribution, validate_figure_reference,
)


def figure_reference():
    return json.loads((ROOT / "reference" / "figure_baselines.json").read_text(encoding="utf-8"))


def record(os_name, bug_id, metric, value, censored=False):
    entry = {"os": os_name, "bug_id": bug_id, "numeric_censored": [metric] if censored else []}
    entry[metric] = value
    return entry


class AssignBinTests(unittest.TestCase):
    def test_boundary_value_goes_up_under_left_closed(self):
        edges = [0, 10, 30, 50]
        self.assertEqual(assign_bin(10, edges, "left_closed"), 1)
        self.assertEqual(assign_bin(30, edges, "left_closed"), 2)

    def test_boundary_value_goes_down_under_right_closed(self):
        edges = [0, 10, 30, 50]
        self.assertEqual(assign_bin(10, edges, "right_closed"), 0)
        self.assertEqual(assign_bin(30, edges, "right_closed"), 1)

    def test_final_bin_is_closed_on_both_ends(self):
        edges = [0, 10, 30]
        self.assertEqual(assign_bin(30, edges, "left_closed"), 1)
        self.assertEqual(assign_bin(30, edges, "right_closed"), 1)

    def test_first_edge_zero_excluded_under_right_closed(self):
        self.assertIsNone(assign_bin(0, [0, 3, 5], "right_closed"))
        self.assertEqual(assign_bin(0, [0, 3, 5], "left_closed"), 0)

    def test_unknown_convention_and_negative_value_are_rejected(self):
        with self.assertRaises(ValueError):
            assign_bin(5, [0, 10], "midpoint")
        with self.assertRaises(ValueError):
            assign_bin(-1, [0, 10], "left_closed")

    def test_values_above_last_edge_fall_outside(self):
        self.assertIsNone(assign_bin(600, [0, 10, 500], "left_closed"))


class ConventionConfigTests(unittest.TestCase):
    def test_censored_metric_gets_both_policies_per_boundary(self):
        configs = convention_configs(CENSORED_METRIC)
        self.assertEqual(configs, [("left_closed", "lower_bound"), ("left_closed", "unassigned"),
                                   ("right_closed", "lower_bound"), ("right_closed", "unassigned")])

    def test_plain_metric_marks_censored_policy_not_applicable(self):
        self.assertEqual(convention_configs("line_changes"),
                         [("left_closed", "not_applicable"), ("right_closed", "not_applicable")])


class BinDistributionTests(unittest.TestCase):
    def test_bin_percent_uses_full_group_denominator(self):
        edges = [0, 10, 500]
        group = [record("Android", "A1", "line_changes", 5),
                 record("Android", "A2", "line_changes", 15)]
        counts, percents, outside = bin_distribution(group, edges, "left_closed", "not_applicable", "line_changes")
        self.assertEqual(counts, [1, 1])
        self.assertAlmostEqual(percents[0], 50.0)
        self.assertEqual(outside, [])

    def test_censored_unassigned_record_leaves_bins_but_not_denominator(self):
        edges = [0, 10, 50]
        group = [record("HarmonyOS", "H1", "involved_functions", 10, censored=True),
                 record("HarmonyOS", "H2", "involved_functions", 2)]
        counts, percents, outside = bin_distribution(group, edges, "left_closed", "unassigned", "involved_functions")
        self.assertEqual(counts, [1, 0])
        self.assertAlmostEqual(sum(percents), 50.0)
        self.assertEqual(len(outside), 1)
        self.assertEqual(outside[0]["bug_id"], "H1")

    def test_zero_functions_outside_bins_only_under_right_closed(self):
        edges = [0, 3, 5]
        group = [record("Linux", "L1", "involved_functions", 0)]
        _, _, outside_left = bin_distribution(group, edges, "left_closed", "lower_bound", "involved_functions")
        _, _, outside_right = bin_distribution(group, edges, "right_closed", "lower_bound", "involved_functions")
        self.assertEqual(outside_left, [])
        self.assertEqual(len(outside_right), 1)


class AnalyzeRepairSizeTests(unittest.TestCase):
    def _run(self, records, outdir):
        return analyze_repair_size(records, figure_reference(), Path(outdir))

    def test_reference_and_transcribed_totals_are_consistent(self):
        reference = figure_reference()
        validate_figure_reference(reference)
        for series in reference["series"]:
            for os_name, values in series["paper_percent"].items():
                self.assertAlmostEqual(sum(values), 100.0, places=2, msg=series["series_id"] + "/" + os_name)

    def test_empty_or_wrong_reference_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_figure_reference({"provenance": {"kind": "wrong"}, "series": []})
        broken = figure_reference()
        broken["series"][0]["paper_percent"]["Android"][0] = 200.0
        with self.assertRaises(ValueError):
            validate_figure_reference(broken)

    def test_analysis_requires_exactly_500_records_per_os(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                self._run([record("Android", "A1", "line_changes", 5)], directory)

    def test_synthetic_interior_value_matches_under_both_conventions(self):
        """500 defects per OS, all with value 5; paper [100,0,0,0,0] matches both
        conventions because 5 lies strictly inside the first bin."""
        with tempfile.TemporaryDirectory() as directory:
            records = []
            for os_name in ("Android", "Linux", "HarmonyOS"):
                for index in range(500):
                    records.append(record(os_name, os_name[0] + str(index), "line_changes", 5))
            reference = figure_reference()
            reference["series"] = [reference["series"][0]]
            reference["series"][0]["paper_percent"] = {name: [100.0, 0.0, 0.0, 0.0, 0.0] for name in ("Android", "Linux", "HarmonyOS")}
            result = analyze_repair_size(records, reference, Path(directory))
            configs = result["series"]["figure_2_line_changes"]["configurations"]
            self.assertEqual(configs["left_closed/not_applicable"]["matches"], 15)
            self.assertEqual(configs["right_closed/not_applicable"]["matches"], 15)

    def test_boundary_value_distinguishes_conventions_end_to_end(self):
        """500 defects per OS, all with value exactly 10; paper [0,100,0,0,0].

        Under [lo, hi) the boundary value 10 belongs to the second bin and every
        cell matches; under (lo, hi] it falls into the first bin, which breaks
        both the first and the second bin for every operating system."""
        with tempfile.TemporaryDirectory() as directory:
            records = []
            for os_name in ("Android", "Linux", "HarmonyOS"):
                for index in range(500):
                    records.append(record(os_name, os_name[0] + str(index), "line_changes", 10))
            reference = figure_reference()
            reference["series"] = [reference["series"][0]]
            reference["series"][0]["paper_percent"] = {name: [0.0, 100.0, 0.0, 0.0, 0.0] for name in ("Android", "Linux", "HarmonyOS")}
            result = analyze_repair_size(records, reference, Path(directory))
            configs = result["series"]["figure_2_line_changes"]["configurations"]
            self.assertEqual(configs["left_closed/not_applicable"]["matches"], 15)
            self.assertEqual(configs["right_closed/not_applicable"]["matches"], 9)
            self.assertEqual(configs["right_closed/not_applicable"]["cells"]
                             - configs["right_closed/not_applicable"]["matches"], 6)

    def test_outputs_are_written_for_every_series_and_config(self):
        with tempfile.TemporaryDirectory() as directory:
            records = []
            for os_name in ("Android", "Linux", "HarmonyOS"):
                for index in range(500):
                    records.append(record(os_name, os_name[0] + str(index), "line_changes", 5))
                    records[-1]["involved_functions"] = 1
                    records[-1]["modified_files"] = 1
            result = self._run(records, Path(directory) / "out")
            outdir = Path(directory) / "out"
            self.assertTrue((outdir / "convention_comparison.csv").exists())
            self.assertTrue((outdir / "config_match_summary.csv").exists())
            self.assertTrue((outdir / "repair_size_sensitivity.json").exists())
            expected = sum(len(info["configurations"]) * len(info["bin_labels"]) * 3
                           for info in result["series"].values())
            self.assertEqual(result["comparison_count"], expected)
            self.assertEqual(len(result["series"]), 3)


if __name__ == "__main__":
    unittest.main()
