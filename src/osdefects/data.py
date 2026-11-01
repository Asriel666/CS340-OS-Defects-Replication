"""Pinned author-data ingestion, explicit normalization, and structural checks.

The author's data are JSON arrays inside a JavaScript object in index.html.
Only the object keys use JavaScript syntax. We parse keys and decode each
array with the JSON decoder; no JavaScript or Python expression is executed.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen


SOURCE_COMMIT = "832d536f5d381d428a887e59ceeacc90a40e3b7e"
SOURCE_URL = (
    "https://raw.githubusercontent.com/zuohongyao/zuohongyao.github.io/"
    + SOURCE_COMMIT
    + "/index.html"
)
# Hash of the pinned UTF-8 source after CRLF/CR -> LF normalization.
SOURCE_SHA256_LF = "c617aa2478fea265b61c6b18ac158234ad1f2f4c4b3d0c8abbb7760f75e26a56"
OS_NAMES = {"android": "Android", "linux": "Linux", "harmony": "HarmonyOS"}
LAYER_MAP = {
    "Kernel Layer": "Kernel",
    "System Library Layer": "SystemLib",
    "Runtime/Virtual Machine Layer": "RuntimeVM",
    "Framework Layer": "Framework",
    "System Service Layer": "SystemService",
    "Application Layer": "Application",
}
FUNCTION_MAP = {
    "Memory and Resource Management": "Mem/Res Mng",
    "Process and Task Scheduling": "Pro/Tas Sch",
    "Storage Management": "Sto Mng",
    "Device Management and Drivers": "Dev/Drv",
    "Network and Communication": "Net/Com",
    "Compatibility and Adaptation": "Com/Adp",
    "Security and Permission Control": "Sec/Perm",
    "Graphics and Rendering": "Gra/Ren",
}
TRIGGER_MAP = {
    "Permission/Identity Dependency Trigger": "Per/Ide Dep",
    "Regular Operation Trigger": "Reg Ope",
    "Boundary Condition Trigger": "Bor Con",
    "Concurrency/Multi-thread Trigger": "Con/Mul Thr",
    "State Dependency Trigger": "Sta Dep",
    "Environment Dependency Trigger": "Env Dep",
    "Multi-Language/Localization Trigger": "Mul/Loc Dep",
}
SEVERITY_MAP = {label: label for label in ("Critical", "High", "Medium", "Low", "Undecided")}
# Author dashboard uses Unknown for six HarmonyOS rows; Table II calls this
# category Undecided. Keep the original label in every record's raw dictionary.
SEVERITY_MAP["Unknown"] = "Undecided"
CODE_MAP = {
    "Entire Class": "Class",
    "Entire Function": "Function",
    "Function Signature": "Signature",
    "Loop": "Loop",
    "If": "If",
    "Exception": "Exception",
    "Function Call": "Call",
    "Assignment": "Assignment",
    "Return": "Return",
    "Condition": "Condition",
    "Object": "Object",
    "Variable": "Variable",
}
CANONICAL_CATEGORIES = {
    "os_layer": list(LAYER_MAP.values()),
    "affected_function": list(FUNCTION_MAP.values()),
    "trigger_scenario": list(TRIGGER_MAP.values()),
    "severity": ["Critical", "High", "Medium", "Low", "Undecided"],
    "code_level": list(CODE_MAP.values()),
}
NUMERIC_FIELDS = {
    "line_deletions": "Line Deletions",
    "line_additions": "Line Additions",
    "line_changes": "Line Changes",
    "involved_functions": "Involved Functions",
    "modified_files": "Modified Files",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _lf_bytes(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fetch_source(path: Path, offline: bool = False) -> dict:
    """Use a checksum-verified cache, or fetch this exact pinned source.

    A cache without acquisition metadata gets retrieved_at_utc=None: inspecting
    a local file is not represented as a network retrieval. An actual download
    records its timestamp. Both paths record the current inspection timestamp.
    """
    path = Path(path)
    meta_path = path.with_suffix(".provenance.json")
    metadata = {}
    if meta_path.exists():
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    if path.exists():
        payload = path.read_bytes()
        acquisition = "verified_cache"
    else:
        if offline:
            raise FileNotFoundError("Offline source cache is missing: " + str(path))
        request = Request(SOURCE_URL, headers={"User-Agent": "CS340-OS-Defects-Replication/1.0"})
        with urlopen(request, timeout=30) as response:
            payload = response.read(5_000_001)
        if len(payload) > 5_000_000:
            raise ValueError("Source exceeds the 5 MB download limit")
        metadata = {
            "retrieved_at_utc": _utc_now(),
            "download_bytes_sha256": hashlib.sha256(payload).hexdigest(),
        }
        acquisition = "downloaded"
    normalized = _lf_bytes(payload)
    normalized.decode("utf-8", errors="strict")
    digest = hashlib.sha256(normalized).hexdigest()
    if digest != SOURCE_SHA256_LF:
        raise ValueError("Pinned source checksum mismatch: expected " + SOURCE_SHA256_LF + ", got " + digest)
    if acquisition == "downloaded":
        path.parent.mkdir(parents=True, exist_ok=True)
        # Validate before replacing the cache, and replace it atomically.
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temp:
            temp.write(normalized)
            temp_path = Path(temp.name)
        temp_path.replace(path)
    metadata.update({
        "source_url": SOURCE_URL,
        "source_commit": SOURCE_COMMIT,
        "source_sha256_lf": digest,
        "source_bytes_lf": len(normalized),
        "line_ending_policy": "CRLF and CR normalized to LF for hash verification",
        "retrieved_at_utc": metadata.get("retrieved_at_utc"),
        "inspected_at_utc": _utc_now(),
        "acquisition_mode": acquisition,
        "source_path": str(path),
    })
    _write_json(meta_path, metadata)
    return metadata


def _balanced_object(text: str, start: int) -> str:
    """Find the DATA object's end while honoring escaped JSON string content."""
    if start >= len(text) or text[start] != "{":
        raise ValueError("DATA must begin with an object")
    stack = []
    in_string = False
    escaped = False
    for i in range(start, len(text)):
        char = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char in "{[":
            stack.append(char)
        elif char in "}]":
            expected = "{" if char == "}" else "["
            if not stack or stack.pop() != expected:
                raise ValueError("Mismatched DATA brackets")
            if not stack:
                return text[start:i + 1]
    raise ValueError("Unterminated DATA object or string")


def extract_raw_data(text: str) -> dict:
    """Extract exactly the three OS arrays, permitting only outer JS key syntax."""
    matches = list(re.finditer(r"\b(?:var|let|const)\s+DATA\s*=\s*", text))
    if len(matches) != 1:
        raise ValueError("Expected exactly one DATA assignment")
    literal = _balanced_object(text, matches[0].end())
    decoder = json.JSONDecoder()
    result = {}
    pos = 1

    def skip_space(index: int) -> int:
        while index < len(literal) and literal[index].isspace():
            index += 1
        return index

    while True:
        pos = skip_space(pos)
        if literal[pos] == "}":
            break
        if literal[pos] == '"':
            key, pos = decoder.raw_decode(literal, pos)
        else:
            match = re.match(r"[A-Za-z_$][A-Za-z0-9_$]*", literal[pos:])
            if not match:
                raise ValueError("Invalid DATA object key")
            key = match.group()
            pos += len(key)
        if key not in OS_NAMES or key in result:
            raise ValueError("Unknown or duplicate OS data key: " + str(key))
        pos = skip_space(pos)
        if literal[pos] != ":":
            raise ValueError("Missing colon after DATA key")
        pos = skip_space(pos + 1)
        try:
            rows, pos = decoder.raw_decode(literal, pos)
        except json.JSONDecodeError as exc:
            raise ValueError("DATA arrays must contain JSON, not executable code") from exc
        if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
            raise ValueError("Each OS DATA value must be an array of objects")
        result[key] = rows
        pos = skip_space(pos)
        if literal[pos] == "}":
            break
        if literal[pos] != ",":
            raise ValueError("Expected comma between OS arrays")
        pos = skip_space(pos + 1)
        if literal[pos] == "}":
            raise ValueError("Trailing comma is not part of the accepted DATA format")
    if set(result) != set(OS_NAMES):
        raise ValueError("DATA must contain android, linux, and harmony")
    return result


def _mapped(value: object, mapping: dict, field: str) -> str:
    if not isinstance(value, str) or value not in mapping:
        raise ValueError("Unexpected " + field + " label: " + repr(value))
    return mapping[value]


def _numeric(value: object, field: str) -> tuple[int, bool]:
    if type(value) is int:
        return value, False
    if isinstance(value, str) and re.fullmatch(r"\d+\+?", value):
        censored = value.endswith("+")
        if censored and field != "involved_functions":
            raise ValueError("Unexpected censored numeric field: " + field)
        return int(value.rstrip("+")), censored
    raise ValueError("Expected nonnegative integer in " + field + ": " + repr(value))


def load_records(source_path: Path) -> list[dict]:
    """Normalize rows without filtering or silently repairing author values."""
    data = extract_raw_data(Path(source_path).read_text(encoding="utf-8"))
    records = []
    for source_os, os_name in OS_NAMES.items():
        for row in data[source_os]:
            required = ["Bug ID", "OS Layer", "Affected Function", "Trigger Scenario", "Severity Level", "Code Level", "Patch", *NUMERIC_FIELDS.values()]
            missing = [key for key in required if key not in row]
            if missing:
                raise ValueError("Missing source columns: " + ", ".join(missing))
            code_raw = row["Code Level"]
            if not isinstance(code_raw, str) or not code_raw:
                raise ValueError("Code Level must be a nonempty comma-separated string")
            codes = [_mapped(code.strip(), CODE_MAP, "Code Level") for code in code_raw.split(",")]
            record = {
                "os": os_name,
                "bug_id": row["Bug ID"],
                "os_layer": _mapped(row["OS Layer"], LAYER_MAP, "OS Layer"),
                "affected_function": _mapped(row["Affected Function"], FUNCTION_MAP, "Affected Function"),
                "trigger_scenario": _mapped(row["Trigger Scenario"], TRIGGER_MAP, "Trigger Scenario"),
                "severity": _mapped(row["Severity Level"], SEVERITY_MAP, "Severity Level"),
                "code_level": codes,
                "patch": row["Patch"],
                "raw": dict(row),
                "numeric_censored": [],
            }
            for normalized_field, source_field in NUMERIC_FIELDS.items():
                value, censored = _numeric(row[source_field], normalized_field)
                record[normalized_field] = value
                if censored:
                    record["numeric_censored"].append(normalized_field)
            records.append(record)
    validate_records(records)
    return records


def validate_records(records: list[dict]) -> dict:
    """Enforce curated dataset shape; disclose anomalies without rewriting them."""
    if not isinstance(records, list):
        raise ValueError("Records must be a list")
    counts = Counter()
    seen = set()
    anomalies = []
    censored = []
    severity_mappings = []
    zero_function_rows = []
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("Each record must be an object")
        os_name, bug_id = record.get("os"), record.get("bug_id")
        if os_name not in OS_NAMES.values() or not isinstance(bug_id, str) or not bug_id.strip():
            raise ValueError("Invalid OS name or bug ID")
        identity = (os_name, bug_id)
        if identity in seen:
            raise ValueError("Duplicate OS/bug ID: " + repr(identity))
        seen.add(identity)
        counts[os_name] += 1
        for field, categories in CANONICAL_CATEGORIES.items():
            value = record.get(field)
            if field == "code_level":
                if not isinstance(value, list) or not value or len(value) != len(set(value)) or any(code not in categories for code in value):
                    raise ValueError("Invalid multi-label code_level for " + repr(identity))
            elif not isinstance(value, str) or value not in categories:
                raise ValueError("Invalid " + field + " for " + repr(identity))
        for field in NUMERIC_FIELDS:
            value = record.get(field)
            if type(value) is not int or value < 0:
                raise ValueError("Invalid integer field " + field + " for " + repr(identity))
            if field in ("line_deletions", "line_additions", "line_changes") and value > 500:
                raise ValueError("Line count exceeds curated <=500 bound for " + repr(identity))
        if record["line_changes"] == 0 or record["modified_files"] == 0:
            raise ValueError("A repair must have positive line_changes and modified_files")
        if not isinstance(record.get("patch"), str) or not record["patch"].startswith(("https://", "http://")):
            raise ValueError("Missing or invalid patch link for " + repr(identity))
        if record["line_deletions"] + record["line_additions"] != record["line_changes"]:
            anomalies.append({"os": os_name, "bug_id": bug_id, "line_deletions": record["line_deletions"], "line_additions": record["line_additions"], "line_changes": record["line_changes"]})
        if record.get("numeric_censored"):
            censored.append({"os": os_name, "bug_id": bug_id, "fields": record["numeric_censored"], "raw_involved_functions": record.get("raw", {}).get("Involved Functions")})
        if record.get("raw", {}).get("Severity Level") == "Unknown":
            severity_mappings.append({"os": os_name, "bug_id": bug_id, "original": "Unknown", "normalized": "Undecided"})
        if record["involved_functions"] == 0:
            zero_function_rows.append({"os": os_name, "bug_id": bug_id})
    expected = {name: 500 for name in OS_NAMES.values()}
    if dict(counts) != expected:
        raise ValueError("Expected 500 records per OS; got " + repr(dict(counts)))
    return {
        "valid": True,
        "record_count": len(records),
        "counts_by_os": dict(counts),
        "unique_os_bug_ids": len(seen),
        "categories": CANONICAL_CATEGORIES,
        "warnings": {
            "line_change_sum_mismatches": anomalies,
            "censored_function_counts": censored,
            "severity_label_mappings": severity_mappings,
            "zero_involved_function_rows": zero_function_rows,
        },
        "normalization_policy": {
            "severity": "Unknown -> Undecided, raw label retained",
            "functions": "Numeric strings converted to integers; n+ becomes lower bound n with numeric_censored flag",
            "line_counts": "All source values retained, including sum mismatch; no inferred repairs",
            "code_level": "Multi-label list, percentages use defect count as denominator",
        },
    }


def write_dataset(records: list[dict], outdir: Path) -> dict:
    """Save normalized JSON/CSV, full raw rows, and machine-readable audit."""
    audit = validate_records(records)
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    paths = {name: outdir / name for name in ("records.json", "records.csv", "raw_records.json", "validation.json")}
    _write_json(paths["records.json"], records)
    _write_json(paths["raw_records.json"], [{"os": row["os"], **row["raw"]} for row in records])
    _write_json(paths["validation.json"], audit)
    columns = ["os", "bug_id", "os_layer", "affected_function", "trigger_scenario", "severity", "code_level", *NUMERIC_FIELDS, "patch", "numeric_censored"]
    with paths["records.csv"].open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for record in records:
            row = {key: record[key] for key in columns}
            row["code_level"] = "|".join(row["code_level"])
            row["numeric_censored"] = "|".join(row["numeric_censored"])
            writer.writerow(row)
    return {name: str(path) for name, path in paths.items()}
