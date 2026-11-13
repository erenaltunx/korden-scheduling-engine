"""Versioned, sector-neutral contract for single-resource, sequential workflow scheduling.

This is an explicit *capability-based adapter*, not a claim of universal constraint
support: each step occupies exactly one exclusive resource, tasks within an order
are sequential, and time is integral in the declared time unit. Unsupported rules
must be rejected rather than silently dropped.
"""
from __future__ import annotations
from copy import deepcopy
from typing import Any
from .model import validate_scenario

UNIVERSAL_SCHEMA_VERSION = 1
UNITS = {'minute', 'hour'}


def _mapping(value: Any, label: str, fields: set[str]) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f'{label} must be an object')
    unknown = set(value) - fields
    if unknown:
        raise ValueError(f'{label} has unsupported fields: {", ".join(sorted(unknown))}; unsupported constraints cannot be ignored')
    return value


def _name(obj: dict, key: str, location: str) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip() or len(value) > 100:
        raise ValueError(f'{location}.{key} must be a non-empty string (max 100 characters)')
    return value.strip()


def _int(obj: dict, key: str, location: str, minimum: int = 0, maximum: int = 10000) -> int:
    value = obj.get(key)
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f'{location}.{key} must be an integer between {minimum} and {maximum}')
    return value


def _caps(value: Any, location: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(x, str) or not x.strip() or len(x)>60 for x in value):
        raise ValueError(f'{location} must be an array of non-empty capability names')
    if len(value) > 25 or len(value) != len(set(value)):
        raise ValueError(f'{location} must contain at most 25 unique capabilities')
    return value


def normalize_universal(scenario: dict) -> dict:
    """Validate a universal workload and compile it into the trusted v1 solver schema.

    Source object is not modified. Fail closed on every unmodeled key rather than
    suggesting we optimize constraints that the solver has not implemented.
    """
    data = _mapping(scenario, 'scenario', {
        'schema_version', 'name', 'industry', 'time_unit', 'resources', 'work_orders'
    })
    if data.get('schema_version') != 1 or type(data.get('schema_version')) is not int:
        raise ValueError('Universal scenario schema_version must be 1')
    title = _name(data, 'name', 'scenario')
    industry = _name(data, 'industry', 'scenario')
    unit = data.get('time_unit')
    if unit not in UNITS:
        raise ValueError('time_unit must be minute or hour; no implicit unit conversion')
    resources = data.get('resources')
    orders = data.get('work_orders')
    if not isinstance(resources, list) or not 1 <= len(resources) <= 12:
        raise ValueError('resources must contain 1–12 capacity-one resources')
    if not isinstance(orders, list) or not 1 <= len(orders) <= 30:
        raise ValueError('work_orders must contain 1–30 orders')

    known_resources: dict[str, list[str]] = {}
    compiled_resources = []
    for number, raw in enumerate(resources):
        loc = f'resources[{number}]'
        r = _mapping(raw, loc, {'id', 'name', 'kind', 'capabilities', 'unavailable'})
        rid = _name(r, 'id', loc)
        _name(r, 'name', loc)
        _name(r, 'kind', loc)
        if rid in known_resources:
            raise ValueError(f'Duplicate resource id {rid}')
        tags = _caps(r.get('capabilities', []), loc+'.capabilities')
        intervals = r.get('unavailable', [])
        if not isinstance(intervals, list):
            raise ValueError(f'{loc}.unavailable must be an array')
        blocked = []
        for idx, raw_window in enumerate(intervals):
            place = f'{loc}.unavailable[{idx}]'
            window = _mapping(raw_window, place, {'start', 'end'})
            begin = _int(window, 'start', place)
            end = _int(window, 'end', place)
            if begin >= end:
                raise ValueError(f'{place} must end after it starts')
            blocked.append({'start': begin, 'end': end})
        known_resources[rid] = tags
        compiled_resources.append({'id': rid, 'downtime': deepcopy(blocked)})

    known_orders: set[str] = set()
    compiled_orders = []
    step_count = 0
    for index, raw in enumerate(orders):
        loc = f'work_orders[{index}]'
        order = _mapping(raw, loc, {'id', 'name', 'available_at', 'due_at', 'priority', 'steps'})
        oid = _name(order, 'id', loc)
        _name(order, 'name', loc)
        if oid in known_orders:
            raise ValueError(f'Duplicate work order id {oid}')
        known_orders.add(oid)
        start = _int(order, 'available_at', loc)
        due = _int(order, 'due_at', loc)
        priority = _int(order, 'priority', loc, 1, 100)
        steps = order.get('steps')
        if not isinstance(steps, list) or not 1 <= len(steps) <= 12:
            raise ValueError(f'{loc}.steps must contain 1–12 sequential steps')
        compiled_steps = []
        seen_steps: set[str] = set()
        for j, raw_step in enumerate(steps):
            place = f'{loc}.steps[{j}]'
            step = _mapping(raw_step, place, {
                'id', 'name', 'duration', 'requires_all', 'eligible_resources'
            })
            sid = _name(step, 'id', place)
            _name(step, 'name', place)
            if sid in seen_steps:
                raise ValueError(f'Duplicate step id {sid} within {oid}')
            seen_steps.add(sid)
            duration = _int(step, 'duration', place, 1, 1000)
            requirements = _caps(step.get('requires_all', []), place+'.requires_all')
            if 'eligible_resources' in step:
                explicit = step['eligible_resources']
                if not isinstance(explicit, list) or not explicit or any(
                    not isinstance(rid, str) or rid not in known_resources for rid in explicit
                ) or len(explicit) != len(set(explicit)):
                    raise ValueError(f'{place}.eligible_resources must be a nonempty list of unique known resources')
            else:
                explicit = list(known_resources)
            eligible = [rid for rid in explicit if set(requirements).issubset(known_resources[rid])]
            if not eligible:
                raise ValueError(f'{place} has no resource satisfying all required capabilities')
            compiled_steps.append({'id': sid, 'duration': duration, 'machines': eligible})
            step_count += 1
        compiled_orders.append({
            'id': oid, 'release': start, 'due': due, 'weight': priority,
            'operations': compiled_steps,
        })
    if step_count > 65:
        raise ValueError('The current solver supports at most 65 steps; partition workloads or use a future scaled solver')
    compiled = {
        'schema_version': 1, 'factory_name': title,
        'machines': compiled_resources, 'jobs': compiled_orders,
    }
    validate_scenario(compiled)
    return compiled


def describe_universal(scenario: dict) -> dict:
    compiled = normalize_universal(scenario)
    return {
        'schema_version': 1,
        'industry': scenario['industry'],
        'name': scenario['name'],
        'time_unit': scenario['time_unit'],
        'resources': len(compiled['machines']),
        'work_orders': len(compiled['jobs']),
        'steps': sum(len(job['operations']) for job in compiled['jobs']),
        'capabilities': sorted({cap for r in scenario['resources'] for cap in r.get('capabilities', [])}),
        'model_scope': ['one exclusive resource per step', 'sequential steps per order',
                        'integer time grid', 'fixed resource unavailability',
                        'weighted tardiness or makespan'],
        'unsupported': ['simultaneous multi-resource teams', 'batch capacities',
                        'travel times', 'sequence-dependent setup times',
                        'materials/inventory', 'cross-order precedence', 'stochastic processing'],
    }
