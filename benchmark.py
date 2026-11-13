"""Run reproducible single-scenario experiment. Example: python benchmark.py samples/assembly_cell.json"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from korden.service import compare


def main():
    p = argparse.ArgumentParser(description="KORDEN: EDD vs. MILP benchmark")
    p.add_argument("scenario", nargs="?", default="samples/assembly_cell.json")
    p.add_argument("--time-limit", type=float, default=10)
    p.add_argument("--out", help="Optional JSON results path")
    args = p.parse_args()
    scenario = json.loads(Path(args.scenario).read_text(encoding="utf-8"))
    result = compare(scenario, args.time_limit)
    print(f"Factory: {result['factory']}")
    print(f"Solver: {result['solver']['status']} ({result['solver']['solve_seconds']:.3f}s)")
    print(f"{'Metric':24} {'EDD':>12} {'MILP':>12}")
    for key in ("weighted_tardiness", "total_tardiness", "late_jobs", "makespan"):
        print(f"{key:24} {result['baseline']['metrics'][key]:>12} {result['optimized']['metrics'][key]:>12}")
    print(f"Improvement, weighted tardiness: {result['improvement_percent']}%")
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"Results saved to {args.out}")


if __name__ == "__main__":
    main()
