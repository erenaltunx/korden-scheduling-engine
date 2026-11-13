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
