"""RQ2 contracts, including independent known-answer joint proportions."""
import copy
import csv
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from osdefects.common import OS_ORDER
from osdefects.joint import analyze_joint, joint_distribution, validate_joint_reference


def published_reference():
    return json.loads((ROOT / "reference" / "joint_baselines.json").read_text(encoding="utf-8"))


def known_corpus():
    # Three populations: 40% kernel/memory/boundary, 20% kernel/storage/routine,
    # 40% application/storage/routine. Joint percentages must not sum to 100 per row.
    records = []
    for os_name in OS_ORDER:
        for i in range(500):
            records.append({
                "os": os_name,
                "os_layer": "Kernel" if i < 300 else "Application",
                "affected_function": "Mem/Res Mng" if i < 200 else "Sto Mng",
                "trigger_scenario": "Bor Con" if i < 200 else "Reg Ope",
            })
    return records


class JointDistributionTests(unittest.TestCase):
    def test_denominator_and_both_marginals(self):
        group = known_corpus()[:500]
        matrix = joint_distribution(group, "os_layer", "affected_function")
        self.assertEqual(matrix["counts"][0], [200, 0, 100, 0, 0, 0, 0, 0])
        self.assertEqual(matrix["counts"][5], [0, 0, 200, 0, 0, 0, 0, 0])
        self.assertEqual(matrix["percent"][0], [40, 0, 20, 0, 0, 0, 0, 0])
        self.assertEqual(sum(matrix["percent"][0]), 60)
        self.assertEqual(matrix["row_marginal_counts"], [300, 0, 0, 0, 0, 200])
        self.assertEqual(matrix["column_marginal_counts"], [200, 0, 300, 0, 0, 0, 0, 0])
        self.assertTrue(matrix["marginals_valid"])
        self.assertEqual(sum(map(sum, matrix["counts"])), 500)

    def test_small_corpus_preserves_empty_categories(self):
        matrix = joint_distribution(known_corpus()[:2], "affected_function", "trigger_scenario")
        self.assertEqual(matrix["n"], 2)
        self.assertEqual(matrix["percent"][0][2], 100)
        self.assertEqual(len(matrix["counts"]), 8)
        self.assertTrue(all(len(row) == 7 for row in matrix["counts"]))

    def test_unknown_and_empty_inputs_fail(self):
        with self.assertRaisesRegex(ValueError, "empty corpus"):
            joint_distribution([], "os_layer", "affected_function")
        group = known_corpus()[:2]
        group[0]["os_layer"] = "Unmapped layer"
        with self.assertRaisesRegex(ValueError, "Unknown os_layer"):
            joint_distribution(group, "os_layer", "affected_function")
        with self.assertRaisesRegex(ValueError, "different single-label"):
            joint_distribution(group, "code_level", "os_layer")


class JointReferenceTests(unittest.TestCase):
    def test_published_reference_has_438_cells_and_sources(self):
        reference = published_reference()
        validate_joint_reference(reference)
        tables = reference["tables"]
        counts = [sum(len(row) for matrix in spec["paper_percent"].values() for row in matrix) for spec in tables.values()]
        self.assertEqual(counts, [144, 126, 168])
        self.assertTrue(reference["provenance"]["not_replication_results"])
        # Published Table III: Android system services / security = 28.60%.
        self.assertEqual(tables["table_iii"]["paper_percent"]["Android"][4][6], 28.6)
        # Published Table IV: HarmonyOS kernel / boundary = 39.60%.
        self.assertEqual(tables["table_iv"]["paper_percent"]["HarmonyOS"][0][2], 39.6)
        # Published Table V: Linux compatibility / environment = 35.80%.
        self.assertEqual(tables["table_v"]["paper_percent"]["Linux"][5][5], 35.8)

    def test_missing_table_os_row_or_cell_rejected(self):
        for failure in ("table", "os", "row", "cell"):
            with self.subTest(failure=failure):
                reference = published_reference()
                if failure == "table":
                    del reference["tables"]["table_v"]
                else:
                    matrices = reference["tables"]["table_v"]["paper_percent"]
                    if failure == "os":
                        del matrices["Linux"]
                    elif failure == "row":
                        matrices["Linux"].pop()
                    else:
                        matrices["Linux"][0].pop()
                with self.assertRaises(ValueError):
                    validate_joint_reference(reference)

    def test_reordered_axes_and_wrong_fields_rejected(self):
        for key in ("row_categories", "column_categories", "row_field", "column_field"):
            with self.subTest(key=key):
                reference = published_reference()
                table = reference["tables"]["table_iii"]
                table[key] = list(reversed(table[key])) if isinstance(table[key], list) else "severity"
                with self.assertRaises(ValueError):
                    validate_joint_reference(reference)

    def test_invalid_percentages_and_totals_rejected(self):
        for value in (True, "1.0", float("nan"), float("inf"), -0.1, 100.1):
            with self.subTest(value=value):
                reference = published_reference()
                reference["tables"]["table_iii"]["paper_percent"]["Android"][0][0] = value
                with self.assertRaisesRegex(ValueError, "Invalid joint reference"):
                    validate_joint_reference(reference)
        reference = published_reference()
        reference["tables"]["table_iii"]["paper_percent"]["Android"][0][0] = 0
        with self.assertRaisesRegex(ValueError, "total 100"):
            validate_joint_reference(reference)

    def test_missing_source_and_wrong_denominator_rejected(self):
        reference = published_reference()
        del reference["tables"]["table_v"]["source_url"]
        with self.assertRaisesRegex(ValueError, "source"):
            validate_joint_reference(reference)
        reference = published_reference()
        reference["per_os_n"] = 100
        with self.assertRaisesRegex(ValueError, "500"):
            validate_joint_reference(reference)


class JointAnalysisTests(unittest.TestCase):
    def test_output_has_all_cells_and_explicit_unknowns(self):
        reference = published_reference()
        reference["tables"]["table_iii"]["paper_percent"]["Android"][0][0] = None
        before = copy.deepcopy(reference)
        with tempfile.TemporaryDirectory() as temporary:
            result = analyze_joint(known_corpus(), reference, temporary)
            self.assertEqual(result["cell_count"], 438)
            self.assertEqual(result["unconfirmed_cells"], 1)
            self.assertEqual(result["matched_cells"] + result["mismatched_cells"] + result["unconfirmed_cells"], 438)
            self.assertEqual(result["unconfirmed"][0]["status"], "unconfirmed")
            self.assertIsNone(result["unconfirmed"][0]["matches_to_2dp"])
            self.assertIsNone(result["unconfirmed"][0]["difference_pp"])
            with (Path(temporary) / "joint_comparison.csv").open(encoding="utf-8", newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 438)
            self.assertTrue(all(row["n"] == "500" for row in rows))
            self.assertEqual(rows[0]["paper_percent"], "")
            self.assertEqual(json.loads((Path(temporary) / "joint_summary.json").read_text(encoding="utf-8")), result)
        self.assertEqual(reference, before)

    def test_wrong_corpus_size_or_os_fails(self):
        for group in (known_corpus()[:-1], known_corpus() + [{"os": "Unknown"}]):
            with self.subTest(length=len(group)), tempfile.TemporaryDirectory() as temporary:
                with self.assertRaises(ValueError):
                    analyze_joint(group, published_reference(), temporary)
                self.assertFalse((Path(temporary) / "joint_comparison.csv").exists())


if __name__ == "__main__":
    unittest.main()
