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
- [x] Publish full repository to GitHub.
- [ ] Verify all GitHub Actions jobs pass in the hosted environment.
- [ ] Publish an accessible hosted demo and smoke-test it externally.

## Foundation hardening (v0.3 — implemented locally)

- [x] Complete KORDEN rebrand across code, frontend and runtime configuration.
- [x] Versioned scenario input and fail-safe future-version rejection.
- [x] Stable explicit solver registry, independent feasibility checker preserved.
- [x] SQLite WAL experiment history, checksummed records and verified online backup.
- [x] History UI and recovery API, disabled on publicly hosted demos.
- [x] Docker persistent volume, dependency pins, Dependabot and container smoke CI.
- [x] Threat boundary and disaster recovery/restore playbook.
- [x] Publish code to GitHub.
- [ ] Verify hosted CI, create a GitHub release tag.
- [ ] Restore a backup from production-like deployment and verify with browser.

## Milestone 2: rigorous benchmarking (v0.4)

- [x] Generate initial 20 small synthetic instances with fixed seeds.
- [x] Run 60 deterministic held-out small synthetic instances (seed 100..159).
- [ ] Add heterogeneous public benchmark families and medium instances.
- [x] Compare EDD, FIFO, SPT, WSPT and MILP against best classical baseline.
- [ ] Add critical-ratio and public benchmark comparisons.
- [x] Track solver gap and run time, write initial 20-instance summary.
- [ ] Add larger instances and percentile statistics.
- [x] Export reproducible per-instance CSV and JSON summaries.
- [ ] Add publication-ready figure generation.
- [x] Import JSPLIB FT06 and LA01 and compare makespan against published reference optima (v0.5).
- [ ] Expand to medium/large public benchmarks with diverse difficulty and explicit solver/time caps.

## Milestone 3: factory realism (v0.4)

- [ ] Sequence-dependent changeovers and setup times.
- [ ] Shift calendars, operator availability, overtime cost.
- [ ] Multiple competing objectives with transparent weighting.
- [ ] Import production orders from CSV and validate errors.

## Milestone 4: disruption management (v0.5)

- [x] Counterfactual downtime scenario generator and web editor from time zero.
- [x] Rolling rescheduling that freezes started operations; stop on impossible outage interruptions (v0.5).
- [ ] Add urgent-order insertion and active-event ingestion.
- [x] Measure schedule stability (moved operations, machine switches, shift hours) after disruption.
- [ ] Add mathematical schedule-stability objective rather than reporting it alone.
- [x] Deterministic 20-case disruption simulation with fixed seeds and complete trial results.
- [ ] Monte Carlo stochastic disruption and uncertainty sensitivity.

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
