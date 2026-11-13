#!/usr/bin/env python3
"""Run the three project-added gap analyses (Figures 2/3 evidence, 4c, 4d).

All computations run three times in memory and are written exactly once after
their semantic digests agree. Outputs go to results/gap_analysis/ by default
and are explicitly labelled as exploratory, never as verified replication.
No network requests to patch URLs are made; only the pinned author source is
read through the existing checksum-verified cache.
"""
import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from osdefects.common import semantic_digest, write_json
from osdefects.data import fetch_source, load_records, validate_records
from osdefects.gap_analysis import analyze_gaps
from osdefects.runner import environment


def main():
    parser = argparse.ArgumentParser(description="Exploratory analyses for the remaining Figure 4 / repair-size gaps")
    parser.add_argument("--runs", type=int, default=3, help="Deterministic recomputation count (minimum 3)")
    parser.add_argument("--offline", action="store_true", help="Fail instead of downloading when the cache is missing")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-dir", type=Path, default=None, help="Separate output directory")
    args = parser.parse_args()
    if args.runs < 3:
        parser.error("--runs must be at least 3")
    root = args.root.resolve()
    stage_dir = Path(args.output_dir).resolve() if args.output_dir is not None else root / "results" / "gap_analysis"
    provenance = fetch_source(root / "data" / "raw" / "index.html", offline=args.offline)
    reference = json.loads((root / "reference" / "similarity_baselines.json").read_text(encoding="utf-8"))
    stage_dir.mkdir(parents=True, exist_ok=True)
    write_json(stage_dir / "source_provenance.json", provenance)

    started_at_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")
    digests, elapsed = [], []
    records = result = None
    for index in range(1, args.runs + 1):
        tick = time.perf_counter()
        records = load_records(root / "data" / "raw" / "index.html")
        result = analyze_gaps(records, reference, write_outputs=False)
        digests.append(semantic_digest(result))
        elapsed.append(round(time.perf_counter() - tick, 4))
    if len(set(digests)) != 1:
        raise RuntimeError("Deterministic gap analysis produced differing outputs across runs")

    result = analyze_gaps(records, reference, stage_dir / "tables")
    write_json(stage_dir / "data_validation.json", validate_records(records))
    write_json(stage_dir / "environment.json", environment(root))
    write_json(stage_dir / "run_log.json", {
        "analysis": "figure_gap_exploration", "verification_runs": args.runs,
        "semantic_result_sha256": digests[0],
        "elapsed_seconds_per_verification_run": elapsed,
        "source_sha256_lf": provenance["source_sha256_lf"], "status": "success",
        "meaning": "Three deterministic runs verify execution stability only. All outputs are exploratory and remain excluded from the 561 core comparisons.",
        "invocation": sys.argv, "started_at_utc": started_at_utc,
    })
    print(json.dumps({
        "analysis": "figure_gap_exploration", "directory": str(stage_dir), "runs": args.runs,
        "figure_4c_variants": result["figure_4c"]["enumeration_count"],
        "figure_4c_candidates": len(result["figure_4c"]["candidates"]),
        "figure_4d_candidates": result["figure_4d"]["candidate_count"],
        "repair_evidence_rows": result["repair_evidence"]["row_count"],
        "repeatable": True,
    }, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
