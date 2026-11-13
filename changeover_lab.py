"""Reproducible single-cell setup/changeover audit against four heuristics.

These workloads are fully synthetic. The solver optimizes weighted tardiness;
changeover count is descriptive, not a promised secondary minimization.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path
import random

from optera.baseline import POLICIES, dispatch
from optera.evaluation import check_schedule, evaluate
from optera.optimizer import optimize


def generate(seed: int) -> dict:
    r = random.Random(seed)
    n_jobs = r.randint(4, 6)
    n_families = r.randint(2, 3)
    changeover = r.randint(2, 5)
    jobs = []
    for n in range(n_jobs):
        duration = r.randint(1, 5)
        jobs.append({
            'id': f'J{n+1}', 'release': 0, 'due': r.randint(4, 18),
            'weight': r.randint(1, 5),
            'operations': [{'id': 'process', 'duration': duration, 'machines': ['CELL'],
                            'setup_family': f'F{r.randint(1, n_families)}'}]
        })
    return {'schema_version': 1, 'factory_name': f'Synthetic HMLV cell {seed}',
            'machines': [{'id': 'CELL', 'downtime': [], 'changeover_time': changeover}],
            'jobs': jobs}


def run_lab(count: int = 20, start_seed: int = 20261113, time_limit: float = 2.0) -> dict:
    rows = []
    for seed in range(start_seed, start_seed + count):
        data = generate(seed)
        baselines = {p: evaluate(data, dispatch(data, p)) for p in POLICIES}
        best_policy = min(POLICIES, key=lambda p: (baselines[p]['weighted_tardiness'],
                                                  baselines[p]['makespan'], p))
        baseline = baselines[best_policy]
        result = optimize(data, time_limit)
        if result['schedule'] is None:
            raise RuntimeError(f'No feasible solution for seed {seed}')
        errors = check_schedule(data, result['schedule'])
        if errors:
            raise RuntimeError(f'Invalid optimization on {seed}: {errors}')
        optimized = evaluate(data, result['schedule'])
        if (optimized['weighted_tardiness'], optimized['makespan']) > (baseline['weighted_tardiness'], baseline['makespan']):
            optimized = baseline  # honest incumbent fallback; do not claim a failed solver plan
            selected = 'baseline_retained'
        else:
            selected = result['solver']['status']
        rows.append({
            'seed': seed, 'jobs': len(data['jobs']), 'changeover_time': data['machines'][0]['changeover_time'],
            'best_heuristic': best_policy,
            'baseline_weighted_tardiness': baseline['weighted_tardiness'],
            'optimized_weighted_tardiness': optimized['weighted_tardiness'],
            'baseline_changeovers': baseline['changeover_count'],
            'optimized_changeovers': optimized['changeover_count'],
            'baseline_setup_time_units': baseline['setup_time_units'],
            'optimized_setup_time_units': optimized['setup_time_units'],
            'solver_status': selected, 'optimality_proven': bool(result['solver']['optimality_proven']),
            'solve_seconds': result['solver']['solve_seconds']
        })
    base = sum(a['baseline_weighted_tardiness'] for a in rows)
    opt = sum(a['optimized_weighted_tardiness'] for a in rows)
    summary = {
        'count': len(rows), 'jobs': sum(a['jobs'] for a in rows),
        'baseline_total': base, 'optimized_total': opt,
        'reduction_percent': round(100 * (base-opt)/base, 2) if base else None,
        'strict_improvements': sum(a['optimized_weighted_tardiness'] < a['baseline_weighted_tardiness'] for a in rows),
        'ties': sum(a['optimized_weighted_tardiness'] == a['baseline_weighted_tardiness'] for a in rows),
        'proven_optima': sum(a['optimality_proven'] for a in rows),
        'baseline_total_setup': sum(a['baseline_setup_time_units'] for a in rows),
        'optimized_total_setup': sum(a['optimized_setup_time_units'] for a in rows),
    }
    # Input hash excludes solver wall-clock time and equivalent-solution ties.
    encoded = json.dumps([generate(seed) for seed in range(start_seed, start_seed + count)],
                         sort_keys=True, separators=(',', ':'))
    return {'metadata': {'suite': 'hmlv_changeover_v1', 'synthetic': True, 'start_seed': start_seed,
                         'time_limit_seconds': time_limit, 'algorithm': 'SciPy MILP / HiGHS',
                         'baseline_selection': 'best weighted tardiness among EDD/FIFO/SPT/WSPT',
                         'input_checksum_sha256': hashlib.sha256(encoded.encode()).hexdigest()},
            'summary': summary, 'rows': rows}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--count', type=int, default=20)
    parser.add_argument('--start-seed', type=int, default=20261113)
    parser.add_argument('--time-limit', type=float, default=2.0)
    parser.add_argument('--out', type=Path, default=Path('artifacts/changeovers'))
    args = parser.parse_args()
    if not 1 <= args.count <= 100 or not 0.5 <= args.time_limit <= 60:
        parser.error('count must be 1..100; time-limit 0.5..60 seconds')
    result = run_lab(args.count, args.start_seed, args.time_limit)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.with_suffix('.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    with args.out.with_suffix('.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, result['rows'][0].keys())
        writer.writeheader()
        writer.writerows(result['rows'])
    print(json.dumps(result['summary'], indent=2))


if __name__ == '__main__':
    main()
