#!/usr/bin/env python3
"""Verify real download/cache/legacy execution in an isolated source copy."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone


def main():
    root = Path(__file__).resolve().parents[1]
    work = root / "work"
    work.mkdir(exist_ok=True)
    cases = []
    with tempfile.TemporaryDirectory(prefix="rq1-verification-", dir=work) as temp:
        isolated = Path(temp)
        for folder in ("src", "scripts", "reference", "tests"):
            shutil.copytree(root / folder, isolated / folder,
                            ignore=shutil.ignore_patterns("__pycache__"))
        tests = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
                               cwd=isolated, text=True, capture_output=True)
        if tests.returncode:
            raise RuntimeError(tests.stdout + tests.stderr)
        commands = [
            ("fresh_download", ["--analysis", "rq1", "--runs", "3", "--no-plots"]),
            ("offline_cache", ["--analysis", "rq1", "--runs", "3", "--offline", "--no-plots"]),
            ("legacy_stage_1", ["--stage", "1", "--runs", "3", "--offline", "--no-plots"]),
        ]
        for name, arguments in commands:
            output = Path("work") / name
            command = [sys.executable, "scripts/run_stage.py", *arguments, "--output-dir", str(output)]
            completed = subprocess.run(command, cwd=isolated, capture_output=True, text=True)
            if completed.returncode:
                raise RuntimeError(completed.stdout + completed.stderr)
            result_dir = isolated / output
            summary = json.loads((result_dir / "stage_summary.json").read_text(encoding="utf-8"))
            provenance = json.loads((result_dir / "source_provenance.json").read_text(encoding="utf-8"))
            counts = summary["results"]["univariate"]
            expected = 18 if name == "legacy_stage_1" else 114
            if counts["cell_count"] != expected or counts["matched_cells"] != expected:
                raise AssertionError(f"Unexpected Table II result for {name}")
            if provenance["acquisition_mode"] != ("downloaded" if name == "fresh_download" else "verified_cache"):
                raise AssertionError("Unexpected acquisition mode")
            cases.append({"name": name, "command": ["python", *command[1:]],
                          "exit_code": completed.returncode, "stdout": completed.stdout.strip(),
                          "matched_cells": counts["matched_cells"], "cell_count": counts["cell_count"],
                          "repeatability": summary["repeatability"], "source_provenance": provenance})
        if cases[0]["repeatability"]["semantic_result_sha256"] != cases[1]["repeatability"]["semantic_result_sha256"]:
            raise AssertionError("Online and offline results differ")
        published = json.loads((root / "results/rq1/stage_summary.json").read_text(encoding="utf-8"))
        if published["repeatability"]["semantic_result_sha256"] != cases[0]["repeatability"]["semantic_result_sha256"]:
            raise AssertionError("Isolated computation differs from published RQ1 results")
        report = {"verified_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                  "python": sys.version, "status": "passed", "isolated_copy": True,
                  "unit_tests": {"command": "python -m unittest discover -s tests -v",
                                 "exit_code": tests.returncode, "output": tests.stdout + tests.stderr},
                  "cases": cases, "matches_published_rq1": True,
                  "limitations": "Automated verification, not a student's independent execution or human label review. Plots are checked by the separate full run."}
        (root / "results/rq1/verification.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Verified fresh download, offline cache, legacy stage 1, and unit tests.")


if __name__ == "__main__":
    main()
