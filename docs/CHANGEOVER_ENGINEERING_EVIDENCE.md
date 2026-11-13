# Optera v0.9 — high-mix CNC changeover engineering audit

## Question

Does modeling product-family changeovers and optimizing the order sequence improve weighted order lateness compared with classical dispatching, while maintaining a provably feasible machine schedule?

## Model

One primary machine may have `changeover_time >= 0`. Each eligible operation declares `setup_family`. On the same **primary** machine, consecutive different-family operations must have at least `changeover_time` between processing intervals. Switching within the same family requires no gap. Optional support reservations are constrained separately and **do not** create setup gaps. Machine maintenance and order precedence remain hard constraints.

This version is a minimum separation model (the setup can be completed anywhere in the available gap), not a separate setup operation. The model does not cover asymmetric setup matrices, machine-operator setup teams, tool inventory or monetary setup cost. Old scenarios without setup times remain valid.

## Reproducible experiments

`python changeover_lab.py --count 20 --start-seed 20261113 --time-limit 2 --out artifacts/hmlv_changeovers`

20 small, synthetic one-machine job-shop cells, 95 jobs total; 2–3 product families, changeover 2–5 time units, 4–6 orders per cell. In each cell the reference is the **best of EDD, FIFO, SPT and WSPT** (same feasibility constraints), chosen on weighted tardiness. The MILP objective is weighted tardiness, with makespan as a minor tie-break.

| Metric | Best-of-four heuristic | MILP / HiGHS |
|---|---:|---:|
| Aggregate weighted tardiness | 455 | 327 |
| Aggregate modeled setup allowance | 135 | 97 |
| Mathematically proven optimal solutions | not applicable | 20/20 |
| Strict improvement / ties | — | 13 / 7 |

Weighted tardiness reduction: **28.13%**, aggregated across these 20 generated cells. Setup allowance decline is observed only for these particular solutions; the optimization target was weighted tardiness rather than setup minimization. These are **synthetic, small and single-primary-machine scenarios** and cannot establish factory savings or generalize to larger multi-resource cases. All 20 per-case rows in `docs/benchmarks/hmlv_changeover_v1.{csv,json}`; deterministic input hash is included. Solver execution times are hardware-dependent and excluded from the input digest.

## Independent checks

- The verifier rejects nonoverlapping tasks with insufficient setup gap (subtle failure case).
- Legacy no-setup sample metrics remain unchanged; baseline and rolling replanning include the new rule.
- Tiny four-order example independently enumerates all 24 permutations and matches the MILP objective.
- CI regenerates benchmark rows and verifies aggregate results and deterministic scenario digest.

## What would increase confidence

1. Multi-machine setups with staff, outages, realistic releases and immutable committed work; robust shifts next.
2. Independent external public benchmark families with setup constraints; evaluate optimality gaps, timeouts and infeasibility cases.
3. Controlled anonymized real production pilot and scheduling user feedback (not yet done).
