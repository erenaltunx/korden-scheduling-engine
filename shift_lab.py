"""Repeatable synthetic work-calendar validation; never assert factory savings."""
import argparse
import json
from pathlib import Path
from optera.baseline import dispatch
from optera.optimizer import optimize
from optera.evaluation import check_schedule, evaluate

ROOT = Path(__file__).resolve().parent


def run_demo():
    data = json.loads((ROOT / "samples" / "shift_cell.json").read_text(encoding="utf-8"))
    baseline = dispatch(data, "edd")
    result = optimize(data, time_limit=8)
    if result["schedule"] is None:
        raise RuntimeError("No feasible plan returned")
    before = evaluate(data, baseline)
    after = evaluate(data, result["schedule"])
    return {
        "synthetic": True, "shift_aware": True,
        "working_periods": data["machines"][0]["working_windows"],
        "baseline_feasible": not check_schedule(data, baseline),
        "optimized_feasible": not check_schedule(data, result["schedule"]),
        "baseline_weighted_tardiness": before["weighted_tardiness"],
        "optimized_weighted_tardiness": after["weighted_tardiness"],
        "baseline_schedule": baseline,
        "optimized_schedule": result["schedule"],
        "solver": result["solver"],
        "note": "Synthetic hours, not realized industrial savings"
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("artifacts/shift_evidence.json"))
    args = parser.parse_args()
    report = run_demo()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"baseline": report["baseline_weighted_tardiness"],
                      "optimized": report["optimized_weighted_tardiness"],
                      "feasible": report["optimized_feasible"]}, indent=2))


if __name__ == "__main__":
    main()
