# Optera v0.12 — Production scheduling: local search and MILP experiment

## Engineering question

Can a small, deterministic scheduling neighborhood search improve production plans on the congested job-shop problems where time-limited mixed-integer programming struggles, without reducing mathematical or reporting integrity?

**Product focus:** high-mix, low-volume CNC / fabrication cells, not general-purpose ERP. The objective is **weighted job tardiness** (not monetary savings or throughput). Real production data is not included.

## What we developed

1. **MILP/HiGHS formulation tightening:** derive valid earliest/latest operation start bounds using release dates and sequential job precedence; use valid pair-specific big-M constants for disjunctive capacity and downtime; keep the original model available as the `legacy` control. Correct the replanning horizon when a requested rescheduling clock is beyond the original horizon. This improves mathematical formulation quality, but it is **not a guaranteed solver acceleration**.
2. **Deterministic neighborhood search:** start with four conventional priority orders; iteratively test swap/insertion neighbors, respecting the same capacity, machine eligibility, setup, downtime and precedence rules as classical scheduling. Limit the number of evaluated candidate orders (`150` in this experiment).
3. **Safe hybrid selection:** independently validate the local-search and HiGHS plans, select the better feasible plan by weighted tardiness then makespan. **Only the MILP solution can establish an optimality certificate.** If no MILP certificate is available, the selected plan remains *feasible, unproven*.
4. **Audit trail:** retain original input SHA-256, algorithm selected, raw MILP score and gap, local-search evaluations and runtime, total end-to-end wall clock, and per-scenario CSV/JSON.

## Reproduce

```bash
python -m pip install -r requirements.txt
python -m pytest -q tests/test_formulation_tight.py tests/test_hybrid_planning.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python hybrid_lab.py --count 10 --seed 230011 --limit 0.7 --evaluations 150 --profiles single_cell,two_stage,flexible_cell,congested_cell --out artifacts/hybrid_40
```

Generated and reviewed artifacts are archived at [`benchmarks/hybrid_40_v012.csv`](benchmarks/hybrid_40_v012.csv) and [`benchmarks/hybrid_40_v012.json`](benchmarks/hybrid_40_v012.json).

## Paired 40-workshop experiment

| Workload family | Simulated work orders | Operations | Best classical weighted tardiness | Hybrid weighted tardiness | Reduction | MILP optimum proof |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Single-machine CNC | 61 | 61 | 550 | 422 | 23.27% | 10 / 10 |
| Two-stage CUT + CNC | 61 | 122 | 604 | 400 | 33.77% | 10 / 10 |
| Flexible CNC + QC | 57 | 114 | 6 | 6 | 0.00% | 10 / 10 |
| Congested flexible CNC | 102 | 204 | 1597 | 1304 | 18.35% | 0 / 10 |
| **All** | **281** | **501** | **2757** | **2132** | **22.67%** | **30 / 40** |

**25 of 40 instances improve; 15 tie.** The hybrid selected local search in 39/40 cases; MILP supplied 30 optimum certificates on easier instances. All 40 MILP instances returned a feasible candidate, independently validated. The 10 congested schedules are feasible but have **no optimality certificate** in this time budget.

The comparative baseline is the **strongest of four EDD/FIFO/SPT/WSPT rules separately for each instance**. This is not a measured human operator or factory's incumbent schedule. The optimizer uses HiGHS with up to 0.7 seconds **in addition to local-search computation**; it is not an equal-total-wall-time algorithm race. See the per-case recorded wall times before claiming speed advantages.

## Critical findings and limitations

- In congested workshops, adding an inexpensive swap/insertion local search was more effective than changing big-M coefficients alone. The 10-case tight-vs-legacy 0.7-second MILP ablation improved only one case and proved **0/10** optima for both variants.
- All workloads are **synthetic**, use bounded integer time grids and a simple, uniform product-family changeover penalty. They lack real shifts, material availability, physical setup crews and uncertainty.
- A schedule built by local search is **not** optimal merely because it improves four classical heuristics. Even a MILP candidate with a nonzero relative gap is not proven optimal.
- The search neighborhood only modifies entire-job priority order, not individual operation sequences, learned dispatching weights, or the machine plan independent of the common feasible schedule constructor.
- Timed heuristic and MILP results can vary with CPU environment, solver version and scheduling. Preserve inputs and compare distributions across repeated seeds, not just one favorable percentage.
- The repository is an **independent engineering project**, not a factory-integrated MES or an evidence-backed operational savings claim.

## Honest CV phrasing

> Developed a Python MILP/HiGHS and deterministic local-search production scheduler; reduced **aggregate weighted tardiness by 22.7%** against the strongest of four dispatching rules across **501 operations in 40 synthetic workshop scenarios**, with **30/40 mathematical optimality certificates** and independent feasibility validation.

## Next engineering acceptance gates

1. Validate paired workload constraints and objective consistency using a second independent instance generator and established job-shop datasets.
2. Add explicit shift calendars **only when baseline, solver, verifier and negative tests agree**, with no implied cross-shift preemption.
3. Establish whether local search helps at *equal total wall-clock budget* before any speed claim.
4. Seek permissioned, anonymized, real work-order data; complete a small actual-versus-proposed schedule comparison without fabricating production savings.
