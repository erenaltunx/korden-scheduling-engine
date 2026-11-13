"""Real mixed-integer scheduling optimization via SciPy/HiGHS.

Model: job precedence; release times; optional machine assignments; pairwise
machine disjunctions; fixed maintenance windows; weighted tardiness + makespan.
Times use the scenario integer grid. Jobs are non-preemptive. v0.12 provides tested tight/legacy formulations for controlled research.
"""
from __future__ import annotations
from dataclasses import dataclass
from itertools import combinations
from time import perf_counter
import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_array
from .model import (all_tasks, downtime_by_machine, horizon, validate_scenario,
                    changeover_by_machine, changeover_gap)


@dataclass
class Variable:
    name: str
    lb: float
    ub: float
    integer: bool
    cost: float


class LinearModel:
    def __init__(self):
        self.vars: list[Variable] = []
        self.rows: list[dict[int, float]] = []
        self.lows: list[float] = []
        self.highs: list[float] = []

    def var(self, name, lb=0, ub=1, integer=True, cost=0.0) -> int:
        i = len(self.vars)
        self.vars.append(Variable(name, lb, ub, integer, cost))
        return i

    def row(self, terms: dict[int, float], lb=-np.inf, ub=np.inf):
        self.rows.append({k: v for k, v in terms.items() if v})
        self.lows.append(lb)
        self.highs.append(ub)

    def solve(self, time_limit: float):
        i_rows, i_cols, values = [], [], []
        for idx, row in enumerate(self.rows):
            for col, val in row.items():
                i_rows.append(idx)
                i_cols.append(col)
                values.append(val)
        # SciPy HiGHS requires int32 or int64 sparse indices, not Python object arrays.
        mat = coo_array((np.asarray(values, dtype=np.float64),
                         (np.asarray(i_rows, dtype=np.int32),
                          np.asarray(i_cols, dtype=np.int32))),
                        shape=(len(self.rows), len(self.vars))).tocsr()
        return milp(c=np.array([v.cost for v in self.vars]),
                    integrality=np.array([int(v.integer) for v in self.vars], dtype=np.int32),
                    bounds=Bounds([v.lb for v in self.vars], [v.ub for v in self.vars]),
                    constraints=LinearConstraint(mat, self.lows, self.highs),
                    options={"time_limit": time_limit, "mip_rel_gap": 0.0})


def optimize(data: dict, time_limit: float = 8.0, *,
             fixed_operations: dict[str, dict] | None = None,
             not_before: int = 0, objective: str = "weighted_tardiness",
             reference_schedule: list[dict] | None = None,
             tardiness_budget: int | None = None,
             formulation: str = "tight") -> dict:
    validate_scenario(data)
    if formulation not in {"tight", "legacy"}:
        raise ValueError("Formulation must be tight or legacy")
    if not (0.5 <= time_limit <= 60):
        raise ValueError("Solver time limit must be between 0.5 and 60 seconds")
    if objective not in {"weighted_tardiness", "makespan", "stability"}:
        raise ValueError("Unknown optimization objective")
    if objective == "stability":
        if not isinstance(reference_schedule, list) or type(tardiness_budget) is not int or tardiness_budget < 0:
            raise ValueError("Stability optimization requires a reference schedule and nonnegative integer tardiness budget")
        # The old plan may conflict with the *new* outage. It is intentionally
        # a comparison target, not necessarily feasible after a disruption.
        ref_keys = [r.get('key') for r in reference_schedule if isinstance(r, dict)]
        expected = {task.key for task in all_tasks(data)}
        if len(ref_keys) != len(expected) or set(ref_keys) != expected:
            raise ValueError("Reference schedule must contain each operation exactly once")
        if any(type(r.get('start')) is not int or r['start'] < 0 or
               not isinstance(r.get('machine'), str) or
               not isinstance(r.get('support_resources', []), list)
               for r in reference_schedule):
            raise ValueError("Reference schedule has invalid start/resource fields")
    elif reference_schedule is not None or tardiness_budget is not None:
        raise ValueError("Reference schedule and tardiness budget apply only to the stability objective")
    if type(not_before) is not int or not 0 <= not_before <= 10000:
        raise ValueError("not_before must be an integer hour between 0 and 10000")
    fixed_operations = fixed_operations or {}
    tasks = all_tasks(data)
    known_keys = {t.key for t in tasks}
    if set(fixed_operations) - known_keys:
        raise ValueError("Fixed operations contain unknown task keys")
    by_job = {j["id"]: j for j in data["jobs"]}
    windows = downtime_by_machine(data)
    changeovers = changeover_by_machine(data)
    h = horizon(data)
    # Recovery may begin well after the original estimated completion horizon.
    # Preserve enough time for all remaining work beyond the replanning instant.
    if not_before:
        h = max(h, not_before + sum(t.duration for t in tasks) +
                max(changeovers.values(), default=0) * max(0, len(tasks)-1) + 1)
    big_m = h + max(t.duration for t in tasks)
    # Earliest starts from release dates + job precedence. Latest starts reserve
    # enough horizon for all remaining operations in the *same* job. These
    # bounds are mathematically valid even when machine availability differs.
    # Tight mode only: legacy mode is retained as a paired-study control.
    start_bounds: dict[str, tuple[int, int]] = {}
    if formulation == "tight":
        for job in data["jobs"]:
            ops = job["operations"]
            elapsed = 0
            remaining = sum(op["duration"] for op in ops)
            for index, op in enumerate(ops):
                key = f"{job['id']}::{index}"
                lower = max(not_before, job["release"] + elapsed)
                upper = h - remaining
                if key in fixed_operations:
                    # Frozen work may legitimately precede the rescheduling
                    # boundary; preserve its exact timing in the MILP.
                    lower = upper = fixed_operations[key]["start"]
                start_bounds[key] = (lower, upper)
                elapsed += op["duration"]
                remaining -= op["duration"]
    m = LinearModel()
    starts = {}
    for t in tasks:
        if t.key in fixed_operations:
            start = fixed_operations[t.key]["start"]
            if type(start) is not int or not 0 <= start <= h - t.duration:
                raise ValueError(f"Invalid fixed start for {t.key}")
            starts[t.key] = m.var(f"start:{t.key}", start, start)
        else:
            lb, ub = start_bounds[t.key] if formulation == "tight" else (not_before, h - t.duration)
            starts[t.key] = m.var(f"start:{t.key}", lb, ub)
    assignments = {}
    for t in tasks:
        for machine in t.machines:
            if t.key in fixed_operations:
                choice = int(fixed_operations[t.key]["machine"] == machine)
                assignments[(t.key, machine)] = m.var(f"machine:{t.key}:{machine}", choice, choice)
            else:
                assignments[(t.key, machine)] = m.var(f"machine:{t.key}:{machine}")
        # Choose exactly one qualified support from the optional resource pool.
        # This is a real MILP decision, not a greedy pre-selection.
        if t.support_options:
            if t.key in fixed_operations:
                chosen_supports = set(fixed_operations[t.key].get('support_resources', []))
                if len(chosen_supports & set(t.support_options)) != 1:
                    raise ValueError(f"Invalid fixed support assignment for {t.key}")
            for supporting in t.support_options:
                choice = int(supporting in chosen_supports) if t.key in fixed_operations else None
                assignments[(t.key, supporting)] = m.var(
                    f"support_choice:{t.key}:{supporting}",
                    choice if choice is not None else 0,
                    choice if choice is not None else 1)
            m.row({assignments[(t.key, supporting)]: 1 for supporting in t.support_options}, lb=1, ub=1)
        # Fixed support reservations remain mandatory.
        for supporting in t.support_resources:
            assignments[(t.key, supporting)] = m.var(
                f"reserved:{t.key}:{supporting}", 1, 1)
        m.row({assignments[(t.key, mid)]: 1 for mid in t.machines}, lb=1, ub=1)
        if t.index == 0:
            m.row({starts[t.key]: 1}, lb=by_job[t.job_id]["release"])
        if t.index:
            prev = f"{t.job_id}::{t.index - 1}"
            prev_duration = next(op.duration for op in tasks if op.key == prev)
            m.row({starts[t.key]: 1, starts[prev]: -1}, lb=prev_duration)
    # For each pair eligible on same machine, require one task before the other
    # if and only if both choose that machine.
    for machine in windows:
        eligible = [t for t in tasks if machine in t.machines or machine in t.support_resources or machine in t.support_options]
        for a, b in combinations(eligible, 2):
            z = m.var(f"order:{machine}:{a.key}:{b.key}")
            xa, xb = assignments[(a.key, machine)], assignments[(b.key, machine)]
            # Setup applies only to consecutive use of the PRIMARY machine.
            # This uniform family-switch rule obeys triangle inequality; hence
            # the pairwise ordering model also enforces every actual changeover.
            a_to_b = (changeover_gap(a.setup_family, b.setup_family, changeovers[machine])
                      if machine in a.machines and machine in b.machines else 0)
            b_to_a = (changeover_gap(b.setup_family, a.setup_family, changeovers[machine])
                      if machine in a.machines and machine in b.machines else 0)
            # Pair-specific valid disjunction constants avoid the extremely
            # weak global horizon-based relaxation for congested cells.
            # If an operation cannot start early/late because of precedence,
            # the inactive pair inequality needs much less slack.
            if formulation == "tight":
                la, ua = start_bounds[a.key]
                lb, ub = start_bounds[b.key]
                m_ab = max(0, ua - lb + a.duration + a_to_b)
                m_ba = max(0, ub - la + b.duration + b_to_a)
            else:
                m_ab = m_ba = big_m
            m.row({starts[a.key]: 1, starts[b.key]: -1,
                   xa: m_ab, xb: m_ab, z: m_ab}, ub=3*m_ab - a.duration - a_to_b)
            m.row({starts[b.key]: 1, starts[a.key]: -1,
                   xa: m_ba, xb: m_ba, z: -m_ba}, ub=2*m_ba - b.duration - b_to_a)
        for task in eligible:
            x = assignments[(task.key, machine)]
            for k, (ds, de) in enumerate(windows[machine]):
                before = m.var(f"before_downtime:{task.key}:{machine}:{k}")
                if formulation == "tight":
                    lb, ub = start_bounds[task.key]
                    m_before = max(0, ub + task.duration - ds)
                    m_after = max(0, de - lb)
                else:
                    m_before = m_after = big_m
                m.row({starts[task.key]: 1, before: m_before, x: m_before},
                      ub=ds + 2*m_before - task.duration)
                m.row({starts[task.key]: -1, before: -m_after, x: m_after},
                      ub=m_after - de)
    # Scaling makespan tie-break guarantees improving 1 unit weighted tardiness
    # is always preferable to any change in makespan (bounded by h).
    makespan_lb = (max((start_bounds[t.key][0] + t.duration for t in tasks), default=0)
                   if formulation == "tight" else 0)
    makespan = m.var("makespan", makespan_lb, h, cost=1.0)
    tardiness_vars = {}
    for task in tasks:
        m.row({makespan: 1, starts[task.key]: -1}, lb=task.duration)
    for job in data["jobs"]:
        last_key = f"{job['id']}::{len(job['operations'])-1}"
        duration = tasks[next(i for i, t in enumerate(tasks) if t.key == last_key)].duration
        earliest_completion = start_bounds[last_key][0] + duration if formulation == "tight" else 0
        tard_lb = max(0, earliest_completion - job['due']) if formulation == "tight" else 0
        tard = m.var(f"tardiness:{job['id']}", tard_lb, h, cost=(h+1)*job["weight"] if objective == "weighted_tardiness" else 0.0)
        tardiness_vars[job['id']] = tard
        m.row({tard: 1, starts[last_key]: -1}, lb=duration - job["due"])
    if objective == "stability":
        assert tardiness_budget is not None and reference_schedule is not None
        # Epsilon-constraint: protect the customer-service quality of the first
        # scheduling stage, then minimize disruption to previously issued plans.
        m.row({tardiness_vars[j['id']]: j['weight'] for j in data['jobs']}, ub=tardiness_budget)
        previous = {r['key']: r for r in reference_schedule}
        for task in tasks:
            if task.key in fixed_operations:
                continue
            reference = previous[task.key]
            shift = m.var(f"start_change:{task.key}", 0, h, cost=h+1)
            m.row({shift: 1, starts[task.key]: -1}, lb=-reference['start'])
            m.row({shift: 1, starts[task.key]: 1}, lb=reference['start'])
            previous_machine = reference['machine']
            for machine in task.machines:
                if machine != previous_machine:
                    m.vars[assignments[(task.key, machine)]].cost = 5*(h+1)
            previous_support = set(reference.get('support_resources', []))
            for supporter in task.support_options:
                if supporter not in previous_support:
                    m.vars[assignments[(task.key, supporter)]].cost = 5*(h+1)
    clock = perf_counter()
    result = m.solve(time_limit)
    elapsed = perf_counter() - clock
    metadata = {"status": "optimal" if result.status == 0 else
                          "time_limit_with_solution" if result.x is not None else "no_feasible_solution",
                "solver": "SciPy MILP / HiGHS", "objective": objective,
                "formulation": formulation,
                "frozen_operations": len(fixed_operations),
                "tardiness_budget": tardiness_budget if objective == "stability" else None,
                "stability_cost": "absolute start shifts + 5 * resource changes" if objective == "stability" else None,
                "solve_seconds": round(elapsed, 3),
                "model_variables": len(m.vars), "model_constraints": len(m.rows),
                "optimality_proven": result.status == 0,
                "relative_mip_gap": float(getattr(result, "mip_gap", 0) or 0)
                                    if result.x is not None else None}
    if result.x is None:
        return {"schedule": None, "solver": metadata}
    schedule = []
    for t in tasks:
        chosen = max(t.machines, key=lambda mid: result.x[assignments[t.key, mid]])
        start = int(round(result.x[starts[t.key]]))
        row = {"key": t.key, "job": t.job_id, "operation": t.operation_id,
               "machine": chosen, "start": start, "end": start + t.duration,
               "duration": t.duration}
        if t.support_resources or t.support_options:
            row['support_resources'] = [*t.support_resources, *(
                [max(t.support_options, key=lambda rid: result.x[assignments[(t.key, rid)]])]
                if t.support_options else [])]
        schedule.append(row)
    return {"schedule": sorted(schedule, key=lambda r: (r["start"], r["machine"], r["key"])),
            "solver": metadata}
