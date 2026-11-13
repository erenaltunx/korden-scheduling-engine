# Optera v0.11 — Time-budget sensitivity on congested machining cells

**Research question:** Does providing the existing SciPy/HiGHS MILP more time produce materially better **feasible schedules** on the exact same 10 congested small machining workshops, and does it prove optimality?

## Why this study exists

Previous v0.10 tests yielded only 1.25% aggregate weighted-tardiness reduction and zero optimality proofs on the congested subset under a 0.7-second limit. We investigate the bottleneck **before adding another solver or broadening industries**. The project stays a finite-capacity CNC work-cell scheduling portfolio project, not an ERP/MES product.

## Reproduction

```bash
python -m pytest -q tests/test_solver_budget_lab.py
python solver_budget_lab.py --count 10 --seed-base 230011 --budgets 0.7,2,5 --out artifacts/solver_budget
```

Inputs are the same **10 fixed-seed congested instances** at all three budgets, totaling **102 synthetic work orders and 204 operations per budget**. The common classical comparator is the **best** of EDD/FIFO/SPT/WSPT for each instance; machine feasibility and schedule validity are independently checked by `research_lab.run_instance`. Results save separate raw MILP incumbents and *guarded recommendations* (best feasible MILP or best feasible classical baseline); the fallback is **not** counted as MILP improvement. Runs are independent, not warm-started across budgets. Different time limits **do not guarantee monotonic improvement**, and run-to-run numerical results may vary due to machine load and timing.

| Per-instance SciPy/HiGHS time budget | 0.7s | 2s | 5s |
|---|---:|---:|---:|
| Strongest classical aggregate weighted tardiness | 1,597 | 1,597 | 1,597 |
| Guarded recommendation weighted tardiness | 1,569 | 1,452 | 1,265 |
| Aggregate reduction vs classical | 1.75% | 9.08% | **20.79%** |
| Raw solver feasible candidates | 10/10 | 10/10 | 10/10 |
| Raw solver worse than best classical | 7/10 | 4/10 | 0/10 |
| Classical fallbacks retained | 7/10 | 4/10 | 0/10 |
| Mathematically proven optima | **0/10** | **0/10** | **0/10** |
| Median solver runtime | 0.706s | 2.004s | 5.005s |
| 90th-percentile solver runtime | 0.708s | 2.010s | 5.008s |

Source: [per-case CSV](benchmarks/solver_budget_v1.csv) and [full JSON with environment and seed hashes](benchmarks/solver_budget_v1.json). Generated locally using Python 3.13.5 / SciPy 1.17.0 on Linux. Input SHA-256 digest for the paired 10 workloads: `e392f9fce70b4d5fd4add53008d8bd082675a5e4f351e78262fc6ffdf57a42c5`. The generator was independently cross-checked to yield exactly the historical v0.10 70-case input digest.

### What is and isn't proven

1. More solver time led to more effective *guarded recommendations* on these small synthetic scenarios. The 5-second runs improve all 10 cases relative to the strongest classic dispatch policy; the improvement is not observed factory savings.
2. **Proofs remain 0/10 even at 5 seconds**, and gaps remain large: we can report feasible schedules but cannot claim mathematically optimal plans on these congested problems.
3. Differences vs v0.10's previously published 0.7-second value (1.25% vs this run's 1.75%) highlight sensitivity to hardware, runtime and solver timing. The report deliberately preserves both rather than overwriting history.
4. This is a **parameter sensitivity experiment**, not a new algorithm, commercially deployed result, generalizable efficiency guarantee or evidence of large-scale scalability.

## Acceptance gates / next engineering work

- **P1 — Verified reproducibility:** CI must execute at least two fixed seeds across two budgets, validate paired workload hashes, require fallback safety, and upload artifacts. Pass/fail must not be tied to an exact time-limited objective value.
- **P2 — Stronger mathematical formulation:** test bounded start windows and valid inequalities against independent feasibility checks, with a before/after comparison on the same seeds and budgets. Don't assume theoretical tightening makes HiGHS faster.
- **P3 — Benchmarked time–quality tradeoffs:** quantify p50/p90 *end-to-end* runtime, objective quality, solver MIP gap, proof rate and memory limits; expand beyond 10 congested synthetic cases.
- **P4 — Physical realism:** only after improving computational quality, add shift calendars with independent constraint validation and negative tests.
- **P5 — Real data:** no measured operational savings or real customer validation until a permissioned manufacturing pilot is actually completed.

**CV caveat:** The 20.79% is an aggregate *synthetic benchmark result at a 5-second budget*, against the strongest of four algorithms, for a validated MILP-or-baseline policy. It is not a proven optimum and is not evidence of real industrial savings. Do not add an unqualified percentage to a CV.
