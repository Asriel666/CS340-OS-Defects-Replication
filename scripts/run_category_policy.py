#!/usr/bin/env python3
"""Recompute explicit Figure 4(a-c) category policies without changing core RQ3."""
import argparse
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from osdefects.category_policy import analyze_category_policy
from osdefects.common import semantic_digest, write_json
from osdefects.data import fetch_source, load_records, validate_records
from osdefects.runner import environment
from osdefects.similarity import validate_similarity_reference


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--cross-check-scipy", action="store_true", help="Optional independent coefficient/rank check; requires an existing SciPy installation")
    args = parser.parse_args()
    if args.runs < 3:
        parser.error("--runs must be at least 3")
    if args.cross_check_scipy:
        try:
            import scipy
            from scipy.stats import rankdata, spearmanr
        except ImportError:
            parser.error("--cross-check-scipy requires SciPy; omit this optional check to use only the core dependencies")
    root = args.root.resolve()
    outdir = args.output_dir.resolve() if args.output_dir else root / "results" / "category_policy"
    reference = json.loads((root / "reference" / "similarity_baselines.json").read_text(encoding="utf-8"))
    validate_similarity_reference(reference)
    provenance = fetch_source(root / "data" / "raw" / "index.html", offline=args.offline)
    logs, results = [], []
    for index in range(1, args.runs + 1):
        started = datetime.now(timezone.utc).isoformat(timespec="microseconds")
        tick = time.perf_counter()
        records = load_records(root / "data" / "raw" / "index.html")
        result = analyze_category_policy(records, reference)
        digest = semantic_digest(result)
        results.append(result)
        logs.append({
            "run": index, "started_at_utc": started,
            "elapsed_seconds": time.perf_counter() - tick,
            "semantic_result_sha256": digest,
            "source_sha256_lf": provenance["source_sha256_lf"],
            "status": "success",
        })
    if len({log["semantic_result_sha256"] for log in logs}) != 1:
        raise RuntimeError("Category-policy results differ across actual recomputations")
    result = analyze_category_policy(records, reference, outdir / "tables")
    if semantic_digest(result) != logs[0]["semantic_result_sha256"]:
        raise RuntimeError("Serialized analysis differs from verified recomputations")
    for log, run_result in zip(logs, results):
        run_dir = outdir / "runs" / ("run_%02d" % log["run"])
        write_json(run_dir / "run_log.json", log)
        write_json(run_dir / "results.json", run_result)
    write_json(outdir / "source_provenance.json", provenance)
    write_json(outdir / "data_validation.json", validate_records(records))
    write_json(outdir / "environment.json", environment(root))
    summary = {
        "analysis": "category_set_sensitivity", "runs": args.runs,
        "active_runs": ["runs/run_%02d" % log["run"] for log in logs],
        "identical_semantic_outputs": True,
        "semantic_result_sha256": logs[0]["semantic_result_sha256"],
        "source_sha256_lf": provenance["source_sha256_lf"],
        "invocation": sys.argv, "policy_summary": result["policy_summary"],
        "independent_cross_check": {
            "requested": args.cross_check_scipy,
            "status": "pending" if args.cross_check_scipy else "not_requested",
            "evidence_file": None,
            "scope": "Only evidence linked here belongs to this invocation; an existing unlinked SciPy file is historical.",
        },
        "meaning": "Actual repeated deterministic computations establish execution stability only; author methodology and original labels remain unconfirmed.",
    }
    write_json(outdir / "run_summary.json", summary)
    if args.cross_check_scipy:
        checks = []
        for row in result["comparisons"]:
            x, y = row["counts_a"], row["counts_b"]
            scipy_rho = float(spearmanr(x, y).statistic) if len(x) >= 2 else float("nan")
            scipy_rho = scipy_rho if math.isfinite(scipy_rho) else None
            difference = None if scipy_rho is None or row["ours_rho"] is None else abs(scipy_rho - row["ours_rho"])
            coefficient_ok = scipy_rho is row["ours_rho"] if difference is None else difference <= 1e-12
            rank_ok = list(rankdata(x, method="average")) == row["average_ranks_a"] and list(rankdata(y, method="average")) == row["average_ranks_b"]
            checks.append({"policy": row["policy"], "dimension": row["dimension"], "os_a": row["os_a"], "os_b": row["os_b"],
                           "ours_rho": row["ours_rho"], "scipy_rho": scipy_rho,
                           "absolute_difference": difference, "ranks_match": rank_ok,
                           "passed": bool(coefficient_ok and rank_ok)})
        cross_check = {
            "library": "SciPy", "version": scipy.__version__, "functions": ["scipy.stats.spearmanr", "scipy.stats.rankdata(method='average')"],
            "checked_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "semantic_result_sha256": logs[0]["semantic_result_sha256"],
            "absolute_tolerance": 1e-12, "all_passed": all(row["passed"] for row in checks), "comparisons": checks,
            "scope": "Independent numerical implementation on the recorded selected vectors; does not independently validate data labels, category selection, or author intent.",
        }
        write_json(outdir / "scipy_cross_check.json", cross_check)
        summary["independent_cross_check"].update(
            status="passed" if cross_check["all_passed"] else "failed",
            evidence_file="scipy_cross_check.json",
            semantic_result_sha256=logs[0]["semantic_result_sha256"],
            checked_at_utc=cross_check["checked_at_utc"],
        )
        write_json(outdir / "run_summary.json", summary)
        if not cross_check["all_passed"]:
            raise RuntimeError("Independent SciPy numerical cross-check failed")
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
