"""RQ2: independently recompute the published Tables III-V from defect labels."""
from collections import Counter
import math
from pathlib import Path

from .common import OS_ORDER, write_csv, write_json
from .data import CANONICAL_CATEGORIES


TABLE_SPECS = {
    "table_iii": ("os_layer", "affected_function", "S4.T3"),
    "table_iv": ("os_layer", "trigger_scenario", "S4.T4"),
    "table_v": ("affected_function", "trigger_scenario", "S4.T5"),
}
PAPER_URL = "https://arxiv.org/html/2608.20643v1"


def validate_joint_reference(reference):
    """Reject incomplete/misaligned references; explicit null means unconfirmed.

    An omitted value is an error, whereas a present JSON null is retained as an
    unconfirmed comparison. Published blanks were transcribed as zero because
    all three table captions explicitly define this convention.
    """
    if not isinstance(reference, dict) or reference.get("schema_version") != 1:
        raise ValueError("Unsupported joint reference schema")
    if type(reference.get("per_os_n")) is not int or reference["per_os_n"] != 500:
        raise ValueError("Joint reference must use 500 defects per OS")
    if reference.get("os_order") != list(OS_ORDER):
        raise ValueError("Joint reference must follow canonical OS order")
    tables = reference.get("tables")
    if not isinstance(tables, dict) or set(tables) != set(TABLE_SPECS):
        raise ValueError("Joint reference requires exactly Tables III, IV, and V")
    for table_name, (row_field, col_field, anchor) in TABLE_SPECS.items():
        spec = tables[table_name]
        if not isinstance(spec, dict):
            raise ValueError("Joint table reference must be an object: " + table_name)
        if spec.get("row_field") != row_field or spec.get("column_field") != col_field:
            raise ValueError("Incorrect joint dimensions: " + table_name)
        row_categories = CANONICAL_CATEGORIES[row_field]
        column_categories = CANONICAL_CATEGORIES[col_field]
        if spec.get("row_categories") != row_categories or spec.get("column_categories") != column_categories:
            raise ValueError("Joint categories must follow canonical order: " + table_name)
        if spec.get("source_url") != PAPER_URL + "#" + anchor:
            raise ValueError("Missing or incorrect published table source: " + table_name)
        matrices = spec.get("paper_percent")
        if not isinstance(matrices, dict) or set(matrices) != set(OS_ORDER):
            raise ValueError("Joint reference requires exactly three operating systems: " + table_name)
        for os_name in OS_ORDER:
            matrix = matrices[os_name]
            location = table_name + "/" + os_name
            if not isinstance(matrix, list) or len(matrix) != len(row_categories):
                raise ValueError("Joint reference row count mismatch: " + location)
            for row in matrix:
                if not isinstance(row, list) or len(row) != len(column_categories):
                    raise ValueError("Joint reference column count mismatch: " + location)
                for value in row:
                    if value is not None and (type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 100):
                        raise ValueError("Invalid joint reference percentage: " + location)
            values = [v for row in matrix for v in row]
            confirmed_sum = sum(v for v in values if v is not None)
            if confirmed_sum > 100.05 or (None not in values and not math.isclose(confirmed_sum, 100, abs_tol=0.05)):
                raise ValueError("Joint reference percentages must total 100: " + location)


def joint_distribution(records, row_field, column_field):
    """Return joint counts and percentages of *all* supplied defect instances.

    Axes are fixed by the canonical label definitions. The separately counted
    one-dimensional margins are checked before this result is used downstream.
    This helper accepts small corpora for tests; analyze_joint enforces N=500.
    """
    supported = {"os_layer", "affected_function", "trigger_scenario"}
    if row_field not in supported or column_field not in supported or row_field == column_field:
        raise ValueError("Joint distribution requires two different single-label dimensions")
    records = list(records)
    if not records:
        raise ValueError("Cannot compute a joint distribution from an empty corpus")
    row_categories = CANONICAL_CATEGORIES[row_field]
    col_categories = CANONICAL_CATEGORIES[column_field]
    pairs = Counter()
    for record in records:
        row_value, col_value = record.get(row_field), record.get(column_field)
        if not isinstance(row_value, str) or row_value not in row_categories:
            raise ValueError("Unknown " + row_field + " category: " + repr(row_value))
        if not isinstance(col_value, str) or col_value not in col_categories:
            raise ValueError("Unknown " + column_field + " category: " + repr(col_value))
        pairs[row_value, col_value] += 1
    counts = [[pairs[row, col] for col in col_categories] for row in row_categories]
    n = len(records)
    row_marginals = [sum(row) for row in counts]
    col_marginals = [sum(row[j] for row in counts) for j in range(len(col_categories))]
    row_counter = Counter(record[row_field] for record in records)
    col_counter = Counter(record[column_field] for record in records)
    marginals_valid = (
        sum(row_marginals) == n
        and row_marginals == [row_counter[label] for label in row_categories]
        and col_marginals == [col_counter[label] for label in col_categories]
    )
    if not marginals_valid:
        raise ValueError("Joint matrix total or marginal invariant failed")
    return {
        "row_categories": list(row_categories),
        "column_categories": list(col_categories),
        "counts": counts,
        "percent": [[100.0 * value / n for value in row] for row in counts],
        "n": n,
        "row_marginal_counts": row_marginals,
        "column_marginal_counts": col_marginals,
        "marginals_valid": marginals_valid,
    }


def analyze_joint(records, reference, outdir):
    """Write all 438 comparisons and nine matrices without modifying references."""
    validate_joint_reference(reference)
    groups = {os_name: [] for os_name in OS_ORDER}
    for record in records:
        os_name = record.get("os")
        if os_name not in groups:
            raise ValueError("Unknown OS in joint analysis: " + repr(os_name))
        groups[os_name].append(record)
    if any(len(group) != reference["per_os_n"] for group in groups.values()):
        raise ValueError("Joint analysis requires 500 records per OS")
    rows, tables = [], {}
    for table_name, (row_field, col_field, _) in TABLE_SPECS.items():
        spec = reference["tables"][table_name]
        matrices = {}
        table_rows = []
        for os_name in OS_ORDER:
            matrix = joint_distribution(groups[os_name], row_field, col_field)
            matrices[os_name] = matrix
            for i, row_label in enumerate(matrix["row_categories"]):
                for j, col_label in enumerate(matrix["column_categories"]):
                    paper = spec["paper_percent"][os_name][i][j]
                    ours = matrix["percent"][i][j]
                    matches = None if paper is None else round(ours, 2) == round(paper, 2)
                    table_rows.append({
                        "table": table_name, "os": os_name,
                        "row_category": row_label, "column_category": col_label,
                        "count": matrix["counts"][i][j], "n": matrix["n"],
                        "paper_percent": paper, "ours_percent": ours,
                        "difference_pp": None if paper is None else round(ours - paper, 12),
                        "matches_to_2dp": matches,
                        "status": "unconfirmed" if paper is None else "match" if matches else "mismatch",
                        "paper_source": spec["source_url"],
                    })
        rows.extend(table_rows)
        tables[table_name] = {
            "row_field": row_field, "column_field": col_field,
            "matrices": matrices, "cell_count": len(table_rows),
            "matched_cells": sum(row["status"] == "match" for row in table_rows),
            "mismatched_cells": sum(row["status"] == "mismatch" for row in table_rows),
            "unconfirmed_cells": sum(row["status"] == "unconfirmed" for row in table_rows),
            "paper_source": spec["source_url"],
        }
    mismatches = [row for row in rows if row["status"] == "mismatch"]
    unconfirmed = [row for row in rows if row["status"] == "unconfirmed"]
    result = {
        "cell_count": len(rows),
        "matched_cells": sum(row["status"] == "match" for row in rows),
        "mismatched_cells": len(mismatches), "mismatches": mismatches,
        "unconfirmed_cells": len(unconfirmed), "unconfirmed": unconfirmed,
        "tables": tables,
        "denominator": "All 500 defects of each OS; no row normalization.",
        "scope": "Statistical recomputation from released labels; not independent reconstruction or reannotation.",
    }
    outdir = Path(outdir)
    write_csv(outdir / "joint_comparison.csv", rows)
    write_json(outdir / "joint_summary.json", result)
    return result
