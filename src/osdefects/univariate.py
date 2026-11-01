"""Member C analysis: Table II counts recomputed from individual defect labels."""
from collections import Counter
from .common import OS_ORDER, relative_error, write_csv, write_json


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
    dimensions = dimensions or list(reference["dimensions"])
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
                             "matches_to_2dp": round(ours, 2) == round(paper, 2)})
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
