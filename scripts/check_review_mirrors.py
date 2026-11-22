"""Read-only public-mirror audit; never applies patches or fills human reviews.

Run: py -3.11 scripts/check_review_mirrors.py
Raw third-party responses stay under ignored work/. Published results are metadata.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "openharmony/kernel_linux_5.10"
API = f"https://api.github.com/repos/{REPOSITORY}"


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def git_blob_sha(body):
    return hashlib.sha1(b"blob " + str(len(body)).encode() + b"\0" + body).hexdigest()


def parse_patch(body):
    text = body.decode("utf-8", "replace")
    header = re.match(r"From ([0-9a-f]{40}) Mon Sep 17 00:00:00 2001", text)
    files = re.findall(r"^diff --git a/(.+) b/(.+)$", text, re.MULTILINE)
    indices = re.findall(r"^index ([0-9a-f]+)\.\.([0-9a-f]+)(?: |$)", text, re.MULTILINE)
    additions = deletions = hunks = 0
    in_hunk = False
    for line in text.splitlines():
        if line.startswith("diff --git "):
            in_hunk = False
        elif line.startswith("@@ "):
            hunks += 1
            in_hunk = True
        elif line == "-- ":
            in_hunk = False
        elif in_hunk and line.startswith("+"):
            additions += 1
        elif in_hunk and line.startswith("-"):
            deletions += 1
    return {
        "content_kind": "git_patch" if header and files and hunks else "not_verified_patch",
        "from_sha": header.group(1) if header else None,
        "files": [new for old, new in files],
        "old_files": [old for old, new in files],
        "indices": [list(item) for item in indices],
        "hunks": hunks,
        "additions": additions,
        "deletions": deletions,
    }


def verify_identity(requested_sha, commit, patch, blobs):
    """Return evidence checks; abbreviated input is never promoted to full original SHA."""
    resolved = commit.get("sha", "")
    parents = [parent.get("sha", "") for parent in commit.get("parents", [])]
    files = commit.get("files", [])
    checks = {
        "valid_requested_sha": bool(re.fullmatch(r"[0-9a-f]{7,40}", requested_sha)),
        "requested_sha_matches": bool(resolved and resolved.startswith(requested_sha)),
        "resolved_full_sha": bool(re.fullmatch(r"[0-9a-f]{40}", resolved)),
        "single_valid_parent": len(parents) == 1 and bool(re.fullmatch(r"[0-9a-f]{40}", parents[0])),
        "patch_sha_matches": patch.get("from_sha") == resolved and bool(resolved),
        "substantive_diff": patch.get("content_kind") == "git_patch",
        "file_list_matches": bool(files) and sorted(f["filename"] for f in files) == sorted(patch["files"]),
        "line_stats_match": (
            sum(f.get("additions", 0) for f in files) == patch.get("additions")
            and sum(f.get("deletions", 0) for f in files) == patch.get("deletions")
        ),
        "file_blobs_verified": len(blobs) == len(files) and bool(files)
        and all(b.get("current_sha_matches_api") and b.get("current_sha_matches_patch")
                and b.get("parent_sha_matches_patch") for b in blobs),
    }
    verified = all(checks.values())
    return {
        "status": "verified_public_patch" if verified else "unconfirmed",
        "identity_level": ("full_original_sha" if len(requested_sha) == 40 else "original_prefix_resolved") if verified else "unconfirmed",
        "checks": checks,
    }


def fetch(url, cache, label):
    entry = {"label": label, "url": url, "retrieved_utc": utc_now()}
    body = b""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "CS340-reproducibility-audit", "Accept": "*/*"})
        with urllib.request.urlopen(req, timeout=30) as response:
            body = response.read()
            entry.update(http_status=response.status, final_url=response.url,
                         content_type=response.headers.get("Content-Type", ""))
    except urllib.error.HTTPError as error:
        body = error.read()
        entry.update(http_status=error.code, final_url=error.url,
                     content_type=error.headers.get("Content-Type", ""), error=str(error))
    except (OSError, ValueError) as error:
        entry.update(http_status=None, final_url=None, content_type=None, error=str(error))
    entry.update(sha256=hashlib.sha256(body).hexdigest(), bytes=len(body))
    cache.mkdir(parents=True, exist_ok=True)
    (cache / f"{label}.body").write_bytes(body)
    (cache / f"{label}.metadata.json").write_text(json.dumps(entry, indent=2), encoding="utf-8")
    return entry, body


def audit_row(row, cache):
    bug = row["bug_id"]
    requested = row["patch"].rsplit("/", 1)[-1].removesuffix(".patch")
    sources = []

    def get(url, label):
        source, body = fetch(url, cache / bug, label)
        sources.append(source)
        return source, body

    result = {"os": row["os"], "bug_id": bug, "original_url": row["patch"],
              "requested_sha": requested, "status": "unconfirmed", "sources": sources}
    original, original_body = get(row["patch"], "original")
    result["original_access"] = ("login_html" if "/login" in (original.get("final_url") or "")
                                 else parse_patch(original_body)["content_kind"])
    api_source, api_body = get(f"{API}/commits/{requested}", "commit_api")
    if api_source["http_status"] != 200:
        result["reason"] = "Public mirror commit API unavailable."
        return result
    try:
        commit = json.loads(api_body)
    except ValueError:
        result["reason"] = "Commit API did not return JSON."
        return result
    resolved = commit.get("sha", "")
    if not re.fullmatch(r"[0-9a-f]{40}", resolved):
        result["reason"] = "No full commit SHA in API response."
        return result
    patch_url = f"https://github.com/{REPOSITORY}/commit/{resolved}.patch"
    patch_source, patch_body = get(patch_url, "patch")
    patch = parse_patch(patch_body)
    parents = [parent["sha"] for parent in commit.get("parents", [])]
    result.update(resolved_sha=resolved, parents=parents, tree_sha=commit.get("commit", {}).get("tree", {}).get("sha"),
                  commit_title=commit.get("commit", {}).get("message", "").split("\n")[0],
                  commit_mentions_bug=bug in commit.get("commit", {}).get("message", ""),
                  api_stats=commit.get("stats"), mirror_url=f"https://github.com/{REPOSITORY}/commit/{resolved}",
                  mirror_patch_url=patch_url, patch=patch,
                  author_data={key: row[key] for key in ("involved_functions", "modified_files", "line_changes")})
    files = commit.get("files", [])
    result["files"] = [{key: f.get(key) for key in ("filename", "sha", "status", "additions", "deletions", "changes")} for f in files]
    blobs = []
    if len(parents) == 1:
        for i, file in enumerate(files):
            name = file["filename"]
            encoded = urllib.parse.quote(name, safe="/")
            current_meta, current = get(f"https://raw.githubusercontent.com/{REPOSITORY}/{resolved}/{encoded}", f"file_{i}_current")
            parent_meta, parent = get(f"https://raw.githubusercontent.com/{REPOSITORY}/{parents[0]}/{encoded}", f"file_{i}_parent")
            current_sha, parent_sha = git_blob_sha(current), git_blob_sha(parent)
            position = patch["files"].index(name) if name in patch["files"] else -1
            indices = patch["indices"][position] if 0 <= position < len(patch["indices"]) else ["", ""]
            blobs.append({"filename": name, "current_git_blob_sha": current_sha, "parent_git_blob_sha": parent_sha,
                          "patch_old_blob_prefix": indices[0], "patch_new_blob_prefix": indices[1],
                          "current_sha_matches_api": current_meta["http_status"] == 200 and current_sha == file["sha"],
                          "current_sha_matches_patch": bool(indices[1]) and current_sha.startswith(indices[1]),
                          "parent_sha_matches_patch": parent_meta["http_status"] == 200 and bool(indices[0]) and parent_sha.startswith(indices[0])})
    result["file_blob_checks"] = blobs
    result.update(verify_identity(requested, commit, patch, blobs))
    if patch_source["http_status"] != 200:
        result["status"] = "unconfirmed"
    result["prefix_limitation"] = ("Original link contains only 12 SHA characters; GitHub resolves this prefix in this repository. The original Gitee response still does not supply its full SHA."
                                   if len(requested) < 40 else None)
    return result


def write_csv(path, rows, fields):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "review_materials/evidence_checklist.csv")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results/review_evidence_followup")
    parser.add_argument("--cache-dir", type=Path, default=ROOT / "work/review_mirrors")
    args = parser.parse_args()
    with args.input.open(encoding="utf-8-sig", newline="") as stream:
        rows = [row for row in csv.DictReader(stream) if row["os"] == "HarmonyOS"]
    if len(rows) != 4:
        raise SystemExit("Expected exactly four fixed HarmonyOS review samples.")
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda row: audit_row(row, args.cache_dir), rows))
    repository_source, repository_body = fetch(API, args.cache_dir, "repository_api")
    repo = json.loads(repository_body) if repository_source["http_status"] == 200 else {}
    output = {"schema_version": 1, "generated_utc": utc_now(), "audit_actor": "AI assistant; not a student independent review",
              "repository": {"full_name": repo.get("full_name"), "html_url": repo.get("html_url"), "owner_login": repo.get("owner", {}).get("login"), "source": repository_source},
              "summary": {"samples": len(results), "verified_public_patches": sum(r["status"] == "verified_public_patch" for r in results),
                          "full_original_sha": sum(r.get("identity_level") == "full_original_sha" for r in results),
                          "original_prefix_resolved": sum(r.get("identity_level") == "original_prefix_resolved" for r in results)},
              "records": results}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "sources.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    flat = []
    for record in results:
        for source in record["sources"]:
            flat.append({"bug_id": record["bug_id"], **source})
    flat.append({"bug_id": "repository", **repository_source})
    write_csv(args.output_dir / "sources.csv", flat,
              ["bug_id", "label", "url", "retrieved_utc", "http_status", "final_url", "content_type", "sha256", "bytes", "error"])
    print(json.dumps(output["summary"]))
    return 0 if all(r["status"] == "verified_public_patch" for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
