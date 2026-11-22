#!/usr/bin/env python3
"""Verify core, Week 2, category policies and blank review workflow in clean copies."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def source_hashes(root, include_root_entries=False):
    """Match the core environment's LF-normalized hashes, optionally including root entries."""
    root = Path(root)
    paths = set([*root.glob("src/**/*.py"), *root.glob("scripts/*.py"),
                 *root.glob("reference/*.json"), *root.glob("tests/*.py"),
                 *root.glob("SUBMISSION.json"), *root.glob("requirements.txt")])
    if include_root_entries:
        paths.update(root.glob("*.py"))
        paths.update(root.glob("*.json"))
    return {path.relative_to(root).as_posix(): hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
            for path in sorted(paths)}


def source_changes(previous, current):
    """A new/missing file means absent from that snapshot, not a claim about Git history."""
    return {"changed": {key: {"published": previous[key], "current": current[key]}
                        for key in sorted(previous.keys() & current.keys()) if previous[key] != current[key]},
            "new": {key: current[key] for key in sorted(current.keys() - previous.keys())},
            "missing": {key: previous[key] for key in sorted(previous.keys() - current.keys())}}


def check_source_snapshot(previous, current, isolated, allow_source_changes=False):
    """The opt-in never permits a stale or incomplete isolated copy."""
    if isolated != current:
        raise AssertionError("Isolated source hashes differ from the current working source")
    changes = source_changes(previous, current)
    if any(key.startswith("reference/") for group in changes.values() for key in group):
        raise AssertionError("Published reference hashes differ; --allow-source-changes cannot waive reference changes")
    if any(changes.values()) and not allow_source_changes:
        raise AssertionError("Published source hashes are stale; rerun --analysis all, or explicitly use --allow-source-changes to verify unchanged results with current code")
    return changes


def copy_project_inputs(root, destination):
    """Copy runnable source and references, never published output or a data cache."""
    for folder in ("src", "scripts", "reference", "tests"):
        shutil.copytree(root / folder, destination / folder,
                        ignore=shutil.ignore_patterns("__pycache__"))
    for path in {*root.glob("*.py"), *root.glob("*.json"), root / "requirements.txt"}:
        shutil.copy2(path, destination / path.name)


def table_ii_values(path):
    fields = ("count", "n", "paper_percent", "ours_percent", "difference_pp")
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    values = {(row["dimension"], row["os"], row["category"]): tuple(float(row[key]) for key in fields)
              for row in rows}
    if len(rows) != 114 or len(values) != 114:
        raise AssertionError("Week 2 requires exactly 114 distinct Table II comparisons")
    if any(row.get("status") != "match" for row in rows):
        raise AssertionError("Week 2 Table II must match all 114 paper values")
    return values


def inspect_weekend_output(output, expected_table, expected_result, expected_sha, expected_mode):
    """Check actual per-run values, not only the summary's success claims."""
    summary = json.loads((output / "stage_summary.json").read_text(encoding="utf-8"))
    provenance = json.loads((output / "source_provenance.json").read_text(encoding="utf-8"))
    if summary.get("analysis") != "weekend_02" or summary.get("status") != "computationally_complete":
        raise AssertionError("Week 2 did not complete")
    if summary.get("runs") != 3 or summary.get("table_ii_cells") != 114 or summary.get("table_ii_matches") != 114:
        raise AssertionError("Week 2 requires three runs and 114/114 matches")
    if provenance["source_sha256_lf"] != expected_sha or provenance["acquisition_mode"] != expected_mode:
        raise AssertionError("Week 2 source checksum or acquisition mode differs")
    if table_ii_values(output / "tables/table_ii.csv") != expected_table:
        raise AssertionError("Week 2 differs from published core Table II")
    logs = []
    for index in range(1, 4):
        run = output / "runs" / f"run_{index:02d}"
        log = json.loads((run / "run_log.json").read_text(encoding="utf-8"))
        result = json.loads((run / "results.json").read_text(encoding="utf-8"))
        if result != expected_result or log["semantic_result_sha256"] != digest(result):
            raise AssertionError("Week 2 per-run values or semantic digest differ from the published result")
        if log["records"] != 1500 or log["source_sha256_lf"] != expected_sha:
            raise AssertionError("Week 2 run has incorrect input evidence")
        if table_ii_values(run / "tables/table_ii.csv") != expected_table:
            raise AssertionError("Week 2 per-run Table II differs")
        for filename in ("repair_distributions.csv", "repair_claim_checks.csv"):
            if (run / "tables" / filename).read_bytes() != (output / "tables" / filename).read_bytes():
                raise AssertionError("Week 2 per-run repair table differs")
        logs.append(log)
    if summary["repeatability"]["semantic_result_sha256"] != digest(expected_result) or not summary["repeatability"]["identical_semantic_outputs"]:
        raise AssertionError("Week 2 summary digest does not describe its actual result")
    if json.loads((output / "figure_manifest.json").read_text(encoding="utf-8")) != [] or (output / "figures").exists():
        raise AssertionError("Week 2 --no-plots must not generate figures")
    return {"summary": summary, "source_provenance": provenance, "run_logs": logs,
            "matches_published_core_table_ii": True, "matches_published_weekend_results": True}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":")).encode("utf-8")).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, help="Write verification.json here; default remains results/full")
    parser.add_argument("--allow-source-changes", action="store_true", help="Permit source hashes to differ from the historical published snapshot, while requiring the isolated copy to match current source exactly. Input checksums, references and published numerical results remain strict.")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    published_dir = root / "results/full"
    report_dir = args.output_dir.resolve() if args.output_dir is not None else published_dir
    published = json.loads((published_dir / "stage_summary.json").read_text(encoding="utf-8"))
    published_env = json.loads((published_dir / "environment.json").read_text(encoding="utf-8"))
    published_provenance = json.loads((published_dir / "source_provenance.json").read_text(encoding="utf-8"))
    if published.get("analysis") != "all" or published.get("status") != "computationally_complete":
        raise AssertionError("Run --analysis all first to publish the complete core results")
    current_core_hashes = source_hashes(root)
    current_all_hashes = source_hashes(root, include_root_entries=True)
    differences = check_source_snapshot(published_env["files_sha256"], current_core_hashes,
                                        current_core_hashes, args.allow_source_changes)
    work = root / "work"
    work.mkdir(exist_ok=True)
    cases = []
    child_env = dict(os.environ, PYTHONIOENCODING="utf-8")
    with tempfile.TemporaryDirectory(prefix="core-verification-", dir=work) as temp:
        isolated = Path(temp)
        copy_project_inputs(root, isolated)
        if source_hashes(isolated, include_root_entries=True) != current_all_hashes:
            raise AssertionError("Clean copy differs from the current source, including root entries")
        # Only the fixed sampling input is needed; never copy or modify filled forms.
        (isolated / "review_materials").mkdir()
        shutil.copy2(root / "review_materials/evidence_checklist.csv",
                     isolated / "review_materials/evidence_checklist.csv")

        def execute(command, cwd=None):
            return subprocess.run(command, cwd=cwd or isolated, text=True, encoding="utf-8",
                                  capture_output=True, env=child_env, timeout=180)

        test_command = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]
        tests = execute(test_command)
        if tests.returncode:
            raise RuntimeError(tests.stdout + tests.stderr)
        commands = [
            ("fresh_download", ["--analysis", "all"], {"univariate": 114, "joint": 438, "similarity": 9}),
            ("offline_cache", ["--analysis", "all", "--offline"], {"univariate": 114, "joint": 438, "similarity": 9}),
            ("rq1_selection", ["--analysis", "rq1", "--offline"], {"univariate": 114}),
            ("rq2_selection", ["--analysis", "rq2", "--offline"], {"joint": 438}),
            ("rq3_selection", ["--analysis", "rq3", "--offline"], {"similarity": 9}),
            ("legacy_stage_1", ["--stage", "1", "--offline"], {"univariate": 18}),
        ]
        full_results = None
        for name, arguments, expected_counts in commands:
            output = Path("work") / name
            command = [sys.executable, "scripts/run_stage.py", *arguments,
                       "--runs", "3", "--no-plots", "--output-dir", str(output)]
            completed = execute(command)
            if completed.returncode:
                raise RuntimeError(completed.stdout + completed.stderr)
            result_dir = isolated / output
            summary = json.loads((result_dir / "stage_summary.json").read_text(encoding="utf-8"))
            provenance = json.loads((result_dir / "source_provenance.json").read_text(encoding="utf-8"))
            environment = json.loads((result_dir / "environment.json").read_text(encoding="utf-8"))
            results = summary["results"]
            if set(results) != set(expected_counts):
                raise AssertionError(f"Unexpected analysis selection: {name}")
            for key, expected in expected_counts.items():
                if results[key]["cell_count"] != expected:
                    raise AssertionError(f"Unexpected comparison coverage: {name}/{key}")
                if name != "legacy_stage_1" and results[key] != published["results"][key]:
                    raise AssertionError(f"Isolated result differs from published result: {name}/{key}")
            if name == "legacy_stage_1":
                legacy = results["univariate"]
                if legacy["matched_cells"] != 18 or legacy["dimensions"]["os_layer"] != full_results["univariate"]["dimensions"]["os_layer"]:
                    raise AssertionError("Legacy OS-layer result differs from full RQ1")
            check_source_snapshot(published_env["files_sha256"], current_core_hashes,
                                  environment["files_sha256"], args.allow_source_changes)
            expected_mode = "downloaded" if name == "fresh_download" else "verified_cache"
            if provenance["acquisition_mode"] != expected_mode:
                raise AssertionError(f"Unexpected acquisition mode: {name}")
            for field in ("source_sha256_lf", "source_commit", "source_url"):
                if provenance[field] != published_provenance[field]:
                    raise AssertionError(f"Input source differs from the published source: {name}/{field}")
            logs = [json.loads((result_dir / path / "run_log.json").read_text(encoding="utf-8"))
                    for path in summary["active_runs"]]
            if len(logs) != 3 or len({log["semantic_result_sha256"] for log in logs}) != 1:
                raise AssertionError(f"Three actual deterministic runs required: {name}")
            if not summary["repeatability"]["identical_semantic_outputs"]:
                raise AssertionError("Repeated results differ")
            if name == "fresh_download":
                full_results = results
            elif name == "offline_cache" and results != full_results:
                raise AssertionError("Online and offline results differ")
            cases.append({"name": name, "command": ["py", "-3.11", *command[1:]],
                          "exit_code": completed.returncode, "stdout": completed.stdout.strip(),
                          "comparisons": summary["comparisons"], "repeatability": summary["repeatability"],
                          "component_sha256": {key: digest(value) for key, value in results.items()},
                          "source_provenance": provenance, "run_logs": logs})

        supplemental_cases = []
        policy_command = [sys.executable, "scripts/run_category_policy.py", "--runs", "3",
                          "--offline", "--output-dir", "work/category_policy"]
        policy_run = execute(policy_command)
        if policy_run.returncode:
            raise RuntimeError(policy_run.stdout + policy_run.stderr)
        policy_output = isolated / "work/category_policy"
        policy_result = json.loads((policy_output / "tables/category_policy_summary.json").read_text(encoding="utf-8"))
        published_policy = json.loads((root / "results/category_policy/tables/category_policy_summary.json").read_text(encoding="utf-8"))
        policy_summary = json.loads((policy_output / "run_summary.json").read_text(encoding="utf-8"))
        if policy_result != published_policy or not policy_summary["identical_semantic_outputs"]:
            raise AssertionError("Isolated category-policy results differ from published results")
        policy_logs = [json.loads((policy_output / item / "run_log.json").read_text(encoding="utf-8"))
                       for item in policy_summary["active_runs"]]
        if len(policy_logs) != 3 or len({item["semantic_result_sha256"] for item in policy_logs}) != 1:
            raise AssertionError("Category policies require three actual stable runs")
        supplemental_cases.append({"name": "category_policy", "exit_code": policy_run.returncode,
                                   "command": ["py", "-3.11", *policy_command[1:]],
                                   "matches_published_results": True, "summary": policy_summary,
                                   "run_logs": policy_logs})
        for action in ("prepare", "check"):
            review_command = [sys.executable, "scripts/manage_review.py", action]
            review_run = execute(review_command)
            if review_run.returncode:
                raise RuntimeError(review_run.stdout + review_run.stderr)
            supplemental_cases.append({"name": "blank_review_" + action, "exit_code": review_run.returncode,
                                       "command": ["py", "-3.11", *review_command[1:]],
                                       "stdout": review_run.stdout.strip()})
        review_status = json.loads((isolated / "results/human_review/status.json").read_text(encoding="utf-8"))
        if review_status["status"] != "pending_human_review":
            raise AssertionError("Blank forms must not be marked as reviewed")

        # A second clean repository makes Week 2's first acquisition a genuine
        # empty-cache download, independent of the six preceding core cases.
        weekend_repository = isolated / "weekend_repository"
        weekend_repository.mkdir()
        copy_project_inputs(root, weekend_repository)
        if source_hashes(weekend_repository, include_root_entries=True) != current_all_hashes:
            raise AssertionError("Week 2 clean copy differs from current source")
        caller = isolated / "external_caller"
        caller.mkdir()
        expected_table = table_ii_values(published_dir / "tables/table_ii.csv")
        expected_weekend = json.loads((root / "results/weekend_02/runs/run_01/results.json").read_text(encoding="utf-8"))
        published_weekend_env = json.loads((root / "results/weekend_02/environment.json").read_text(encoding="utf-8"))
        baseline = "paper_baselines_weekend_02.json"
        if current_all_hashes[baseline] != published_weekend_env["files_sha256"][baseline]:
            raise AssertionError("Week 2 paper reference changed; --allow-source-changes cannot waive reference changes")
        expected_sha = published_provenance["source_sha256_lf"]
        if expected_weekend["univariate"] != published["results"]["univariate"]:
            raise AssertionError("Published Week 2 and core RQ1 values disagree")
        weekend_cases = []
        for name, flags, mode in (("weekend_02_fresh_download", [], "downloaded"),
                                  ("weekend_02_external_cwd_offline", ["--offline"], "verified_cache")):
            command = [sys.executable, str(weekend_repository / "run_weekend_02.py"),
                       "--runs", "3", "--no-plots", "--output-dir", name, *flags]
            completed = execute(command, caller)
            if completed.returncode:
                raise RuntimeError(completed.stdout + completed.stderr)
            checks = inspect_weekend_output(caller / name, expected_table, expected_weekend, expected_sha, mode)
            weekend_cases.append({"name": name, "command": ["py", "-3.11", *command[1:]],
                                  "cwd": str(caller), "external_working_directory": True,
                                  "relative_output_resolved_against_caller": True,
                                  "exit_code": completed.returncode, **checks})
        cache = weekend_repository / "data/raw/index.html"
        cache.write_bytes(cache.read_bytes() + b"\n")
        rejected = caller / "weekend_02_bad_cache"
        command = [sys.executable, str(weekend_repository / "run_weekend_02.py"), "--offline", "--no-plots",
                   "--output-dir", str(rejected)]
        completed = execute(command, caller)
        if completed.returncode == 0 or "checksum mismatch" not in completed.stderr.lower() or rejected.exists():
            raise AssertionError("Week 2 must reject corrupted cache before creating result files")
        weekend_cases.append({"name": "weekend_02_corrupt_cache_rejected", "command": ["py", "-3.11", *command[1:]],
                              "exit_code": completed.returncode, "expected_failure": True,
                              "stderr": completed.stderr.strip(), "no_output_created": True})

        manifest = json.loads((published_dir / "figure_manifest.json").read_text(encoding="utf-8"))
        expected_figures = ({f"figures/rq1_{dimension}.png" for dimension in published["results"]["univariate"]["dimensions"]}
                            | {f"figures/{table}_{os_name}.png" for table, data in published["results"]["joint"]["tables"].items() for os_name in data["matrices"]}
                            | {f"figures/rq3_{dimension}.png" for dimension in published["results"]["similarity"]["dimensions"]})
        if set(manifest) != expected_figures or len(manifest) != 17:
            raise AssertionError("Published full run must contain the 17 expected figures")
        for figure in manifest:
            if not (published_dir / figure).read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
                raise AssertionError(f"Missing or invalid PNG: {figure}")
        if source_hashes(root, include_root_entries=True) != current_all_hashes or source_hashes(isolated, include_root_entries=True) != current_all_hashes:
            raise AssertionError("Source files changed during verification; freeze code and rerun")
        report = {
            "verified_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "python": sys.version, "status": "passed", "isolated_copy": True,
            "unit_tests": {"command": ["py", "-3.11", *test_command[1:]],
                           "exit_code": tests.returncode, "output": tests.stdout + tests.stderr},
            "cases": cases, "supplemental_cases": supplemental_cases, "weekend_02_cases": weekend_cases,
            "matches_published_core_results": True,
            "matches_published_source_hashes": not any(differences.values()),
            "source_changes_allowed": args.allow_source_changes, "source_changes": differences,
            "source_change_reason": "Explicit opt-in permits historical source-snapshot differences only. Current and isolated sources match exactly; pinned data, references and published numerical result comparisons remain enforced.",
            "matches_current_source_hashes": True, "current_source_hashes": current_all_hashes,
            "historical_source_snapshot": "results/full/environment.json",
            "additional_root_entries": {key: value for key, value in current_all_hashes.items() if key not in current_core_hashes},
            "published_figure_files_checked": manifest,
            "limitations": "Automated clean-copy verification, not independent student execution or human label review. Numerical cases use --no-plots; the separate full run generates figures, whose PNG signatures are checked here."
        }
        report_dir.mkdir(parents=True, exist_ok=True)
        (report_dir / "verification.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("Verified fresh download, offline cache, RQ1/RQ2/RQ3, legacy stage 1, category policies, blank review workflow, Week 2 fresh/offline/corrupt-cache cases, 17 figure files, and unit tests. Report: " + str(report_dir / "verification.json"))


if __name__ == "__main__":
    main()
