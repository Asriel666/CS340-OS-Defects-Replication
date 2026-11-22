"""Export verifiable commit-message attribution without estimating human effort."""
import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def git(*args):
    return subprocess.check_output(
        ['git', '-c', 'i18n.logOutputEncoding=UTF-8', *args], cwd=ROOT
    ).decode('utf-8')


def parse_log(raw, student_id):
    """Retain empty bodies and exact Unicode messages; select an exact ID token."""
    selected = []
    pattern = re.compile(r'(?<![0-9])' + re.escape(student_id) + r'(?![0-9])')
    for entry in raw.split('\x1e'):
        if not entry.strip('\r\n'):
            continue
        fields = entry.strip('\r\n').split('\x1f', 5)
        if len(fields) != 6:
            raise ValueError('Malformed git log record')
        sha, author_time, commit_time, author, title, body = fields
        if pattern.search(title + '\n' + body):
            selected.append(dict(commit=sha, author_time=author_time,
                                 committer_time=commit_time, git_author_name=author,
                                 subject=title, body=body.rstrip('\r\n')))
    return selected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--student-id', default='1230037310')
    parser.add_argument('--ref', default='HEAD', help='Reachable Git revision to audit')
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args()
    if not args.student_id.isascii() or not args.student_id.isdecimal():
        parser.error('--student-id must contain ASCII digits only')
    revision = git('rev-parse', '--verify', '--end-of-options', args.ref + '^{commit}').strip()
    raw = git('log', '--reverse', '--format=%H%x1f%aI%x1f%cI%x1f%an%x1f%s%x1f%b%x1e', revision)
    commits = parse_log(raw, args.student_id)
    for commit in commits:
        paths = git('diff-tree', '--root', '--no-commit-id', '--name-only', '-r', '-z', commit['commit'])
        commit['changed_files'] = [path for path in paths.split('\0') if path]
        commit['changed_file_count'] = len(commit['changed_files'])
        commit['url'] = 'https://github.com/Asriel666/CS340-OS-Defects-Replication/commit/' + commit['commit']
        commit['selection_evidence'] = 'Student ID occurs in the commit subject or body.'
    report = dict(student_id=args.student_id, inspected_ref=revision,
                  generated_at_utc=datetime.now(timezone.utc).isoformat(),
                  commit_count=len(commits), commits=commits,
                  interpretation=[
                      'This is Git message attribution, not proof of unaided manual authorship, hours, or contribution percentage.',
                      'Author and committer timestamps are not push timestamps; weekly submission timing requires separate evidence.',
                      'Other members\' commits are not attributed to this student; no history is rewritten.',
                      'File counts include generated results and documentation and must not be treated as labor measures.',
                      'Commits added after inspected_ref are outside this fixed historical snapshot.'
                  ])
    out = args.output_dir or ROOT / 'results/contributions' / args.student_id
    out.mkdir(parents=True, exist_ok=True)
    (out/'commit_history.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n',
                                         encoding='utf-8', newline='\n')
    columns = ['commit', 'author_time', 'committer_time', 'git_author_name', 'subject',
               'body', 'changed_file_count', 'url', 'selection_evidence']
    with (out/'commit_history.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction='ignore', lineterminator='\n')
        writer.writeheader()
        writer.writerows(commits)
    print(json.dumps(dict(student_id=args.student_id, inspected_ref=revision,
                          commit_count=len(commits), output_dir=str(out))))


if __name__ == '__main__':
    main()
