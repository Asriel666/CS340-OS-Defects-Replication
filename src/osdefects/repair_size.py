"""Repair-size binning sensitivity for published Figures 2 and 3.

The paper prints an exact percentage on every bar but never states the bin
boundary convention, where zero involved-function records land, or how
censored counts such as "10+" are placed. This module recomputes every
published series under explicit alternative conventions and compares each
recomputation with the published bar labels. No convention is adopted as the
paper's method: every variant is reported, and a matching variant is evidence
of consistency, not proof of the authors' actual choice.

This analysis is a project addition. It is not part of the 561 core
comparisons of RQ1/RQ2/RQ3 and must not be counted as verified replication.
"""

import math
from pathlib import Path

from .common import OS_ORDER, relative_error, write_csv, write_json
from .data import NUMERIC_FIELDS

BOUNDARY_CONVENTIONS = ("left_closed", "right_closed")
# "lower_bound" places a censored count such as 10+ into the bin of its lower
# bound; "unassigned" keeps it out of every bin while retaining it in the
# denominator. Only involved_functions contains censored values.
CENSORED_POLICIES = ("lower_bound", "unassigned")
CENSORED_METRIC = "involved_functions"


def validate_figure_reference(reference):
    """Reject incomplete, misaligned, or fabricated-looking figure baselines."""
    if reference.get("provenance", {}).get("kind") != "transcribed_from_published_bar_labels":
        raise ValueError("Figure baselines must declare published-bar-label provenance")
    series_list = reference.get("series")
    if not isinstance(series_list, list) or not series_list:
        raise ValueError("Figure baselines must contain a nonempty series list")
    seen = set()
    for series in series_list:
        if not isinstance(series, dict):
            raise ValueError("Each series must be an object")
        series_id = series.get("series_id")
        if not isinstance(series_id, str) or not series_id or series_id in seen:
            raise ValueError("Missing or duplicate series_id: " + repr(series_id))
        seen.add(series_id)
        metric = series.get("metric")
        if metric not in NUMERIC_FIELDS:
            raise ValueError("Unknown repair-size metric: " + repr(metric))
        edges = series.get("bin_edges")
        labels = series.get("bin_labels")
        if not isinstance(edges, list) or len(edges) < 2 or any(type(e) is not int or e < 0 for e in edges):
            raise ValueError("bin_edges must be nonnegative integers: " + series_id)
        if any(a >= b for a, b in zip(edges, edges[1:])):
            raise ValueError("bin_edges must strictly increase: " + series_id)
        if not isinstance(labels, list) or len(labels) != len(edges) - 1:
            raise ValueError("bin_labels must match the bin count: " + series_id)
        paper = series.get("paper_percent")
        if not isinstance(paper, dict) or set(paper) != set(OS_ORDER):
            raise ValueError("paper_percent must cover exactly the three operating systems: " + series_id)
        for os_name in OS_ORDER:
            values = paper[os_name]
            if not isinstance(values, list) or len(values) != len(edges) - 1:
                raise ValueError("paper_percent length mismatch: " + series_id + "/" + os_name)
            if any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 100 for v in values):
                raise ValueError("Invalid paper percentage: " + series_id + "/" + os_name)
            if not math.isclose(sum(values), 100.0, abs_tol=0.05):
                raise ValueError("Published bins must total 100 percent: " + series_id + "/" + os_name)


def assign_bin(value, edges, convention):
    """Return the bin index under a boundary convention, or None when outside.

    left_closed: bin i is [edges[i], edges[i+1]); the final bin is closed on
    both ends. right_closed: bin i is (edges[i], edges[i+1]]; a value equal to
    the first edge therefore falls outside every bin, which is exactly the
    ambiguity the published labels cannot resolve.
    """
    if convention not in BOUNDARY_CONVENTIONS:
        raise ValueError("Unknown boundary convention: " + repr(convention))
    if type(value) is not int or value < 0:
        raise ValueError("Bin assignment expects a nonnegative integer: " + repr(value))
    last = len(edges) - 2
    for index in range(last + 1):
        low, high = edges[index], edges[index + 1]
        if index == last:
            inside = low <= value <= high
        elif convention == "left_closed":
            inside = low <= value < high
        else:
            inside = low < value <= high
        if inside:
            return index
    return None


def convention_configs(metric):
    """All (boundary, censored) configurations for one metric, in fixed order."""
    configs = []
    for boundary in BOUNDARY_CONVENTIONS:
        if metric == CENSORED_METRIC:
            for censored in CENSORED_POLICIES:
                configs.append((boundary, censored))
        else:
            configs.append((boundary, "not_applicable"))
    return configs


def bin_distribution(group, edges, convention, censored_policy, metric):
    """Bin one OS group; the denominator is always the full group size."""
    counts = [0] * (len(edges) - 1)
    outside = []
    n = len(group)
    if not n:
        raise ValueError("Cannot bin an empty OS group")
    for record in group:
        value = record[metric]
        censored = metric in record.get("numeric_censored", [])
        if censored and censored_policy == "unassigned":
            outside.append({"os": record["os"], "bug_id": record["bug_id"], "value": value,
                            "reason": "censored_count_left_unassigned"})
            continue
        index = assign_bin(value, edges, convention)
        if index is None:
            outside.append({"os": record["os"], "bug_id": record["bug_id"], "value": value,
                            "reason": "value_outside_all_bins_under_convention"})
        else:
            counts[index] += 1
    percents = [100.0 * count / n for count in counts]
    return counts, percents, outside


def _comparison_rows(series, config_rows, paper_source):
    rows = []
    for os_name, per_os in config_rows.items():
        for index, (label, ours) in enumerate(zip(series["bin_labels"], per_os["percent"])):
            paper = series["paper_percent"][os_name][index]
            rows.append({
                "series_id": series["series_id"], "figure": series["figure"], "metric": series["metric"],
                "boundary_convention": per_os["boundary"], "censored_policy": per_os["censored"],
                "os": os_name, "bin_label": label, "bin_index": index,
                "paper_percent": paper, "ours_percent": ours, "count": per_os["counts"][index],
                "n": per_os["n"], "difference_pp": round(ours - paper, 12),
                "relative_error_percent": relative_error(ours, paper),
                "matches_to_2dp": round(ours, 2) == round(paper, 2),
                "status": "match" if round(ours, 2) == round(paper, 2) else "mismatch",
                "outside_bin_count": len(per_os["outside"]),
                "paper_source": paper_source,
            })
    return rows


def analyze_repair_size(records, reference, outdir, write_outputs=True):
    """Compare every published series under every convention; report all of them.

    Pass write_outputs=False to compute in memory only (used by the entry
    script to verify determinism before anything is written to disk).
    """
    from collections import defaultdict
    validate_figure_reference(reference)
    if outdir is not None:
        outdir = Path(outdir)
    images = reference.get("provenance", {}).get("figure_images", {})
    by_os = defaultdict(list)
    for record in records:
        by_os[record["os"]].append(record)
    if set(by_os) != set(OS_ORDER) or any(len(by_os[name]) != 500 for name in OS_ORDER):
        raise ValueError("Repair-size analysis expects 500 records per operating system")
    all_rows, summary = [], {}
    for series in reference["series"]:
        metric, edges = series["metric"], series["bin_edges"]
        paper_source = images.get(series["figure"].lower().replace(" ", "_"), "")
        series_configs = {}
        for boundary, censored in convention_configs(metric):
            config_rows, outside_total = {}, []
            for os_name in OS_ORDER:
                counts, percents, outside = bin_distribution(
                    by_os[os_name], edges, boundary, censored, metric)
                outside_total.extend(outside)
                config_rows[os_name] = {"boundary": boundary, "censored": censored, "n": len(by_os[os_name]),
                                        "counts": counts, "percent": percents, "outside": outside}
            rows = _comparison_rows(series, config_rows, paper_source)
            all_rows.extend(rows)
            series_configs[boundary + "/" + censored] = {
                "boundary_convention": boundary, "censored_policy": censored,
                "cells": len(rows), "matches": sum(1 for row in rows if row["matches_to_2dp"]),
                "records_outside_bins": len(outside_total),
                "outside_records": outside_total,
                "per_os": {name: {"counts": config_rows[name]["counts"],
                                  "percent": config_rows[name]["percent"],
                                  "outside_bin_count": len(config_rows[name]["outside"])}
                           for name in OS_ORDER},
            }
        summary[series["series_id"]] = {
            "figure": series["figure"], "metric": metric, "bin_labels": series["bin_labels"],
            "bin_edges": edges, "paper_percent": series["paper_percent"],
            "n_per_os": {name: len(by_os[name]) for name in OS_ORDER},
            "configurations": series_configs,
        }
    result = {
        "scope": "Project-added sensitivity analysis of published Figure 2/3 binning conventions; not part of the 561 core comparisons.",
        "series_count": len(summary),
        "comparison_count": len(all_rows),
        "matched_cells": sum(1 for row in all_rows if row["matches_to_2dp"]),
        "series": summary,
    }
    if write_outputs:
        if outdir is None:
            raise ValueError("write_outputs=True requires an output directory")
        fieldnames = ["series_id", "figure", "metric", "boundary_convention", "censored_policy", "os",
                      "bin_label", "bin_index", "paper_percent", "ours_percent", "count", "n",
                      "difference_pp", "relative_error_percent", "matches_to_2dp", "status",
                      "outside_bin_count", "paper_source"]
        write_csv(outdir / "convention_comparison.csv", all_rows, fieldnames)
        match_rows = []
        for series_id, info in summary.items():
            for key, config in info["configurations"].items():
                match_rows.append({"series_id": series_id, "figure": info["figure"], "metric": info["metric"],
                                   "boundary_convention": config["boundary_convention"],
                                   "censored_policy": config["censored_policy"],
                                   "cells": config["cells"], "matches": config["matches"],
                                   "mismatches": config["cells"] - config["matches"],
                                   "records_outside_bins": config["records_outside_bins"]})
        write_csv(outdir / "config_match_summary.csv", match_rows)
        write_json(outdir / "repair_size_sensitivity.json", result)
    return result


def make_repair_size_plots(result, outdir):
    """One grouped-bar figure per series and convention, reusing the stage style."""
    from .plots import grouped_bars
    outdir = Path(outdir)
    paths = []
    for series_id, info in result["series"].items():
        for key, config in info["configurations"].items():
            boundary, censored = config["boundary_convention"], config["censored_policy"]
            sign = {"left_closed": "[lo, hi)", "right_closed": "(lo, hi]"}[boundary]
            subtitle = "Bins " + sign + "; censored policy: " + censored
            if config["records_outside_bins"]:
                subtitle += "; " + str(config["records_outside_bins"]) + " records outside all bins"
            subtitle += ". Project-added analysis, not a verified replication of the figure."
            path = outdir / (series_id + "_" + boundary + "_" + censored + ".png")
            grouped_bars("Sensitivity: " + info["metric"].replace("_", " ") + " (" + info["figure"] + ")",
                         info["bin_labels"], {name: config["per_os"][name]["percent"] for name in OS_ORDER},
                         path, subtitle=subtitle)
            paths.append(str(path))
    return paths


def make_convention_comparison_plots(result, outdir):
    """One figure per series: published bar labels vs both boundary conventions.

    Censored counts use their lower bound in both recomputed series; the
    unassigned policy is omitted because it is outside every bin by design.
    Bars coincide where a convention reproduces the published labels.
    """
    from .plots import multi_series_bars
    outdir = Path(outdir)
    paths = []

    def percents(info, boundary):
        for config in info["configurations"].values():
            if config["boundary_convention"] == boundary and config["censored_policy"] in ("lower_bound", "not_applicable"):
                return [config["per_os"][name]["percent"][index]
                        for name in OS_ORDER for index in range(len(info["bin_labels"]))]
        raise KeyError("No comparable configuration for " + boundary)

    for series_id, info in result["series"].items():
        categories = [name + " " + label for name in OS_ORDER for label in info["bin_labels"]]
        paper = [info["paper_percent"][name][index]
                 for name in OS_ORDER for index in range(len(info["bin_labels"]))]
        values = [paper, percents(info, "left_closed"), percents(info, "right_closed")]
        names = ["Paper (published bar labels)", "[lo, hi) recomputed", "(lo, hi] recomputed"]
        subtitle = "Censored counts placed at their lower bound. Bars coincide where a convention matches the paper."
        path = outdir / (series_id + "_paper_vs_conventions.png")
        multi_series_bars("Paper vs conventions: " + info["metric"].replace("_", " ") + " (" + info["figure"] + ")",
                          categories, names, values, path, subtitle=subtitle)
        paths.append(str(path))
    return paths
