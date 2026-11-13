"""Disruption-aware rolling-horizon scheduling with immutable execution history.

Factory clock uses nonnegative integer hours. Work started before ``now`` is
non-preemptive and fixed exactly; future operations can be reassigned.  If a
new outage intersects in-progress work, the engine refuses to invent a repair
or preemption mechanism.
"""
from __future__ import annotations

from .baseline import POLICIES, earliest_slot, policy_priority
from .evaluation import check_schedule, evaluate
from .model import downtime_by_machine, validate_scenario
from .optimizer import optimize
from .whatif import add_outage


def prepare_rolling(original: dict, prior_schedule: list[dict], now: int,
                    revised: dict) -> dict[str, dict]:
    validate_scenario(original)
    validate_scenario(revised)
    if type(now) is not int or not 0 <= now <= 10000:
        raise ValueError('Planning clock now must be an integer hour between 0 and 10000')
    if not isinstance(prior_schedule, list):
        raise ValueError('Prior schedule must be an array')
    errors = check_schedule(original, prior_schedule)
    if errors:
        raise ValueError('Invalid committed schedule: ' + '; '.join(errors))
    # No changes to the model of the production orders in a disruption replay.
    if original['jobs'] != revised['jobs']:
        raise ValueError('Disruption replay cannot rewrite committed job definitions')
    if [m['id'] for m in original['machines']] != [m['id'] for m in revised['machines']]:
        raise ValueError('Disruption replay cannot change machine identities')
    frozen = {s['key']: dict(s) for s in prior_schedule if s['start'] < now}
    outages = downtime_by_machine(revised)
    for row in frozen.values():
        for rid in [row['machine'], *row.get('support_resources', [])]:
            for ds, de in outages[rid]:
                if row['start'] < de and row['end'] > ds:
                    raise ValueError(
                        f"Outage conflicts with already-started operation {row['key']} on {rid}; "
                        'non-preemptive model cannot interrupt work in progress')
    return frozen


def rolling_dispatch(data: dict, fixed: dict[str, dict], now: int,
                     policy: str = 'edd') -> list[dict]:
    validate_scenario(data)
    if policy not in POLICIES:
        raise ValueError(f'Unsupported baseline policy: {policy}')
    occupied = downtime_by_machine(data)
    schedule = list(fixed.values())
    for row in fixed.values():
        for rid in [row['machine'], *row.get('support_resources', [])]:
            occupied[rid].append((row['start'], row['end']))
    for job in sorted(data['jobs'], key=lambda j: policy_priority(j, policy)):
        ready = max(now, job['release'])
        for i, op in enumerate(job['operations']):
            key = f"{job['id']}::{i}"
            if key in fixed:
                ready = max(now, fixed[key]['end'])
                continue
            options = []
            for machine in op['machines']:
                busy = occupied[machine] + [interval for rid in op.get('support_resources', [])
                                            for interval in occupied[rid]]
                start = earliest_slot(ready, op['duration'], busy)
                options.append((start + op['duration'], start, machine))
            end, start, machine = min(options)
            row = {'key': key, 'job': job['id'], 'operation': op['id'],
                   'machine': machine, 'start': int(start), 'end': int(end),
                   'duration': op['duration']}
            if op.get('support_resources'):
                row['support_resources'] = list(op['support_resources'])
            schedule.append(row)
            for rid in [machine, *op.get('support_resources', [])]:
                occupied[rid].append((start, end))
            ready = end
    schedule.sort(key=lambda r: (r['start'], r['machine'], r['key']))
    errors = check_schedule(data, schedule)
    if errors:
        raise RuntimeError('Rolling heuristic is not feasible: ' + '; '.join(errors))
    return schedule


def stability_stats(previous: list[dict], current: list[dict], frozen: dict[str, dict]) -> dict:
    old = {s['key']: s for s in previous}
    current = {s['key']: s for s in current}
    pending = [k for k in old if k not in frozen]
    return {
        'frozen_operations': len(frozen), 'remaining_operations': len(pending),
        'rescheduled_operations': sum(old[k]['start'] != current[k]['start'] or
                                      old[k]['machine'] != current[k]['machine'] for k in pending),
        'machine_reassignments': sum(old[k]['machine'] != current[k]['machine'] for k in pending),
        'total_absolute_start_shift_hours': sum(abs(old[k]['start']-current[k]['start']) for k in pending),
    }


def reschedule(original: dict, prior_schedule: list[dict], now: int,
               machine_id: str, outage_start: int, outage_end: int,
               time_limit: float = 8.0, baseline_policy: str = 'edd',
               objective: str = 'weighted_tardiness') -> dict:
    if type(outage_start) is not int or outage_start < now:
        raise ValueError('New outage must start at or after the planning clock')
    if objective not in {'weighted_tardiness', 'makespan'}:
        raise ValueError('Unknown optimization objective')
    primary_metric = objective
    revised = add_outage(original, machine_id, outage_start, outage_end)
    frozen = prepare_rolling(original, prior_schedule, now, revised)
    baseline = rolling_dispatch(revised, frozen, now, baseline_policy)
    before = evaluate(revised, baseline)
    result = optimize(revised, time_limit, fixed_operations=frozen, not_before=now, objective=objective)
    candidate = result['schedule']
    if candidate is not None:
        errors = check_schedule(revised, candidate)
        if errors:
            raise RuntimeError('Optimizer returned an invalid rolling schedule: ' + '; '.join(errors))
        if any(next(s for s in candidate if s['key'] == k) != row for k, row in frozen.items()):
            raise RuntimeError('Optimizer changed committed operations')
        after = evaluate(revised, candidate)
        if (after[primary_metric], after['makespan']) > (before[primary_metric], before['makespan']):
            candidate = None
    if candidate is None:
        candidate = baseline
        after = before
        result['solver']['status'] = 'rolling_baseline_retained'
    return {
        'schema_version': 1, 'type': 'rolling_reschedule',
        'factory': revised.get('factory_name', 'Factory'), 'planning_clock': now,
        'outage': {'machine': machine_id, 'start': outage_start, 'end': outage_end},
        'revised_scenario': revised,
        'baseline_policy': baseline_policy, 'objective': objective, 'target_metric': primary_metric,
        'baseline': {'name': POLICIES[baseline_policy], 'metrics': before, 'schedule': baseline},
        'optimized': {'name': 'MILP / HiGHS', 'metrics': after, 'schedule': candidate},
        'stability': stability_stats(prior_schedule, candidate, frozen),
        'improvement_percent': round(100*(before[primary_metric] - after[primary_metric]) /
                                     before[primary_metric], 2) if before[primary_metric] else None,
        'solver': result['solver'],
        'note': 'What-if rolling reschedule; started work remains fixed. No real factory execution.'
    }
