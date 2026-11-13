"""Independent feasibility checker and strictly defined KPI computation."""
from __future__ import annotations
from collections import defaultdict
from .model import (all_tasks, downtime_by_machine, validate_scenario,
                    changeover_by_machine, changeover_gap)


def check_schedule(data: dict, schedule: list[dict]) -> list[str]:
    validate_scenario(data)
    tasks = {t.key: t for t in all_tasks(data)}
    jobs = {j["id"]: j for j in data["jobs"]}
    errors = []
    by_key = {}
    occupied = defaultdict(list)
    primary_occupied = defaultdict(list)
    for s in schedule:
        key = s.get("key")
        if key in by_key:
            errors.append(f"Duplicate operation {key}")
            continue
        by_key[key] = s
        if key not in tasks:
            errors.append(f"Unknown operation {key}")
            continue
        t = tasks[key]
        machine, start, end = s.get("machine"), s.get("start"), s.get("end")
        if machine not in t.machines:
            errors.append(f"{key} placed on ineligible machine {machine}")
            continue
        if type(start) is not int or type(end) is not int or start < 0 or end - start != t.duration:
            errors.append(f"{key} has invalid start/end or duration")
            continue
        if t.index == 0 and start < jobs[t.job_id]["release"]:
            errors.append(f"{key} starts before release")
        reserved = s.get('support_resources', [])
        if (not isinstance(reserved, list) or len(reserved) != len(set(reserved)) or
                set(reserved) - set(t.support_resources) - set(t.support_options) or
                not set(t.support_resources).issubset(reserved) or
                len(set(reserved) & set(t.support_options)) != (1 if t.support_options else 0)):
            errors.append(f"{key} has incorrect simultaneous support resource reservations")
            continue
        for rid in [machine, *reserved]:
            occupied[rid].append((start, end, key))
        primary_occupied[machine].append((start, end, key, t.setup_family))
    missing = set(tasks) - set(by_key)
    errors.extend(f"Missing operation {k}" for k in sorted(missing))
    for job in data["jobs"]:
        for i in range(1, len(job["operations"])):
            a, b = by_key.get(f"{job['id']}::{i-1}"), by_key.get(f"{job['id']}::{i}")
            if a and b and type(a.get("end")) is int and type(b.get("start")) is int:
                if a["end"] > b["start"]:
                    errors.append(f"Precedence violated in {job['id']} at operation {i}")
    for mid, intervals in occupied.items():
        intervals = sorted(intervals)
        for x, y in zip(intervals, intervals[1:]):
            if x[1] > y[0]:
                errors.append(f"Machine overlap on {mid}: {x[2]} and {y[2]}")
        for start, end, key in intervals:
            for da, db in downtime_by_machine(data)[mid]:
                if start < db and end > da:
                    errors.append(f"Operation {key} overlaps maintenance on {mid}")
    setup_times = changeover_by_machine(data)
    for mid, ops in primary_occupied.items():
        for prev, following in zip(sorted(ops), sorted(ops)[1:]):
            gap = changeover_gap(prev[3], following[3], setup_times[mid])
            if following[0] < prev[1] + gap:
                errors.append(f"Changeover violation on {mid}: {prev[2]} -> {following[2]} requires {gap} extra units")
    return errors


def evaluate(data: dict, schedule: list[dict]) -> dict:
    errors = check_schedule(data, schedule)
    if errors:
        raise ValueError("Infeasible schedule: " + "; ".join(errors))
    completions = {j["id"]: max(s["end"] for s in schedule if s["job"] == j["id"])
                   for j in data["jobs"]}
    late = sum(completions[j["id"]] > j["due"] for j in data["jobs"])
    total_weighted_tardiness = sum(j["weight"] * max(0, completions[j["id"]] - j["due"])
                                      for j in data["jobs"])
    total_tardiness = sum(max(0, completions[j["id"]] - j["due"]) for j in data["jobs"])
    makespan = max(s["end"] for s in schedule)
    # This is allocated resource-time (primary plus any simultaneous support).
    # Historical field name retained for compatibility with saved experiments.
    busy = {m["id"]: sum(s["duration"] for s in schedule
                         if s["machine"] == m["id"] or m["id"] in s.get('support_resources', []))
            for m in data["machines"]}
    setups = 0
    setup_units = 0
    for mid, machine in ((m['id'], m) for m in data['machines']):
        primary = sorted((s['start'], s['end'], s['key']) for s in schedule if s['machine'] == mid)
        families = {f"{j['id']}::{i}": op.get('setup_family')
                    for j in data['jobs'] for i, op in enumerate(j['operations'])}
        for a, b in zip(primary, primary[1:]):
            extra = changeover_gap(families[a[2]], families[b[2]], machine.get('changeover_time', 0))
            if extra:
                setups += 1
                setup_units += extra
    return {"changeover_count": setups, "setup_time_units": setup_units,
            "weighted_tardiness": int(total_weighted_tardiness),
            "total_tardiness": int(total_tardiness), "late_jobs": int(late),
            "makespan": int(makespan), "machine_busy_hours": busy,
            "job_completion_hours": completions}
