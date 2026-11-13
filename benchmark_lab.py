"""Research-grade comparison against four classical dispatching rules.

All benchmarks use deterministic seeds and the SAME scenario input for all
policies and for the MILP solver. No cherry-picked single baseline.
"""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
from statistics import mean, median
from optera.baseline import POLICIES, dispatch
from optera.evaluation import evaluate, check_schedule
from optera.generator import generate_factory
from optera.optimizer import optimize


def run_lab(count: int = 60, jobs: int = 5, time_limit: float = 2.0,
            start_seed: int = 100) -> dict:
    if type(count) is not int or not 1 <= count <= 200:
        raise ValueError("count must be 1–200")
    if type(start_seed) is not int or start_seed < 0:
        raise ValueError("start_seed must be a nonnegative integer")
    if type(jobs) is not int or not 2 <= jobs <= 12:
        raise ValueError("jobs must be 2–12")
    if not (0.5 <= time_limit <= 60):
        raise ValueError("time_limit must be 0.5–60 seconds")
    rows = []
    for seed in range(start_seed, start_seed+count):
        data = generate_factory(seed, jobs)
        heuristics = {}
        for policy in POLICIES:
            schedule = dispatch(data, policy)
            metrics = evaluate(data, schedule)  # Independent feasibility check.
            heuristics[policy] = metrics
        strongest = min(POLICIES, key=lambda policy: (heuristics[policy]["weighted_tardiness"],
                                                     heuristics[policy]["makespan"], policy))
        before = heuristics[strongest]
        solution = optimize(data, time_limit)
        candidate = solution["schedule"]
        fallback = candidate is None
        if candidate is not None:
            errors = check_schedule(data, candidate)
            if errors:
                raise RuntimeError("Solver returned infeasible schedule: " + "; ".join(errors))
            candidate_metrics = evaluate(data, candidate)
            if (candidate_metrics["weighted_tardiness"], candidate_metrics["makespan"]) > \
               (before["weighted_tardiness"], before["makespan"]):
                fallback = True
        after = before if fallback else candidate_metrics
        base_val = before["weighted_tardiness"]
        after_val = after["weighted_tardiness"]
        rows.append({
            "seed": seed, "jobs": jobs, "operations": jobs*3,
            **{f"{p}_weighted_tardiness": heuristics[p]["weighted_tardiness"] for p in POLICIES},
            "best_policy": strongest, "best_policy_weighted_tardiness": base_val,
            "delivered_weighted_tardiness": after_val,
            "best_policy_makespan": before["makespan"], "delivered_makespan": after["makespan"],
            "improvement_percent": round(100*(base_val-after_val)/base_val,2) if base_val else None,
            "fallback": fallback, "solver_status": solution["solver"]["status"],
            "optimality_proven": solution["solver"]["optimality_proven"],
            "relative_mip_gap": solution["solver"].get("relative_mip_gap"),
            "solve_seconds": solution["solver"]["solve_seconds"]
        })
    nonzero = [r["improvement_percent"] for r in rows if r["improvement_percent"] is not None]
    btotal = sum(r["best_policy_weighted_tardiness"] for r in rows)
    atotal = sum(r["delivered_weighted_tardiness"] for r in rows)
    return {
        "methodology": {
            "data_origin": "synthetic deterministic", "seeds": [start_seed, start_seed+count-1],
            "jobs_per_instance": jobs, "operations_per_instance": jobs*3,
            "policies": POLICIES, "comparison": "MILP with fallback vs strongest of four feasible policies",
            "objective": "weighted tardiness, then makespan", "time_limit_seconds": time_limit,
            "note": "Synthetic scheduling experiments, not real-world cost savings. Optimality applies to modeled problem."},
        "summary": {
            "instances": count, "total_jobs": count*jobs, "total_operations": count*jobs*3,
            "optimality_proven": sum(r["optimality_proven"] for r in rows),
            "fallbacks": sum(r["fallback"] for r in rows),
            "wins": sum(r["delivered_weighted_tardiness"] < r["best_policy_weighted_tardiness"] for r in rows),
            "ties": sum(r["delivered_weighted_tardiness"] == r["best_policy_weighted_tardiness"] for r in rows),
            "baseline_nonzero": len(nonzero),
            "pooled_best_policy_weighted_tardiness": btotal,
            "pooled_delivered_weighted_tardiness": atotal,
            "pooled_improvement_percent": round(100*(btotal-atotal)/btotal,2) if btotal else None,
            "mean_improvement_percent_nonzero": round(mean(nonzero),2) if nonzero else None,
            "median_improvement_percent_nonzero": round(median(nonzero),2) if nonzero else None,
            "mean_solve_seconds": round(mean(r["solve_seconds"] for r in rows),3),
        }, "rows": rows,
    }


def main():
    parser = argparse.ArgumentParser(description="OPTERA held-out four-policy scheduling benchmark")
    parser.add_argument("--count", type=int, default=60)
    parser.add_argument("--jobs", type=int, default=5)
    parser.add_argument("--time-limit", type=float, default=2.0)
    parser.add_argument("--start-seed", type=int, default=100)
    parser.add_argument("--out", default="artifacts/optera_lab")
    args = parser.parse_args()
    try:
        report=run_lab(args.count,args.jobs,args.time_limit,args.start_seed)
    except ValueError as exc:
        parser.error(str(exc))
    path=Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.with_suffix(".json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    with path.with_suffix(".csv").open("w",encoding="utf-8",newline="") as fh:
        writer=csv.DictWriter(fh,fieldnames=list(report["rows"][0]));writer.writeheader();writer.writerows(report["rows"])
    print(json.dumps(report["summary"],indent=2))
    print("CSV/JSON reports:",path)


if __name__ == "__main__":
    main()
