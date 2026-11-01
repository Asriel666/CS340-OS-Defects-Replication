"""Cumulative, auditable weekend-stage orchestration."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import csv
import importlib.metadata
import json
import os
import platform
import shutil
import statistics
import subprocess
import sys
import time
from .common import semantic_digest, sha256, write_csv, write_json
from .data import fetch_source, load_records, validate_records, write_dataset, SOURCE_COMMIT
from .univariate import analyze_univariate


def environment(root, stage=5):
    versions = {}
    for package in ("reportlab", "pillow"):
        try: versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError: versions[package] = "not installed"
    try:
        version = subprocess.run(["pdftoppm", "-v"], capture_output=True, text=True, check=True)
        versions["pdftoppm"] = (version.stderr or version.stdout).splitlines()[0]
    except (OSError, subprocess.CalledProcessError):
        versions["pdftoppm"] = "not installed"
    sources = sorted([*Path(root).glob("src/**/*.py"), *Path(root).glob("scripts/*.py"), *Path(root).glob("reference/*.json")])
    introduced={"repair.py":2,"joint.py":3,"similarity.py":4,"extension.py":4,
                "report.py":5,"package_stages.py":5}
    sources=[p for p in sources if introduced.get(p.name,1)<=stage]
    return {"python": sys.version, "python_executable": sys.executable, "os": platform.platform(),
            "kernel": platform.release(), "machine": platform.machine(), "logical_cpus": os.cpu_count(),
            "packages": versions, "source_commit": SOURCE_COMMIT,
            "files_sha256": {str(p.relative_to(root)): sha256(p) for p in sources}}


def run_analyses(records, reference, stage, outdir):
    result = {"univariate": analyze_univariate(records, reference, outdir,
                                               ["os_layer"] if stage==1 else None)}
    if stage >= 2:
        from .repair import analyze_repairs
        result["repairs"] = analyze_repairs(records, outdir)
    if stage >= 3:
        from .joint import analyze_joint
        result["joint"] = analyze_joint(records, reference, outdir)
    if stage >= 4:
        from .similarity import analyze_similarity
        from .extension import run_extension
        result["similarity"] = analyze_similarity(records, reference, outdir)
        result["extension"] = run_extension(records, reference, outdir)
    return result


def repeated_statistics(stage_dir, runs):
    """Summarize actual repeated table values, retaining all raw run outputs."""
    rows = []
    for filename, metric in (("table_ii.csv", "ours_percent"), ("joint_comparison.csv", "ours_percent"),
                             ("similarity_comparison.csv", "ours_rho")):
        paths = [stage_dir/"runs"/f"run_{i:02d}"/"tables"/filename for i in range(1, runs+1)]
        if not paths[0].exists(): continue
        tables = []
        for path in paths:
            with path.open(newline="", encoding="utf-8") as stream: tables.append(list(csv.DictReader(stream)))
        if len({len(t) for t in tables}) != 1: raise RuntimeError("Repeated outputs have differing row counts")
        for index, row in enumerate(tables[0]):
            values = [float(table[index][metric]) for table in tables]
            key = ";".join(f"{name}={row[name]}" for name in ("dimension", "table", "os", "category", "row_category", "column_category", "os_a", "os_b") if name in row)
            rows.append({"table": filename, "row_key": key, "metric": metric, "runs": runs,
                         "mean": statistics.mean(values), "sd": statistics.stdev(values) if len(values)>1 else 0,
                         "log_directory": "runs/run_*/tables/"+filename})
    write_csv(stage_dir/"tables"/"repeated_run_statistics.csv", rows)
    return rows


def create_review_template(records, path):
    import random
    path = Path(path)
    if path.exists():
        # A rerun must never erase a student's annotations or review notes.
        return
    rows = []
    for os_name in ("Android", "Linux", "HarmonyOS"):
        group = sorted([r for r in records if r["os"]==os_name], key=lambda r:r["bug_id"])
        for record in random.Random(340).sample(group, 10):
            rows.append({"os":os_name,"bug_id":record["bug_id"],"patch":record["patch"],
                         "published_os_layer":record["os_layer"],"reviewer_A_label":"", "reviewer_D_label":"",
                         "evidence":"", "status":"pending_human_review"})
    write_csv(path,rows)


def run_stage(root, stage, runs=3, offline=False, plots=True):
    if runs < 3: raise ValueError("This project records at least three actual runs per stage")
    root = Path(root).resolve()
    stage_dir = root/"results"/f"weekend_{stage:02d}"
    stage_dir.mkdir(parents=True,exist_ok=True)
    source = root/"data"/"raw"/"index.html"
    provenance = fetch_source(source,offline=offline)
    reference = json.loads((root/"reference"/"paper_baselines.json").read_text(encoding="utf-8"))
    env = environment(root,stage)
    write_json(stage_dir/"environment.json",env)
    write_json(stage_dir/"source_provenance.json",provenance)
    results, run_logs = [], []
    for index in range(1,runs+1):
        started = datetime.now(timezone.utc).isoformat(timespec="seconds")
        tick = time.perf_counter()
        records = load_records(source)
        validation = validate_records(records)
        destination = stage_dir/"runs"/f"run_{index:02d}"
        result = run_analyses(records,reference,stage,destination/"tables")
        write_json(destination/"results.json",result)
        log = {"started_at_utc":started,"elapsed_seconds":time.perf_counter()-tick,
               "stage":stage,"run":index,"records":len(records), "source_sha256_lf":provenance.get("sha256_lf_normalized",provenance.get("source_sha256_lf", "see source_provenance.json")),
               "semantic_result_sha256":semantic_digest(result),"status":"success",
               "invocation":sys.argv,"data_validation":validation,"environment_file":"../../environment.json"}
        write_json(destination/"run_log.json",log)
        results.append(result); run_logs.append(log)
    if len({log["semantic_result_sha256"] for log in run_logs}) != 1:
        raise RuntimeError("Deterministic repeated analysis produced differing outputs")
    table_dir=stage_dir/"tables"
    shutil.copytree(stage_dir/"runs"/"run_01"/"tables",table_dir,dirs_exist_ok=True)
    repeat = repeated_statistics(stage_dir,runs)
    # Stage-local data make each stage auditable; canonical inputs stay in data/processed.
    write_dataset(records,root/"data"/"processed")
    create_review_template(records,root/"data"/"review"/"manual_label_review.csv")
    summary = {"stage":stage,"run_count":runs,"status":"computationally_complete",
               "results":results[0],"repeatability":{"identical_semantic_outputs":True,
               "semantic_result_sha256":run_logs[0]["semantic_result_sha256"],
               "summary_rows":len(repeat),"meaning":"Repeated deterministic calculation verifies execution stability, not annotation validity or sampling uncertainty."},
               "human_review":"30-record dual-review template is unfilled; no human reannotation or student contribution claimed."}
    write_json(stage_dir/"stage_summary.json",summary)
    if plots:
        from .plots import make_plots
        paths=make_plots(results[0],stage_dir/"figures")
        write_json(stage_dir/"figure_manifest.json",[str(Path(p).relative_to(stage_dir)) for p in paths])
    if stage == 5:
        from .report import build_report
        build_report(root,stage_dir,summary)
    return {"stage":stage,"directory":str(stage_dir),"runs":runs,
            "table_ii_matches":results[0]["univariate"]["matched_cells"],
            "table_ii_cells":results[0]["univariate"]["cell_count"],
            "repeatable":True}


def main():
    parser=argparse.ArgumentParser(description="Run a cumulative weekend-stage reproduction")
    parser.add_argument("--stage",type=int,choices=range(1,6),default=1)
    parser.add_argument("--all",action="store_true",help="Run stages 1 through 5 now; does not schedule future runs")
    parser.add_argument("--runs",type=int,default=3)
    parser.add_argument("--offline",action="store_true")
    parser.add_argument("--no-plots",action="store_true")
    parser.add_argument("--root",type=Path,default=Path(__file__).resolve().parents[2])
    args=parser.parse_args()
    snapshot_config=args.root/"SNAPSHOT.json"
    maximum=json.loads(snapshot_config.read_text())["max_stage"] if snapshot_config.exists() else 5
    if not args.all and args.stage>maximum:
        parser.error(f"This snapshot supports stages 1-{maximum}; use the next cumulative package")
    for stage in range(1,maximum+1) if args.all else [args.stage]:
        print(json.dumps(run_stage(args.root,stage,args.runs,args.offline,not args.no_plots),ensure_ascii=False),flush=True)


if __name__=="__main__": main()
