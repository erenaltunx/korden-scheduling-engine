"""Transparent earliest-due-date dispatching baseline, with earliest machine availability."""
from __future__ import annotations
from .model import downtime_by_machine, validate_scenario


def earliest_slot(start: int, duration: int, busy: list[tuple[int, int]]) -> int:
    candidate = start
    for a, b in sorted(busy):
        if candidate + duration <= a:
            break
        if candidate >= b:
            continue
        candidate = b
    return candidate


def dispatch_edd(data: dict) -> list[dict]:
    validate_scenario(data)
    occupied = downtime_by_machine(data)
    jobs = sorted(data["jobs"], key=lambda j: (j["due"], -j["weight"], j["id"]))
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
