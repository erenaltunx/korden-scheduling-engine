"""Deterministic classical dispatching policies for fair scheduling comparisons.

Each policy uses exactly the same earliest feasible slot algorithm, machine
eligibility and machine downtime; only job priority changes.
"""
from __future__ import annotations
from fractions import Fraction
from .model import (downtime_by_machine, horizon, validate_scenario, changeover_by_machine,
                    changeover_gap)

POLICIES = {
    "edd": "Earliest Due Date (EDD)",
    "fifo": "First In, First Out (FIFO)",
    "spt": "Shortest Processing Time (SPT)",
    "wspt": "Weighted Shortest Processing Time (WSPT)",
}


def earliest_slot(start: int, duration: int, busy: list[tuple[int, int]]) -> int:
    candidate = start
    for a, b in sorted(busy):
        if candidate + duration <= a:
            break
        if candidate >= b:
            continue
        candidate = b
    return candidate


def earliest_slot_with_changeover(start: int, duration: int, busy: list[tuple[int, int]],
                                  prior_primary: list[tuple[int, int, str | None]],
                                  family: str | None, setup_time: int) -> int:
    """Find earliest feasible time, reserving switch gaps on the PRIMARY machine.

    Already scheduled primary operations are inflated on both sides when their
    setup family differs from the candidate. Support resources never trigger setup.
    """
    if not setup_time:
        return earliest_slot(start, duration, busy)
    blocked = busy + [
        (a - changeover_gap(previous, family, setup_time),
         b + changeover_gap(family, previous, setup_time))
        for a, b, previous in prior_primary
    ]
    return earliest_slot(start, duration, blocked)


def policy_priority(job: dict, policy: str) -> tuple:
    duration = sum(op["duration"] for op in job["operations"])
    if policy == "edd":
        return (job["due"], -job["weight"], job["id"])
    if policy == "fifo":
        return (job["release"], job["id"])
    if policy == "spt":
        return (duration, job["due"], job["id"])
    if policy == "wspt":
        return (Fraction(duration, job["weight"]), job["due"], job["id"])
    raise ValueError(f"Unknown baseline policy {policy!r}; valid policies: {', '.join(POLICIES)}")


def _schedule_jobs(data: dict, jobs: list[dict]) -> list[dict]:
    """Common capacity-feasible schedule builder for policies and local search."""
    occupied = downtime_by_machine(data)
    primary_occupied = {mid: [] for mid in occupied}
    setup_times = changeover_by_machine(data)
    schedule = []
    for job in jobs:
        ready = job["release"]
        for i, op in enumerate(job["operations"]):
            options = []
            for machine in op["machines"]:
                for choice in (op.get('support_options') or [None]):
                    reserved = [*op.get('support_resources', []), *([choice] if choice else [])]
                    # All selected resources must be simultaneously available.
                    taken = occupied[machine] + [window for rid in reserved for window in occupied[rid]]
                    start = earliest_slot_with_changeover(
                        ready, op["duration"], taken,
                        primary_occupied[machine], op.get('setup_family'), setup_times[machine])
                    options.append((start + op["duration"], start, machine, choice or ''))
            end, start, machine, choice = min(options)
            if end > horizon(data):
                raise ValueError(
                    f"No feasible working period for order {job['id']} operation {op['id']}; "
                    "extend working_windows or review operation durations")
            reserved = [*op.get('support_resources', []), *([choice] if choice else [])]
            row = {"key": f"{job['id']}::{i}", "job": job["id"],
                   "operation": op["id"], "machine": machine,
                   "start": int(start), "end": int(end), "duration": op["duration"]}
            if reserved:
                row['support_resources'] = reserved
            schedule.append(row)
            for rid in [machine, *reserved]:
                occupied[rid].append((start, end))
            primary_occupied[machine].append((start, end, op.get('setup_family')))
            ready = end
    return sorted(schedule, key=lambda x: (x["start"], x["machine"], x["key"]))


def dispatch(data: dict, policy: str = "edd") -> list[dict]:
    validate_scenario(data)
    if policy not in POLICIES:
        raise ValueError(f"Unknown baseline policy {policy!r}; valid policies: {', '.join(POLICIES)}")
    return _schedule_jobs(data, sorted(data["jobs"], key=lambda j: policy_priority(j, policy)))


def dispatch_job_order(data: dict, job_ids: list[str] | tuple[str, ...]) -> list[dict]:
    """Feasible schedule for a specific total work-order priority ordering.

    Restricted search space by design: the entire operation sequence within
    each job stays intact and all original physical constraints are respected.
    """
    validate_scenario(data)
    by_id = {j['id']: j for j in data['jobs']}
    if not isinstance(job_ids, (list, tuple)) or len(job_ids) != len(by_id) or set(job_ids) != set(by_id):
        raise ValueError('job_ids must be a complete unique permutation of all work orders')
    return _schedule_jobs(data, [by_id[jid] for jid in job_ids])


def dispatch_edd(data: dict) -> list[dict]:
    """Stable legacy API. This schedule must not change across releases."""
    return dispatch(data, "edd")
