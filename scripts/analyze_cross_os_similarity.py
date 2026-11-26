import argparse
import csv
import json
import shutil
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from cross_os_rank_correlation import DIMENSIONS, analyze_similarity
from osdefects.common import OS_ORDER, semantic_digest, sha256, write_json
from osdefects.data import fetch_source, load_records
from osdefects.plots import make_plots
from osdefects.runner import environment, repeated_statistics
from sample_size_sensitivity import run_extension

REPEATS = 3
SIZES = (50, 100, 250, 500)
SEEDS = tuple(range(30))
SOURCE = ROOT / 'data/raw/index.html'
BASELINE = ROOT / 'reference/cross_os_similarity.json'
RESULTS = ROOT / 'results/cross_os_similarity'


def analyze_run(work_dir, reference, provenance, index):
    started = datetime.now(timezone.utc).isoformat(timespec='seconds')
    timer = time.perf_counter()
    records = load_records(SOURCE)
    expected_n = reference['dataset']['per_os_n']
    counts = Counter(record['os'] for record in records)
    if counts != dict.fromkeys(OS_ORDER, expected_n):
        raise ValueError(f'Expected {expected_n} records per OS; found {dict(counts)}')

    run_path = work_dir / 'runs' / f'run_{index:02d}'
    tables = run_path / 'tables'
    similarity = analyze_similarity(records, reference, tables)
    extension = run_extension(records, reference, tables, sizes=SIZES, seeds=SEEDS)
    result_file_hashes = {p.name: sha256(p) for p in sorted(tables.iterdir())}
    digest = semantic_digest(result_file_hashes)
    write_json(run_path / 'run_log.json', {
        'stage': 4, 'run': index, 'started_at_utc': started,
        'elapsed_seconds': time.perf_counter() - timer,
        'records_per_os': dict(counts), 'source_sha256_lf': provenance['source_sha256_lf'],
        'matched_pairs_all_categories': similarity['matched_pairs'],
        'matched_pairs_joint_zero_excluded': similarity['controlled_zero_category_check']['matched_pairs'],
        'semantic_result_sha256': digest, 'result_tables_sha256': result_file_hashes,
        'environment_file': '../../environment.json', 'status': 'success',
    })
    return similarity, extension, digest


def summarize(work_dir, similarity, extension, digest):
    matches = similarity['policy_matching']
    control_rows = similarity['controlled_zero_category_check']['checks']
    changed_rows = [row for row in control_rows if row['excluded_categories']]
    outcome_counts = {str(size): Counter() for size in SIZES}
    with (work_dir / 'tables/extension_trials.csv').open(newline='', encoding='utf-8') as stream:
        for row in csv.DictReader(stream):
            if row['os'] == 'HarmonyOS' and row['dimension'] == 'affected_function':
                outcome_counts[row['sample_size']][row['dominant_category_outcome']] += 1
    return {
        'stage': 4, 'research_question': 'RQ3: Cross-OS distribution similarity',
        'records_per_os': 500, 'dimensions': list(DIMENSIONS),
        'figures_4a_to_4c': matches,
        'change_when_joint_zeros_are_excluded': changed_rows,
        'figure_4d': {
            'verdict': similarity['dimensions']['overall']['verdict'],
            'reason': similarity['dimensions']['overall']['caution'],
            'exploratory_candidate_only': similarity['dimensions']['overall']['candidate_definition'],
        },
        'sample_size_extension': {
            'sizes_per_os': extension['sizes'], 'seeds': extension['seeds'],
            'sampling': extension['sampling'], 'limitation': extension['limitation'],
            'trial_rows': len(OS_ORDER) * len(DIMENSIONS) * len(SIZES) * len(SEEDS),
            'harmonyos_affected_function_top_category': {
                size: dict(outcomes) for size, outcomes in outcome_counts.items()
            },
        },
        'runs': REPEATS, 'identical_result_hashes': True, 'semantic_result_sha256': digest,
        'figures': sorted(p.relative_to(work_dir).as_posix() for p in (work_dir / 'figures').glob('*.png')),
        'scope': 'Statistics recomputed from the released labels at the pinned source commit.',
    }


def main():
    parser = argparse.ArgumentParser(description='Recompute cross-OS similarity and test sample-size sensitivity')
    parser.add_argument('--offline', action='store_true', help='Require the verified cached source dataset')
    args = parser.parse_args()
    reference = json.loads(BASELINE.read_text(encoding='utf-8'))
    provenance = fetch_source(SOURCE, offline=args.offline)
    provenance['source_path'] = SOURCE.relative_to(ROOT).as_posix()
    RESULTS.parent.mkdir(parents=True, exist_ok=True)

    with TemporaryDirectory(prefix='.cross-os-', dir=RESULTS.parent) as temporary:
        work_dir = Path(temporary)
        digests = set()
        for index in range(1, REPEATS + 1):
            similarity, extension, digest = analyze_run(work_dir, reference, provenance, index)
            digests.add(digest)
        if len(digests) != 1:
            raise RuntimeError('Repeat runs produced different numerical tables')

        first_tables = work_dir / 'runs/run_01/tables'
        shutil.copytree(first_tables, work_dir / 'tables')
        statistics = repeated_statistics(work_dir, REPEATS)
        if len(statistics) != 12 or any(row['sd'] != 0 for row in statistics):
            raise RuntimeError('Repeated correlation values are incomplete or inconsistent')
        for index in range(1, REPEATS + 1):
            for file in (work_dir / 'runs' / f'run_{index:02d}' / 'tables').iterdir():
                if file.name != 'similarity_comparison.csv':
                    file.unlink()
        make_plots({'similarity': similarity, 'extension': extension}, work_dir / 'figures')

        env = environment(ROOT, stage=4)
        env.pop('python_executable', None)
        write_json(work_dir / 'environment.json', env)
        write_json(work_dir / 'source_provenance.json', provenance)
        summary = summarize(work_dir, similarity, extension, digest)
        write_json(work_dir / 'summary.json', summary)
        for file in sorted(work_dir.rglob('*')):
            if file.is_file() and file.name != 'summary.json':
                target = RESULTS / file.relative_to(work_dir)
                target.parent.mkdir(parents=True, exist_ok=True)
                file.replace(target)
        (work_dir / 'summary.json').replace(RESULTS / 'summary.json')

    print(json.dumps({
        'all_categories': similarity['matched_pairs'],
        'joint_zero_excluded': similarity['controlled_zero_category_check']['matched_pairs'],
        'comparable_pairs': similarity['comparable_pairs'],
        'figure_4d': summary['figure_4d']['verdict'],
        'sample_trials': summary['sample_size_extension']['trial_rows'],
        'runs': REPEATS,
    }))


if __name__ == '__main__':
    main()
