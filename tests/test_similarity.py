"""Offline checks for rank statistics and independently transcribed Figure 4."""

import copy
import csv
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from osdefects.common import OS_ORDER
from osdefects.data import CANONICAL_CATEGORIES
from osdefects.similarity import (
    SIMILARITY_DIMENSIONS, analyze_similarity, average_ranks, spearman,
    validate_similarity_reference,
)


def figure_reference():
    return json.loads((ROOT / "reference" / "similarity_baselines.json").read_text(encoding="utf-8"))


def records_from_table_ii():
    """Synthetic records reproducing only Table II marginals, not joint labels."""
    baseline = json.loads((ROOT / "reference" / "paper_baselines.json").read_text(encoding="utf-8"))
    records = []
    for os_name in OS_ORDER:
        group = [{"os": os_name, "bug_id": str(i)} for i in range(500)]
        for dimension in SIMILARITY_DIMENSIONS:
            spec = baseline["dimensions"][dimension]
            labels = []
            for category, percent in zip(spec["categories"], spec["table_ii_percent"][os_name]):
                labels.extend([category] * round(percent * 5))
            if len(labels) != len(group):
                raise AssertionError("Synthetic marginal fixture must contain 500 labels")
            for record, label in zip(group, labels):
                record[dimension] = label
        records.extend(group)
    return records


class RankTests(unittest.TestCase):
    def test_average_ranks_preserve_original_order_and_ties(self):
        self.assertEqual(average_ranks([40, 10, 20, 20]), [4.0, 1.0, 2.5, 2.5])
        self.assertEqual(average_ranks([0, 0, 0]), [2.0, 2.0, 2.0])

    def test_monotonic_and_reverse_vectors(self):
        self.assertEqual(spearman([1, 2, 3], [10, 20, 30]), 1)
        self.assertEqual(spearman([1, 2, 3], [30, 20, 10]), -1)

    def test_ties_use_pearson_of_average_ranks(self):
        # Centered ranks are (-1, .5, .5) and (-1, 0, 1).
        self.assertAlmostEqual(spearman([1, 2, 2], [1, 2, 3]), math.sqrt(3) / 2)
        self.assertEqual(spearman([1, 2, 2], [3, 1, 1]), -1)

    def test_constant_vector_is_undefined(self):
        self.assertIsNone(spearman([1, 1, 1], [1, 2, 3]))
        self.assertIsNone(spearman([1, 2, 3], [0, 0, 0]))

    def test_bad_length_or_nonfinite_values_are_rejected(self):
        for x, y in [([], []), ([1], [1]), ([1, 2], [1, 2, 3]),
                     ([1, float("nan")], [1, 2]), ([1, float("inf")], [1, 2]),
                     ([True, 2], [1, 2]), (["1", 2], [1, 2])]:
            with self.subTest(x=x, y=y), self.assertRaises(ValueError):
                spearman(x, y)
        with self.assertRaises(ValueError):
            average_ranks([])


class SimilarityReferenceTests(unittest.TestCase):
    def test_published_matrix_axes_and_values_are_not_guessed(self):
        baseline = figure_reference()
        validate_similarity_reference(baseline)
        trigger = baseline["dimensions"]["trigger_scenario"]
        self.assertEqual(trigger["os_order"], ["Android", "HarmonyOS", "Linux"])
        self.assertEqual(trigger["paper_matrix"][0][1], 0.38)
        self.assertEqual(trigger["paper_matrix"][0][2], 0.21)

    def test_missing_dimension_pair_and_reordered_axes_are_rejected(self):
        original = figure_reference()
        mutations = []
        changed = copy.deepcopy(original)
        del changed["dimensions"]["trigger_scenario"]
        mutations.append(changed)
        changed = copy.deepcopy(original)
        changed["dimensions"]["os_layer"]["paper_matrix"][0].pop()
        mutations.append(changed)
        changed = copy.deepcopy(original)
        changed["dimensions"]["os_layer"]["os_order"] = list(OS_ORDER)
        mutations.append(changed)
        changed = copy.deepcopy(original)
        changed["dimensions"]["os_layer"]["categories"].reverse()
        mutations.append(changed)
        for changed in mutations:
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                validate_similarity_reference(changed)

    def test_asymmetric_nonfinite_and_out_of_range_references_are_rejected(self):
        for value in [None, float("nan"), float("inf"), 1.01, True]:
            changed = figure_reference()
            changed["dimensions"]["os_layer"]["paper_matrix"][0][1] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_similarity_reference(changed)
        changed = figure_reference()
        changed["dimensions"]["os_layer"]["paper_matrix"][0][1] = 0.5
        with self.assertRaises(ValueError):
            validate_similarity_reference(changed)


class SimilarityAnalysisTests(unittest.TestCase):
    def test_all_nine_pairs_and_the_published_trigger_discrepancy(self):
        with tempfile.TemporaryDirectory() as directory:
            result = analyze_similarity(records_from_table_ii(), figure_reference(), directory)
            with (Path(directory) / "similarity_comparison.csv").open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(result["cell_count"], 9)
            self.assertEqual(result["matched_cells"], 8)
            self.assertEqual(result["unconfirmed_cells"], 0)
            keys = {(row["dimension"], row["os_a"], row["os_b"]) for row in rows}
            self.assertEqual(len(keys), 9)
            self.assertTrue(all(row["os_a"] != row["os_b"] for row in rows))
            self.assertEqual(len(result["mismatches"]), 1)
            mismatch = result["mismatches"][0]
            self.assertEqual((mismatch["dimension"], mismatch["os_a"], mismatch["os_b"]),
                             ("trigger_scenario", "Android", "HarmonyOS"))
            self.assertEqual(mismatch["paper_rho"], 0.38)
            self.assertAlmostEqual(mismatch["ours_rho"], 0.6126374746329801, places=14)
            for dimension, summary in result["dimensions"].items():
                self.assertEqual(summary["categories"], CANONICAL_CATEGORIES[dimension])
                self.assertEqual(summary["os_order"], list(OS_ORDER))
                for os_name in OS_ORDER:
                    self.assertEqual(sum(summary["counts"][os_name]), 500)
                    self.assertAlmostEqual(sum(summary["percent_vectors"][os_name]), 100)
            encoded = json.loads((Path(directory) / "similarity_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(encoded, result)
            self.assertNotIn("overall", result["dimensions"])

    def test_constant_inputs_emit_null_and_unconfirmed_not_match(self):
        records = []
        # 168 is divisible by the 6/8/7 category counts, so every vector is flat.
        for os_name in OS_ORDER:
            for index in range(168):
                record = {"os": os_name}
                for dimension in SIMILARITY_DIMENSIONS:
                    categories = CANONICAL_CATEGORIES[dimension]
                    record[dimension] = categories[index % len(categories)]
                records.append(record)
        with tempfile.TemporaryDirectory() as directory:
            result = analyze_similarity(records, figure_reference(), directory)
            self.assertEqual(result["unconfirmed_cells"], 9)
            self.assertEqual(result["matched_cells"], 0)
            self.assertEqual(result["mismatches"], [])
            self.assertTrue(all(row["ours_rho"] is None for row in result["unconfirmed"]))
            payload = (Path(directory) / "similarity_summary.json").read_text(encoding="utf-8")
            self.assertNotIn("NaN", payload)

    def test_missing_os_and_unknown_labels_fail(self):
        records = records_from_table_ii()
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                analyze_similarity([r for r in records if r["os"] != "Linux"], figure_reference(), directory)
            records[0]["os_layer"] = "unknown"
            with self.assertRaises(ValueError):
                analyze_similarity(records, figure_reference(), directory)


if __name__ == "__main__":
    unittest.main()
