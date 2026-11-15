import argparse
import json
import shutil
import sys
import tempfile
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from osdefects.common import OS_ORDER, semantic_digest, write_csv, write_json
from osdefects.data import fetch_source, load_records
from osdefects.plots import make_plots
from osdefects.runner import environment, repeated_statistics
from osdefects.univariate import analyze_univariate

REPAIR_FIELDS = ('line_changes', 'involved_functions', 'modified_files')
LINE_BINS = ('0', '1-10', '11-50', '51-100', '101-500', '501+')
COUNT_BINS = ('0', '1', '2', '3', '4-9', '10+')


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
                               'paper_numeric_percent': 'not published in accessible text',
                               'interpretation': 'Descriptive support only; original plot bin heights not independently verified.'})
    return {'distributions': distributions, 'textual_claim_checks': checks}, rows, checks


def main():
    parser = argparse.ArgumentParser(description='Reproduce Week 2 Table II and repair-size results')
    parser.add_argument('--offline', action='store_true')
    args = parser.parse_args()
    source = ROOT / 'data/raw/index.html'
    reference = json.loads((ROOT / 'reference/paper_baselines_weekend_02.json').read_text(encoding='utf-8'))
    provenance = fetch_source(source, offline=args.offline)
    provenance['source_path'] = source.relative_to(ROOT).as_posix()
    stage_dir = ROOT / 'results/weekend_02'
    digests = set()
    for index in range(1, 4):
        started = datetime.now(timezone.utc).isoformat(timespec='seconds')
        timer = time.perf_counter()
        records = load_records(source)
        repairs, repair_rows, repair_checks = analyze_repairs(records)
        run_dir = stage_dir / 'runs' / f'run_{index:02d}'
        run_tables = run_dir / 'tables'
        run_tables.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='osdefects-week2-') as temporary:
            scratch = Path(temporary)
            distribution = analyze_univariate(records, reference, scratch)
            shutil.copyfile(scratch / 'table_ii.csv', run_tables / 'table_ii.csv')
        digest = semantic_digest({'univariate': distribution, 'repairs': repairs})
        digests.add(digest)
        write_json(run_dir / 'run_log.json', {
            'stage': 2, 'run': index, 'started_at_utc': started,
            'elapsed_seconds': time.perf_counter() - timer, 'records': len(records),
            'source_sha256_lf': provenance['source_sha256_lf'], 'semantic_result_sha256': digest,
            'table_ii_cells': distribution['cell_count'], 'table_ii_matches': distribution['matched_cells'],
            'status': 'success', 'invocation': sys.argv, 'environment_file': '../../environment.json',
        })
    if len(digests) != 1:
        raise RuntimeError('Week 2 results differed across the three runs')

    tables = stage_dir / 'tables'
    tables.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(stage_dir / 'runs/run_01/tables/table_ii.csv', tables / 'table_ii.csv')
    write_csv(tables / 'repair_distributions.csv', repair_rows)
    write_csv(tables / 'repair_claim_checks.csv', repair_checks)
    repeated_statistics(stage_dir, 3)
    new_dimensions = {name: groups for name, groups in distribution['dimensions'].items() if name != 'os_layer'}
    figures = make_plots({'univariate': {'dimensions': new_dimensions}, 'repairs': repairs}, stage_dir / 'figures')
    env = environment(ROOT, stage=2)
    env.pop('python_executable', None)
    write_json(stage_dir / 'environment.json', env)
    write_json(stage_dir / 'source_provenance.json', provenance)
    print(json.dumps({'table_ii_cells': distribution['cell_count'],
                      'table_ii_matches': distribution['matched_cells'], 'runs': 3, 'figures': len(figures)}))


if __name__ == '__main__':
    main()
