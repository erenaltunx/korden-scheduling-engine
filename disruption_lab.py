"""Reproducible rolling-horizon factory disruption audit.

Every selected seed is reported, including solver fallbacks, without discarding
unfavorable instances. Outcomes are scenarios, not realized plant savings.
"""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
from statistics import mean
from korden.generator import generate_factory
from korden.optimizer import optimize
from korden.evaluation import check_schedule, evaluate
from korden.baseline import dispatch
from korden.reschedule import reschedule


def run_disruption_lab(count: int = 20, start_seed: int = 300,
                       time_limit: float = 3.0) -> dict:
    if type(count) is not int or not 1 <= count <= 100:
        raise ValueError('count must be between 1 and 100')
    if type(start_seed) is not int or start_seed < 0:
        raise ValueError('start_seed must be a nonnegative integer')
    if not 0.5 <= time_limit <= 60:
        raise ValueError('time_limit must be 0.5–60 seconds')
    rows = []
    for seed in range(start_seed, start_seed + count):
        scenario = generate_factory(seed, 5)
        initial = optimize(scenario, time_limit)
        previous = initial['schedule']
        if previous is None:
            previous = dispatch(scenario, 'edd')
        assert not check_schedule(scenario, previous)
        now = 4
        # Deterministic event: a CUT breakdown begins just after any currently
        # executing CUT task finishes. No invented preemption or history rewrite.
        frozen_cut_ends = [r['end'] for r in previous if r['machine'] == 'CUT' and r['start'] < now]
        outage_start = max([now] + frozen_cut_ends) + 1
        outage_end = outage_start + 4
        report = reschedule(scenario, previous, now, 'CUT', outage_start, outage_end,
                            time_limit, 'edd')
        base = report['baseline']['metrics']
        updated = report['optimized']['metrics']
        rows.append({
            'seed': seed, 'jobs': 5, 'operations': 15, 'clock': now,
            'outage_start': outage_start, 'outage_end': outage_end,
            'before_outage_weighted_tardiness': evaluate(scenario, previous)['weighted_tardiness'],
            'rolling_edd_weighted_tardiness': base['weighted_tardiness'],
            'rolling_optimizer_weighted_tardiness': updated['weighted_tardiness'],
            'frozen_operations': report['stability']['frozen_operations'],
            'changed_future_operations': report['stability']['rescheduled_operations'],
            'machine_reassignments': report['stability']['machine_reassignments'],
            'start_shift_hours': report['stability']['total_absolute_start_shift_hours'],
            'solver_status': report['solver']['status'],
            'optimality_proven': report['solver']['optimality_proven'],
            'relative_mip_gap': report['solver']['relative_mip_gap'],
            'solve_seconds': report['solver']['solve_seconds'],
        })
    total_before = sum(r['rolling_edd_weighted_tardiness'] for r in rows)
    total_after = sum(r['rolling_optimizer_weighted_tardiness'] for r in rows)
    return {
        'methodology': {
            'scope': 'deterministic synthetic rolling-replan, fixed execution history',
            'seeds': [start_seed, start_seed+count-1], 'jobs_per_instance': 5,
            'operations_per_instance': 15, 'planning_clock_hours': 4,
            'event': 'CUT outage, 4 hours, after latest already-started CUT task',
            'baseline': 'rolling EDD with identical committed work and outage',
            'solver_time_limit_seconds': time_limit,
            'warning': 'Only a synthetic test, no measured factory savings; makespan is not the objective.'
        },
        'summary': {
            'instances': len(rows), 'operations': len(rows)*15,
            'proven_optimal': sum(r['optimality_proven'] for r in rows),
            'wins': sum(r['rolling_optimizer_weighted_tardiness'] < r['rolling_edd_weighted_tardiness'] for r in rows),
            'ties': sum(r['rolling_optimizer_weighted_tardiness'] == r['rolling_edd_weighted_tardiness'] for r in rows),
            'total_rolling_edd_weighted_tardiness': total_before,
            'total_rolling_optimizer_weighted_tardiness': total_after,
            'pooled_reduction_percent': round(100*(total_before-total_after)/total_before,2) if total_before else None,
            'mean_frozen_operations': round(mean(r['frozen_operations'] for r in rows),2),
            'mean_changed_future_operations': round(mean(r['changed_future_operations'] for r in rows),2),
            'mean_solver_seconds': round(mean(r['solve_seconds'] for r in rows),3),
        }, 'rows': rows,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--count',type=int,default=20)
    parser.add_argument('--start-seed',type=int,default=300)
    parser.add_argument('--time-limit',type=float,default=3.0)
    parser.add_argument('--out',type=Path,default=Path('artifacts/disruption_lab'))
    opts=parser.parse_args()
    report=run_disruption_lab(opts.count,opts.start_seed,opts.time_limit)
    opts.out.parent.mkdir(parents=True,exist_ok=True)
    opts.out.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    with opts.out.with_suffix('.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=report['rows'][0].keys())
        writer.writeheader()
        writer.writerows(report['rows'])
    print(json.dumps(report['summary'],indent=2))

if __name__=='__main__':
    main()
