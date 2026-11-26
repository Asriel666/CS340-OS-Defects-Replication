"""Spearman similarity of the paper's three categorical defect distributions.

Spearman rho is Pearson correlation of average ranks. Ties are handled
explicitly; no no-tie shortcut or mandatory SciPy dependency is used.
"""

from __future__ import annotations

import csv
import json
import math
from collections import Counter
from itertools import combinations
from pathlib import Path
from typing import Any, Sequence


OS_ORDER = ("Android", "Linux", "HarmonyOS")
DIMENSIONS = ("os_layer", "affected_function", "trigger_scenario")


def average_ranks(values: Sequence[float]) -> list[float]:
    """One-based ascending ranks, assigning each tied group its mean rank."""
    if any(not math.isfinite(value) for value in values):
        raise ValueError("Ranks require finite values")
    order = sorted(range(len(values)), key=lambda index: values[index])
    ranks = [0.0] * len(values)
    begin = 0
    while begin < len(order):
        end = begin + 1
        while end < len(order) and values[order[end]] == values[order[begin]]:
            end += 1
        mean_rank = (begin + 1 + end) / 2
        for index in order[begin:end]:
            ranks[index] = mean_rank
        begin = end
    return ranks


def pearson(x: Sequence[float], y: Sequence[float]) -> float | None:
    if len(x) != len(y) or len(x) < 2:
        raise ValueError("Correlation requires equal vectors with at least two values")
    if any(not math.isfinite(value) for value in [*x, *y]):
        raise ValueError("Correlation requires finite values")
    x_mean, y_mean = sum(x) / len(x), sum(y) / len(y)
    dx, dy = [value - x_mean for value in x], [value - y_mean for value in y]
    denominator = math.sqrt(sum(value * value for value in dx) * sum(value * value for value in dy))
    if denominator == 0:
        return None
    result = sum(a * b for a, b in zip(dx, dy)) / denominator
    return max(-1.0, min(1.0, result))


def spearman(x: Sequence[float], y: Sequence[float]) -> float | None:
    """Return rho or None when either vector is constant (undefined)."""
    if len(x) != len(y) or len(x) < 2:
        raise ValueError("Spearman correlation requires equal nontrivial vectors")
    return pearson(average_ranks(x), average_ranks(y))


def spearman_without_joint_zeros(
    x: Sequence[float], y: Sequence[float]
) -> tuple[float | None, list[int]]:
    """A disclosed sensitivity check; it is not the default category policy."""
    if len(x) != len(y):
        raise ValueError("Paired category vectors must have equal lengths")
    kept = [i for i, (a, b) in enumerate(zip(x, y)) if a != 0 or b != 0]
    removed = [i for i in range(len(x)) if i not in kept]
    if len(kept) < 2:
        return None, removed
    return spearman([x[i] for i in kept], [y[i] for i in kept]), removed


def marginal_vector(
    records: list[dict[str, Any]], os_name: str, dimension: str, categories: list[str]
) -> list[int]:
    selected = [record for record in records if record["os"] == os_name]
    if not selected:
        raise ValueError(f"No records for {os_name}")
    counts: Counter[str] = Counter(record[dimension] for record in selected)
    unknown = set(counts) - set(categories)
    if unknown:
        raise ValueError(f"Unknown {dimension} categories: {sorted(unknown)}")
    return [counts[category] for category in categories]


def _reference_panels(reference: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    figure = reference["rq3"]["figures"]["figure_4"]
    return figure["os_order"], figure["panels"]


def analyze_similarity(
    records: list[dict[str, Any]], reference: dict[str, Any], outdir: Path
) -> dict[str, Any]:
    """Recompute Fig. 4a-c and explicitly flag the under-specified overall panel.

    A concatenated marginal-vector candidate for Fig. 4d is exported only as
    exploratory output. It does not resolve the paper's missing construction.
    """
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    ref_order, panels = _reference_panels(reference)
    vectors: dict[str, dict[str, list[int]]] = {}
    results: dict[str, Any] = {}
    comparisons: list[dict[str, Any]] = []
    zero_checks: list[dict[str, Any]] = []
    vector_rows: list[dict[str, Any]] = []
    for dimension in DIMENSIONS:
        categories = reference["dimensions"][dimension]["categories"]
        vectors[dimension] = {
            os_name: marginal_vector(records, os_name, dimension, categories) for os_name in OS_ORDER
        }
        for os_name, vector in vectors[dimension].items():
            for category, count, rank in zip(categories, vector, average_ranks(vector)):
                vector_rows.append({"dimension": dimension, "os": os_name, "category": category, "count": count, "average_rank": rank})
        matrix = [[spearman(vectors[dimension][a], vectors[dimension][b]) for b in OS_ORDER] for a in OS_ORDER]
        dimension_rows: list[dict[str, Any]] = []
        for a, b in combinations(OS_ORDER, 2):
            paper = float(panels[dimension]["matrix"][ref_order.index(a)][ref_order.index(b)])
            ours = spearman(vectors[dimension][a], vectors[dimension][b])
            gap = None if ours is None else ours - paper
            table_ii_rho = spearman(
                reference["dimensions"][dimension]["table_ii_percent"][a],
                reference["dimensions"][dimension]["table_ii_percent"][b],
            )
            excluding_joint_zeros, removed = spearman_without_joint_zeros(
                vectors[dimension][a], vectors[dimension][b]
            )
            zero_checks.append({
                "dimension": dimension, "os_a": a, "os_b": b,
                "paper_rho_rounded": paper, "all_categories_rho": ours,
                "rho_from_published_table_ii": table_ii_rho,
                "all_categories_count": len(categories),
                "excluded_categories": ";".join(categories[i] for i in removed),
                "retained_categories_count": len(categories) - len(removed),
                "joint_zeros_excluded_rho": excluding_joint_zeros,
                "joint_zeros_excluded_matches_2dp": excluding_joint_zeros is not None and abs(excluding_joint_zeros - paper) <= 0.005 + 1e-12,
                "interpretation": "Controlled alternative; original paper does not specify treatment of jointly absent categories.",
            })
            row = {
                "dimension": dimension, "os_a": a, "os_b": b,
                "paper_rho_rounded": paper, "ours_rho": ours,
                "signed_gap": gap, "absolute_gap": None if gap is None else abs(gap),
                "matches_published_precision": gap is not None and abs(gap) <= 0.005 + 1e-12,
                "status": "comparable marginal distribution",
            }
            comparisons.append(row)
            dimension_rows.append(row)
        results[dimension] = {
            "categories": categories, "vectors": vectors[dimension],
            "os_order": list(OS_ORDER), "matrix": matrix,
            "matched_pairs": sum(row["matches_published_precision"] for row in dimension_rows),
            "pairs": 3,
            "verdict": "supported" if all(row["matches_published_precision"] for row in dimension_rows) else "partially supported",
        }
    overall_vectors = {
        os_name: [value for dimension in DIMENSIONS for value in vectors[dimension][os_name]] for os_name in OS_ORDER
    }
    overall_matrix = [[spearman(overall_vectors[a], overall_vectors[b]) for b in OS_ORDER] for a in OS_ORDER]
    overall_comparisons = []
    for a, b in combinations(OS_ORDER, 2):
        paper = float(panels["overall"]["matrix"][ref_order.index(a)][ref_order.index(b)])
        ours = spearman(overall_vectors[a], overall_vectors[b])
        row = {
            "dimension": "overall_concatenation_candidate", "os_a": a, "os_b": b,
            "paper_rho_rounded": paper, "ours_rho": ours,
            "signed_gap": None if ours is None else ours - paper,
            "absolute_gap": None if ours is None else abs(ours - paper),
            "matches_published_precision": None,
            "status": "not a verified reconstruction; paper omits overall construction",
        }
        comparisons.append(row)
        overall_comparisons.append(row)
    results["overall"] = {
        "construction_status": "not specified by paper",
        "verdict": "inconclusive",
        "candidate_definition": "Concatenate OS-layer, affected-function and trigger-scenario category counts (6+8+7=21 values) in Table II order, then Spearman correlate.",
        "candidate_os_order": list(OS_ORDER), "candidate_vectors": overall_vectors,
        "candidate_matrix": overall_matrix,
        "caution": "The candidate is a disclosed analytical choice, not evidence that Fig. 4d was exactly reproduced. Figure/prose pair labels disagree for the -0.11 value.",
        "comparisons": overall_comparisons,
    }
    fields = ["dimension", "os_a", "os_b", "paper_rho_rounded", "ours_rho", "signed_gap", "absolute_gap", "matches_published_precision", "status"]
    with (outdir / "similarity_comparison.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(comparisons)
    with (outdir / "similarity_rank_inputs.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["dimension", "os", "category", "count", "average_rank"])
        writer.writeheader()
        writer.writerows(vector_rows)
    with (outdir / "similarity_zero_category_check.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(zero_checks[0]))
        writer.writeheader()
        writer.writerows(zero_checks)
    zero_summary = {
        "factor_changed": "Treatment of categories with zero counts in both members of each OS pair",
        "default_policy": "Retain all taxonomy categories, including jointly zero categories.",
        "alternative_policy": "Remove a category for a pair only when both systems have count zero; keep all other methods and inputs fixed.",
        "matched_pairs": sum(row["joint_zeros_excluded_matches_2dp"] for row in zero_checks),
        "comparable_pairs": len(zero_checks),
        "checks": zero_checks,
        "interpretation": "An exact rounded match under an inferred convention is evidence of a plausible explanation, not proof that the authors used that convention.",
    }
    (outdir / "similarity_zero_category_check.json").write_text(json.dumps(zero_summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    summary = {
        "metric": "Spearman rank correlation; average ranks for ties",
        "tolerance_rho": 0.005,
        "comparable_pairs": 9,
        "matched_pairs": sum(row["matches_published_precision"] is True for row in comparisons if row["dimension"] in DIMENSIONS),
        "dimensions": results,
        "zero_category_sensitivity": zero_summary,
        "controlled_zero_category_check": zero_summary,
        "policy_matching": {
            "all_categories": {"matched_pairs": sum(row["matches_published_precision"] is True for row in comparisons if row["dimension"] in DIMENSIONS), "comparable_pairs": 9, "status": "default, fully aligned taxonomy"},
            "joint_zero_excluded": {"matched_pairs": zero_summary["matched_pairs"], "comparable_pairs": 9, "status": "inferred alternative convention, not author-confirmed"},
        },
        "scope": "Author-released categorical labels, with explicit treatment of under-specified overall comparison.",
    }
    (outdir / "similarity_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return summary
