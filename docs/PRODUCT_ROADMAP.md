# Optera — focused engineering product roadmap

**Product thesis:** reliable, explainable finite-capacity scheduling and disruption recovery **for high-mix, low-volume manufacturing cells**.

**Buyer/decision maker:** production planning lead or manufacturing engineering manager. **Operator:** scheduler/production planner. **Measured value:** weighted order lateness, late orders, makespan, modeled changeovers and schedule stability, measured against the strongest eligible manual heuristic. **Not** an AI chat assistant, a generic ERP, or a broad industrial platform.

## Verified gap and next focused gate (v0.10)

We replaced a single-machine success story with a **70-instance, four-complexity-family experiment**. Across 807 synthetic operations, a validated MILP-or-classical fallback policy reduced aggregate weighted tardiness **16.72%** (60/70 proven optima); in 10 congested workshops the gain was only **1.25%** and **0/10** could prove optimal within 0.7 seconds. Full details: [engineering evidence](ENGINEERING_EVIDENCE_V1.md).

**Next priority: difficult-instance optimization quality**, not new industries or broad software features. Use the same fixed-seed congested instances under 0.7s, 2s, and 5s limits; compare raw candidate quality, fallback rate, relative MIP gap, proof rate, model-size limits, and full wall-clock runtime. Only then evaluate tighter mathematical formulations or CP-SAT. A larger number of favorable synthetic examples alone does not raise maturity score.

## v0.11 solver-budget experiment — completed locally; independently checked in CI

A fixed-seed 10-congested-workshop time-budget study found guarded weighted tardiness 1,569 / 1,452 / 1,265 under 0.7 / 2 / 5 seconds (classic comparator 1,597). No mathematical proof of optimality was achieved for any of these 10 scenarios, **even at 5 seconds**. The immediate next effort is mathematical-model strengthening on these same seeds under equal compute budgets. See [evidence](SOLVER_BUDGET_STUDY.md). These are *synthetic* results, not factory savings or an algorithmic breakthrough.

## Current gate: v0.12 hybrid scheduling and tightening

**Completed engineering:** deterministic swap/insertion local search (150-order evaluation budget) under existing plant constraints, HiGHS MILP with tighter time bounds/Big-M coefficients, independently checked hybrid selection, and 40-scenario paired research export. Across 501 synthetic operations the strongest four classical dispatch rules scored 2,757 weighted delay units versus hybrid 2,132 (**−22.67%**); 30/40 MILP optima proven. Congested cases improved 18.35% but remain 0/10 proof-certified in 0.7-second MILP budget. Technical evidence: [v0.12 study](HYBRID_ENGINEERING_EVIDENCE.md). The heuristic does not prove optimality; its additional computation is tracked separately.

**Next gate:** field-level production constraints (shift calendars in all three model/verifier/baseline layers), matched **equal total wall-time** comparison vs MILP alone, additional external known-optimum instances, and a permissioned real work-order sample. No additional sectors or AI layers. Moving above 65 requires demonstrated shift correctness and an externally verifiable demonstration; above 75 requires real operational data or independent external validation.

## Hard boundaries (protect deep specialization)

- Domain: job-shop and flexible job-shop scheduling on machining/fabrication cells, under finite machine and qualified-worker capacity.
- Secondary demos for service and warehousing stay regression fixtures; no additional sector marketing until manufacturing quality gates pass.
- Any new constraint must be represented in the **data contract, baseline, mathematical optimizer, independent verifier, negative tests and UI** before being called supported.
- A fast but unproven feasible solution is reported as *feasible, not optimal*. No silent fallback claims.
- Reproducibility, explicit units and retained datasets precede favorable marketing numbers.

## Iterative plan — milestones and acceptance criteria

| Gate | Engineering deliverable | Objective acceptance criteria | State |
|---|---|---|---|
| P0 | Stable engine, reproducible baseline and CI | Original cases unchanged; independent constraint checks; Windows/Linux and Docker CI | Implemented; online validation depends on current branch |
| P1 | **Uniform sequence-dependent setup allowance** (v0.9) | Exact MILP + four heuristics + rolling replay + verifier; negative tests, one brute-force case, 20 fixed-seed cases and artifact export | Implemented locally; GitHub promotion pending |
| P2 | **Shift calendars and labor feasibility** | Prevent work across closed shifts; strict cross-midnight/DST assumptions; show two independently verified schedules | Planned |
| P3 | **Robust disruption recovery** | Freeze started work; new machine outage and urgent order; compare tardiness vs plan disturbance using epsilon-constraint; no hidden rule violations | Partial rolling implementation, more evidence required |
| P4 | **Scaling & two-solver research** | CP-SAT alternative, 20–100 heterogeneous public job-shop benchmarks, wall-clock/optimality-gap percentiles, memory and CPU budget | Planned |
| P5 | **Production-planner UX & integration** | Guided XLSX/CSV import, field-level validation, Gantt changeover markers, publishable setup summary, no manual JSON required; externally verified live sandbox | Partial import; hosted demo unverified |
| P6 | **Controlled real pilot** | Permissioned, anonymized order data; baseline operations and independent follow-up measures; written limitations and operator evaluation | Not started |

## Engineering maturity score (not a recruitment score)

Weighted rubric with evidence required to move above 75: mathematical fidelity **25**; benchmark validity and scalability **20**; end-to-end planner usability **15**; real manufacturing constraint coverage **15**; automated reliability and recovery **15**; field validation and rollout **10**. High scores are blocked by lack of real pilot, shift calendars and missing live demonstration even if synthetic optimization results improve.

Initial score: **53/100**. A new local feature alone does not justify raising the published score; publish, verify CI and compare against rubric first.

## Future study and learning loop

Each completed gate adds: (1) model assumptions, (2) counterexample that fails without the feature, (3) reproducible benchmark with at least one unflattering case, (4) new risk/limitation, (5) next bottleneck ranked by industrial impact. If a gate exposes an unexpected issue, adjust the order and record the reason. The project never chooses breadth over finite-capacity manufacturing scheduling correctness.
