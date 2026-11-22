"""Recompute the Week 2 Table II deliverable and descriptive repair-size bins.

This root-level compatibility entry keeps its historical supplementary bins;
the dedicated repair-size sensitivity pipeline handles original Figures 2/3.
"""
import argparse
import hashlib
import json
import shutil
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))

from osdefects.common import OS_ORDER, semantic_digest, write_csv, write_json
from osdefects.data import fetch_source, load_records
from osdefects.runner import environment, repeated_statistics
from osdefects.univariate import analyze_univariate, validate_reference

REPAIR_FIELDS = ('line_changes', 'involved_functions', 'modified_files')
LINE_BINS = ('0', '1-10', '11-50', '51-100', '101-500', '501+')
COUNT_BINS = ('0', '1', '2', '3', '4-9', '10+')


def validate_output_directory(path, root=ROOT):
    """Resolve and preflight an output location without writing or fetching data."""
    root, path = Path(root).resolve(), Path(path).resolve()
    protected = ('src', 'scripts', 'tests', 'reference', 'data', '.git', '.agents', '.codex',
                 'docs', 'papers', 'presentations', 'review_materials', 'weekend_02', 'results/full')
    if path == root or any(path == root / name or (root / name) in path.parents for name in protected):
        raise ValueError('Output directory is a protected project or historical path: ' + str(path))
    # An empty subdirectory inside another analysis is still not our output area.
    for ancestor in (path, *path.parents):
        marker = ancestor / 'stage_summary.json'
        if marker.is_file():
            try:
                previous = json.loads(marker.read_text(encoding='utf-8'))
            except (ValueError, OSError) as error:
                raise ValueError('Existing output marker is unreadable: ' + str(marker)) from error
            if not isinstance(previous, dict) or previous.get('analysis') != 'weekend_02':
                raise ValueError('Output directory belongs to another analysis: ' + str(ancestor))
    if path.exists():
        if not path.is_dir():
            raise ValueError('Output path must be a directory: ' + str(path))
        if any(path.iterdir()) and not (path / 'stage_summary.json').is_file():
            raise ValueError('Nonempty output directory lacks a Week 2 marker; choose a new directory: ' + str(path))
    return path


def size_bin(value, field):
    if field == 'line_changes':
        for limit, label in zip((0, 10, 50, 100, 500), LINE_BINS):
            if value <= limit:
                return label
        return LINE_BINS[-1]
    if value <= 3:
        return str(value)
    return '4-9' if value < 10 else '10+'


def analyze_repairs(records):
    distributions, rows, checks = {}, [], []
    for field in REPAIR_FIELDS:
        bins = LINE_BINS if field == 'line_changes' else COUNT_BINS
        distributions[field] = {}
        for os_name in OS_ORDER:
            values = [record[field] for record in records if record['os'] == os_name]
            n = len(values)
            counts = Counter(size_bin(value, field) for value in values)
            distributions[field][os_name] = {
                'bins': list(bins),
                'counts': [counts[label] for label in bins],
                'percent': [100 * counts[label] / n for label in bins],
            }
            for label in bins:
                rows.append({'metric': field, 'os': os_name, 'bin': label,
                             'count': counts[label], 'n': n, 'percent': 100 * counts[label] / n})
            if field == 'line_changes':
                thresholds = [('changed_lines_le10', sum(value <= 10 for value in values)),
                              ('changed_lines_lt30', sum(value < 30 for value in values))]
            else:
                thresholds = [(field + '_between_1_and_3', sum(1 <= value <= 3 for value in values))]
            for name, count in thresholds:
                checks.append({'os': os_name, 'check': name, 'count': count, 'n': n,
                               'ours_percent': 100 * count / n,
                               'paper_numeric_percent': 'not compared by this descriptive entry',
                               'interpretation': 'Project-specific descriptive thresholds, not exact Figure 2/3 replication. Censored function counts use their recorded lower bounds.'})
    return {'distributions': distributions, 'textual_claim_checks': checks}, rows, checks


def make_weekend_plots(distribution, repairs, outdir):
    # Keep optional rendering dependencies out of the --no-plots execution path.
    from osdefects.plots import grouped_bars, make_plots
    new_dimensions = {name: groups for name, groups in distribution['dimensions'].items() if name != 'os_layer'}
    figures = make_plots({'univariate': {'dimensions': new_dimensions}}, outdir)
    for field, groups in repairs['distributions'].items():
        path = outdir / f'repair_{field}.png'
        grouped_bars('Descriptive repair size: ' + field.replace('_', ' '), groups['Android']['bins'],
                     {name: groups[name]['percent'] for name in OS_ORDER}, path,
                     subtitle='Supplementary bins, not original Figures 2/3; censored function counts use lower bounds')
        figures.append(str(path))
    return figures


def main():
    parser = argparse.ArgumentParser(description='Recompute Week 2 Table II and descriptive repair-size results')
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--runs', type=int, default=3, help='At least three actual recomputations')
    parser.add_argument('--output-dir', type=Path, help='Separate output directory; defaults to results/weekend_02')
    parser.add_argument('--no-plots', action='store_true', help='Skip figures and optional rendering dependencies')
    args = parser.parse_args()
    if args.runs < 3:
        parser.error('--runs must be at least 3')
    stage_dir = validate_output_directory(args.output_dir if args.output_dir is not None else ROOT / 'results/weekend_02')
    source = ROOT / 'data/raw/index.html'
    reference_path = ROOT / 'paper_baselines_weekend_02.json'
    reference = json.loads(reference_path.read_text(encoding='utf-8'))
    validate_reference(reference, list(reference['dimensions']))
    provenance = fetch_source(source, offline=args.offline)
    provenance['source_path'] = source.relative_to(ROOT).as_posix()
    stage_dir.mkdir(parents=True, exist_ok=True)
    write_json(stage_dir / 'stage_summary.json', {'analysis': 'weekend_02', 'status': 'running', 'runs': args.runs})
    digests = set()
    for index in range(1, args.runs + 1):
        started = datetime.now(timezone.utc).isoformat(timespec='seconds')
        timer = time.perf_counter()
        records = load_records(source)
        repairs, repair_rows, repair_checks = analyze_repairs(records)
        run_dir = stage_dir / 'runs' / f'run_{index:02d}'
        run_tables = run_dir / 'tables'
        run_tables.mkdir(parents=True, exist_ok=True)
        distribution = analyze_univariate(records, reference, run_tables)
        write_csv(run_tables / 'repair_distributions.csv', repair_rows)
        write_csv(run_tables / 'repair_claim_checks.csv', repair_checks)
        result = {'univariate': distribution, 'repairs': repairs}
        write_json(run_dir / 'results.json', result)
        digest = semantic_digest(result)
        digests.add(digest)
        write_json(run_dir / 'run_log.json', {
            'stage': 2, 'run': index, 'started_at_utc': started,
            'elapsed_seconds': time.perf_counter() - timer, 'records': len(records),
            'source_sha256_lf': provenance['source_sha256_lf'], 'semantic_result_sha256': digest,
            'table_ii_cells': distribution['cell_count'], 'table_ii_matches': distribution['matched_cells'],
            'status': 'success', 'invocation': sys.argv, 'environment_file': '../../environment.json',
        })
    if len(digests) != 1:
        raise RuntimeError('Week 2 results differed across the actual runs')

    tables = stage_dir / 'tables'
    tables.mkdir(parents=True, exist_ok=True)
    shutil.copytree(stage_dir / 'runs/run_01/tables', tables, dirs_exist_ok=True)
    repeated_statistics(stage_dir, args.runs)
    figures = [] if args.no_plots else make_weekend_plots(distribution, repairs, stage_dir / 'figures')
    env = environment(ROOT, stage=2)
    env.pop('python_executable', None)
    # The shared helper hashes src/, scripts/ and reference/. These two legacy
    # entry files live at the root and must also appear in this run's record.
    for path in (Path(__file__).resolve(), reference_path):
        env['files_sha256'][path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_text(encoding='utf-8').encode('utf-8')).hexdigest()
    write_json(stage_dir / 'environment.json', env)
    write_json(stage_dir / 'source_provenance.json', provenance)
    write_json(stage_dir / 'figure_manifest.json', [Path(path).relative_to(stage_dir).as_posix() for path in figures])
    summary = {'analysis': 'weekend_02', 'status': 'computationally_complete',
               'table_ii_cells': distribution['cell_count'], 'table_ii_matches': distribution['matched_cells'],
               'runs': args.runs, 'active_runs': [f'runs/run_{index:02d}' for index in range(1, args.runs + 1)],
               'figures': len(figures), 'reference_file': reference_path.relative_to(ROOT).as_posix(),
               'source_sha256_lf': provenance['source_sha256_lf'],
               'repeatability': {'identical_semantic_outputs': True, 'semantic_result_sha256': digest,
                                 'meaning': 'Repeated execution stability, not independent annotation validation.'},
               'repair_scope': 'Descriptive supplementary bins and thresholds; no exact Figure 2/3 comparison is performed by this entry.'}
    write_json(stage_dir / 'stage_summary.json', summary)
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
