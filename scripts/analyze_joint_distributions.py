import argparse
import json
import math
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from osdefects.common import OS_ORDER, semantic_digest, write_csv, write_json
from osdefects.data import fetch_source, load_records
from osdefects.plots import heatmap
from osdefects.runner import environment, repeated_statistics

TABLE_NAMES = {'table_iii': 'Table III', 'table_iv': 'Table IV', 'table_v': 'Table V'}
TABLE_GROUPS = {
    'table_iii': ('layer_function', 'OS layer and affected function'),
    'table_iv': ('layer_trigger', 'OS layer and trigger scenario'),
    'table_v': ('function_trigger', 'Affected function and trigger scenario'),
}


def analyze_joint(records, reference):
    comparisons, lineage, tables, matrices = [], [], {}, {}
    expected_n = reference['dataset']['per_os_n']
    for table_name, spec in reference['rq2'].items():
        row_dimension = spec['row_dimension']
        column_dimension = spec['column_dimension']
        row_labels = spec['row_categories']
        column_labels = spec['column_categories']
        matrices[table_name] = {}
        table_rows = []
        for os_name in OS_ORDER:
            group = [record for record in records if record['os'] == os_name]
            if len(group) != expected_n:
                raise ValueError(f'Expected {expected_n} records for {os_name}')
            counts = Counter((record[row_dimension], record[column_dimension]) for record in group)
            if any(row not in row_labels or column not in column_labels for row, column in counts):
                raise ValueError(f'Unknown category in {table_name}, {os_name}')
            matrix = [[counts[row, column] for column in column_labels] for row in row_labels]
            if sum(map(sum, matrix)) != expected_n:
                raise ValueError(f'Incomplete joint table for {table_name}, {os_name}')
            row_counts = Counter(record[row_dimension] for record in group)
            column_counts = Counter(record[column_dimension] for record in group)
            for dimension, marginal_counts in ((row_dimension, row_counts), (column_dimension, column_counts)):
                baseline = reference['dimensions'][dimension]
                for label, percentage in zip(baseline['categories'], baseline['table_ii_percent'][os_name]):
                    if not math.isclose(100 * marginal_counts[label] / expected_n, percentage, abs_tol=1e-9):
                        raise ValueError(f'Marginal mismatch for {os_name}, {dimension}, {label}')
            percentages = [[100 * count / expected_n for count in row] for row in matrix]
            for i, row_label in enumerate(row_labels):
                for j, column_label in enumerate(column_labels):
                    paper = spec['percent'][os_name][i][j]
                    ours = percentages[i][j]
                    gap = ours - paper
                    table_rows.append({
                        'table': table_name, 'os': os_name, 'n': expected_n,
                        'row_category': row_label, 'column_category': column_label,
                        'count': matrix[i][j], 'paper_percent': paper, 'ours_percent': ours,
                        'signed_gap_pp': gap, 'absolute_gap_pp': abs(gap),
                        'relative_gap_percent': None if paper == 0 else 100 * abs(gap) / abs(paper),
                        'matches_published_precision': abs(gap) <= 0.005 + 1e-12,
                    })
            matrices[table_name][os_name] = {
                'row_labels': row_labels, 'column_labels': column_labels, 'percent': percentages,
            }
        for record in records:
            lineage.append({
                'table': table_name, 'os': record['os'], 'bug_id': record['bug_id'],
                'row_category': record[row_dimension], 'column_category': record[column_dimension],
            })
        matched = sum(row['matches_published_precision'] for row in table_rows)
        tables[table_name] = {
            'row_dimension': row_dimension, 'column_dimension': column_dimension,
            'compared_cells': len(table_rows), 'matched_cells': matched,
            'max_absolute_gap_pp': max(row['absolute_gap_pp'] for row in table_rows),
            'marginals_match_table_ii': True,
            'verdict': 'supported' if matched == len(table_rows) else 'partially supported',
        }
        comparisons.extend(table_rows)
    return comparisons, lineage, tables, matrices


def main():
    parser = argparse.ArgumentParser(description='Reproduce RQ2 joint distributions in Tables III-V')
    parser.add_argument('--offline', action='store_true')
    args = parser.parse_args()
    source = ROOT / 'data/raw/index.html'
    reference = json.loads((ROOT / 'reference/joint_distributions.json').read_text(encoding='utf-8'))
    provenance = fetch_source(source, offline=args.offline)
    provenance['source_path'] = source.relative_to(ROOT).as_posix()
    stage_dir = ROOT / 'results/joint_distributions'
    digests = set()
    for index in range(1, 4):
        started = datetime.now(timezone.utc).isoformat(timespec='seconds')
        timer = time.perf_counter()
        records = load_records(source)
        comparisons, lineage, tables, matrices = analyze_joint(records, reference)
        digest = semantic_digest({'comparisons': comparisons, 'lineage': lineage})
        digests.add(digest)
        run_dir = stage_dir / 'runs' / f'run_{index:02d}'
        write_csv(run_dir / 'tables/joint_comparison.csv', comparisons)
        write_json(run_dir / 'run_log.json', {
            'analysis': 'joint_distributions', 'run': index, 'started_at_utc': started,
            'elapsed_seconds': time.perf_counter() - timer, 'records': len(records),
            'source_sha256_lf': provenance['source_sha256_lf'], 'semantic_result_sha256': digest,
            'compared_cells': len(comparisons),
            'matched_cells': sum(row['matches_published_precision'] for row in comparisons),
            'status': 'success', 'invocation': sys.argv, 'environment_file': '../../environment.json',
        })
    if len(digests) != 1:
        raise RuntimeError('Joint-distribution results differed across the three runs')

    for table_name in tables:
        rows = [row for row in comparisons if row['table'] == table_name]
        group_name, title = TABLE_GROUPS[table_name]
        write_csv(stage_dir / group_name / 'comparison.csv', rows)
        tables[table_name]['title'] = title
        tables[table_name]['comparison_file'] = f'{group_name}/comparison.csv'
    write_csv(stage_dir / 'traceability/defect_lineage.csv', lineage)
    statistics_rows = repeated_statistics(stage_dir, 3)
    statistics_dir = stage_dir / 'statistics'
    statistics_dir.mkdir(parents=True, exist_ok=True)
    temporary_tables = stage_dir / 'tables'
    (temporary_tables / 'repeated_run_statistics.csv').replace(statistics_dir / 'repeated_run_statistics.csv')
    if not any(temporary_tables.iterdir()):
        temporary_tables.rmdir()
    figure_paths = []
    for table_name, systems in matrices.items():
        for os_name, matrix in systems.items():
            group_name, title = TABLE_GROUPS[table_name]
            path = stage_dir / group_name / f'{os_name}.png'
            heatmap(
                f'{title} / {os_name}',
                matrix['row_labels'], matrix['column_labels'], matrix['percent'], path,
                f'{TABLE_NAMES[table_name]} / Joint percentages of the 500 released defect records for this OS',
            )
            figure_paths.append(path.relative_to(stage_dir).as_posix())
    env = environment(ROOT, stage=3)
    env.pop('python_executable', None)
    write_json(stage_dir / 'environment.json', env)
    write_json(stage_dir / 'source_provenance.json', provenance)
    summary = {
        'analysis': 'Joint defect distributions', 'metric': 'joint defect percentage', 'denominator_per_os': 500,
        'compared_cells': len(comparisons),
        'matched_cells': sum(row['matches_published_precision'] for row in comparisons),
        'max_absolute_gap_pp': max(row['absolute_gap_pp'] for row in comparisons),
        'runs': 3, 'identical_result_hashes': len(digests) == 1,
        'all_repeated_sd_zero': all(row['sd'] == 0 for row in statistics_rows),
        'lineage_rows': len(lineage), 'tables': tables, 'figures': figure_paths,
        'scope': 'Joint-distribution statistics computed from author-released labels.',
    }
    write_json(stage_dir / 'summary.json', summary)
    print(json.dumps({
        'compared_cells': summary['compared_cells'], 'matched_cells': summary['matched_cells'],
        'runs': 3, 'figures': len(figure_paths), 'lineage_rows': len(lineage),
    }))


if __name__ == '__main__':
    main()
