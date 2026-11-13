"""Project-added analyses for the three remaining Figure 4 / repair-size gaps.

Nothing here is a verified replication, and nothing changes the 561 core
comparisons. Each part is explicitly labelled as an exploratory computation:

1. Figure 4(c): test whether any common input transform, category set or
   coefficient reproduces the published 0.38 for Android-HarmonyOS trigger
   scenarios. The paper does not publish the actual input vectors.
2. Figure 4(d): compute Overall correlations under explicit candidate
   aggregation rules and compare them with the published heatmap values,
   while keeping the status "unconfirmed" (the input definition is missing
   and the paper's prose contradicts its own figure).
3. Figures 2/3: export a structured evidence checklist for the 177
   zero-function records and the 7 censored "n+" records, with local
   cross-field consistency statistics. No patch content is fetched, no
   author value is changed, and no human patch review is implied.
"""

from itertools import combinations, product
import math
from pathlib import Path
from urllib.parse import urlparse

from .common import OS_ORDER, write_csv, write_json
from .data import CANONICAL_CATEGORIES
from .similarity import (
    SIMILARITY_DIMENSIONS, average_ranks, spearman, validate_similarity_reference,
)
from .univariate import distribution

TRANSFORMS = ("counts", "proportions", "log1p", "binary")
CATEGORY_SETS = ("all_categories", "drop_all_zero_categories")
COEFFICIENTS = ("spearman", "pearson")
VECTOR_DEFINITIONS = (
    "concat_counts", "concat_proportions", "concat_log1p", "concat_binary",
    "concat_per_dimension_ranks", "weighted_by_category_count",
)
AGGREGATION_DEFINITIONS = ("mean_of_dimension_rho", "median_of_dimension_rho")
CANDIDATE_TOLERANCE = 0.005  # rounds to 0.38 at two decimals


def validate_gap_reference(reference):
    """Require the transcribed Figure 4(a-c) matrices and the excluded 4(d) panel."""
    validate_similarity_reference(reference)
    overall = reference.get("excluded", {}).get("overall")
    if not isinstance(overall, dict) or overall.get("status") != "unconfirmed":
        raise ValueError("Figure 4(d) must remain explicitly unconfirmed")
    order = overall.get("os_order")
    triangle = overall.get("published_lower_triangle")
    if not isinstance(order, list) or len(order) != 3 or set(order) != set(OS_ORDER):
        raise ValueError("Figure 4(d) baseline must cover the three operating systems")
    if not isinstance(triangle, list) or len(triangle) != 3:
        raise ValueError("Figure 4(d) lower triangle must have three rows")
    for index, row in enumerate(triangle):
        if not isinstance(row, list) or len(row) != index + 1:
            raise ValueError("Figure 4(d) lower triangle shape is invalid")
        if any(type(value) not in (int, float) or not -1 <= value <= 1 for value in row):
            raise ValueError("Figure 4(d) published coefficients must be in [-1, 1]")
    if not isinstance(overall.get("source_url"), str) or not overall["source_url"].startswith("https://"):
        raise ValueError("Figure 4(d) baseline needs its published source URL")


def pearson(x, y):
    """Pearson correlation of raw values; constant inputs return None."""
    x, y = list(x), list(y)
    if len(x) != len(y) or len(x) < 2:
        raise ValueError("Pearson requires equal vector lengths of at least two")
    if any(type(value) not in (int, float) or not math.isfinite(value) for value in x + y):
        raise ValueError("Pearson inputs must be finite real numbers")
    mx, my = math.fsum(x) / len(x), math.fsum(y) / len(y)
    xc, yc = [value - mx for value in x], [value - my for value in y]
    xx, yy = math.fsum(v * v for v in xc), math.fsum(v * v for v in yc)
    if xx == 0 or yy == 0:
        return None
    return max(-1.0, min(1.0, math.fsum(a * b for a, b in zip(xc, yc)) / math.sqrt(xx * yy)))


def _coefficient(x, y, name):
    if name == "spearman":
        return spearman(x, y)
    if name == "pearson":
        return pearson(x, y)
    raise ValueError("Unknown coefficient: " + repr(name))


def _groups(records):
    groups = {name: [record for record in records if record["os"] == name] for name in OS_ORDER}
    if any(len(group) != 500 for group in groups.values()):
        raise ValueError("Gap analysis expects 500 records per operating system")
    return groups


def _count_vectors(groups, dimension, category_set):
    categories = list(CANONICAL_CATEGORIES[dimension])
    counts = {name: distribution(group, dimension, categories)[0] for name, group in groups.items()}
    if category_set == "drop_all_zero_categories":
        keep = [index for index in range(len(categories))
                if any(counts[name][index] for name in OS_ORDER)]
        categories = [categories[index] for index in keep]
        counts = {name: [counts[name][index] for index in keep] for name in OS_ORDER}
    elif category_set != "all_categories":
        raise ValueError("Unknown category set: " + repr(category_set))
    return counts, categories


def _transform(values, name, n):
    if name == "counts":
        return [float(value) for value in values]
    if name == "proportions":
        return [value / n for value in values]
    if name == "log1p":
        return [math.log1p(value) for value in values]
    if name == "binary":
        return [1.0 if value > 0 else 0.0 for value in values]
    raise ValueError("Unknown transform: " + repr(name))


def _paper_rho(reference, dimension, os_a, os_b):
    spec = reference["dimensions"][dimension]
    order = spec["os_order"]
    return spec["paper_matrix"][order.index(os_a)][order.index(os_b)]


def explore_figure4c(groups, reference):
    """Enumerate common conventions and look for the published 0.38."""
    spec = reference["dimensions"]["trigger_scenario"]
    target = _paper_rho(reference, "trigger_scenario", "Android", "HarmonyOS")
    rows = []
    for dimension, category_set, transform, coefficient in product(
            SIMILARITY_DIMENSIONS, CATEGORY_SETS, TRANSFORMS, COEFFICIENTS):
        counts, categories = _count_vectors(groups, dimension, category_set)
        vectors = {name: _transform(counts[name], transform, len(group))
                   for name, group in groups.items()}
        for os_a, os_b in combinations(OS_ORDER, 2):
            rho = None if len(categories) < 2 else _coefficient(vectors[os_a], vectors[os_b], coefficient)
            paper = _paper_rho(reference, dimension, os_a, os_b)
            difference = None if rho is None else abs(rho - target)
            is_target = dimension == "trigger_scenario" and {os_a, os_b} == {"Android", "HarmonyOS"}
            rows.append({
                "dimension": dimension, "category_set": category_set, "categories_kept": len(categories),
                "transform": transform, "coefficient": coefficient,
                "os_a": os_a, "os_b": os_b,
                "paper_rho": paper, "target_rho_0_38": target, "ours_rho": rho,
                "abs_difference_from_target": difference,
                "matches_published_pair": None if rho is None else round(rho, 2) == round(paper, 2),
                "is_android_harmony_trigger_pair": is_target,
                "candidate_for_0_38": bool(is_target and difference is not None and difference <= CANDIDATE_TOLERANCE),
                "status": "exploratory_not_replication",
                "paper_source": spec["source_url"],
            })
    target_rows = [row for row in rows if row["is_android_harmony_trigger_pair"] and row["ours_rho"] is not None]
    defined = sorted(target_rows, key=lambda row: row["abs_difference_from_target"])
    anywhere = [row for row in rows if row["ours_rho"] is not None]
    nearest_anywhere = sorted(anywhere, key=lambda row: row["abs_difference_from_target"])[:5]
    return {
        "target_rho": target, "candidate_tolerance": CANDIDATE_TOLERANCE,
        "enumeration_count": len(rows),
        "target_pair_variants": len(target_rows),
        "candidates": [row for row in rows if row["candidate_for_0_38"]],
        "closest_variants": defined[:5],
        "closest_anywhere": nearest_anywhere,
        "candidates_anywhere": sum(1 for row in anywhere
                                   if row["abs_difference_from_target"] <= CANDIDATE_TOLERANCE),
        "note": "A matching variant is a compatibility observation only; it does not establish the authors' actual method. nearest_anywhere includes other dimensions and system pairs and is evidence about possible transcription errors, not a replication.",
    }, rows


def _overall_vector(groups, definition):
    per_dimension = {}
    for dimension in SIMILARITY_DIMENSIONS:
        categories = list(CANONICAL_CATEGORIES[dimension])
        per_dimension[dimension] = {
            name: distribution(group, dimension, categories)[0] for name, group in groups.items()
        }
    vectors = {}
    for name, group in groups.items():
        if definition == "concat_counts":
            values = [float(value) for dimension in SIMILARITY_DIMENSIONS for value in per_dimension[dimension][name]]
        elif definition == "concat_proportions":
            values = [value / len(group) for dimension in SIMILARITY_DIMENSIONS for value in per_dimension[dimension][name]]
        elif definition == "concat_log1p":
            values = [math.log1p(value) for dimension in SIMILARITY_DIMENSIONS for value in per_dimension[dimension][name]]
        elif definition == "concat_binary":
            values = [1.0 if value > 0 else 0.0 for dimension in SIMILARITY_DIMENSIONS for value in per_dimension[dimension][name]]
        elif definition == "concat_per_dimension_ranks":
            values = [rank for dimension in SIMILARITY_DIMENSIONS
                      for rank in average_ranks(per_dimension[dimension][name])]
        elif definition == "weighted_by_category_count":
            values = [value / len(CANONICAL_CATEGORIES[dimension])
                      for dimension in SIMILARITY_DIMENSIONS for value in per_dimension[dimension][name]]
        else:
            raise ValueError("Unknown Overall vector definition: " + repr(definition))
        vectors[name] = values
    return vectors, per_dimension


def explore_figure4d(groups, reference):
    """Compare candidate aggregation rules with the published 4(d) values."""
    overall = reference["excluded"]["overall"]
    order, triangle = overall["os_order"], overall["published_lower_triangle"]
    published = {}
    for i in range(3):
        for j in range(i):
            published[frozenset((order[i], order[j]))] = triangle[i][j]
    rows = []
    for definition, coefficient in product(VECTOR_DEFINITIONS, COEFFICIENTS):
        vectors, _ = _overall_vector(groups, definition)
        for os_a, os_b in combinations(OS_ORDER, 2):
            rho = _coefficient(vectors[os_a], vectors[os_b], coefficient)
            paper = published[frozenset((os_a, os_b))]
            rows.append({
                "definition": definition, "coefficient": coefficient,
                "os_a": os_a, "os_b": os_b, "paper_rho": paper, "ours_rho": rho,
                "difference": None if rho is None else rho - paper,
                "abs_difference": None if rho is None else abs(rho - paper),
                "status": "unconfirmed_candidate", "scope": "project_added_analysis",
                "paper_source": overall["source_url"],
            })
    for definition in AGGREGATION_DEFINITIONS:
        per_dimension_rho = {}
        for dimension in SIMILARITY_DIMENSIONS:
            counts_by_dimension = {
                name: distribution(group, dimension, list(CANONICAL_CATEGORIES[dimension]))[0]
                for name, group in groups.items()
            }
            for os_a, os_b in combinations(OS_ORDER, 2):
                per_dimension_rho.setdefault((os_a, os_b), []).append(
                    spearman(counts_by_dimension[os_a], counts_by_dimension[os_b]))
        for (os_a, os_b), values in per_dimension_rho.items():
            defined = [value for value in values if value is not None]
            rho = (sum(defined) / len(defined) if definition == "mean_of_dimension_rho"
                   else sorted(defined)[len(defined) // 2]) if defined else None
            paper = published[frozenset((os_a, os_b))]
            rows.append({
                "definition": definition, "coefficient": "mean_or_median_of_spearman",
                "os_a": os_a, "os_b": os_b, "paper_rho": paper, "ours_rho": rho,
                "difference": None if rho is None else rho - paper,
                "abs_difference": None if rho is None else abs(rho - paper),
                "status": "unconfirmed_candidate", "scope": "project_added_analysis",
                "paper_source": overall["source_url"],
            })
    scores = {}
    for row in rows:
        key = (row["definition"], row["coefficient"])
        if row["abs_difference"] is not None:
            scores.setdefault(key, []).append(row["abs_difference"])
    ranked = sorted(({"definition": key[0], "coefficient": key[1],
                      "mean_abs_difference": sum(values) / len(values), "pairs": len(values)}
                     for key, values in scores.items() if len(values) == 3),
                    key=lambda item: item["mean_abs_difference"])
    return {
        "candidate_count": len(rows), "ranked_definitions": ranked,
        "closest_definition": ranked[0] if ranked else None,
        "note": "The paper never defines the Overall input vector, concatenation or weighting; prose also contradicts the figure. Every row stays unconfirmed and is excluded from the 561 core comparisons.",
        "published_values": {f"{a}-{b}": published[frozenset((a, b))] for a, b in combinations(OS_ORDER, 2)},
    }, rows


def repair_evidence(records):
    """Structured checklist and local cross-field checks, without fetching patches."""
    rows, zeros, censored = [], [], []
    for record in records:
        reasons = []
        if record["involved_functions"] == 0:
            reasons.append("zero_involved_functions")
            zeros.append(record)
        if "involved_functions" in record.get("numeric_censored", []):
            reasons.append("censored_lower_bound")
            censored.append(record)
        if not reasons:
            continue
        rows.append({
            "os": record["os"], "bug_id": record["bug_id"],
            "raw_involved_functions": record["raw"]["Involved Functions"],
            "normalized_involved_functions": record["involved_functions"],
            "line_changes": record["line_changes"], "line_deletions": record["line_deletions"],
            "line_additions": record["line_additions"], "modified_files": record["modified_files"],
            "os_layer": record["os_layer"], "patch": record["patch"],
            "patch_host": urlparse(record["patch"]).netloc,
            "anomaly_reasons": "|".join(reasons),
            "evidence_status": "pending_manual_patch_review",
            "patch_accessible": "", "verified_function_count": "",
            "reviewer_evidence": "", "adjudication": "",
        })
    stats = {
        "zero_function_records": len(zeros),
        "zero_records_with_multiple_modified_files": sum(1 for record in zeros if record["modified_files"] > 1),
        "zero_records_with_line_changes_ge_50": sum(1 for record in zeros if record["line_changes"] >= 50),
        "zero_records_with_both_signals": sum(1 for record in zeros
                                              if record["modified_files"] > 1 and record["line_changes"] >= 50),
        "zero_records_by_os": {name: sum(1 for record in zeros if record["os"] == name) for name in OS_ORDER},
        "censored_records": len(censored),
        "censored_raw_labels": sorted({str(record["raw"]["Involved Functions"]) for record in censored}),
        "censored_records_by_os": {name: sum(1 for record in censored if record["os"] == name) for name in OS_ORDER},
        "distinct_patch_hosts": sorted({urlparse(record["patch"]).netloc for record in zeros + censored}),
        "interpretation": "Of the zero-function records, 81 involve multiple modified files and 10 change at least 50 lines (9 satisfy both). These subset signals are more consistent with unrecorded function counts than with genuine zero-function fixes, but the majority of zero records are single-file, smaller changes; the data cannot settle the question. No source value is changed and no patch content was fetched.",
        "limitation": "An automated checklist is not patch review. Verifying actual function counts requires reading each linked patch and must be recorded by a human reviewer.",
    }
    return stats, rows


def analyze_gaps(records, reference, outdir=None, write_outputs=True):
    """Compute all three exploratory analyses; write once when requested."""
    validate_gap_reference(reference)
    groups = _groups(records)
    c_summary, c_rows = explore_figure4c(groups, reference)
    d_summary, d_rows = explore_figure4d(groups, reference)
    evidence_stats, evidence_rows = repair_evidence(records)
    result = {
        "scope": "Project-added exploratory analyses for the three remaining gaps; not a verified replication and not part of the 561 core comparisons.",
        "figure_4c": c_summary, "figure_4d": d_summary,
        "repair_evidence": {"statistics": evidence_stats, "row_count": len(evidence_rows)},
    }
    if write_outputs:
        if outdir is None:
            raise ValueError("write_outputs=True requires an output directory")
        outdir = Path(outdir)
        write_csv(outdir / "figure_4c_exploration.csv", c_rows)
        write_csv(outdir / "figure_4d_candidates.csv", d_rows)
        write_csv(outdir / "repair_anomaly_evidence.csv", evidence_rows)
        write_json(outdir / "gap_analysis_summary.json", result)
    return result
