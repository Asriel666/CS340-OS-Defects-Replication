"""Table II counts recomputed from individual defect labels."""
from collections import Counter
import math
from .common import OS_ORDER, relative_error, write_csv, write_json
from .data import CANONICAL_CATEGORIES


def validate_reference(reference, dimensions):
    """Reject incomplete or misaligned paper tables before comparing any cell."""
    specs = reference.get("dimensions", {})
    for dimension in dimensions:
        if dimension not in CANONICAL_CATEGORIES or dimension not in specs:
            raise ValueError("Missing or unknown reference dimension: " + dimension)
        spec = specs[dimension]
        if spec.get("categories") != CANONICAL_CATEGORIES[dimension]:
            raise ValueError("Reference categories must follow canonical order: " + dimension)
        if spec.get("multilabel") is not (dimension == "code_level"):
            raise ValueError("Incorrect multilabel policy: " + dimension)
        values_by_os = spec.get("table_ii_percent", {})
        if set(values_by_os) != set(OS_ORDER):
            raise ValueError("Reference must contain exactly three operating systems: " + dimension)
        for os_name in OS_ORDER:
            values = values_by_os[os_name]
            if not isinstance(values, list) or len(values) != len(spec["categories"]):
                raise ValueError("Reference percentage length mismatch: " + dimension + "/" + os_name)
            if any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 100 for v in values):
                raise ValueError("Invalid reference percentage: " + dimension + "/" + os_name)
            if not spec["multilabel"] and not math.isclose(sum(values), 100, abs_tol=0.05):
                raise ValueError("Single-label reference percentages must total 100: " + dimension)


def distribution(records, field, categories, multilabel=False):
    counts = Counter()
    for record in records:
        labels = record[field] if multilabel else [record[field]]
        if len(labels) != len(set(labels)):
            raise ValueError("A defect has a repeated multilabel category")
        unexpected = set(labels) - set(categories)
        if unexpected:
            raise ValueError(f"Unknown {field} categories: {unexpected}")
        counts.update(labels)
    n = len(records)
    if not n:
        raise ValueError("Cannot compute a distribution from an empty corpus")
    return [counts[category] for category in categories], [100.0 * counts[category] / n for category in categories]


def analyze_univariate(records, reference, outdir, dimensions=None):
    from pathlib import Path
    outdir = Path(outdir)
    dimensions = list(CANONICAL_CATEGORIES) if dimensions is None else list(dimensions)
    if not dimensions or len(set(dimensions)) != len(dimensions):
        raise ValueError("Select at least one distinct dimension")
    validate_reference(reference, dimensions)
    rows, summary = [], {}
    for dimension in dimensions:
        spec = reference["dimensions"][dimension]
        dimension_summary = {}
        for os_name in OS_ORDER:
            group = [row for row in records if row["os"] == os_name]
            counts, percents = distribution(group, dimension, spec["categories"], spec["multilabel"])
            for category, count, ours, paper in zip(spec["categories"], counts, percents, spec["table_ii_percent"][os_name]):
                rows.append({"dimension": dimension, "os": os_name, "category": category,
                             "count": count, "n": len(group), "paper_percent": paper,
                             "ours_percent": ours, "difference_pp": round(ours-paper, 12),
                             "relative_error_percent": relative_error(ours, paper),
                             "matches_to_2dp": round(ours, 2) == round(paper, 2),
                             "status": "match" if round(ours, 2) == round(paper, 2) else "mismatch",
                             "paper_source": spec.get("source_url", "https://arxiv.org/html/2608.20643v1#S4.T2")})
            max_count = max(counts)
            dimension_summary[os_name] = {"n": len(group), "categories": spec["categories"], "counts": counts,
                                          "percent": percents, "dominant_categories": [c for c, n in zip(spec["categories"], counts) if n == max_count]}
        summary[dimension] = dimension_summary
    mismatches = [row for row in rows if not row["matches_to_2dp"]]
    result = {"cell_count": len(rows), "matched_cells": len(rows)-len(mismatches),
              "mismatches": mismatches, "dimensions": summary,
              "scope": "Statistical recomputation from released labels; not independent reconstruction or reannotation."}
    write_csv(outdir / "table_ii.csv", rows)
    write_json(outdir / "univariate_summary.json", result)
    return result
