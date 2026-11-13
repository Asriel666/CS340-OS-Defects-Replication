"""Explicit category-set sensitivity for the nine Figure 4(a-c) pairs.

The core analysis includes every canonical category. This supplementary module
keeps that result and compares two declared zero-category exclusion policies;
agreement with a figure is not proof of the authors' unpublished implementation.
"""

from itertools import combinations
import json
from pathlib import Path

from .common import OS_ORDER, write_csv, write_json
from .data import CANONICAL_CATEGORIES
from .similarity import SIMILARITY_DIMENSIONS, average_ranks, spearman, validate_similarity_reference
from .univariate import distribution


POLICIES = {
    "fixed_all": "Retain every canonical category, including zero counts (unchanged core method).",
    "global_nonzero": "Exclude a category only when its count is zero in all three systems.",
    "pairwise_nonzero": "Exclude a category only when its count is zero in both systems in this pair.",
}


def select_categories(categories, counts_by_os, os_a, os_b, policy):
    """Select from aligned category-keyed counts, rejecting omissions and extras."""
    categories = list(categories)
    if not categories or any(not isinstance(c, str) or not c for c in categories) or len(set(categories)) != len(categories):
        raise ValueError("Categories must be a nonempty sequence of unique names")
    if policy not in POLICIES:
        raise ValueError("Unknown category policy: " + str(policy))
    if set(counts_by_os) != set(OS_ORDER):
        raise ValueError("Counts must contain exactly Android, Linux and HarmonyOS")
    if os_a not in OS_ORDER or os_b not in OS_ORDER or os_a == os_b:
        raise ValueError("A comparison requires two distinct known systems")
    for os_name, counts in counts_by_os.items():
        if not isinstance(counts, dict) or set(counts) != set(categories):
            raise ValueError("Missing or extra category counts for " + os_name)
        if any(type(value) is not int or value < 0 for value in counts.values()):
            raise ValueError("Category counts must be nonnegative integers")
    compared_os = OS_ORDER if policy == "global_nonzero" else (os_a, os_b)
    return [category for category in categories
            if policy == "fixed_all" or any(counts_by_os[name][category] != 0 for name in compared_os)]


def compare_pair(categories, counts_by_os, os_a, os_b, policy):
    """Re-rank after category selection and represent undefined results explicitly."""
    categories = list(categories)
    kept = select_categories(categories, counts_by_os, os_a, os_b, policy)
    left = [counts_by_os[os_a][category] for category in kept]
    right = [counts_by_os[os_b][category] for category in kept]
    ranks_a = average_ranks(left) if left else []
    ranks_b = average_ranks(right) if right else []
    ours = spearman(left, right) if len(kept) >= 2 else None
    reason = "fewer_than_two_retained_categories" if len(kept) < 2 else "constant_retained_vector" if ours is None else None
    return {
        "retained_categories": kept,
        "excluded_categories": [category for category in categories if category not in kept],
        "retained_category_count": len(kept),
        "counts_a": left, "counts_b": right,
        "average_ranks_a": ranks_a, "average_ranks_b": ranks_b,
        "ours_rho": ours, "undefined_reason": reason,
    }


def analyze_category_policy(records, reference, outdir=None):
    """Compute all three predeclared policies for all three dimensions and pairs."""
    validate_similarity_reference(reference)
    records = list(records)
    if any(record.get("os") not in OS_ORDER for record in records):
        raise ValueError("Unknown operating system in category-policy input")
    groups = {name: [record for record in records if record["os"] == name] for name in OS_ORDER}
    rows, evidence, inputs = [], [], {}
    for dimension in SIMILARITY_DIMENSIONS:
        categories = list(CANONICAL_CATEGORIES[dimension])
        counts = {name: dict(zip(categories, distribution(groups[name], dimension, categories)[0])) for name in OS_ORDER}
        inputs[dimension] = {"categories": categories, "counts_by_os": counts}
        spec = reference["dimensions"][dimension]
        for policy in POLICIES:
            for os_a, os_b in combinations(OS_ORDER, 2):
                detail = compare_pair(categories, counts, os_a, os_b, policy)
                i, j = spec["os_order"].index(os_a), spec["os_order"].index(os_b)
                paper = spec["paper_matrix"][i][j]
                ours = detail["ours_rho"]
                matches = None if ours is None else round(ours, 2) == round(paper, 2)
                row = {
                    "policy": policy, "dimension": dimension, "os_a": os_a, "os_b": os_b,
                    **detail, "paper_rho": paper,
                    "difference": None if ours is None else ours - paper,
                    "matches_to_2dp": matches,
                    "status": "unconfirmed" if matches is None else "match" if matches else "mismatch",
                    "paper_source": spec["source_url"],
                }
                rows.append(row)
                retained_index = {category: index for index, category in enumerate(detail["retained_categories"])}
                for category in categories:
                    index = retained_index.get(category)
                    evidence.append({
                        "policy": policy, "dimension": dimension, "os_a": os_a, "os_b": os_b,
                        "category": category, "retained": index is not None,
                        "count_a": counts[os_a][category], "count_b": counts[os_b][category],
                        "counts_all_os": json.dumps({name: counts[name][category] for name in OS_ORDER}, ensure_ascii=False),
                        "average_rank_a": None if index is None else detail["average_ranks_a"][index],
                        "average_rank_b": None if index is None else detail["average_ranks_b"][index],
                        "paper_rho": paper, "ours_rho": ours, "status": row["status"],
                        "paper_source": spec["source_url"],
                    })
    statistics = {}
    for policy in POLICIES:
        selected = [row for row in rows if row["policy"] == policy]
        statistics[policy] = {
            "independent_pairs": len(selected),
            "matched_pairs": sum(row["status"] == "match" for row in selected),
            "mismatched_pairs": sum(row["status"] == "mismatch" for row in selected),
            "unconfirmed_pairs": sum(row["status"] == "unconfirmed" for row in selected),
            "pairs_with_exclusions": sum(bool(row["excluded_categories"]) for row in selected),
        }
    fixed = {(row["dimension"], row["os_a"], row["os_b"]): row for row in rows if row["policy"] == "fixed_all"}
    changed = [row for row in rows if row["policy"] != "fixed_all"
               and row["ours_rho"] != fixed[(row["dimension"], row["os_a"], row["os_b"])]["ours_rho"]]
    result = {
        "analysis": "category_set_sensitivity", "schema_version": 1,
        "policies": POLICIES, "policy_summary": statistics,
        "comparison_count": len(rows), "unique_published_pairs": 9,
        "inputs": inputs, "comparisons": rows, "changed_from_fixed_all": changed,
        "method": {
            "coefficient": "Existing similarity.spearman: Pearson correlation of ascending average ranks",
            "ties": "Recompute average ranks after category selection",
            "input": "Canonical category count vectors; policy changes only the shared category subset, never counts or algorithm",
            "comparison": "Compare rounded-to-two-decimal values to the same independently transcribed Figure 4(a-c) reference",
            "undefined": "Fewer than two retained categories or either retained vector constant: rho null, status unconfirmed",
        },
        "interpretation": "Exploratory category-set sensitivity, not an author-confirmed reconstruction. A matching candidate does not establish the authors' actual category policy. Core fixed_all results remain unchanged.",
    }
    if outdir is not None:
        outdir = Path(outdir)
        csv_rows = [{key: json.dumps(value, ensure_ascii=False) if isinstance(value, list) else value
                     for key, value in row.items()} for row in rows]
        write_csv(outdir / "category_policy_comparison.csv", csv_rows)
        write_csv(outdir / "category_policy_evidence.csv", evidence)
        write_csv(outdir / "category_policy_summary.csv", [{"policy": policy, **values} for policy, values in statistics.items()])
        write_json(outdir / "category_policy_summary.json", result)
    return result
