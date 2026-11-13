#!/usr/bin/env python3
"""Prepare separate blind forms or check real submissions without filling judgments."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from osdefects.common import write_json
from osdefects.review_workflow import prepare_review_materials, read_rows, validate_review_sample, validate_reviews


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "check"))
    parser.add_argument("--materials", type=Path, default=ROOT / "review_materials")
    parser.add_argument("--evidence", type=Path, default=ROOT / "review_materials/evidence_checklist.csv")
    parser.add_argument("--output", type=Path, default=ROOT / "results/human_review/status.json")
    args = parser.parse_args()
    if args.action == "prepare":
        result = prepare_review_materials(args.evidence, args.materials)
    else:
        folder = args.materials / "blind"
        cases = read_rows(folder / "cases.csv")
        validate_review_sample(cases, read_rows(args.evidence))
        result = validate_reviews(cases, read_rows(folder / "reviewer_A.csv"),
                                  read_rows(folder / "reviewer_B.csv"))
        write_json(args.output, result)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
