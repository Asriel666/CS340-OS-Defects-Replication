"""Recompute Figure 4(a-c) using Pearson correlation of average ranks.

No defect labels or published coefficients are inferred from one another. The
paper's lower triangles are transcribed separately, with their original axes.
"""

from itertools import combinations
import math
from pathlib import Path

from .common import OS_ORDER, write_csv, write_json
from .data import CANONICAL_CATEGORIES
from .univariate import distribution


SIMILARITY_DIMENSIONS = ("os_layer", "affected_function", "trigger_scenario")
PAPER_OS_ORDER = ("Android", "HarmonyOS", "Linux")


def _finite_values(values):
    values = list(values)
    try:
        valid = all(type(value) in (int, float) and math.isfinite(value) for value in values)
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError("Correlation inputs must contain only finite real numbers")
    return values


def average_ranks(values):
    """Return one-based ascending ranks; equal values share their mean rank."""
    values = _finite_values(values)
    if not values:
        raise ValueError("Cannot rank an empty vector")
    order = sorted(range(len(values)), key=values.__getitem__)
    ranks = [0.0] * len(values)
    start = 0
    while start < len(order):
        stop = start + 1
        while stop < len(order) and values[order[stop]] == values[order[start]]:
            stop += 1
        rank = (start + 1 + stop) / 2.0
        for index in order[start:stop]:
            ranks[index] = rank
        start = stop
    return ranks


def spearman(x, y):
    """Pearson correlation of average ranks; constant inputs return None.

Vectors must have equal length, at least two entries and only finite numbers.
The rank-difference shortcut without tie correction is deliberately not used.
"""
    x, y = _finite_values(x), _finite_values(y)
    if len(x) != len(y) or len(x) < 2:
        raise ValueError("Spearman requires equal vector lengths of at least two")
    xr, yr = average_ranks(x), average_ranks(y)
    mean = (len(x) + 1) / 2.0
    xc, yc = [rank - mean for rank in xr], [rank - mean for rank in yr]
    xx, yy = math.fsum(value * value for value in xc), math.fsum(value * value for value in yc)
    if xx == 0 or yy == 0:
        return None
    rho = math.fsum(a * b for a, b in zip(xc, yc)) / math.sqrt(xx * yy)
    return max(-1.0, min(1.0, rho))


def validate_similarity_reference(reference):
    """Reject missing pairs, swapped axes, and malformed published matrices."""
    specs = reference.get("dimensions", {})
    if set(specs) != set(SIMILARITY_DIMENSIONS):
        raise ValueError("Similarity reference must contain exactly the three Figure 4(a-c) dimensions")
    for dimension in SIMILARITY_DIMENSIONS:
        spec = specs[dimension]
        if spec.get("categories") != CANONICAL_CATEGORIES[dimension]:
            raise ValueError("Reference categories must follow canonical order: " + dimension)
        if spec.get("os_order") != list(PAPER_OS_ORDER):
            raise ValueError("Published Figure 4 axes must be Android, HarmonyOS, Linux")
        matrix = spec.get("paper_matrix")
        if not isinstance(matrix, list) or len(matrix) != 3:
            raise ValueError("Published correlation matrix must have three rows")
        for row in matrix:
            if not isinstance(row, list) or len(row) != 3:
                raise ValueError("Published correlation matrix must have three columns")
            values = _finite_values(row)
            if any(not -1 <= value <= 1 for value in values):
                raise ValueError("Published correlation coefficients must be in [-1, 1]")
        for i in range(3):
            if matrix[i][i] != 1:
                raise ValueError("Published correlation diagonal must equal one")
            for j in range(i):
                if matrix[i][j] != matrix[j][i]:
                    raise ValueError("Published correlation matrix must be symmetric")
        if not isinstance(spec.get("source_url"), str) or not spec["source_url"].startswith("https://"):
            raise ValueError("Each correlation reference needs its published source URL")


def analyze_similarity(records, reference, outdir):
    """Compare nine independent OS pairs and retain input vectors as evidence."""
    validate_similarity_reference(reference)
    outdir = Path(outdir)
    records = list(records)
    if any(record["os"] not in OS_ORDER for record in records):
        raise ValueError("Unknown operating system in similarity input")
    groups = {os_name: [record for record in records if record["os"] == os_name] for os_name in OS_ORDER}
    rows, dimensions = [], {}
    for dimension in SIMILARITY_DIMENSIONS:
        spec = reference["dimensions"][dimension]
        categories = list(CANONICAL_CATEGORIES[dimension])
        counts, percent_vectors = {}, {}
        for os_name in OS_ORDER:
            counts[os_name], percent_vectors[os_name] = distribution(groups[os_name], dimension, categories)
        matrix = [[spearman(counts[a], counts[b]) for b in OS_ORDER] for a in OS_ORDER]
        source_indices = [spec["os_order"].index(os_name) for os_name in OS_ORDER]
        paper_matrix = [[spec["paper_matrix"][i][j] for j in source_indices] for i in source_indices]
        for i, j in combinations(range(len(OS_ORDER)), 2):
            ours, paper = matrix[i][j], paper_matrix[i][j]
            matches = None if ours is None else round(ours, 2) == round(paper, 2)
            rows.append({
                "dimension": dimension, "os_a": OS_ORDER[i], "os_b": OS_ORDER[j],
                "paper_rho": paper, "ours_rho": ours,
                "difference": None if ours is None else ours - paper,
                "matches_to_2dp": matches,
                "status": "unconfirmed" if matches is None else "match" if matches else "mismatch",
                "paper_source": spec["source_url"],
            })
        dimensions[dimension] = {
            "os_order": list(OS_ORDER), "matrix": matrix, "paper_matrix": paper_matrix,
            "categories": categories, "counts": counts, "percent_vectors": percent_vectors,
            "average_ranks": {os_name: average_ranks(counts[os_name]) for os_name in OS_ORDER},
            "n_by_os": {os_name: len(groups[os_name]) for os_name in OS_ORDER},
            "paper_axis_order": list(spec["os_order"]), "paper_source": spec["source_url"],
        }
    result = {
        "cell_count": len(rows), "matched_cells": sum(row["status"] == "match" for row in rows),
        "unconfirmed_cells": sum(row["status"] == "unconfirmed" for row in rows),
        "mismatches": [row for row in rows if row["status"] == "mismatch"],
        "unconfirmed": [row for row in rows if row["status"] == "unconfirmed"],
        "dimensions": dimensions,
        "method": {
            "coefficient": "Spearman: Pearson correlation of ascending average ranks",
            "input": "Category count vectors aligned in CANONICAL_CATEGORIES order, including zero counts",
            "ties": "Equal values receive the average of their one-based ranks",
            "constant_vector": "Undefined (JSON null / blank CSV); status unconfirmed",
            "comparison": "Nine independent off-diagonal pairs; compare after rounding to two decimal places",
            "precision": "Full float precision retained for coefficients, differences and input evidence",
            "normalization": "Within each OS, counts and percentages have identical ranks",
        },
        "excluded": reference.get("excluded", {}),
        "scope": "Statistical recomputation from released labels; not independent reconstruction or reannotation.",
    }
    write_csv(outdir / "similarity_comparison.csv", rows)
    write_json(outdir / "similarity_summary.json", result)
    return result
