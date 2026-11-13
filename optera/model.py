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
    support_resources: tuple[str, ...] = ()
    support_options: tuple[str, ...] = ()
    setup_family: str | None = None


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
    changeover = {}
    for m in machines:
        if not isinstance(m, dict) or not isinstance(m.get("id"), str) or not m["id"].strip():
            raise ValueError("Every machine needs a non-empty id")
        mid = m["id"]
        if mid in ids:
            raise ValueError(f"Duplicate machine: {mid}")
        ids.add(mid)
        setup = m.get("changeover_time", 0)
        if type(setup) is not int or not 0 <= setup <= 120:
            raise ValueError(f"Machine {mid}: changeover_time must be an integer 0–120")
        changeover[mid] = setup
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
            family = op.get('setup_family')
            if family is not None and (not isinstance(family, str) or not family.strip() or len(family) > 40):
                raise ValueError(f"Job {jid}/{op['id']}: setup_family must be a non-empty string (max 40)")
            if family is None and any(changeover[mid] for mid in eligible):
                raise ValueError(f"Job {jid}/{op['id']}: setup_family required on changeover-enabled machines")
            supports = op.get('support_resources', [])
            if (not isinstance(supports, list) or
                    any(not isinstance(r, str) or r not in ids for r in supports) or
                    len(supports) != len(set(supports))):
                raise ValueError(f"Job {jid}/{op['id']}: support_resources must be unique known resource IDs")
            if set(supports) & set(eligible):
                raise ValueError(f"Job {jid}/{op['id']}: support resources cannot also be candidate primary machines")
            choices = op.get('support_options', [])
            if (not isinstance(choices, list) or any(not isinstance(r, str) or r not in ids for r in choices)
                    or len(choices) != len(set(choices)) or len(choices) > 12):
                raise ValueError(f"Job {jid}/{op['id']}: support_options must be unique known resource IDs")
            if set(choices) & (set(eligible) | set(supports)):
                raise ValueError(f"Job {jid}/{op['id']}: support_options cannot include primary or fixed support resources")
            num_ops += 1
    if num_ops > 65:
        raise ValueError("This first version supports at most 65 operations per scenario")
    return data


def all_tasks(data: dict) -> list[Task]:
    tasks = []
    for job in data["jobs"]:
        for idx, op in enumerate(job["operations"]):
            tasks.append(Task(f"{job['id']}::{idx}", job["id"], op["id"], idx,
                              op["duration"], tuple(op["machines"]),
                              tuple(op.get("support_resources", [])), tuple(op.get("support_options", [])),
                              op.get('setup_family')))
    return tasks


def downtime_by_machine(data: dict) -> dict[str, list[tuple[int, int]]]:
    return {m["id"]: sorted((w["start"], w["end"]) for w in m.get("downtime", []))
            for m in data["machines"]}


def changeover_by_machine(data: dict) -> dict[str, int]:
    return {m['id']: m.get('changeover_time', 0) for m in data['machines']}


def changeover_gap(family_before: str | None, family_after: str | None, setup_time: int) -> int:
    # Uniform family-switch penalty obeys triangle inequality, so pairwise MILP
    # non-overlap constraints are equivalent to consecutive changeovers.
    return setup_time if setup_time and family_before != family_after else 0


def horizon(data: dict) -> int:
    total_duration = sum(t.duration for t in all_tasks(data))
    max_anchor = max([j["release"] for j in data["jobs"]] +
                     [w["end"] for m in data["machines"] for w in m.get("downtime", [])] + [0])
    # Valid upper bound: all tasks can run in sequence after every release and outage ends.
    tasks = all_tasks(data)
    max_setup = max(changeover_by_machine(data).values(), default=0)
    # A serial schedule is always a valid time upper bound, including every
    # possible switch between consecutive operations.
    return max_anchor + total_duration + max(0, len(tasks) - 1) * max_setup + 1
