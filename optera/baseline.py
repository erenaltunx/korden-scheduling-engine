"""Deterministic classical dispatching policies for fair scheduling comparisons.

Each policy uses exactly the same earliest feasible slot algorithm, machine
eligibility and machine downtime; only job priority changes.
"""
from __future__ import annotations
from fractions import Fraction
from .model import (downtime_by_machine, validate_scenario, changeover_by_machine,
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


def dispatch(data: dict, policy: str = "edd") -> list[dict]:
    validate_scenario(data)
    if policy not in POLICIES:
        raise ValueError(f"Unknown baseline policy {policy!r}; valid policies: {', '.join(POLICIES)}")
    occupied = downtime_by_machine(data)
    primary_occupied = {mid: [] for mid in occupied}
    setup_times = changeover_by_machine(data)
    jobs = sorted(data["jobs"], key=lambda j: policy_priority(j, policy))
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


def dispatch_edd(data: dict) -> list[dict]:
    """Stable legacy API. This schedule must not change across releases."""
    return dispatch(data, "edd")
