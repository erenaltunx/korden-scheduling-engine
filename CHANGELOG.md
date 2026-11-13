## v0.12.0 — Hybrid finite-capacity scheduling and solution-quality audit (2026-11-13)
- Added deterministic swap/insertion job-priority local search, independently validated against the same resource, sequence, maintenance and setup constraints as four classical dispatch policies.
- Introduced hybrid local-search + MILP engine (separate research-grade optimum proof status, raw candidate evidence, timing and selected algorithm); kept MILP-only makespan option.
- Tightened operation start bounds, machine disjunction Big-M values and downtime inequalities; retained legacy formulation for matched ablation. Fixed the rolling-horizon boundary exceeding original planning horizon.
- Reproducible 40-scenario synthetic benchmark: 501 operations, aggregate weighted tardiness 2757→2132 (−22.67%), 30/40 proven optima. In 10 congested instances: 1597→1304 (−18.35%), 0/10 optimality proofs.
- Added independent mathematical and API tests and CI smoke audit; no real factory-savings or total-runtime advantage claimed.

## v0.9.0 — Production cell setup/changeover modeling (2026-11-13)
- Narrowed primary product focus to high-mix, low-volume manufacturing finite-capacity scheduling.
- Added uniform product-family changeover time to the validated scenario contract and portable adapter.
- Implemented identical machine setup constraints in MILP, classical baselines, rolling replanning and independent checker; expanded worst-case horizon.
- Added reproducible 20-instance research lab, 13 new regression/negative/property tests, interactive setup controls and modeled setup KPI.
- No claim of asymmetric setup matrices, setup crew reservations, live production savings or industrial rollout.

## v0.8.0 — Capability-based staff assignment + SQL/CSV business integration (2026-11-13)
- Choose one qualified worker from a capability pool in the MILP itself, without double booking or forgetting existing fixed supports; baselines and rolling replay updated.
- Added skill selector to universal v1 contract (additive, backwards-compatible), explicit validation and eight new staff-choice tests.
- Enterprise CSV ingestion and SQLite/BI reporting with independent feasibility revalidation, Power BI-compatible CSV exports, foreign-keyed run facts and reusable SQL queries.
- Three demo industry input bundles, audited API/CSV/SQL roundtrip, seeded 24-instance staffing optimization study with explicit limitations.
- CI skill-allocation and enterprise ETL quality gate added; no real business savings, live ERP, or claimed SAP experience.

## v0.5.0 — Rolling-horizon scheduling and external benchmark validation (2026-11-13)
- Real non-preemptive disruption replay: freeze operations already started; reallocate future tasks only.
- Explicit rejection of outages interrupting in-progress operations; no hidden preemption assumption.
- Rolling baseline and stability metrics (shift hours, reassignment, changed future operations).
- Dual optimization objectives: weighted tardiness and makespan, with no cross-objective benchmark conflation.
- Strict JSPLIB FT06/LA01 importer and reference optimum audit. FT06 solver-proven; LA01 reference value reached without solver proof in time budget.
- 20 deterministic rolling disruption cases and documented limitations; CI regression added.
- API `/api/reschedule`, public benchmark metadata and compatible browser controls; Docker includes bundled instance data.
- Full engineering case study with reproducible commands, limitations and provenance.

## v0.4.0 — Stronger evidence and disruption what-if (2026-11-13)
- Four deterministic classical scheduling policies (EDD, FIFO, SPT, WSPT) with identical feasibility rules.
- Held-out seed benchmark compares solver recommendation with best of four valid heuristics, avoiding one weak comparator.
- Non-destructive machine outage counterfactual editor; clear limitation about not freezing already executed tasks.
- New API/UI policy input, regression tests, and GitHub Actions benchmark-artifact job.
- CI concurrency control and research methodology with documented limitations.

# Changelog

## v0.3.0 — OPTERA architecture & data-safety baseline (2026-11-13)

- Renamed the product and Python package consistently to OPTERA; previous prototype source preserved separately.
- Added explicit optimizer registry and backward-compatible scenario schema version 1.
- Added durable local SQLite experiment history, checksums, online consistent backups, version guard and history API/UI.
- Public demo does not store or expose private run history; solver concurrency and request-size controls added.
- Added Docker Compose persistent volume, fixed direct dependency versions, cross-platform Windows/Linux CI, container smoke checks and Dependabot update PRs.
- Added recovery, architecture, security and quality-gate documentation.
- Existing MILP schedule objective and baseline preserved, with regression tests.

## v0.6.0 — Sector-neutral resource studio (2026-11-13)
- Universal v1 domain contract: resources, capabilities, unavailability, work orders and sequential steps; strict fail-closed input validation.
- Working manufacturing, field-service and warehouse scenarios run through the same MILP/HiGHS engine and independent schedule validator.
- API: template discovery, scenario normalization/validation, cross-industry optimization; local persistence, public-demo safeguards retained.
- Guided web editing of order due times, priorities and resource unavailability without writing JSON.
- Cross-industry benchmark tool + real CI checks; domain-scoped technical vision and explicit unsupported-constraint matrix.
- Existing v1 factory scenarios, historic experiments and optimizer behavior preserved.


## v0.7.0 — Simultaneous resource reservations (2026-11-13)
- A step may reserve explicitly named supporting resources concurrently with a primary skill-matched resource.
- MILP, four classical baselines, independent verifier, rolling replay and Gantt now honor these reservations.
- Illustrative manufacturing, field-service and warehouse workflows include a shared operator/vehicle/packing worker.
- Historical v0.6 data archived and proven reproducible despite evolving sector sample constraints.
- Negative tests prove shared support resources cannot be double-booked or scheduled during unavailability.
- Dynamic staff selection, travel times and multi-capacity resources remain unmodeled.
