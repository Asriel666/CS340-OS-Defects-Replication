#!/usr/bin/env python3
"""Run the Figure 2/3 binning-convention sensitivity analysis.

This is a project-added analysis, separate from scripts/run_stage.py and the
561 core RQ1/RQ2/RQ3 comparisons. It recomputes the published repair-size
series under every explicit binning convention and writes comparisons, a
match summary, and figures to results/repair_size/ by default. The analysis
is computed three times in memory and only written to disk after all three
semantic digests agree; differing outputs are a hard error that leaves no
partial outputs behind.
"""
import argparse
import json
import shutil
import sys
import time
from datetime import datetime, timezone
from importlib.metadata import version as package_version
from importlib.metadata import PackageNotFoundError
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from osdefects.common import semantic_digest, write_json
from osdefects.data import fetch_source, load_records, validate_records
from osdefects.repair_size import (
    analyze_repair_size, make_convention_comparison_plots, make_repair_size_plots,
)
from osdefects.runner import environment


def _check_plot_dependencies(parser):
    """Fail with a readable message instead of a renderer traceback."""
    missing = []
    for package in ("reportlab", "pillow"):
        try:
            package_version(package)
        except PackageNotFoundError:
            missing.append(package)
    if shutil.which("pdftoppm") is None:
        missing.append("pdftoppm (Poppler)")
    if missing:
        parser.error("Plot dependencies missing: " + ", ".join(missing)
                     + ". Install requirements.txt and Poppler, or pass --no-plots.")


def main():
    parser = argparse.ArgumentParser(description="Sensitivity analysis of published Figure 2/3 binning conventions")
    parser.add_argument("--runs", type=int, default=3, help="Deterministic recomputation count (minimum 3)")
    parser.add_argument("--offline", action="store_true", help="Fail instead of downloading when the cache is missing")
    parser.add_argument("--no-plots", action="store_true", help="Skip PNG figures (no Poppler needed)")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-dir", type=Path, default=None, help="Separate output directory")
    args = parser.parse_args()
    if args.runs < 3:
        parser.error("--runs must be at least 3")
    if not args.no_plots:
        _check_plot_dependencies(parser)
    root = args.root.resolve()
    stage_dir = Path(args.output_dir).resolve() if args.output_dir is not None else root / "results" / "repair_size"
    provenance = fetch_source(root / "data" / "raw" / "index.html", offline=args.offline)
    reference = json.loads((root / "reference" / "figure_baselines.json").read_text(encoding="utf-8"))
    stage_dir.mkdir(parents=True, exist_ok=True)
    write_json(stage_dir / "source_provenance.json", provenance)

    started_at_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")
    digests, elapsed = [], []
    records = result = None
    for index in range(1, args.runs + 1):
        tick = time.perf_counter()
        records = load_records(root / "data" / "raw" / "index.html")
        result = analyze_repair_size(records, reference, None, write_outputs=False)
        digests.append(semantic_digest(result))
        elapsed.append(round(time.perf_counter() - tick, 4))
    if len(set(digests)) != 1:
        raise RuntimeError("Deterministic sensitivity analysis produced differing outputs across runs")

    # All runs agreed: write the verified result exactly once.
    result = analyze_repair_size(records, reference, stage_dir / "tables")
    write_json(stage_dir / "data_validation.json", validate_records(records))
    write_json(stage_dir / "environment.json", environment(root))
    write_json(stage_dir / "run_log.json", {
        "analysis": "repair_size_sensitivity",
        "verification_runs": args.runs,
        "semantic_result_sha256": digests[0],
        "elapsed_seconds_per_verification_run": elapsed,
        "source_sha256_lf": provenance["source_sha256_lf"],
        "status": "success",
        "meaning": "Repeated deterministic calculation verifies execution stability, not the authors' actual binning convention.",
        "invocation": sys.argv,
        "started_at_utc": started_at_utc,
    })
    paths = []
    if not args.no_plots:
        paths = make_repair_size_plots(result, stage_dir / "figures")
        paths += make_convention_comparison_plots(result, stage_dir / "figures")
    write_json(stage_dir / "figure_manifest.json",
               [Path(p).relative_to(stage_dir).as_posix() for p in paths])
    print(json.dumps({
        "analysis": "repair_size_sensitivity", "directory": str(stage_dir), "runs": args.runs,
        "series": result["series_count"], "comparisons": result["comparison_count"],
        "matched_cells": result["matched_cells"], "figures": len(paths),
        "repeatable": True,
    }, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
