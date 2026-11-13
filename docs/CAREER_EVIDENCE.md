# Career evidence ledger — independently auditable claims

## Verified capabilities

1. **Operations research / MILP** — Python SciPy/HiGHS, integer decision variables, capacity and sequencing constraints, independent feasible-plan validator, solve-time and optimality metadata.
2. **Skills-based staff allocation** — an optional worker is now a real binary MILP decision; v0.8 supports choosing exactly one worker per operation from a capability-matched, exclusive-capacity pool. Feasibility checks and rolling replay both cover selected staff.
3. **Data engineering / SQL** — validated CSV ingestion from 4 related source tables; normalized domain objects; 5-table append-only SQLite analytical schema; SQL joins, grouping, reconciliation and utilization proxies.
4. **API / product engineering** — FastAPI request validation, safe CSV import and server-side independent schedule validation for BI export; GitHub CI, Docker, Windows test matrix and reproducible experiment artifacts.
5. **Cross-domain adaptability** — manufacturing, field service and fulfillment use the same solver with separate skills, resources and work-order workflows.

## Numerical study A: 24 seeded staffing instances

- Generator: `staffing_lab.py`, seeds 1000–1023.
- Same orders, machines, three technicians, availability, deadlines, weights and mathematical solver. Fixed-roster policy uses a predetermined round-robin worker; flexible policy optimizes qualified staff choice.
- 144 orders (one operation each). Both formulations proven optimal in 24/24 seeded instances.
- Pooled weighted tardiness: **967 → 645** (**33.30% lower**). 19 improvements, 5 ties, no regressions.
- The result isolates staffing flexibility relative to a restricted fixed assignment policy, *not* a claim of actual realized personnel savings or a comparison against an externally optimized staffing policy.

## Numerical study B: earlier operations scheduling research

- v0.4 60 additional small synthetic factory instances: **404 → 238** pooled weighted tardiness vs the best of EDD/FIFO/SPT/WSPT (41.09% lower); optimality proved for 60/60.
- v0.5 published benchmark FT06: **55** makespan (published optimum and solver proof). LA01: **666** makespan (published optimum matched, not independently proved within time limit).
- v0.5 20 small disruption test cases: **833 → 563** pooled weighted tardiness vs rolling heuristic (32.41% lower) with completed work frozen.
- *Do not combine any of these metrics across objectives or minute/hour scales.*

## Example CV bullet — only after GitHub CI is green

> Engineered OPTERA, a cross-industry scheduling platform integrating Python/SciPy MILP optimization, capability-based workforce assignment, FastAPI, structured CSV ingestion and SQLite/SQL reporting. Across 24 reproducible synthetic staffing scenarios (144 jobs), reduced weighted tardiness 33.3% relative to a fixed-roster policy, with optimal solutions verified for both models across all instances.

**Must not claim:** live SAP integration, real cost savings, production deployment, advanced Power BI/DAX proficiency, industrial-scale optimization, or ERP administrator experience. Those require separate demonstrable work.
