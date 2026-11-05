"""Offline integration guards for analysis dispatch, repeats and review work."""

import csv
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from osdefects.common import OS_ORDER, write_csv
from osdefects.runner import create_review_template, repeated_statistics, run_analyses


def read_csv(path):
    with Path(path).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def similarity_row(value, os_b="HarmonyOS"):
    return {"dimension": "trigger_scenario", "os_a": "Android", "os_b": os_b, "ours_rho": value}


def write_similarity_runs(directory, rows):
    for index, row in enumerate(rows, start=1):
        write_csv(Path(directory) / "runs" / f"run_{index:02d}" / "tables" / "similarity_comparison.csv", [row])


class AnalysisDispatchTests(unittest.TestCase):
    def test_each_scope_selects_only_the_requested_implemented_analyses(self):
        expected = {
            None: {"univariate"}, "rq1": {"univariate"}, "rq2": {"joint"},
            "rq3": {"similarity"}, "all": {"univariate", "joint", "similarity"},
        }
        records = [{"fixture": "analysis functions are mocked"}]
        reference = {"joint": {"fixture": "joint"}, "similarity": {"fixture": "similarity"}}
        for selection, keys in expected.items():
            with self.subTest(selection=selection), \
                 patch("osdefects.runner.analyze_univariate", return_value={"source": "rq1"}) as rq1, \
                 patch("osdefects.joint.analyze_joint", return_value={"source": "rq2"}) as rq2, \
                 patch("osdefects.similarity.analyze_similarity", return_value={"source": "rq3"}) as rq3:
                destination = Path("unused-mocked-destination")
                result = run_analyses(records, reference, 1, destination, analysis=selection)
                self.assertEqual(set(result), keys)
                if "univariate" in keys:
                    rq1.assert_called_once_with(records, reference, destination, ["os_layer"] if selection is None else None)
                else:
                    rq1.assert_not_called()
                if "joint" in keys:
                    rq2.assert_called_once_with(records, reference["joint"], destination)
                else:
                    rq2.assert_not_called()
                if "similarity" in keys:
                    rq3.assert_called_once_with(records, reference["similarity"], destination)
                else:
                    rq3.assert_not_called()

    def test_unimplemented_stages_and_unknown_analysis_are_rejected_before_dispatch(self):
        with patch("osdefects.runner.analyze_univariate") as analysis:
            for stage, selection in [(2, None), (3, "all"), (None, "rq1"), (1, "repairs")]:
                with self.subTest(stage=stage, selection=selection), self.assertRaises(ValueError):
                    run_analyses([], {}, stage, Path("unused"), selection)
            analysis.assert_not_called()


class RepeatedStatisticsTests(unittest.TestCase):
    def test_same_row_count_with_different_comparison_keys_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            write_similarity_runs(directory, [similarity_row(0.6), similarity_row(0.6, "Linux"), similarity_row(0.6)])
            with self.assertRaisesRegex(RuntimeError, "comparison keys"):
                repeated_statistics(Path(directory), 3, ["similarity"])

    def test_undefined_coefficients_remain_blank_in_exported_statistics(self):
        with tempfile.TemporaryDirectory() as directory:
            write_similarity_runs(directory, [similarity_row(None) for _ in range(3)])
            result = repeated_statistics(Path(directory), 3, ["similarity"])
            self.assertEqual(result[0]["status"], "undefined")
            self.assertIsNone(result[0]["mean"])
            self.assertIsNone(result[0]["sd"])
            row = read_csv(Path(directory) / "tables" / "repeated_run_statistics.csv")[0]
            self.assertEqual((row["mean"], row["sd"]), ("", ""))

    def test_disagreement_about_definedness_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            write_similarity_runs(directory, [similarity_row(None), similarity_row(0.6), similarity_row(None)])
            with self.assertRaisesRegex(RuntimeError, "undefined"):
                repeated_statistics(Path(directory), 3, ["similarity"])

    def test_numeric_summary_uses_actual_repeated_values(self):
        with tempfile.TemporaryDirectory() as directory:
            write_similarity_runs(directory, [similarity_row(value) for value in (0.1, 0.2, 0.3)])
            result = repeated_statistics(Path(directory), 3, ["similarity"])
            self.assertAlmostEqual(result[0]["mean"], 0.2)
            self.assertAlmostEqual(result[0]["sd"], 0.1)
            self.assertEqual(result[0]["status"], "defined")
            self.assertEqual(result[0]["runs"], 3)


class ReviewTemplateTests(unittest.TestCase):
    @staticmethod
    def records():
        return [{"os": os_name, "bug_id": f"{index:03d}", "patch": f"https://example.invalid/{os_name}/{index}"}
                for os_name in OS_ORDER for index in range(20)]

    def test_seed_340_selects_four_per_os_independent_of_input_order(self):
        with tempfile.TemporaryDirectory() as directory:
            first, second = Path(directory) / "first.csv", Path(directory) / "second.csv"
            create_review_template(self.records(), first)
            create_review_template(list(reversed(self.records())), second)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            rows = read_csv(first)
            self.assertEqual(len(rows), 12)
            for os_name in OS_ORDER:
                sampled = [row for row in rows if row["os"] == os_name]
                self.assertEqual([row["bug_id"] for row in sampled], ["012", "018", "003", "016"])
            self.assertTrue(all(row["status"] == "pending_human_review" for row in rows))
            self.assertTrue(all(value == "" for row in rows for key, value in row.items() if key.startswith("reviewer_")))

    def test_rerun_preserves_existing_human_entries_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "review.csv"
            create_review_template(self.records(), target)
            rows = read_csv(target)
            rows[0]["reviewer_A_os_layer"] = "Kernel"
            rows[0]["reviewer_A_evidence"] = "学生已核对补丁；保留此记录。"
            rows[0]["status"] = "reviewer_A_done"
            write_csv(target, rows)
            before = target.read_bytes()
            create_review_template([], target)
            self.assertEqual(target.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
