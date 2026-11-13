# Optera — Evidence-first finite-capacity scheduling (November 2026)

## Question and scope
Can an independently validated **MILP/HiGHS production scheduler** reduce weighted tardiness compared with the strongest of **EDD, FIFO, SPT and WSPT** on different small manufacturing-workshop problems?

This is a reproducible **synthetic experiment**, not a live factory pilot, measured cost saving, verified production system or sales claim. The objective is **weighted tardiness**; makespan and modeled setup allowance are **secondary metrics**. Scenarios have integer time units, orders with release dates and due dates, machine eligibility, job precedence and uniform family-changeover gaps. Shift calendars, sequence-specific setup matrices and material constraints remain unsupported.

## Study design
- [Source](../research_lab.py) / [tests](../tests/test_research_lab.py).
- 20 single CNC cells, 20 two-stage CUT+CNC cells, 20 flexible CNC+QC cells (5–7 orders each), and 10 **congested flexible** cells (9–11 orders, with machine outage).
- Identical feasibility conditions for both methods and independent verification of **every emitted schedule**.
- For each scenario choose **the strongest of the four classical rules**: this is deliberately a strong comparator, not an observed manual-planning policy.
- Limit the MILP solver to **0.7 seconds per scenario**, distinguish feasible candidates from mathematically proven optima, and keep the validated baseline when a timed-out MILP candidate is worse. **The final recommendation's gain is not a MILP-only gain**.
- Save per-instance seed, deterministic input SHA-256, raw MILP score, baseline score, recommended plan score, solver status, gap, proof, runtime, setup time and makespan.
- Input digest: **afb16f2955c5c1cd65306614b4aea5379466cb29264d651b5fc25ab8e3a61d2c**.

## Results: 70 synthetic workshops, 462 orders, 807 operations

| Workload family | Instances | Classical | Recommended | Weighted delay reduction | Optima proven |
|---|---:|---:|---:|---:|---:|
| Single CNC | 20 | 839 | 634 | 24.43% | 20/20 |
| Two-stage CUT+CNC | 20 | 1057 | 722 | 31.69% | 20/20 |
| Flexible CNC + QC | 20 | 71 | 35 | 50.70% | 20/20 |
| **Congested flexible** | **10** | **1597** | **1577** | **1.25%** | **0/10** |
| **Overall** | **70** | **3564** | **2968** | **16.72%** | **60/70** |

**Critical context:** Across all 70 instances, 35 improve, 35 tie, 8 use the classical fallback; raw MILP solutions were inferior to classical baselines in those 8 cases. Among flexible CNC instances, 15/20 classical baselines already achieved zero lateness; the apparent 50.70% relative gain is driven by very few instances. This is why subgroup results matter.

Modeled total setup allowance **270 → 219** (descriptive -18.89%, not directly optimized); summed makespans **1877 → 1797** (descriptive -4.26%, not actual factory throughput). Solver-only runtime: p50 **0.093 seconds**, p90 **0.703 seconds**, dependent on runtime hardware and not including UI, input parsing or baseline calculation.

**Main discovery:** difficult 9–11-order flexible jobs caused a sharp decline in gain, with no mathematically proven optima under the 0.7-second budget. We must improve difficult-instance handling before generalizing the earlier 28.13% single-machine result.

## Reproduce and audit

Run using the same code version and dependency environment. Performance timings and feasible incumbent scores may vary across hardware and solver versions, but scenario inputs must produce the same SHA.

~~~bash
python -m pip install -r requirements.txt
python -m pytest -q tests/test_research_lab.py
python research_lab.py --count-per-profile 20 --stress-count 10 --seed-base 230011 --time-limit 0.7 --out artifacts/heterogeneous_workshops
~~~

The GitHub Actions smoke experiment runs a smaller number of seed-fixed cases and uploads the CSV/JSON as a build artifact. The full 70-scenario research CSV and JSON are available as separate study deliverables, not falsely inferred from a small CI run.

## Next gates
1. **Solver-quality study:** rerun the *same 10 congested instances* with controlled 0.7/2/5-second budgets; compare objective, nonzero gap, proof rate and actual runtime, including negative results.
2. **Mathematical formulation:** study tighter big-M bounds and CP-SAT as controlled alternatives, only if matched inputs/verification show real improvements.
3. **Manufacturing fidelity:** add shift calendars only with baseline, optimizer, independent verifier, negative tests and an operator-facing explanation.
4. **Independent external benchmark:** add more heterogeneous public job-shop instances with known provenance, while clearly distinguishing their makespan objective from this weighted-tardiness study.
5. **Real-data pilot:** only claim realized operational savings after consented anonymized manufacturing data and follow-up measurements.

## CV-safe formulation
> Built a Python/SciPy-HiGHS MILP production scheduler and validated schedules across **807 operations in 70 reproducible synthetic workshop scenarios**. A guarded optimization-or-baseline policy reduced aggregate weighted tardiness **16.7%** versus the strongest of four classical methods; **60/70** instances achieved proven optimality.

Do **not** call this 16.7% factory savings or claim that the solver independently improved all 70 scenarios.
