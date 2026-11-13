# KORDEN v0.5 — Scheduling, rolling-horizon disruption handling, and external validation

**13 November 2026 · Reproducible engineering research prototype.**

## Problem statement

Manufacturers must allocate precedence-constrained operations across scarce machines while respecting release times, maintenance closures, job due dates and non-preemptive execution. Frequent replanning is necessary, but previously started operations must not be rewritten. KORDEN treats these as explicit mathematical constraints and provides an independent feasibility certificate.

## Formulation and decision hierarchy

- Mixed-integer optimization in Python using SciPy/HiGHS.
- Integer start times; one eligible machine per operation; disjunctive machine no-overlap; ordered job routes; maintenance intervals; release dates.
- **Two selectable objectives:** (1) weighted tardiness, with makespan tie-break, or (2) standalone makespan minimization. Do not compare results from different objectives.
- **Rolling mode:** freeze all operations already started before current simulated factory hour; pending operations must start at or after that hour; reject outages intersecting ongoing non-preemptive work. Optimize the remaining plan, then validate the full plan independently. Fallback to a feasible rolling heuristic if needed.
- **Stability instrumentation:** report number of frozen tasks, changed future operations, machine reassignments and total absolute start-time shift. **Stability is measured, not yet minimized.**

## Experiment A — 60 deterministic synthetic factories, v0.4

Five jobs, three operations per job, seeds 100–159. Strongest per-instance baseline across EDD/FIFO/SPT/WSPT. Aggregate weighted tardiness **404 vs. 238**, or **41.09% decrease**; 21 wins, 39 ties, 60/60 proven model optima. See `docs/benchmarks/heldout_60.*`. Not actual plant savings.

## Experiment B — external, published benchmarks, v0.5

| Public JSPLIB instance | Operations | Best classical heuristic Cmax | KORDEN Cmax | Published optimum Cmax | Solver optimum proven? | Time cap |
|---|---:|---:|---:|---:|---|---:|
| Fisher–Thompson FT06 | 36 | 71 | **55** | 55 | **Yes** | 15s |
| Lawrence LA01 | 50 | 1078 | **666** | 666 | **No** | 15s |

Numbers denote **benchmark processing-time units**, not independently verified factory hours. Both recovered schedules passed independent feasibility checks. For LA01 the solver achieved a plan matching the published optimum but did **not** prove optimality within its 15-second budget (reported relative MIP gap ~22.37%). Do not label LA01 solver-proven optimal.

Source data: [JSPLIB reference repository](https://github.com/tamy0612/JSPLIB) — `instances/ft06`, `instances/la01`; original benchmark families attributed to Fisher–Thompson (1963) and Lawrence (1984). Published reference makespans independently documented by [ScheduleOpt JSPLib](https://scheduleopt.github.io/benchmarks/jsplib). Data copies are kept only for explicit reproducibility, with file-level attribution.

Commands:

```sh
python public_benchmark.py --instance ft06 --time-limit 15 --out artifacts/ft06.json
python public_benchmark.py --instance la01 --time-limit 15 --out artifacts/la01.json
```

Machine cap, job cap and operation count are limited by the current v0.5 implementation; this is not general large-scale industrial scheduling.

## Experiment C — 20 rolling factory disruptions, v0.5

Deterministic seeds 300–319, each with five orders and 15 operations. At simulated factory hour 4 a four-unit breakdown is added to CUT after any already-running CUT operation finishes (no unmodeled preemption). Baseline: feasible rolling EDD with exactly the same frozen operations and outage. KORDEN: MILP reoptimization with the same constraints.

- **20/20** solutions with model optimality proven at the test configuration.
- **13** improving instances, **7** ties; none worsened against the rolling EDD baseline.
- Pooled weighted tardiness: **833 to 563**, a **32.41% reduction**.
- Mean **1.25 already-started operations frozen** per factory; mean **12.2 future operations changed** compared with the previous production plan.

The high number of schedule changes is an **identified engineering weakness**; a future stability-aware secondary objective will trade off customer tardiness and plan disruption. Until then this output must not be described as operationally optimal for a real plant.

Reproduce:

```sh
python disruption_lab.py --count 20 --start-seed 300 --time-limit 3 --out artifacts/disruption_lab
```

CSV and JSON result files in `docs/benchmarks/` are reproducible snapshots of the same algorithms and seeds. Timing varies with hardware and solver versions.

## Quality gates and release limits

- 67 local automated tests (on this revision, subject to fresh CI); independent schedule feasibility, API isolation, versioning and immutable execution tests.
- GitHub Actions must validate Python 3.11/3.12/3.13, Windows, external benchmark, synthetic benchmark, disruption replay and Docker smoke before merge.
- Public demo has no persistence, <=5-second solver caps and strict operation limits. Full FT06/LA01 benchmarks are CLI or private Codespaces exercises; public demo intentionally rejects larger inputs.
- Not an MES or safety-certified controller. No operators, material balances, sequence-dependent setups, shop-floor event ingestion or live machine integration yet.

## Next bottleneck: mathematical and software scalability

The pairwise Big-M MILP has quadratic sequencing variable growth; larger instances have weak relaxations and longer proof times. Next meaningful research milestone: stronger formulations and a CP-SAT interval solver, plus plan-stability-aware rolling objectives, head-to-head benchmark comparisons, and repeatable hardware/timing measurements. The LA01 proof gap is concrete evidence of this limit.
