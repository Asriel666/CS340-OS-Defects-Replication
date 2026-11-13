"""Prepare answer-free forms and check submitted review records without certifying people."""
import csv
import ipaddress
import re
from collections import Counter
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from .common import OS_ORDER, write_csv
from .data import CANONICAL_CATEGORIES

FIELDS = ("os_layer", "affected_function", "trigger_scenario")
FORM_FIELDS = ("reviewer", "os", "bug_id", "patch_url", "reviewer_name", "reviewed_on",
               "your_os_layer", "your_affected_function", "your_trigger_scenario",
               "evidence_urls", "notes")


def read_rows(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        headers = reader.fieldnames
        if not headers or any(not header or header != header.strip() for header in headers) or len(set(headers)) != len(headers):
            raise ValueError("CSV headers must be nonempty, unique and unambiguous: " + str(path))
        rows = list(reader)
    if not rows or any(None in row or any(v is None for v in row.values()) for row in rows):
        raise ValueError("CSV must have a header and complete, unambiguous rows: " + str(path))
    return rows


def indexed(rows):
    result = {}
    for row in rows:
        key = (row.get("os"), row.get("bug_id"))
        if key[0] not in OS_ORDER or not key[1] or key in result:
            raise ValueError("Missing, duplicate, or invalid review identity: " + repr(key))
        result[key] = row
    return result


def valid_http_url(value):
    """Validate URL syntax only; this does not assert availability or evidence quality."""
    if not isinstance(value, str) or any(char.isspace() or ord(char) < 32 for char in value):
        return False
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
        # Accessing .port also rejects malformed or out-of-range ports.
        parsed.port
        if parsed.scheme not in ("http", "https") or not host:
            return False
        try:
            ipaddress.ip_address(host)
            return True
        except ValueError:
            host = host.rstrip(".").encode("idna").decode("ascii")
            return bool(host) and len(host) <= 253 and all(
                re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", part)
                for part in host.split("."))
    except (ValueError, UnicodeError):
        return False


def evidence_manifest(source):
    """Derive the fixed twelve-case manifest from the original evidence checklist."""
    indexed(source)
    if Counter(row["os"] for row in source) != Counter({os_name: 4 for os_name in OS_ORDER}):
        raise ValueError("Expected exactly four sampled defects per OS")
    manifest = []
    for row in source:
        if not valid_http_url(row.get("patch")):
            raise ValueError("Original evidence checklist contains an invalid patch URL")
        manifest.append({"os": row["os"], "bug_id": row["bug_id"], "patch_url": row["patch"]})
    return manifest


def validate_review_sample(cases, source):
    """Check edited working copies against the original 4-per-OS sample and URLs."""
    expected = indexed(evidence_manifest(source))
    current = indexed(cases)
    if set(current) != set(expected):
        raise ValueError("Working cases differ from the original twelve-case evidence sample")
    if any(current[key] != expected[key] for key in expected):
        raise ValueError("Working case columns or patch URL differ from original evidence")


def prepare_review_materials(evidence_path, destination):
    """Keep answer keys in a separate directory; never overwrite existing forms."""
    source = read_rows(evidence_path)
    manifest, labels = evidence_manifest(source), []
    for row in source:
        for field in FIELDS:
            if row.get("paper_" + field) not in CANONICAL_CATEGORIES[field]:
                raise ValueError("Unknown author label in evidence checklist: " + field)
        labels.append({"os": row["os"], "bug_id": row["bug_id"],
                       **{field: row["paper_" + field] for field in FIELDS}})
    destination = Path(destination)
    outputs = {destination / "blind/cases.csv": manifest,
               destination / "coordinator/author_labels.csv": labels}
    for reviewer in ("A", "B"):
        outputs[destination / f"blind/reviewer_{reviewer}.csv"] = [
            {**dict.fromkeys(FORM_FIELDS, ""), "reviewer": reviewer, **row} for row in manifest]
    # Preflight every existing path before writing anything. Filled judgments stay byte-for-byte intact.
    for path, rows in outputs.items():
        if path.exists():
            existing = read_rows(path)
            if set(indexed(existing)) != set(indexed(rows)):
                raise ValueError("Existing material belongs to a different sample: " + str(path))
            if path.name.startswith("reviewer_"):
                if any(set(row) != set(FORM_FIELDS) for row in existing):
                    raise ValueError("Existing reviewer form has unexpected columns: " + str(path))
            elif existing != rows:
                raise ValueError("Existing manifest/answer key differs; preserve and inspect it: " + str(path))
    created = []
    for path, rows in outputs.items():
        if not path.exists():
            write_csv(path, rows)
            created.append(str(path))
    return {"sample_size": len(manifest), "created": created,
            "meaning": "Prepared forms only; no human judgments or evidence have been supplied."}


def validate_reviews(cases, sheet_a, sheet_b):
    """Return completeness and observed agreement; blank/unconfirmed labels never count as agreement."""
    manifest = indexed(cases)
    if not manifest:
        raise ValueError("Cannot check an empty sample")
    reviewers, judgments = {}, {}
    for reviewer, rows in (("A", sheet_a), ("B", sheet_b)):
        entries = indexed(rows)
        if set(entries) != set(manifest):
            raise ValueError("Review form does not contain exactly the sampled cases: " + reviewer)
        submitted, fully_confirmed, names = 0, 0, set()
        judgments[reviewer] = {}
        for key, row in entries.items():
            if set(row) != set(FORM_FIELDS) or row["reviewer"] != reviewer:
                raise ValueError("Unexpected reviewer or form columns: " + reviewer)
            if row["patch_url"] != manifest[key]["patch_url"]:
                raise ValueError("Original patch URL was changed: " + repr(key))
            values = {field: row["your_" + field].strip() for field in FIELDS}
            for field, value in values.items():
                if value and value != "unconfirmed" and value not in CANONICAL_CATEGORIES[field]:
                    raise ValueError("Unknown human-review label: " + field + "=" + value)
            name, reviewed_on = row["reviewer_name"].strip(), row["reviewed_on"].strip()
            if name:
                names.add(name)
            if reviewed_on:
                try:
                    date.fromisoformat(reviewed_on)
                except ValueError as error:
                    raise ValueError("reviewed_on must be an ISO date") from error
            complete = bool(name and reviewed_on and all(values.values()) and row["notes"].strip())
            urls = row["evidence_urls"].replace(";", " ").split()
            if urls and not all(valid_http_url(url) for url in urls):
                complete = False
            if complete and any(value != "unconfirmed" for value in values.values()):
                complete = bool(urls)
            if complete:
                submitted += 1
                fully_confirmed += all(value != "unconfirmed" for value in values.values())
                judgments[reviewer][key] = values
        if len(names) > 1:
            raise ValueError("One form must identify one reviewer: " + reviewer)
        reviewers[reviewer] = {"declared_name": next(iter(names), None), "submitted_cases": submitted,
                               "fully_confirmed_cases": fully_confirmed,
                               "incomplete_cases": len(manifest) - submitted}
    if reviewers["A"]["declared_name"] and reviewers["A"]["declared_name"] == reviewers["B"]["declared_name"]:
        raise ValueError("A and B declare the same name; this is not two identified reviewers")
    agreement, disagreements = {}, []
    for field in FIELDS:
        eligible, equal = 0, 0
        for key in manifest:
            a = judgments["A"].get(key, {}).get(field)
            b = judgments["B"].get(key, {}).get(field)
            if a in (None, "unconfirmed") or b in (None, "unconfirmed"):
                continue
            eligible += 1
            equal += a == b
            if a != b:
                disagreements.append({"os": key[0], "bug_id": key[1], "dimension": field, "A": a, "B": b})
        agreement[field] = {"eligible_pairs": eligible, "agreements": equal,
                            "agreement_fraction": equal / eligible if eligible else None}
    ready = all(value["submitted_cases"] == len(manifest) for value in reviewers.values())
    return {"sample_size": len(manifest), "status": "ready_for_adjudication" if ready else "pending_human_review",
            "reviewers": reviewers, "agreement": agreement, "disagreements": disagreements,
            "adjudication_complete": False,
            "meaning": "Checks record structure and declared completion only. It cannot certify reviewer identity, independent work, or correctness. Unconfirmed labels are excluded from agreement denominators."}
