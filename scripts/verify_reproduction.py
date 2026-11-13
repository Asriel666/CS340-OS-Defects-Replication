#!/usr/bin/env python3
"""Verify core, category policies and blank review workflow in a clean copy."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":")).encode("utf-8")).hexdigest()


def main():
    root = Path(__file__).resolve().parents[1]
    published_dir = root / "results/full"
    published = json.loads((published_dir / "stage_summary.json").read_text(encoding="utf-8"))
    published_env = json.loads((published_dir / "environment.json").read_text(encoding="utf-8"))
    if published.get("analysis") != "all" or published.get("status") != "computationally_complete":
        raise AssertionError("Run --analysis all first to publish the complete core results")
    work = root / "work"
    work.mkdir(exist_ok=True)
    cases = []
    child_env = dict(os.environ, PYTHONIOENCODING="utf-8")
    with tempfile.TemporaryDirectory(prefix="core-verification-", dir=work) as temp:
        isolated = Path(temp)
        for folder in ("src", "scripts", "reference", "tests"):
            shutil.copytree(root / folder, isolated / folder,
                            ignore=shutil.ignore_patterns("__pycache__"))
        for filename in ("requirements.txt", "SUBMISSION.json", "SNAPSHOT.json"):
            shutil.copy2(root / filename, isolated / filename)
        # Only the fixed sampling input is needed; never copy or modify filled forms.
        (isolated / "review_materials").mkdir()
        shutil.copy2(root / "review_materials/evidence_checklist.csv",
                     isolated / "review_materials/evidence_checklist.csv")

        def execute(command):
            return subprocess.run(command, cwd=isolated, text=True, encoding="utf-8",
                                  capture_output=True, env=child_env)

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
            if environment["files_sha256"] != published_env["files_sha256"]:
                raise AssertionError("Published source hashes are stale; rerun --analysis all")
            expected_mode = "downloaded" if name == "fresh_download" else "verified_cache"
            if provenance["acquisition_mode"] != expected_mode:
                raise AssertionError(f"Unexpected acquisition mode: {name}")
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

        manifest = json.loads((published_dir / "figure_manifest.json").read_text(encoding="utf-8"))
        expected_figures = ({f"figures/rq1_{dimension}.png" for dimension in published["results"]["univariate"]["dimensions"]}
                            | {f"figures/{table}_{os_name}.png" for table, data in published["results"]["joint"]["tables"].items() for os_name in data["matrices"]}
                            | {f"figures/rq3_{dimension}.png" for dimension in published["results"]["similarity"]["dimensions"]})
        if set(manifest) != expected_figures or len(manifest) != 17:
            raise AssertionError("Published full run must contain the 17 expected figures")
        for figure in manifest:
            if not (published_dir / figure).read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
                raise AssertionError(f"Missing or invalid PNG: {figure}")
        report = {
            "verified_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "python": sys.version, "status": "passed", "isolated_copy": True,
            "unit_tests": {"command": ["py", "-3.11", *test_command[1:]],
                           "exit_code": tests.returncode, "output": tests.stdout + tests.stderr},
            "cases": cases, "supplemental_cases": supplemental_cases,
            "matches_published_core_results": True,
            "matches_published_source_hashes": True, "published_figure_files_checked": manifest,
            "limitations": "Automated clean-copy verification, not independent student execution or human label review. Numerical cases use --no-plots; the separate full run generates figures, whose PNG signatures are checked here."
        }
        (published_dir / "verification.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("Verified fresh download, offline cache, RQ1/RQ2/RQ3, legacy stage 1, category policies, blank review workflow, 17 figure files, and unit tests.")


if __name__ == "__main__":
    main()
