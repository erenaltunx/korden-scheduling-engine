"""Optera independent, paired multi-complexity synthetic scheduling benchmark.

Reports raw MILP outcomes separately from deployable 'best feasible' recommendation.
Never treats synthetic gains as observed factory savings or time-limited as optimal.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import random
import statistics
from pathlib import Path

import scipy

from optera.baseline import POLICIES, dispatch
from optera.evaluation import check_schedule, evaluate
from optera.model import validate_scenario
from optera.optimizer import optimize

PROFILES = ('single_cell', 'two_stage', 'flexible_cell', 'congested_cell')
BASE_SEED = 230011


def make_factory(profile: str, seed: int) -> dict:
    """Same structural constraints as the deployed engine, not separate toy rules."""
    if profile not in PROFILES or type(seed) is not int:
        raise ValueError(f'Unknown profile or seed: {profile!r}, {seed!r}')
    rng = random.Random(f'optera-mix-v1:{profile}:{seed}')
    n = rng.randint(9, 11) if profile == 'congested_cell' else rng.randint(5, 7)
    switch = rng.randint(1, 4)
    if profile == 'single_cell':
        machines = [{'id': 'CNC', 'downtime': [], 'changeover_time': switch}]
    elif profile == 'two_stage':
        machines = [
            {'id': 'CUT', 'downtime': []},
            {'id': 'CNC', 'downtime': [], 'changeover_time': switch},
        ]
    else:
        machines = [
            {'id': 'CNC-A', 'downtime': [], 'changeover_time': switch},
            {'id': 'CNC-B', 'downtime': [{'start': 8, 'end': 11}] if (seed % 2 == 0 or profile == 'congested_cell') else [],
             'changeover_time': switch},
            {'id': 'QC', 'downtime': []},
        ]
    jobs = []
    for i in range(n):
        family = 'A' if rng.random() < .5 else 'B'
        duration = rng.randint(2, 6)
        release = rng.randint(0, 5)
        ops = []
        if profile == 'two_stage':
            ops.append({'id': 'cut', 'duration': rng.randint(1, 4), 'machines': ['CUT']})
            ops.append({'id': 'machine', 'duration': duration, 'machines': ['CNC'], 'setup_family': family})
        elif profile in ('flexible_cell', 'congested_cell'):
            ops.append({'id': 'machine', 'duration': duration,
                        'machines': ['CNC-A', 'CNC-B'], 'setup_family': family})
            ops.append({'id': 'inspect', 'duration': rng.randint(1, 3), 'machines': ['QC']})
        else:
            ops.append({'id': 'machine', 'duration': duration, 'machines': ['CNC'], 'setup_family': family})
        work = sum(x['duration'] for x in ops)
        due = release + work + rng.randint(0, 5 if profile == 'congested_cell' else 17)
        jobs.append({'id': f'WO{i+1:02d}', 'release': release, 'due': due,
                     'weight': rng.randint(1, 5), 'operations': ops})
    data = {'schema_version': 1, 'factory_name': f'Optera research {profile} {seed}',
            'machines': machines, 'jobs': jobs}
    validate_scenario(data)
    return data


def _digest(data: dict) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def run_instance(profile: str, seed: int, time_limit: float) -> dict:
    factory = make_factory(profile, seed)
    policies = {}
    for p in POLICIES:
        sched = dispatch(factory, p)
        violations = check_schedule(factory, sched)
        if violations:
            raise AssertionError(f'Baseline {p} infeasible: {violations}')
        policies[p] = evaluate(factory, sched)
    best_policy = min(POLICIES, key=lambda p: (policies[p]['weighted_tardiness'], policies[p]['makespan'], p))
    baseline = policies[best_policy]
    result = optimize(factory, time_limit=time_limit)
    solver = result['solver']
    raw_metric = None
    if result['schedule'] is not None:
        violations = check_schedule(factory, result['schedule'])
        if violations:
            raise AssertionError(f'Solver emitted an invalid plan: {violations}')
        raw_metric = evaluate(factory, result['schedule'])
    # A timed solver may return an inferior candidate: retain the valid baseline.
    # Never credit a baseline fallback as a mathematical optimization gain.
    best_solver = (raw_metric is not None and
                   (raw_metric['weighted_tardiness'], raw_metric['makespan']) <=
                   (baseline['weighted_tardiness'], baseline['makespan']))
    recommended = raw_metric if best_solver else baseline
    return {
        'profile': profile, 'seed': seed, 'input_sha256': _digest(factory),
        'jobs': len(factory['jobs']), 'operations': sum(len(j['operations']) for j in factory['jobs']),
        'resources': len(factory['machines']), 'best_rule': best_policy,
        'baseline_weighted_tardiness': baseline['weighted_tardiness'],
        'baseline_makespan': baseline['makespan'],
        'baseline_late_jobs': baseline['late_jobs'],
        'baseline_setup_time': baseline['setup_time_units'],
        'milp_weighted_tardiness': raw_metric['weighted_tardiness'] if raw_metric else None,
        'milp_makespan': raw_metric['makespan'] if raw_metric else None,
        'milp_setup_time': raw_metric['setup_time_units'] if raw_metric else None,
        'recommended_weighted_tardiness': recommended['weighted_tardiness'],
        'recommended_makespan': recommended['makespan'],
        'recommended_setup_time': recommended['setup_time_units'],
        'selection': 'milp' if best_solver else 'baseline_fallback',
        'solver_status': solver['status'],
        'optimality_proven': bool(solver['optimality_proven']) and best_solver,
        'solve_seconds': round(float(solver['solve_seconds']), 3),
        'relative_mip_gap': solver.get('relative_mip_gap'),
    }


def _summary(rows: list[dict]) -> dict:
    base = sum(x['baseline_weighted_tardiness'] for x in rows)
    rec = sum(x['recommended_weighted_tardiness'] for x in rows)
    solvetimes = sorted(x['solve_seconds'] for x in rows)
    return {
        'instances': len(rows), 'jobs': sum(x['jobs'] for x in rows),
        'operations': sum(x['operations'] for x in rows),
        'baseline_weighted_tardiness': base,
        'recommended_weighted_tardiness': rec,
        'relative_reduction_percent': round(100 * (base-rec)/base, 2) if base else None,
        'improved': sum(x['recommended_weighted_tardiness'] < x['baseline_weighted_tardiness'] for x in rows),
        'equal': sum(x['recommended_weighted_tardiness'] == x['baseline_weighted_tardiness'] for x in rows),
        'fallbacks': sum(x['selection'] == 'baseline_fallback' for x in rows),
        'solver_with_feasible_candidate': sum(x['milp_weighted_tardiness'] is not None for x in rows),
        'proven_optima': sum(x['optimality_proven'] for x in rows),
        'baseline_total_setup': sum(x['baseline_setup_time'] for x in rows),
        'recommended_total_setup': sum(x['recommended_setup_time'] for x in rows),
        'baseline_total_makespan': sum(x['baseline_makespan'] for x in rows),
        'recommended_total_makespan': sum(x['recommended_makespan'] for x in rows),
        'zero_delay_baselines': sum(x['baseline_weighted_tardiness'] == 0 for x in rows),
        'raw_milp_worse_than_baseline': sum(x['milp_weighted_tardiness'] is not None and
                                           x['milp_weighted_tardiness'] > x['baseline_weighted_tardiness']
                                           for x in rows),
        'p50_solver_seconds': round(statistics.median(solvetimes), 3) if rows else None,
        'p90_solver_seconds': solvetimes[min(len(solvetimes)-1, math.ceil(.9*len(solvetimes))-1)] if rows else None,
    }


def run_study(count_per_profile: int = 20, seed_base: int = BASE_SEED,
              time_limit: float = 1.0, stress_count: int = 10) -> dict:
    if not 1 <= count_per_profile <= 50 or not 1 <= stress_count <= 30 or not .5 <= time_limit <= 30:
        raise ValueError('count_per_profile must be 1..50, stress_count 1..30, time_limit 0.5..30 seconds')
    counts = {p: (stress_count if p == 'congested_cell' else count_per_profile) for p in PROFILES}
    rows = [run_instance(profile, seed_base + i, time_limit)
            for profile in PROFILES for i in range(counts[profile])]
    by_profile = {p: _summary([r for r in rows if r['profile'] == p]) for p in PROFILES}
    input_hash = hashlib.sha256(''.join(r['input_sha256'] for r in rows).encode()).hexdigest()
    return {
        'metadata': {
            'title': 'Heterogeneous small-workshop scheduling experiment',
            'synthetic': True, 'version': 'multi-profile-v1',
            'seed_base': seed_base, 'profile_counts': counts,
            'time_limit_seconds_per_instance': time_limit,
            'machine': platform.platform(), 'python': platform.python_version(), 'scipy': scipy.__version__,
            'primary_objective': 'weighted tardiness (not cost, not makespan)',
            'baseline': 'best EDD/FIFO/SPT/WSPT policy per instance, same model constraints',
            'recommendation': 'min(validated solver candidate, validated best classical baseline)',
            'seeded_inputs_sha256': input_hash,
            'assumptions': ['integer time units', 'synthetic work orders', 'uniform family changeovers',
                            'no shift calendars', 'solving limited to small workloads'],
        },
        'summary': _summary(rows), 'profile_summaries': by_profile, 'rows': rows,
    }


def write_study(report: dict, prefix: Path) -> tuple[Path, Path]:
    prefix.parent.mkdir(parents=True, exist_ok=True)
    js = prefix.with_suffix('.json')
    cs = prefix.with_suffix('.csv')
    js.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    with cs.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(report['rows'][0]))
        writer.writeheader()
        writer.writerows(report['rows'])
    return js, cs


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--count-per-profile', type=int, default=20)
    ap.add_argument('--seed-base', type=int, default=BASE_SEED)
    ap.add_argument('--time-limit', type=float, default=1.0)
    ap.add_argument('--stress-count', type=int, default=10)
    ap.add_argument('--out', type=Path, default=Path('artifacts/optera_mixed_workshop'))
    args = ap.parse_args()
    report = run_study(args.count_per_profile, args.seed_base, args.time_limit, args.stress_count)
    js, cs = write_study(report, args.out)
    print(json.dumps({'summary': report['summary'], 'by_profile': report['profile_summaries'],
                      'input_sha256': report['metadata']['seeded_inputs_sha256'],
                      'json': str(js), 'csv': str(cs)}, indent=2))


if __name__ == '__main__':
    main()
