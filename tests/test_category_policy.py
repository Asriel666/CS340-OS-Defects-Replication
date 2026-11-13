"""Category selection affects inputs, while the core rank algorithm stays fixed."""
import copy
import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from osdefects.category_policy import analyze_category_policy, compare_pair, select_categories
from osdefects.common import OS_ORDER, semantic_digest
from osdefects.data import CANONICAL_CATEGORIES
from osdefects.similarity import SIMILARITY_DIMENSIONS, analyze_similarity


def reference():
    return json.loads((ROOT / "reference" / "similarity_baselines.json").read_text(encoding="utf-8"))


def marginal_fixture():
    """Test data from transcribed Table II, not the released defect-level dataset."""
    table = json.loads((ROOT / "reference" / "paper_baselines.json").read_text(encoding="utf-8"))
    records = []
    for name in OS_ORDER:
        group = [{"os": name} for _ in range(500)]
        for dimension in SIMILARITY_DIMENSIONS:
            spec = table["dimensions"][dimension]
            values = [category for category, percent in zip(spec["categories"], spec["table_ii_percent"][name])
                      for _ in range(round(percent * 5))]
            if len(values) != 500:
                raise AssertionError("Invalid marginal fixture")
            for record, value in zip(group, values):
                record[dimension] = value
        records.extend(group)
    return records


def counts(a, b, linux):
    return {"Android": a, "HarmonyOS": b, "Linux": linux}


class CategorySelectionTests(unittest.TestCase):
    def test_global_and_pairwise_have_different_population_rules(self):
        values = counts({"x": 1, "y": 0}, {"x": 2, "y": 0}, {"x": 3, "y": 4})
        self.assertEqual(select_categories(["x", "y"], values, "Android", "HarmonyOS", "global_nonzero"), ["x", "y"])
        self.assertEqual(select_categories(["x", "y"], values, "Android", "HarmonyOS", "pairwise_nonzero"), ["x"])

    def test_a_single_zero_is_retained_and_only_shared_zero_is_removed(self):
        values = counts({"x": 0, "y": 5, "z": 0}, {"x": 3, "y": 0, "z": 0}, {"x": 0, "y": 0, "z": 0})
        for policy in ("global_nonzero", "pairwise_nonzero"):
            self.assertEqual(select_categories(["x", "y", "z"], values, "Android", "HarmonyOS", policy), ["x", "y"])
        self.assertEqual(select_categories(["x", "y", "z"], values, "Android", "HarmonyOS", "fixed_all"), ["x", "y", "z"])

    def test_category_mapping_order_cannot_misalign_vectors(self):
        values = counts({"y": 2, "x": 1}, {"x": 4, "y": 3}, {"x": 0, "y": 0})
        detail = compare_pair(["x", "y"], values, "Android", "HarmonyOS", "fixed_all")
        self.assertEqual(detail["counts_a"], [1, 2])
        self.assertEqual(detail["counts_b"], [4, 3])
        self.assertEqual(detail["ours_rho"], -1)

    def test_missing_extra_duplicate_categories_or_systems_are_rejected(self):
        base = counts({"x": 1, "y": 2}, {"x": 2, "y": 1}, {"x": 0, "y": 1})
        mutations = []
        changed = copy.deepcopy(base)
        del changed["Linux"]["y"]
        mutations.append(changed)
        changed = copy.deepcopy(base)
        changed["Android"]["z"] = 0
        mutations.append(changed)
        changed = copy.deepcopy(base)
        del changed["Linux"]
        mutations.append(changed)
        for values in mutations:
            with self.subTest(values=values), self.assertRaises(ValueError):
                select_categories(["x", "y"], values, "Android", "HarmonyOS", "fixed_all")
        with self.assertRaises(ValueError):
            select_categories(["x", "x"], base, "Android", "HarmonyOS", "fixed_all")

    def test_bad_counts_policy_or_pair_are_rejected(self):
        for value in (-1, True, 1.5, float("nan"), None):
            values = counts({"x": value, "y": 2}, {"x": 2, "y": 1}, {"x": 0, "y": 1})
            with self.subTest(value=value), self.assertRaises(ValueError):
                select_categories(["x", "y"], values, "Android", "HarmonyOS", "fixed_all")
        values = counts({"x": 1}, {"x": 2}, {"x": 3})
        for a, b, policy in [("Android", "Linux", "drop_any_zero"), ("Android", "Android", "fixed_all"), ("unknown", "Linux", "fixed_all")]:
            with self.subTest(a=a, b=b, policy=policy), self.assertRaises(ValueError):
                select_categories(["x"], values, a, b, policy)

    def test_empty_or_singleton_after_filtering_is_undefined(self):
        for data in [({"x": 0, "y": 0}, {"x": 0, "y": 0}), ({"x": 1, "y": 0}, {"x": 2, "y": 0})]:
            values = counts(*data, {"x": 0, "y": 1})
            detail = compare_pair(["x", "y"], values, "Android", "HarmonyOS", "pairwise_nonzero")
            self.assertIsNone(detail["ours_rho"])
            self.assertEqual(detail["undefined_reason"], "fewer_than_two_retained_categories")

    def test_constant_retained_vector_is_undefined(self):
        values = counts({"x": 2, "y": 2, "z": 0}, {"x": 1, "y": 3, "z": 0}, {"x": 1, "y": 2, "z": 1})
        detail = compare_pair(["x", "y", "z"], values, "Android", "HarmonyOS", "pairwise_nonzero")
        self.assertIsNone(detail["ours_rho"])
        self.assertEqual(detail["undefined_reason"], "constant_retained_vector")
        self.assertEqual(detail["average_ranks_a"], [1.5, 1.5])

    def test_known_trigger_pair_retains_full_precision_and_reranks_ties(self):
        categories = CANONICAL_CATEGORIES["trigger_scenario"]
        values = counts(dict(zip(categories, [156, 44, 185, 36, 74, 5, 0])),
                        dict(zip(categories, [14, 33, 263, 120, 56, 14, 0])),
                        dict(zip(categories, [1, 2, 3, 4, 5, 6, 7])))
        full = compare_pair(categories, values, "Android", "HarmonyOS", "fixed_all")
        filtered = compare_pair(categories, values, "Android", "HarmonyOS", "pairwise_nonzero")
        self.assertAlmostEqual(full["ours_rho"], 0.6126374746329801, places=15)
        self.assertAlmostEqual(filtered["ours_rho"], 0.3768511731740915, places=15)
        self.assertEqual(filtered["excluded_categories"], ["Mul/Loc Dep"])
        self.assertEqual(filtered["average_ranks_b"], [1.5, 3.0, 6.0, 5.0, 4.0, 1.5])


class PolicyAnalysisTests(unittest.TestCase):
    def test_all_policies_all_pairs_and_unchanged_core(self):
        records, baseline = marginal_fixture(), reference()
        before = semantic_digest({"records": records, "reference": baseline})
        with tempfile.TemporaryDirectory() as directory:
            core = analyze_similarity(records, baseline, Path(directory) / "core")
            result = analyze_category_policy(records, baseline, Path(directory) / "policy")
            self.assertEqual(core["matched_cells"], 8)
            self.assertEqual(result["comparison_count"], 27)
            self.assertEqual(result["unique_published_pairs"], 9)
            for policy, matches in (("fixed_all", 8), ("global_nonzero", 8), ("pairwise_nonzero", 9)):
                stats = result["policy_summary"][policy]
                self.assertEqual(stats["independent_pairs"], 9)
                self.assertEqual(stats["matched_pairs"], matches)
            self.assertEqual(len(result["changed_from_fixed_all"]), 1)
            for row in result["comparisons"]:
                if row["policy"] == "fixed_all":
                    summary = core["dimensions"][row["dimension"]]
                    i, j = summary["os_order"].index(row["os_a"]), summary["os_order"].index(row["os_b"])
                    self.assertEqual(row["ours_rho"], summary["matrix"][i][j])
            self.assertEqual(analyze_similarity(records, baseline, Path(directory) / "after"), core)
            restored = json.loads((Path(directory) / "policy" / "category_policy_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(restored, result)
            with (Path(directory) / "policy" / "category_policy_comparison.csv").open(encoding="utf-8", newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 27)
            self.assertEqual(len({(r["policy"], r["dimension"], r["os_a"], r["os_b"]) for r in rows}), 27)
            with (Path(directory) / "policy" / "category_policy_evidence.csv").open(encoding="utf-8", newline="") as stream:
                evidence = list(csv.DictReader(stream))
            self.assertEqual(len(evidence), 189)
            self.assertEqual(sum(row["retained"] == "False" for row in evidence), 1)
        self.assertEqual(semantic_digest({"records": records, "reference": baseline}), before)

    def test_reference_missing_category_or_pair_fails(self):
        for target in ("categories", "paper_matrix"):
            baseline = reference()
            baseline["dimensions"]["trigger_scenario"][target].pop()
            with self.subTest(target=target), self.assertRaises(ValueError):
                analyze_category_policy(marginal_fixture(), baseline)

    def test_unknown_label_and_missing_system_fail(self):
        records = marginal_fixture()
        with self.assertRaises(ValueError):
            analyze_category_policy([r for r in records if r["os"] != "Linux"], reference())
        records[0]["trigger_scenario"] = "not a label"
        with self.assertRaises(ValueError):
            analyze_category_policy(records, reference())

    def test_cli_requires_at_least_three_runs(self):
        completed = subprocess.run([sys.executable, str(ROOT / "scripts" / "run_category_policy.py"), "--runs", "2"], capture_output=True, text=True)
        self.assertEqual(completed.returncode, 2)
        self.assertIn("at least 3", completed.stderr)


if __name__ == "__main__":
    unittest.main()
