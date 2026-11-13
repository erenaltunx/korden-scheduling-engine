"""Disruption-aware rolling-horizon scheduling with immutable execution history.

Factory clock uses nonnegative integer hours. Work started before ``now`` is
non-preemptive and fixed exactly; future operations can be reassigned.  If a
new outage intersects in-progress work, the engine refuses to invent a repair
or preemption mechanism.
"""
from __future__ import annotations

from .baseline import POLICIES, earliest_slot_with_changeover, policy_priority
from .evaluation import check_schedule, evaluate
from .model import downtime_by_machine, validate_scenario, changeover_by_machine
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
    primary_occupied = {mid: [] for mid in occupied}
    setup_times = changeover_by_machine(data)
    task_families = {f"{j['id']}::{idx}": op.get('setup_family')
                     for j in data['jobs'] for idx, op in enumerate(j['operations'])}
    schedule = list(fixed.values())
    for row in fixed.values():
        for rid in [row['machine'], *row.get('support_resources', [])]:
            occupied[rid].append((row['start'], row['end']))
        primary_occupied[row['machine']].append((row['start'], row['end'], task_families[row['key']]))
    for job in sorted(data['jobs'], key=lambda j: policy_priority(j, policy)):
        ready = max(now, job['release'])
        for i, op in enumerate(job['operations']):
            key = f"{job['id']}::{i}"
            if key in fixed:
                ready = max(now, fixed[key]['end'])
                continue
            options = []
            for machine in op['machines']:
                for choice in (op.get('support_options') or [None]):
                    reserved = [*op.get('support_resources', []), *([choice] if choice else [])]
                    busy = occupied[machine] + [interval for rid in reserved for interval in occupied[rid]]
                    start = earliest_slot_with_changeover(
                        ready, op['duration'], busy, primary_occupied[machine],
                        op.get('setup_family'), setup_times[machine])
                    options.append((start + op['duration'], start, machine, choice or ''))
            end, start, machine, choice = min(options)
            reserved = [*op.get('support_resources', []), *([choice] if choice else [])]
            row = {'key': key, 'job': job['id'], 'operation': op['id'],
                   'machine': machine, 'start': int(start), 'end': int(end),
                   'duration': op['duration']}
            if reserved:
                row['support_resources'] = reserved
            schedule.append(row)
            for rid in [machine, *reserved]:
                occupied[rid].append((start, end))
            primary_occupied[machine].append((start, end, op.get('setup_family')))
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
        'support_reassignments': sum(set(old[k].get('support_resources', [])) !=
                                     set(current[k].get('support_resources', [])) for k in pending),
        'total_absolute_start_shift_hours': sum(abs(old[k]['start']-current[k]['start']) for k in pending),
    }


def reschedule(original: dict, prior_schedule: list[dict], now: int,
               machine_id: str, outage_start: int, outage_end: int,
               time_limit: float = 8.0, baseline_policy: str = 'edd',
               objective: str = 'weighted_tardiness',
               stability_policy: str = 'off', max_added_tardiness: int = 0) -> dict:
    if type(outage_start) is not int or outage_start < now:
        raise ValueError('New outage must start at or after the planning clock')
    if objective not in {'weighted_tardiness', 'makespan'}:
        raise ValueError('Unknown optimization objective')
    if stability_policy not in {'off', 'preserve'}:
        raise ValueError('stability_policy must be off or preserve')
    if type(max_added_tardiness) is not int or not 0 <= max_added_tardiness <= 100:
        raise ValueError('max_added_tardiness must be an integer between 0 and 100')
    if stability_policy == 'preserve' and objective != 'weighted_tardiness':
        raise ValueError('Plan stability currently requires weighted_tardiness objective')
    if stability_policy == 'off' and max_added_tardiness:
        raise ValueError('max_added_tardiness requires stability_policy=preserve')
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
    first_stage = candidate
    stage_one = dict(result['solver'])
    stability_research = {'enabled': stability_policy == 'preserve',
                          'max_added_tardiness': max_added_tardiness}
    if stability_policy == 'preserve':
        # Independent second-stage MILP with an explicit service-quality cap.
        # This never overwrites completed operations or the baseline.
        budget = int(after['weighted_tardiness']) + max_added_tardiness
        second = optimize(revised, time_limit, fixed_operations=frozen, not_before=now,
                          objective='stability', reference_schedule=prior_schedule,
                          tardiness_budget=budget)
        replacement = second['schedule']
        stability_research['second_stage_solver'] = second['solver']
        before_stability = stability_stats(prior_schedule, first_stage, frozen)
        stability_research['first_stage_stability'] = before_stability
        if replacement is not None:
            violation = check_schedule(revised, replacement)
            if violation:
                raise RuntimeError('Stability optimizer returned invalid schedule: ' + '; '.join(violation))
            replacement_kpis = evaluate(revised, replacement)
            after_stability = stability_stats(prior_schedule, replacement, frozen)
            # Never trust a rounded solver output without independent checking.
            valid = replacement_kpis['weighted_tardiness'] <= budget
            original_score = (before_stability['total_absolute_start_shift_hours'] +
                              5*(before_stability['machine_reassignments'] + before_stability['support_reassignments']))
            replacement_score = (after_stability['total_absolute_start_shift_hours'] +
                                 5*(after_stability['machine_reassignments'] + after_stability['support_reassignments']))
            if valid and (replacement_score, replacement_kpis['makespan']) < (original_score, after['makespan']):
                candidate, after = replacement, replacement_kpis
                stability_research['accepted'] = True
            else:
                stability_research['accepted'] = False
        else:
            stability_research['accepted'] = False
        stability_research['service_cap'] = budget
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
        'solver': stage_one,
        'stability_optimization': stability_research,
        'note': 'What-if rolling reschedule; started work remains fixed. No real factory execution.'
    }
