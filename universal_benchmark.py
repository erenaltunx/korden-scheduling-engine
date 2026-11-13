"""Deterministic cross-industry scheduling audit, separate from marketing claims.

This is a regression + feasibility benchmark on three illustrative scenarios,
NOT a statistical generalization or evidence of actual customer savings.
"""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
from time import perf_counter

from optera.baseline import POLICIES, dispatch
from optera.evaluation import evaluate, check_schedule
from optera.engines import optimize_with
from optera.universal import normalize_universal, describe_universal

ROOT = Path(__file__).resolve().parent


def benchmark_sector(name: str, time_limit: float = 8.0,
                     dataset_dir: Path | None = None) -> dict:
    source = json.loads(((dataset_dir or ROOT / 'samples' / 'universal') / (name+'.json')).read_text('utf-8'))
    scenario = normalize_universal(source)
    profile = describe_universal(source)
    baselines = []
    for policy in POLICIES:
        planned = dispatch(scenario, policy)
        assert not check_schedule(scenario, planned)
        kpis = evaluate(scenario, planned)
        baselines.append({'policy': policy, 'weighted_tardiness': kpis['weighted_tardiness'],
                          'makespan': kpis['makespan']})
    best = min(baselines, key=lambda a: (a['weighted_tardiness'], a['makespan']))
    start = perf_counter()
    solved = optimize_with('milp_highs', scenario, time_limit,
                           objective='weighted_tardiness')
    elapsed = round(perf_counter()-start, 3)
    feasible = solved['schedule'] is not None and not check_schedule(scenario, solved['schedule'])
    result = evaluate(scenario, solved['schedule']) if feasible else None
    improvement = (round(100*(best['weighted_tardiness']-result['weighted_tardiness']) /
                         best['weighted_tardiness'], 2)
                   if result is not None and best['weighted_tardiness'] > 0 else None)
    return {
        'template': name,
        'industry': profile['industry'],
        'time_unit': profile['time_unit'],
        'resources': profile['resources'], 'work_orders': profile['work_orders'],
        'steps': profile['steps'], 'baselines': baselines, 'best_baseline': best,
        'optimized_weighted_tardiness': result['weighted_tardiness'] if result else None,
        'optimized_makespan': result['makespan'] if result else None,
        'relative_improvement_vs_best_percent': improvement,
        'feasible_schedule': feasible,
        'optimality_proven': bool(solved['solver']['optimality_proven']),
        'solve_seconds': elapsed, 'solver_status': solved['solver']['status'],
        'note': 'Illustrative synthetic workflow. No evidence of live operational savings.'
    }


def run(names: list[str], limit: float, output: Path,
        dataset_dir: Path | None = None) -> list[dict]:
    results = [benchmark_sector(name, limit, dataset_dir) for name in names]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.with_suffix('.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    cols = ['template','industry','time_unit','resources','work_orders','steps',
            'optimized_weighted_tardiness','optimized_makespan',
            'relative_improvement_vs_best_percent','feasible_schedule',
            'optimality_proven','solve_seconds','solver_status']
    with output.with_suffix('.csv').open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=cols)
        writer.writeheader()
        for item in results:
            writer.writerow({k:item.get(k) for k in cols})
    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='OPTERA cross-industry model regression')
    parser.add_argument('--limit', type=float, default=8.0)
    parser.add_argument('--out', type=Path, default=Path('artifacts/universal_sectors'))
    parser.add_argument('--dataset-dir', type=Path, default=None,
                        help='Immutable workload source folder for historical reproduction')
    args = parser.parse_args()
    outcome = run(['manufacturing','field_service','warehouse'], args.limit, args.out, args.dataset_dir)
    for item in outcome:
        print(f"{item['industry']}: baseline={item['best_baseline']['weighted_tardiness']}, "
              f"optimized={item['optimized_weighted_tardiness']}, "
              f"proof={item['optimality_proven']}, solve={item['solve_seconds']} s")
    if not all(item['feasible_schedule'] for item in outcome):
        raise SystemExit('Not all sector workflows produced valid schedules')
