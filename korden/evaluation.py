"""Independent feasibility checker and strictly defined KPI computation."""
from __future__ import annotations
from collections import defaultdict
from .model import all_tasks, downtime_by_machine, validate_scenario


def check_schedule(data: dict, schedule: list[dict]) -> list[str]:
    validate_scenario(data)
    tasks = {t.key: t for t in all_tasks(data)}
    jobs = {j["id"]: j for j in data["jobs"]}
    errors = []
    by_key = {}
    occupied = defaultdict(list)
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
        occupied[machine].append((start, end, key))
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
    busy = {m["id"]: sum(s["duration"] for s in schedule if s["machine"] == m["id"])
            for m in data["machines"]}
    return {"weighted_tardiness": int(total_weighted_tardiness),
            "total_tardiness": int(total_tardiness), "late_jobs": int(late),
            "makespan": int(makespan), "machine_busy_hours": busy,
            "job_completion_hours": completions}
