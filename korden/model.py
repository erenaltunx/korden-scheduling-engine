"""Factory scenario schema and strong input validation (integer-hour time grid)."""
from __future__ import annotations
from dataclasses import dataclass

SCENARIO_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class Task:
    key: str
    job_id: str
    operation_id: str
    index: int
    duration: int
    machines: tuple[str, ...]


def validate_scenario(data: dict) -> dict:
    if not isinstance(data, dict):
        raise ValueError("Scenario must be a JSON object")
    schema_version = data.get("schema_version", 1)  # v0.1 imported scenarios remain readable
    if type(schema_version) is not int or schema_version != SCENARIO_SCHEMA_VERSION:
        raise ValueError(f"Unsupported scenario schema_version {schema_version!r}; expected {SCENARIO_SCHEMA_VERSION}")
    machines = data.get("machines")
    jobs = data.get("jobs")
    if not isinstance(machines, list) or not (1 <= len(machines) <= 12):
        raise ValueError("Provide between 1 and 12 machines")
    if not isinstance(jobs, list) or not (1 <= len(jobs) <= 30):
        raise ValueError("Provide between 1 and 30 jobs")
    ids = set()
    downtime = {}
    for m in machines:
        if not isinstance(m, dict) or not isinstance(m.get("id"), str) or not m["id"].strip():
            raise ValueError("Every machine needs a non-empty id")
        mid = m["id"]
        if mid in ids:
            raise ValueError(f"Duplicate machine: {mid}")
        ids.add(mid)
        windows = m.get("downtime", [])
        if not isinstance(windows, list):
            raise ValueError(f"Invalid downtime for {mid}")
        parsed = []
        for window in windows:
            if not isinstance(window, dict):
                raise ValueError(f"Downtime for {mid} must contain start and end")
            start, end = window.get("start"), window.get("end")
            if type(start) is not int or type(end) is not int or not (0 <= start < end <= 10000):
                raise ValueError(f"Invalid downtime interval for {mid}")
            parsed.append((start, end))
        parsed.sort()
        for a, b in zip(parsed, parsed[1:]):
            if a[1] > b[0]:
                raise ValueError(f"Overlapping downtime windows on {mid}")
        downtime[mid] = parsed
    jobids = set()
    num_ops = 0
    for job in jobs:
        if not isinstance(job, dict) or not isinstance(job.get("id"), str) or not job["id"].strip():
            raise ValueError("Every job needs an id")
        jid = job["id"]
        if jid in jobids:
            raise ValueError(f"Duplicate job: {jid}")
        jobids.add(jid)
        for field in ("release", "due", "weight"):
            v = job.get(field)
            if type(v) is not int or v < (1 if field == "weight" else 0) or v > 10000:
                raise ValueError(f"Job {jid}: {field} must be a non-negative integer (weight >= 1)")
        if job["weight"] > 100:
            raise ValueError(f"Job {jid}: weight must not exceed 100")
        operations = job.get("operations")
        if not isinstance(operations, list) or not (1 <= len(operations) <= 12):
            raise ValueError(f"Job {jid}: provide 1–12 operations")
        op_ids = set()
        for op in operations:
            if not isinstance(op, dict) or not isinstance(op.get("id"), str) or not op["id"].strip():
                raise ValueError(f"Job {jid}: invalid operation id")
            if op["id"] in op_ids:
                raise ValueError(f"Job {jid}: duplicate operation id")
            op_ids.add(op["id"])
            dur, eligible = op.get("duration"), op.get("machines")
            if type(dur) is not int or not 1 <= dur <= 1000:
                raise ValueError(f"Job {jid}/{op['id']}: duration must be 1–1000")
            if (not isinstance(eligible, list) or not eligible or
                    any(not isinstance(mid, str) or mid not in ids for mid in eligible) or
                    len(set(eligible)) != len(eligible)):
                raise ValueError(f"Job {jid}/{op['id']}: machines must be valid unique machine IDs")
            num_ops += 1
    if num_ops > 65:
        raise ValueError("This first version supports at most 65 operations per scenario")
    return data


def all_tasks(data: dict) -> list[Task]:
    tasks = []
    for job in data["jobs"]:
        for idx, op in enumerate(job["operations"]):
            tasks.append(Task(f"{job['id']}::{idx}", job["id"], op["id"], idx,
                              op["duration"], tuple(op["machines"])))
    return tasks


def downtime_by_machine(data: dict) -> dict[str, list[tuple[int, int]]]:
    return {m["id"]: sorted((w["start"], w["end"]) for w in m.get("downtime", []))
            for m in data["machines"]}


def horizon(data: dict) -> int:
    total_duration = sum(t.duration for t in all_tasks(data))
    max_anchor = max([j["release"] for j in data["jobs"]] +
                     [w["end"] for m in data["machines"] for w in m.get("downtime", [])] + [0])
    # Valid upper bound: all tasks can run in sequence after every release and outage ends.
    return max_anchor + total_duration + 1
