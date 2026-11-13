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

## v0.3.0 — KORDEN architecture & data-safety baseline (2026-11-13)

- Renamed the product and Python package consistently to KORDEN; previous prototype source preserved separately.
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
