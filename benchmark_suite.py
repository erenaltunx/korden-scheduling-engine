"""Run multiple fixed-seed experiments; output CSV and structured JSON report."""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
from statistics import mean, median
from korden.generator import generate_factory
from korden.service import compare


def run_suite(count: int, jobs: int, time_limit: float):
    rows = []
    for seed in range(count):
        experiment = compare(generate_factory(seed, jobs), time_limit)
        before, after = experiment['baseline']['metrics'], experiment['optimized']['metrics']
        rows.append({
            'seed': seed, 'orders': jobs, 'operations': jobs * 3,
            'baseline_weighted_tardiness': before['weighted_tardiness'],
            'optimized_weighted_tardiness': after['weighted_tardiness'],
            'improvement_percent': experiment['improvement_percent'],
            'baseline_late_orders': before['late_jobs'],
            'optimized_late_orders': after['late_jobs'],
            'baseline_makespan': before['makespan'],
            'optimized_makespan': after['makespan'],
            'solver_status': experiment['solver']['status'],
            'optimality_proven': experiment['solver']['optimality_proven'],
            'solve_seconds': experiment['solver']['solve_seconds'],
        })
    reductions = [r['improvement_percent'] for r in rows if r['improvement_percent'] is not None]
    return {
        'config': {'seed_range': [0, count-1], 'job_count': jobs, 'time_limit_seconds': time_limit,
                   'instance_origin': 'Deterministic synthetic data', 'baseline': 'EDD'},
        'summary': {
            'instances': len(rows),
            'nonzero_baseline_instances': len(reductions),
            'optimality_proven_count': sum(r['optimality_proven'] for r in rows),
            'mean_improvement_percent_nonzero': round(mean(reductions), 2) if reductions else None,
            'median_improvement_percent_nonzero': round(median(reductions), 2) if reductions else None,
            'mean_solver_seconds': round(mean(r['solve_seconds'] for r in rows), 3),
            'combined_baseline_weighted_tardiness': sum(r['baseline_weighted_tardiness'] for r in rows),
            'combined_optimized_weighted_tardiness': sum(r['optimized_weighted_tardiness'] for r in rows),
        },
        'rows': rows,
    }


def main():
    parser = argparse.ArgumentParser(description='KORDEN reproducible multi-instance benchmark')
    parser.add_argument('--count', type=int, default=20, help='number of integer seeds starting at zero')
    parser.add_argument('--jobs', type=int, default=5)
    parser.add_argument('--time-limit', type=float, default=3)
    parser.add_argument('--out', default='results/suite')
    args = parser.parse_args()
    if not 1 <= args.count <= 200:
        parser.error('count must be between 1 and 200')
    report = run_suite(args.count, args.jobs, args.time_limit)
    dest = Path(args.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.with_suffix('.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    with dest.with_suffix('.csv').open('w', newline='', encoding='utf-8') as f:
        writer=csv.DictWriter(f, fieldnames=list(report['rows'][0]))
        writer.writeheader()
        writer.writerows(report['rows'])
    print(json.dumps(report['summary'], indent=2))
    print('Saved', dest.with_suffix('.csv'), 'and', dest.with_suffix('.json'))


if __name__ == '__main__':
    main()
