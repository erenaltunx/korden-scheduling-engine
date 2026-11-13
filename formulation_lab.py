"""Paired engineering experiment: original versus tightened HiGHS MILP formulation.

Same deterministic manufacturing scenario, solver, objective and time budget.
Reported gains may be sensitive to hardware, thread scheduling, and HiGHS version.
The operational recommendation always keeps the better independently feasible
schedule of the optimizer candidate and strongest classical dispatching rule.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import statistics
from pathlib import Path
from time import perf_counter

import scipy

from optera.baseline import POLICIES, dispatch
from optera.evaluation import check_schedule, evaluate
from optera.optimizer import optimize
from research_lab import BASE_SEED, make_factory

VARIANTS = ('legacy', 'tight')


def run_pair(seed: int, time_limit: float = 0.7, profile: str = 'congested_cell') -> list[dict]:
    scenario = make_factory(profile, seed)
    digest = hashlib.sha256(json.dumps(scenario, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    baselines = []
    for policy in POLICIES:
        scheduled = dispatch(scenario, policy)
        if check_schedule(scenario, scheduled):
            raise AssertionError(f'Infeasible baseline {policy}')
        metrics = evaluate(scenario, scheduled)
        baselines.append((metrics['weighted_tardiness'], metrics['makespan'], policy))
    baseline_score, baseline_makespan, baseline_policy = min(baselines)
    outputs = []
    for variant in VARIANTS:
        wall_start = perf_counter()
        result = optimize(scenario, time_limit=time_limit, formulation=variant)
        wall = perf_counter() - wall_start
        details = result['solver']
        raw = None
        raw_makespan = None
        if result['schedule'] is not None:
            invalid = check_schedule(scenario, result['schedule'])
            if invalid:
                raise AssertionError(f'{variant} returned infeasible schedule: {invalid}')
            calculated = evaluate(scenario, result['schedule'])
            raw = calculated['weighted_tardiness']
            raw_makespan = calculated['makespan']
        use_milp = raw is not None and (raw, raw_makespan) <= (baseline_score, baseline_makespan)
        recommended = raw if use_milp else baseline_score
        outputs.append({
            'seed': seed, 'profile': profile, 'input_sha256': digest,
            'variant': variant, 'time_budget_seconds': time_limit,
            'orders': len(scenario['jobs']), 'operations': sum(len(j['operations']) for j in scenario['jobs']),
            'baseline_policy': baseline_policy, 'baseline_weighted_tardiness': baseline_score,
            'milp_weighted_tardiness': raw, 'recommended_weighted_tardiness': recommended,
            'selection': 'milp' if use_milp else 'baseline_fallback',
            'optimality_proven': bool(details['optimality_proven']),
            'reported_relative_mip_gap': details.get('relative_mip_gap'),
            'model_variables': details['model_variables'], 'model_constraints': details['model_constraints'],
            'solver_seconds': details['solve_seconds'], 'end_to_end_wall_seconds': round(wall, 3),
        })
    return outputs


def _summary(rows: list[dict]) -> dict:
    baseline = sum(r['baseline_weighted_tardiness'] for r in rows)
    rec = sum(r['recommended_weighted_tardiness'] for r in rows)
    milp = [r for r in rows if r['milp_weighted_tardiness'] is not None]
    seconds = [r['solver_seconds'] for r in rows]
    gaps = [r['reported_relative_mip_gap'] for r in rows if r['reported_relative_mip_gap'] is not None]
    return {
        'instances': len(rows), 'baseline_total': baseline, 'recommended_total': rec,
        'reduction_percent': round(100 * (baseline-rec) / baseline, 2) if baseline else None,
        'feasible_milp_candidates': len(milp),
        'proven_optima': sum(r['optimality_proven'] for r in rows),
        'fallbacks': sum(r['selection'] == 'baseline_fallback' for r in rows),
        'p50_solver_seconds': round(statistics.median(seconds), 3),
        'p90_solver_seconds': sorted(seconds)[math.ceil(.9 * len(seconds))-1],
        'max_reported_mip_gap': max(gaps) if gaps else None,
    }


def run_study(*, count: int = 10, seed_base: int = BASE_SEED,
              time_limit: float = 0.7, profile: str = 'congested_cell') -> dict:
    if type(count) is not int or not 1 <= count <= 20:
        raise ValueError('count must be 1..20')
    if type(seed_base) is not int or not 0 <= seed_base <= 1_000_000_000:
        raise ValueError('seed_base invalid')
    if not math.isfinite(time_limit) or not .5 <= time_limit <= 30:
        raise ValueError('time_limit must be .5..30 seconds')
    if profile not in {'single_cell','two_stage','flexible_cell','congested_cell'}:
        raise ValueError('unknown workload family')
    rows = [record for seed in range(seed_base, seed_base + count)
            for record in run_pair(seed, time_limit, profile)]
    grouped = {v: [row for row in rows if row['variant'] == v] for v in VARIANTS}
    paired = []
    for i in range(count):
        old, new = rows[2*i], rows[2*i+1]
        if old['input_sha256'] != new['input_sha256'] or old['baseline_weighted_tardiness'] != new['baseline_weighted_tardiness']:
            raise AssertionError('Unpaired comparison')
        paired.append({'seed': seed_base+i,
                       'legacy_recommendation': old['recommended_weighted_tardiness'],
                       'tight_recommendation': new['recommended_weighted_tardiness'],
                       'tight_better': new['recommended_weighted_tardiness'] < old['recommended_weighted_tardiness'],
                       'tight_worse': new['recommended_weighted_tardiness'] > old['recommended_weighted_tardiness']})
    return {
        'metadata': {'study': 'Optera MILP formulation ablation', 'schema': 1,
                     'synthetic': True, 'profile': profile, 'seed_base': seed_base,
                     'count': count, 'time_limit_seconds': time_limit,
                     'scipy': scipy.__version__, 'platform': platform.platform(),
                     'objective': 'weighted tardiness, makespan secondary',
                     'comparison': 'same input, same solver, one model formulation factor',
                     'limitations': 'No warm-start, hardware variability, no live production data'},
        'summary': {v: _summary(grouped[v]) for v in VARIANTS},
        'paired': paired, 'rows': rows,
    }


def save_study(study: dict, output: Path) -> tuple[Path, Path]:
    output.parent.mkdir(parents=True, exist_ok=True)
    jpath = output.with_suffix('.json')
    cpath = output.with_suffix('.csv')
    jpath.write_text(json.dumps(study, indent=2, sort_keys=True, ensure_ascii=False)+'\n', encoding='utf8')
    with cpath.open('w', newline='', encoding='utf8') as f:
        writer = csv.DictWriter(f, fieldnames=list(study['rows'][0]))
        writer.writeheader()
        writer.writerows(study['rows'])
    return jpath, cpath


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--count', type=int, default=10)
    parser.add_argument('--seed-base', type=int, default=BASE_SEED)
    parser.add_argument('--time-limit', type=float, default=.7)
    parser.add_argument('--profile', default='congested_cell')
    parser.add_argument('--out', type=Path, default=Path('artifacts/formulation_ablation'))
    args=parser.parse_args()
    study=run_study(count=args.count, seed_base=args.seed_base, time_limit=args.time_limit, profile=args.profile)
    j,c=save_study(study,args.out)
    print(json.dumps({'summary':study['summary'],
                      'tight_better':sum(r['tight_better'] for r in study['paired']),
                      'tight_worse':sum(r['tight_worse'] for r in study['paired']),
                      'json':str(j),'csv':str(c)},indent=2))


if __name__=='__main__':
    main()
