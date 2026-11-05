"""Auditable RQ1/RQ2/RQ3 execution, retaining the original OS-layer entry point."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import csv
import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import statistics
import subprocess
import sys
import time
from .common import semantic_digest, write_csv, write_json
from .data import fetch_source, load_records, validate_records, write_dataset, SOURCE_COMMIT, CANONICAL_CATEGORIES
from .univariate import analyze_univariate, validate_reference

ANALYSES = (None, "rq1", "rq2", "rq3", "all")
RESULT_FOLDERS = {None: "weekend_01", "rq1": "rq1", "rq2": "rq2", "rq3": "rq3", "all": "full"}
TABLE_METRICS = {"univariate": ("table_ii.csv", "ours_percent"),
                 "joint": ("joint_comparison.csv", "ours_percent"),
                 "similarity": ("similarity_comparison.csv", "ours_rho")}


def environment(root, stage=1):
    versions = {}
    for package in ("reportlab", "pillow"):
        try: versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError: versions[package] = "not installed"
    try:
        version = subprocess.run(["pdftoppm", "-v"], capture_output=True, text=True, check=True)
        versions["pdftoppm"] = (version.stderr or version.stdout).splitlines()[0]
    except (OSError, subprocess.CalledProcessError):
        versions["pdftoppm"] = "not installed"
    sources = sorted([*Path(root).glob("src/**/*.py"), *Path(root).glob("scripts/*.py"),
                      *Path(root).glob("reference/*.json"), *Path(root).glob("tests/*.py"),
                      *Path(root).glob("SUBMISSION.json"), *Path(root).glob("requirements.txt")])
    return {"python": sys.version, "python_executable": sys.executable, "os": platform.platform(),
            "kernel": platform.release(), "machine": platform.machine(), "logical_cpus": os.cpu_count(),
            "packages": versions, "source_commit": SOURCE_COMMIT,
            "source_file_hash_policy": "UTF-8 text with CRLF/CR normalized to LF",
            "files_sha256": {p.relative_to(root).as_posix(): hashlib.sha256(p.read_text(encoding="utf-8").encode("utf-8")).hexdigest() for p in sources}}


def run_analyses(records, reference, stage, outdir, analysis=None):
    if stage != 1 or analysis not in ANALYSES:
        raise ValueError("Supported scope: legacy stage 1 or --analysis rq1/rq2/rq3/all")
    result = {}
    if analysis in (None, "rq1", "all"):
        result["univariate"] = analyze_univariate(records, reference, outdir,
                                                  ["os_layer"] if analysis is None else None)
    if analysis in ("rq2", "all"):
        from .joint import analyze_joint
        result["joint"] = analyze_joint(records, reference["joint"], outdir)
    if analysis in ("rq3", "all"):
        from .similarity import analyze_similarity
        result["similarity"] = analyze_similarity(records, reference["similarity"], outdir)
    return result


def repeated_statistics(stage_dir, runs, analysis_keys=("univariate",)):
    """Summarize actual repeated table values, retaining all raw run outputs."""
    rows = []
    for filename, metric in (TABLE_METRICS[key] for key in analysis_keys):
        paths = [stage_dir/"runs"/f"run_{i:02d}"/"tables"/filename for i in range(1, runs+1)]
        tables = []
        for path in paths:
            with path.open(newline="", encoding="utf-8") as stream: tables.append(list(csv.DictReader(stream)))
        if len({len(t) for t in tables}) != 1: raise RuntimeError("Repeated outputs have differing row counts")
        for index, row in enumerate(tables[0]):
            key_fields = ("dimension", "table", "os", "category", "row_category", "column_category", "os_a", "os_b")
            identity = tuple(row.get(name) for name in key_fields)
            if any(tuple(table[index].get(name) for name in key_fields) != identity for table in tables):
                raise RuntimeError("Repeated outputs have differing comparison keys")
            raw = [table[index][metric] for table in tables]
            if any(v == "" for v in raw) and not all(v == "" for v in raw):
                raise RuntimeError("Repeated outputs disagree on undefined values")
            values = [float(v) for v in raw if v != ""]
            key = ";".join(f"{name}={row[name]}" for name in key_fields if name in row)
            rows.append({"table": filename, "row_key": key, "metric": metric, "runs": runs,
                         "mean": statistics.mean(values) if values else None,
                         "sd": statistics.stdev(values) if len(values)>1 else (0 if values else None),
                         "status": "defined" if values else "undefined",
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
        for record in random.Random(340).sample(group, 4):
            row = {"os":os_name, "bug_id":record["bug_id"], "patch":record["patch"]}
            for reviewer in ("A", "B"):
                for field in ("os_layer", "affected_function", "trigger_scenario"):
                    row[f"reviewer_{reviewer}_{field}"] = ""
                row[f"reviewer_{reviewer}_evidence"] = ""
            row.update({"adjudication":"", "status":"pending_human_review"})
            rows.append(row)
    write_csv(path,rows)


def run_stage(root, stage, runs=3, offline=False, plots=True, analysis=None, output_dir=None):
    if runs < 3: raise ValueError("This project records at least three actual runs per stage")
    if stage != 1 or analysis not in ANALYSES:
        raise ValueError("Supported scope: legacy stage 1 or --analysis rq1/rq2/rq3/all")
    root = Path(root).resolve()
    stage_dir = Path(output_dir).resolve() if output_dir is not None else root/"results"/RESULT_FOLDERS[analysis]
    previous_summary = stage_dir/"stage_summary.json"
    if previous_summary.exists():
        previous = json.loads(previous_summary.read_text(encoding="utf-8"))
        if previous.get("analysis", "os_layer") != (analysis or "os_layer"):
            raise ValueError("Output directory belongs to another analysis; choose a separate --output-dir")
    reference = {}
    if analysis in (None, "rq1", "all"):
        reference = json.loads((root/"reference"/"paper_baselines.json").read_text(encoding="utf-8"))
        validate_reference(reference, list(CANONICAL_CATEGORIES) if analysis else ["os_layer"])
    if analysis in ("rq2", "all"):
        from .joint import validate_joint_reference
        reference["joint"] = json.loads((root/"reference/joint_baselines.json").read_text(encoding="utf-8"))
        validate_joint_reference(reference["joint"])
    if analysis in ("rq3", "all"):
        from .similarity import validate_similarity_reference
        reference["similarity"] = json.loads((root/"reference/similarity_baselines.json").read_text(encoding="utf-8"))
        validate_similarity_reference(reference["similarity"])
    env = environment(root,stage)
    if plots and any(value == "not installed" for value in env["packages"].values()):
        raise RuntimeError("Plot dependencies are missing. Install requirements.txt and Poppler, or use --no-plots.")
    source = root/"data"/"raw"/"index.html"
    provenance = fetch_source(source,offline=offline)
    stage_dir.mkdir(parents=True,exist_ok=True)
    write_json(stage_dir/"stage_summary.json", {"status":"running", "analysis":analysis or "os_layer", "run_count":runs})
    write_json(stage_dir/"environment.json",env)
    write_json(stage_dir/"source_provenance.json",provenance)
    results, run_logs = [], []
    for index in range(1,runs+1):
        started = datetime.now(timezone.utc).isoformat(timespec="seconds")
        tick = time.perf_counter()
        records = load_records(source)
        validation = validate_records(records)
        destination = stage_dir/"runs"/f"run_{index:02d}"
        result = run_analyses(records,reference,stage,destination/"tables",analysis)
        write_json(destination/"results.json",result)
        log = {"started_at_utc":started,"elapsed_seconds":time.perf_counter()-tick,
               "stage":stage,"analysis":analysis or "os_layer","run":index,"records":len(records), "source_sha256_lf":provenance["source_sha256_lf"],
               "semantic_result_sha256":semantic_digest(result),"status":"success",
               "invocation":sys.argv,"data_validation":validation,"environment_file":"../../environment.json"}
        write_json(destination/"run_log.json",log)
        results.append(result); run_logs.append(log)
    if len({log["semantic_result_sha256"] for log in run_logs}) != 1:
        raise RuntimeError("Deterministic repeated analysis produced differing outputs")
    table_dir=stage_dir/"tables"
    shutil.copytree(stage_dir/"runs"/"run_01"/"tables",table_dir,dirs_exist_ok=True)
    repeat = repeated_statistics(stage_dir,runs,results[0])
    # Stage-local data make each stage auditable; canonical inputs stay in data/processed.
    write_dataset(records,root/"data"/"processed")
    create_review_template(records,root/"data"/"review"/"rq123_label_review.csv")
    write_json(stage_dir/"data_validation.json",validation)
    comparisons = {key: {"cell_count": value["cell_count"], "matched_cells":value["matched_cells"],
                         "unconfirmed_cells":value.get("unconfirmed_cells",0),
                         "mismatched_cells":value["cell_count"]-value["matched_cells"]-value.get("unconfirmed_cells",0)}
                   for key,value in results[0].items()}
    summary = {"stage":stage,"analysis":analysis or "os_layer","run_count":runs,"status":"computationally_complete",
               "active_runs":[f"runs/run_{index:02d}" for index in range(1,runs+1)], "comparisons":comparisons,
               "results":results[0],"repeatability":{"identical_semantic_outputs":True,
               "semantic_result_sha256":run_logs[0]["semantic_result_sha256"],
               "summary_rows":len(repeat),"meaning":"Repeated deterministic calculation verifies execution stability, not annotation validity or sampling uncertainty."},
               "human_review":{"status":"pending_human_review", "sample_size":12, "per_os":4, "seed":340,
                               "template":"data/review/rq123_label_review.csv",
                               "meaning":"Blank template created only when missing. No human review or individual coding contribution is certified."}}
    submission = root/"SUBMISSION.json"
    if submission.exists():
        summary["submission"] = json.loads(submission.read_text(encoding="utf-8"))
    paths = []
    if plots:
        from .plots import make_plots
        paths=make_plots(results[0],stage_dir/"figures")
    write_json(stage_dir/"figure_manifest.json",[Path(p).relative_to(stage_dir).as_posix() for p in paths])
    write_json(stage_dir/"stage_summary.json",summary)
    return {"stage":stage,"analysis":analysis or "os_layer","directory":str(stage_dir),"runs":runs,
            "table_ii_matches":results[0].get("univariate",{}).get("matched_cells",0),
            "table_ii_cells":results[0].get("univariate",{}).get("cell_count",0),
            "comparisons":comparisons,
            "repeatable":True}


def main():
    parser=argparse.ArgumentParser(description="Recompute RQ1, RQ2 and RQ3 from the pinned author labels")
    scope=parser.add_mutually_exclusive_group()
    scope.add_argument("--analysis",choices=["rq1","rq2","rq3","all"],help="RQ1 Table II, RQ2 Tables III-V, RQ3 Fig.4(a-c), or all three")
    scope.add_argument("--stage",type=int,choices=[1],help="Legacy OS-layer-only analysis (18 cells; default)")
    scope.add_argument("--all",action="store_true",help="Legacy alias for the only available numbered stage (1)")
    parser.add_argument("--runs",type=int,default=3)
    parser.add_argument("--offline",action="store_true")
    parser.add_argument("--no-plots",action="store_true")
    parser.add_argument("--root",type=Path,default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output-dir",type=Path,help="Separate output directory for verification runs")
    args=parser.parse_args()
    if args.runs < 3:
        parser.error("--runs must be at least 3")
    result=run_stage(args.root,1,args.runs,args.offline,not args.no_plots,args.analysis,args.output_dir)
    print(json.dumps(result,ensure_ascii=False),flush=True)


if __name__=="__main__": main()
