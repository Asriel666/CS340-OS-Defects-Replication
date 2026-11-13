"""Fetch the 12 sampled patch links and inspect their bodies, not just HTTP status.

Raw response bodies stay in ignored work/. Published artifacts contain provenance,
hashes and structural observations only; this is not independent human annotation.
"""
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def retrieval_url(url: str) -> tuple[str, str]:
    """Use Gitiles' equivalent base64 diff endpoint for Googlesource links."""
    parts = urlsplit(url)
    if parts.hostname == "android.googlesource.com":
        query = dict(parse_qsl(parts.query))
        query["format"] = "TEXT"
        return urlunsplit(parts._replace(query=urlencode(query))), "base64"
    return url, "identity"


def inspect_body(body: bytes, content_type: str = "") -> dict:
    text = body.decode("utf-8", errors="replace")
    first = text.lstrip()[:4096].lower()
    if first.startswith(("<!doctype html", "<html")) or (
        "<html" in first and "text/html" in content_type.lower()
    ):
        if any(s in first for s in ("captcha", "challenge", "access denied", "robot check")):
            kind = "html_access_challenge"
        elif any(s in first for s in ("sign in", "signin", "log in", "login")):
            kind = "html_login_or_site_page"
        else:
            kind = "html_page"
        return {"content_kind": kind, "changed_files": [], "hunk_count": 0,
                "nested_hunk_count": 0, "nested_changed_files": [], "hunk_contexts": []}
    files = []
    old_name = None
    for line in text.splitlines():
        if line.startswith("--- "):
            old_name = line[4:].split("\t", 1)[0].strip()
        if line.startswith("+++ "):
            name = line[4:].split("\t", 1)[0].strip()
            if name == "/dev/null":
                name = old_name
            if name != "/dev/null" and name not in files:
                if name:
                    files.append(name)
    hunks = re.findall(r"^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@(.*)$", text, re.M)
    nested_hunks = re.findall(r"^[+]@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@", text, re.M)
    nested_files = []
    for match in re.finditer(r"^[+]\+\+\+ (.+)$", text, re.M):
        name = match.group(1).split("\t", 1)[0].strip()
        if name != "/dev/null" and name not in nested_files:
            nested_files.append(name)
    kind = "unified_diff" if files and hunks else "unrecognized_text"
    return {"content_kind": kind, "changed_files": files, "hunk_count": len(hunks),
            "nested_hunk_count": len(nested_hunks), "nested_changed_files": nested_files,
            "hunk_contexts": [s.strip() for s in hunks if s.strip()]}


def fetch_one(row: dict, cache_dir: Path, timeout: float) -> dict:
    url, encoding = retrieval_url(row["patch"])
    result = {"os": row["os"], "bug_id": row["bug_id"], "original_url": row["patch"],
              "requested_url": url, "transport_encoding": encoding,
              "retrieved_utc": datetime.now(timezone.utc).isoformat(),
              "source_involved_functions": row["involved_functions"],
              "source_modified_files": row.get("modified_files", ""),
              "source_line_changes": row.get("line_changes", ""),
              "status": "unconfirmed", "http_status": None, "final_url": url,
              "content_type": "", "response_bytes": 0, "response_sha256": "",
              "decoded_bytes": 0, "decoded_sha256": "", "error": ""}
    body = b""
    try:
        request = Request(url, headers={"User-Agent": "CS340-Reproduction-Evidence-Audit/1.0"})
        with urlopen(request, timeout=timeout) as response:
            result.update(http_status=response.status, final_url=response.url,
                          content_type=response.headers.get("Content-Type", ""))
            body = response.read(5_000_001)
            if len(body) > 5_000_000:
                raise ValueError("response exceeds 5 MB audit limit")
    except HTTPError as exc:
        result.update(http_status=exc.code, final_url=exc.url,
                      content_type=exc.headers.get("Content-Type", ""))
        body = exc.read(5_000_000)
        result["error"] = str(exc)
    except (URLError, TimeoutError, OSError, ValueError) as exc:
        result["error"] = str(exc)
    result["response_bytes"] = len(body)
    result["response_sha256"] = hashlib.sha256(body).hexdigest() if body else ""
    safe_id = re.sub(r"[^A-Za-z0-9_.-]", "_", row["bug_id"])
    if body:
        (cache_dir / f"{safe_id}.response").write_bytes(body)
    decoded = body
    # An error/HTML response from Gitiles is not necessarily base64.
    if encoding == "base64" and result["http_status"] == 200:
        try:
            decoded = base64.b64decode(b"".join(body.split()), validate=True)
        except ValueError as exc:
            result["error"] = f"Gitiles base64 decode failed: {exc}"
    if decoded:
        (cache_dir / f"{safe_id}.decoded").write_bytes(decoded)
    result["decoded_bytes"] = len(decoded)
    result["decoded_sha256"] = hashlib.sha256(decoded).hexdigest() if decoded else ""
    result.update(inspect_body(decoded, result["content_type"]))
    if result["http_status"] == 200 and not result["error"] and result["content_kind"] == "unified_diff":
        result["status"] = "confirmed_diff"
    result["evidence_summary_zh"] = (
        f"可读 unified diff；外层 {len(result['changed_files'])} 个文件、{result['hunk_count']} 个 hunk；"
        f"嵌套补丁 {result['nested_hunk_count']} 个 hunk。"
        if result["status"] == "confirmed_diff" else
        "尚未取得可确认的补丁正文；HTTP 状态不能单独证明材料可用。"
    )
    result["limitation_zh"] = "hunk 数量不是受影响函数数量；本检查不替代 A/B 独立标签核验。"
    return result


def fetch_cve_records(rows: list[dict], cache_dir: Path, timeout: float) -> list[dict]:
    """Retrieve the CNA records as context, never as replacement for a fork patch."""
    records = []
    for row in rows:
        cve = row["bug_id"]
        if not re.fullmatch(r"CVE-\d{4}-\d{4,}", cve):
            continue
        _, year, number = cve.split("-")
        url = f"https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/{year}/{number[:-3]}xxx/{cve}.json"
        entry = {"bug_id": cve, "url": url, "retrieved_utc": datetime.now(timezone.utc).isoformat(),
                 "status": "unconfirmed", "relation": "CNA context only; does not establish identity with the inaccessible OpenHarmony patch."}
        try:
            with urlopen(Request(url, headers={"User-Agent": "CS340-Reproduction-Evidence-Audit/1.0"}), timeout=timeout) as response:
                body = response.read(5_000_001)
                if len(body) > 5_000_000:
                    raise ValueError("CVE response exceeds 5 MB audit limit")
                entry.update(http_status=response.status, final_url=response.url,
                             content_type=response.headers.get("Content-Type", ""))
            (cache_dir / f"{cve}.cve.json").write_bytes(body)
            entry.update(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
            data = json.loads(body)
            if data.get("cveMetadata", {}).get("cveId") != cve:
                raise ValueError("CVE record identifier does not match requested identifier")
            cna = data["containers"]["cna"]
            descriptions = cna.get("descriptions", [])
            # Keep only the short issue title, not entire third-party descriptions.
            description = next((x["value"] for x in descriptions if x.get("lang") == "en"), "")
            paragraphs = description.split("\n\n")
            title = paragraphs[1] if len(paragraphs) > 1 else paragraphs[0]
            entry.update(status="confirmed_record", cve_metadata=data["cveMetadata"],
                         provider=cna.get("providerMetadata", {}), title=title[:300],
                         rejected_reasons=cna.get("rejectedReasons", []),
                         references=cna.get("references", []))
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, KeyError) as exc:
            entry["error"] = str(exc)
        records.append(entry)
    return records


def audit(input_path: Path, outdir: Path, cache_dir: Path, timeout: float = 30.0) -> dict:
    with input_path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    cache_dir.mkdir(parents=True, exist_ok=True)
    outdir.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda row: fetch_one(row, cache_dir, timeout), rows))
    interpretations_path = outdir / "interpretations.json"
    interpretations = (json.loads(interpretations_path.read_text(encoding="utf-8"))
                       if interpretations_path.exists() else {})
    for result in results:
        interpretation = interpretations.get(result["bug_id"], {})
        matches = interpretation.get("decoded_sha256") == result["decoded_sha256"] and bool(result["decoded_sha256"])
        result["interpretation_hash_matches"] = matches
        result["inspected_content_note_zh"] = interpretation.get("note_zh", "") if matches else ""
    summary = {"audit_type": "automated_fetch_and_diff_structure_inspection",
               "human_reannotation_completed": False,
               "input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
               "sample_count": len(results),
               "confirmed_diff_count": sum(x["status"] == "confirmed_diff" for x in results),
               "unconfirmed_count": sum(x["status"] != "confirmed_diff" for x in results),
               "interpretation": "HTTP 200 alone is insufficient. Nested diff hunks are counted separately. No human review labels are populated.",
               "records": results}
    (outdir / "audit.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (outdir / "cve_sources.json").write_text(json.dumps(fetch_cve_records(rows, cache_dir, timeout), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if results:
        with (outdir / "audit.csv").open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(results[0]))
            writer.writeheader()
            for result in results:
                writer.writerow({key: json.dumps(value, ensure_ascii=False) if isinstance(value, list) else value
                                 for key, value in result.items()})
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "review_materials/evidence_checklist.csv")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results/review_evidence")
    parser.add_argument("--cache-dir", type=Path, default=ROOT / "work/review_evidence")
    parser.add_argument("--timeout", type=float, default=30)
    args = parser.parse_args()
    result = audit(args.input, args.output_dir, args.cache_dir, args.timeout)
    print(json.dumps({k: v for k, v in result.items() if k != "records"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
