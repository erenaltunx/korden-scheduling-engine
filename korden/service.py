"""One benchmark pipeline shared by CLI, API and tests."""
from .baseline import dispatch_edd
from .evaluation import evaluate, check_schedule
from .model import validate_scenario
from .engines import optimize_with


def compare(data: dict, time_limit: float = 8.0, engine: str = "milp_highs") -> dict:
    validate_scenario(data)
    baseline = dispatch_edd(data)
    before = evaluate(data, baseline)
    solution = optimize_with(engine, data, time_limit)
    after_schedule = solution["schedule"]
    if after_schedule is not None:
        errors = check_schedule(data, after_schedule)
        if errors:
            raise RuntimeError("Optimizer returned invalid schedule: " + "; ".join(errors))
        after = evaluate(data, after_schedule)
        # A timed-out solver may have an inferior incumbent; compare fairly.
        if (after["weighted_tardiness"], after["makespan"]) > (before["weighted_tardiness"], before["makespan"]):
            solution["solver"]["status"] = "baseline_retained"
            after_schedule = baseline
            after = before
    else:
        after_schedule = baseline
        after = before
        solution["solver"]["status"] = "baseline_retained_no_solution"
    gain = None
    if before["weighted_tardiness"] > 0:
        gain = round(100 * (before["weighted_tardiness"] - after["weighted_tardiness"])
                     / before["weighted_tardiness"], 2)
    return {"schema_version": 1, "engine": engine, "factory": data.get("factory_name", "Untitled factory"),
            "baseline": {"name": "Earliest Due Date (EDD)", "metrics": before, "schedule": baseline},
            "optimized": {"name": "MILP / HiGHS", "metrics": after, "schedule": after_schedule},
            "improvement_percent": gain, "solver": solution["solver"],
            "note": "Benchmark on scenario input; not verified real-world savings."}
