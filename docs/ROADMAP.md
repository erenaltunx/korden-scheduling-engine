# KORDEN development roadmap

## Career positioning

**Specialization:** Operations Research / Mathematical Optimization / Decision Analytics.

The core evidence is not a dashboard screenshot but a **reproducible numerical improvement with a validated optimization formulation**. Performance should be reported against explicit baseline algorithms and on disclosed benchmark data.

## Milestone 1: working engine (v0.1)

- [x] Input schema with precedence, alternative machines, release and due dates.
- [x] Downtime windows and basic data validation.
- [x] Deterministic EDD heuristic baseline.
- [x] Mixed-integer programming optimizer and optimality/gap metadata.
- [x] Independent feasible-schedule checker.
- [x] Weighted tardiness, late orders, makespan reporting.
- [x] Browser Gantt timeline + scenario JSON editing and export.
- [x] Docker and Windows launcher.
- [x] Automated unit and integration tests.

## GitHub readiness (v0.2)

- [x] GitHub Actions test matrix and deterministic benchmark artifact.
- [x] Codespaces container for no-download browser development.
- [x] Render deployment blueprint and public-demo resource limits.
- [x] MIT license, contribution instructions and deployment guide.
- [ ] Publish repository and verify GitHub Actions in the hosted environment.
- [ ] Publish an accessible hosted demo and smoke-test it externally.

## Foundation hardening (v0.3 — implemented locally)

- [x] Complete KORDEN rebrand across code, frontend and runtime configuration.
- [x] Versioned scenario input and fail-safe future-version rejection.
- [x] Stable explicit solver registry, independent feasibility checker preserved.
- [x] SQLite WAL experiment history, checksummed records and verified online backup.
- [x] History UI and recovery API, disabled on publicly hosted demos.
- [x] Docker persistent volume, dependency pins, Dependabot and container smoke CI.
- [x] Threat boundary and disaster recovery/restore playbook.
- [ ] Publish code to GitHub, verify hosted CI, create a GitHub release tag.
- [ ] Restore a backup from production-like deployment and verify with browser.

## Milestone 2: rigorous benchmarking (v0.4)

- [x] Generate initial 20 small synthetic instances with fixed seeds.
- [ ] Extend to ≥50 heterogeneous small/medium instances.
- [ ] Compare EDD, shortest-processing-time, critical-ratio and MILP.
- [x] Track solver gap and run time, write initial 20-instance summary.
- [ ] Add larger instances and percentile statistics.
- [x] Export reproducible per-instance CSV and JSON summaries.
- [ ] Add publication-ready figure generation.
- [ ] Use a public scheduling benchmark format (e.g. JSPLib), with appropriate instance attribution and interpretation.

## Milestone 3: factory realism (v0.4)

- [ ] Sequence-dependent changeovers and setup times.
- [ ] Shift calendars, operator availability, overtime cost.
- [ ] Multiple competing objectives with transparent weighting.
- [ ] Import production orders from CSV and validate errors.

## Milestone 4: disruption management (v0.5)

- [ ] Machine breakdown and urgent-order what-if scenarios.
- [ ] Penalize changes to an already committed schedule (schedule stability).
- [ ] Stochastic evaluation across sampled disruption scenarios.

## Milestone 5: portfolio proof (v1.0)

- [ ] Deploy a reproducible public demo.
- [ ] CI green, integration coverage and additional property-based checks.
- [ ] Package technical case study with methods, benchmark data, limitations and results.
- [ ] Write evidence-based CV summary after final benchmarks.

## Evidence rules

1. Benchmark results must include scenario, baseline, solver, solver gap, and time limit.
2. Percent reduction is `(baseline - optimized) / baseline * 100` for a metric with nonzero baseline.
3. Never report an observed simulation reduction as factory savings without real deployment evidence.
4. One instance is a demo; multiple diverse instances are needed to support robust performance claims.
