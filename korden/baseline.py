"""Deterministic classical dispatching policies for fair scheduling comparisons.

Each policy uses exactly the same earliest feasible slot algorithm, machine
eligibility and machine downtime; only job priority changes.
"""
from __future__ import annotations
from fractions import Fraction
from .model import downtime_by_machine, validate_scenario

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
    jobs = sorted(data["jobs"], key=lambda j: policy_priority(j, policy))
    schedule = []
    for job in jobs:
        ready = job["release"]
        for i, op in enumerate(job["operations"]):
            options = []
            for machine in op["machines"]:
                start = earliest_slot(ready, op["duration"], occupied[machine])
                options.append((start + op["duration"], start, machine))
            end, start, machine = min(options)
            schedule.append({"key": f"{job['id']}::{i}", "job": job["id"],
                             "operation": op["id"], "machine": machine,
                             "start": int(start), "end": int(end), "duration": op["duration"]})
            occupied[machine].append((start, end))
            ready = end
    return sorted(schedule, key=lambda x: (x["start"], x["machine"], x["key"]))


def dispatch_edd(data: dict) -> list[dict]:
    """Stable legacy API. This schedule must not change across releases."""
    return dispatch(data, "edd")
