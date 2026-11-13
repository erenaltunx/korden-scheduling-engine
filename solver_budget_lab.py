"""Controlled, paired solver-budget study for congested small machining cells.

Independent experiments per time budget: no solver warm-start or cross-budget
carry-over. The deployable policy remains the independently checked better of
MILP and the strongest of four classical dispatching rules. Results are
synthetic and do not represent observed factory savings.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import statistics
from collections import defaultdict
from pathlib import Path
from time import perf_counter

import scipy

from research_lab import BASE_SEED, make_factory, run_instance

DEFAULT_BUDGETS = (0.7, 2.0, 5.0)
PROFILE = "congested_cell"


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = max(0, min(len(ordered) - 1, math.ceil(percentile * len(ordered)) - 1))
    return round(ordered[position], 3)


def parse_budgets(raw: str) -> tuple[float, ...]:
    try:
        parsed = tuple(float(x.strip()) for x in raw.split(','))
    except ValueError as exc:
        raise ValueError('Budgets must be comma-separated numbers') from exc
    if not parsed or len(parsed) > 6 or any(not math.isfinite(x) or not .5 <= x <= 60 for x in parsed):
        raise ValueError('Require 1–6 finite solve budgets in [0.5, 60] seconds')
    if sorted(parsed) != list(parsed) or len(set(parsed)) != len(parsed):
        raise ValueError('Budgets must be strictly increasing')
    return parsed


def _budget_stats(rows: list[dict]) -> dict:
    if not rows:
        raise ValueError('No rows to summarize')
    base = sum(x['baseline_weighted_tardiness'] for x in rows)
    rec = sum(x['recommended_weighted_tardiness'] for x in rows)
    milp = [x for x in rows if x['milp_weighted_tardiness'] is not None]
    gaps = [float(x['relative_mip_gap']) for x in rows
            if x.get('relative_mip_gap') is not None and math.isfinite(float(x['relative_mip_gap']))]
    return {
        'instances': len(rows), 'jobs': sum(x['jobs'] for x in rows),
        'operations': sum(x['operations'] for x in rows),
        'baseline_weighted_tardiness': base,
        'recommended_weighted_tardiness': rec,
        'recommended_reduction_percent': round(100*(base-rec)/base, 2) if base else None,
        'raw_milp_feasible': len(milp),
        'raw_milp_better_than_baseline': sum(x['milp_weighted_tardiness'] < x['baseline_weighted_tardiness'] for x in milp),
        'raw_milp_worse_than_baseline': sum(x['milp_weighted_tardiness'] > x['baseline_weighted_tardiness'] for x in milp),
        'fallbacks': sum(x['selection']=='baseline_fallback' for x in rows),
        'proved_optimal': sum(x['optimality_proven'] for x in rows),
        'p50_solver_seconds': _percentile([float(x['solve_seconds']) for x in rows], .5),
        'p90_solver_seconds': _percentile([float(x['solve_seconds']) for x in rows], .9),
        'p90_total_wall_seconds': _percentile([float(x['total_wall_seconds']) for x in rows], .9),
        'max_reported_mip_gap': round(max(gaps), 6) if gaps else None,
    }


def run_study(*, count: int = 10, seed_base: int = BASE_SEED,
              budgets: tuple[float, ...] = DEFAULT_BUDGETS) -> dict:
    if type(count) is not int or not 1 <= count <= 20:
        raise ValueError('count must be an integer in [1, 20]')
    if type(seed_base) is not int or not 0 <= seed_base <= 1000000000:
        raise ValueError('seed_base must be a nonnegative integer up to 1 billion')
    if not isinstance(budgets, tuple) or tuple(sorted(budgets)) != budgets or len(set(budgets))!=len(budgets):
        raise ValueError('Solve budgets must be strictly ascending')
    if not 1 <= len(budgets) <= 6 or any(type(x) not in (int, float) or not math.isfinite(x) or not .5 <= x <= 60 for x in budgets):
        raise ValueError('Solve budgets must be finite and within [0.5, 60] seconds')

    rows = []
    hashes_by_seed: dict[int, str] = {}
    for index in range(count):
        seed = seed_base + index
        for budget in budgets:
            t0 = perf_counter()
            run = run_instance(PROFILE, seed, budget)
            total_wall = perf_counter() - t0
            if seed in hashes_by_seed and hashes_by_seed[seed] != run['input_sha256']:
                raise AssertionError('Paired experiment inputs changed between budgets')
            hashes_by_seed[seed] = run['input_sha256']
            if run['recommended_weighted_tardiness'] > run['baseline_weighted_tardiness']:
                raise AssertionError('Recommendation regressed behind independently validated baseline')
            rows.append({**run, 'time_budget_seconds': budget, 'total_wall_seconds': round(total_wall, 3)})

    # Every budget is compared on exactly the same seed-set; no pooling of
    # objectives across budgets or cherry-picking the best run per instance.
    summary = {}
    for budget in budgets:
        group = [r for r in rows if r['time_budget_seconds'] == budget]
        assert len(group)==count
        summary[str(budget)] = _budget_stats(group)
    per_seed = defaultdict(list)
    for row in rows:
        per_seed[row['seed']].append(row)
    transitions = []
    for seed, same_input_rows in per_seed.items():
        previous = same_input_rows[0]
        for current in same_input_rows[1:]:
            transitions.append({
                'seed': seed, 'short_budget': previous['time_budget_seconds'],
                'long_budget': current['time_budget_seconds'],
                'short_recommendation': previous['recommended_weighted_tardiness'],
                'long_recommendation': current['recommended_weighted_tardiness'],
                'longer_budget_improved': current['recommended_weighted_tardiness'] < previous['recommended_weighted_tardiness'],
                'longer_budget_worsened': current['recommended_weighted_tardiness'] > previous['recommended_weighted_tardiness'],
                'both_optimal': previous['optimality_proven'] and current['optimality_proven'],
            })
            previous = current

    digest = hashlib.sha256(''.join(hashes_by_seed[k] for k in sorted(hashes_by_seed)).encode()).hexdigest()
    return {
        'metadata': {
            'version': 'solver-budget-v1', 'dataset': 'synthetic-congested-machining-cells',
            'independent_solver_runs': True, 'warm_start': False,
            'seeds': list(sorted(hashes_by_seed)), 'input_sha256': digest,
            'budgets_seconds': list(budgets), 'platform': platform.platform(),
            'python': platform.python_version(), 'scipy': scipy.__version__,
            'interpretation': 'Per-budget aggregate of independent runs; higher time limits do not guarantee monotone quality',
            'scope': 'Small deterministic synthetic production cells, not actual factory savings',
        }, 'summary_by_budget': summary, 'transitions': transitions, 'rows': rows,
    }


def write_study(study: dict, prefix: Path) -> tuple[Path, Path]:
    if not study['rows']:
        raise ValueError('Cannot export an empty study')
    prefix.parent.mkdir(parents=True, exist_ok=True)
    json_path = prefix.with_suffix('.json')
    csv_path = prefix.with_suffix('.csv')
    json_path.write_text(json.dumps(study, ensure_ascii=False, indent=2, sort_keys=True)+'\n', encoding='utf-8')
    with csv_path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(study['rows'][0]))
        writer.writeheader()
        writer.writerows(study['rows'])
    return json_path, csv_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--count', type=int, default=10)
    parser.add_argument('--seed-base', type=int, default=BASE_SEED)
    parser.add_argument('--budgets', type=str, default='0.7,2,5')
    parser.add_argument('--out', type=Path, default=Path('artifacts/budget_study'))
    args = parser.parse_args()
    try:
        budgets = parse_budgets(args.budgets)
        study = run_study(count=args.count, seed_base=args.seed_base, budgets=budgets)
    except ValueError as exc:
        parser.error(str(exc))
    js, cs = write_study(study, args.out)
    print(json.dumps({'summary_by_budget': study['summary_by_budget'],
                      'longer_budget_worsenings': sum(t['longer_budget_worsened'] for t in study['transitions']),
                      'json': str(js), 'csv': str(cs)}, indent=2))


if __name__ == '__main__':
    main()
