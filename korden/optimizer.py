"""Real mixed-integer scheduling optimization via SciPy/HiGHS.

Model: job precedence; release times; optional machine assignments; pairwise
machine disjunctions; fixed maintenance windows; weighted tardiness + makespan.
All times integer hours. Jobs are non-preemptive. No setup/changeover yet.
"""
from __future__ import annotations
from dataclasses import dataclass
from itertools import combinations
from time import perf_counter
import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_array
from .model import all_tasks, downtime_by_machine, horizon, validate_scenario


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


def optimize(data: dict, time_limit: float = 8.0) -> dict:
    validate_scenario(data)
    if not (0.5 <= time_limit <= 60):
        raise ValueError("Solver time limit must be between 0.5 and 60 seconds")
    tasks = all_tasks(data)
    by_job = {j["id"]: j for j in data["jobs"]}
    windows = downtime_by_machine(data)
    h = horizon(data)
    big_m = h + max(t.duration for t in tasks)
    m = LinearModel()
    starts = {t.key: m.var(f"start:{t.key}", 0, h - t.duration) for t in tasks}
    assignments = {}
    for t in tasks:
        for machine in t.machines:
            assignments[(t.key, machine)] = m.var(f"machine:{t.key}:{machine}")
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
        eligible = [t for t in tasks if machine in t.machines]
        for a, b in combinations(eligible, 2):
            z = m.var(f"order:{machine}:{a.key}:{b.key}")
            xa, xb = assignments[(a.key, machine)], assignments[(b.key, machine)]
            # z=1 -> a precedes b; z=0 -> b precedes a, conditional on both selected.
            m.row({starts[a.key]: 1, starts[b.key]: -1,
                   xa: big_m, xb: big_m, z: big_m}, ub=3*big_m - a.duration)
            m.row({starts[b.key]: 1, starts[a.key]: -1,
                   xa: big_m, xb: big_m, z: -big_m}, ub=2*big_m - b.duration)
        for task in eligible:
            x = assignments[(task.key, machine)]
            for k, (ds, de) in enumerate(windows[machine]):
                before = m.var(f"before_downtime:{task.key}:{machine}:{k}")
                m.row({starts[task.key]: 1, before: big_m, x: big_m},
                      ub=ds + 2*big_m - task.duration)
                m.row({starts[task.key]: -1, before: -big_m, x: big_m},
                      ub=big_m - de)
    # Scaling makespan tie-break guarantees improving 1 unit weighted tardiness
    # is always preferable to any change in makespan (bounded by h).
    makespan = m.var("makespan", 0, h, cost=1.0)
    for task in tasks:
        m.row({makespan: 1, starts[task.key]: -1}, lb=task.duration)
    for job in data["jobs"]:
        last_key = f"{job['id']}::{len(job['operations'])-1}"
        duration = tasks[next(i for i, t in enumerate(tasks) if t.key == last_key)].duration
        tard = m.var(f"tardiness:{job['id']}", 0, h, cost=(h+1)*job["weight"])
        m.row({tard: 1, starts[last_key]: -1}, lb=duration - job["due"])
    clock = perf_counter()
    result = m.solve(time_limit)
    elapsed = perf_counter() - clock
    metadata = {"status": "optimal" if result.status == 0 else
                          "time_limit_with_solution" if result.x is not None else "no_feasible_solution",
                "solver": "SciPy MILP / HiGHS", "solve_seconds": round(elapsed, 3),
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
        schedule.append({"key": t.key, "job": t.job_id, "operation": t.operation_id,
                         "machine": chosen, "start": start, "end": start + t.duration,
                         "duration": t.duration})
    return {"schedule": sorted(schedule, key=lambda r: (r["start"], r["machine"], r["key"])),
            "solver": metadata}
