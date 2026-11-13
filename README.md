# Optera — Finite-Capacity Production Scheduling & Recovery

**Plan smarter. Produce better.**

OPTERA is an independent, local-first **finite-capacity manufacturing scheduling** project that solves production scheduling problems rather than merely showing dashboards. It builds an Earliest Due Date (EDD) baseline and four classical dispatching policies (EDD/FIFO/SPT/WSPT) alongside a real mixed-integer (MILP/HiGHS) plan, checks both schedules independently for feasibility, and reports fair, reproducible KPIs. No AI subscription, API key, or company data required.

**Version:** 0.9.0 — versioned engineering prototype. **Not an authenticated, production-grade MES.**


## v0.10 — Harder, more honest manufacturing evidence

**Independent paired research** across 70 deterministic synthetic workshop scenarios (462 orders; 807 operations): 20 single CNC, 20 two-stage, 20 flexible CNC and 10 congested CNC workcells. The guarded recommendation policy (validated MILP candidate or validated classical fallback) reduced aggregate weighted tardiness **3564 → 2968 (16.72%)**, with **60/70 proven optima**. In the **10 congested shops**, improvement was only **1.25%**, with **no proven optima** under the 0.7-second solver budget; 8 cases required retaining the classical baseline.

This is a deliberately more difficult test than our earlier 28.13% single-machine study, **not a real factory savings claim or a pure MILP-only gain**. Run:

~~~bash
python research_lab.py --count-per-profile 20 --stress-count 10 --seed-base 230011 --time-limit 0.7 --out artifacts/heterogeneous_workshops
~~~

See [research evidence and caveats](docs/ENGINEERING_EVIDENCE_V1.md). Detailed CSV/JSON are produced on demand; GitHub CI also uploads a smaller fixed-seed smoke report.

## Product focus: high-mix, low-volume production cells

**Target operator:** a production planner managing changing customer orders on a small CNC/fabrication/machining cell (not an entire factory ERP system). Optera answers: **Which jobs should run on which qualified resources and in what order, while respecting real machine availability, product-family changeovers, and firm in-progress commitments?**

- **Inputs:** orders/step precedence, due times, machine eligibility, qualified support personnel, machine downtime, *uniform product-family switch time* (optional).
- **Outputs:** independently validated finite-capacity Gantt schedule, weighted order lateness, changeovers, setup time, solver proof/gap, disruption-aware revised plan.
- **Pilot boundary:** at most 12 resources / 65 operations, integer-hour/minute grids. No live MES connection, large-scale shift calendars, material constraints, real savings or authenticated multi-user workflows. 
- **Secondary workflows:** the existing universal data adapters and service/warehouse templates remain for compatibility, not primary product marketing.

**Version 0.9** models machine-specific *uniform family-change penalties*: switching from family A to B (or B to A) consumes a fixed time allowance on the primary machine; staying within a family adds none. This is a **minimum separation constraint**, not a time-stamped setup activity. It does **not** support arbitrary asymmetric family-to-family matrices, setup workers, or preventive material checks. Unsupported rules must never be silently assumed.

### Reproducible high-mix benchmark

Run `python changeover_lab.py --count 20 --start-seed 20261113 --time-limit 2 --out artifacts/hmlv_changeovers`.

| 20 synthetic high-mix production cells | Strongest of EDD/FIFO/SPT/WSPT | Optera MILP/HiGHS |
|---|---:|---:|
| Aggregate weighted tardiness | 455 | 327 |
| Total modeled setup allowance | 135 | 97 |
| Scenarios with mathematical proof | — | 20 of 20 |

Weighted tardiness fell **28.13%** in this synthetic, explicitly bounded experiment. The optimizer targets weighted tardiness, *not* setup cost: reduced setup time is a secondary observation in this sample, not a general guarantee. These are not production savings. Full per-instance evidence and deterministic input hash are under `docs/benchmarks/hmlv_changeover_v1.*`. The demonstration scenario is `samples/setup_cell.json`, with a guided-editable version in `samples/universal/setup_cell.json`.

See [focused engineering roadmap](docs/PRODUCT_ROADMAP.md) for acceptance gates and maturity scoring.

## Cross-industry resource studio (v0.6)

OPTERA now supports an explicit **universal resource / capability / workflow contract**. Use the **Cross-Industry Resource Studio** in the web UI to choose a manufacturing, field-service or warehouse workflow, edit due times/priorities and block resource availability without hand-writing JSON. The sector-specific data is validated and compiled into the *same* tested MILP/HiGHS engine; all existing factory scenarios continue working.

The v1 domain supports **one capability-matched primary resource plus optional fixed simultaneous supporting resources per sequential step** (for example CNC machine + operator), integer minutes or hours and fixed unavailability. It intentionally rejects unknown or unsupported constraints: it does **not** solve *automatic selection of substitute support staff*, driving routes, inventories, setup times or complex calendars yet. This is a decision-engine foundation, **not** a complete production operations system. See [vision, actual scope and architecture](docs/VISION_AND_DOMAIN_CONTRACT.md).

```bash
python universal_benchmark.py --limit 8 --out artifacts/cross_industry
```

The three fictional sector scenarios now reserve simultaneous support resources too. They are compared against the strongest of EDD/FIFO/SPT/WSPT for each workflow. **Results are synthetic, per-sector and in different time units**, so they are not claims about live industrial savings. See the [v0.6 historical benchmark](docs/CROSS_INDUSTRY_EXPERIMENTS.md) and current [v0.7 concurrent-resources benchmark](docs/CONCURRENT_RESOURCE_EXPERIMENTS.md). Frozen v0.6 input data is in `samples/archives/v06/`.

**API endpoints:** `GET /api/universal/templates`, `GET /api/universal/templates/{id}`, `POST /api/universal/validate`, `POST /api/universal/run`. All other legacy APIs remain unchanged.

## Run with no ZIP or local installation — once published on GitHub

Go to **GitHub repository → Code → Codespaces → Create codespace**. Its preconfigured development container installs dependencies, starts the application and forwards port **8000**. Open the forwarded port to use the application. Hosted demonstration can be deployed via `render.yaml` separately; GitHub Pages cannot execute the Python solver.

The public Render demo sets `OPTERA_PUBLIC_DEMO=1`: stricter solver limits, **no persistence**, and no private experiment history. It is intended for synthetic test data only.

## Local development (optional)

**Requires Python 3.12** for the tested deployment environment.

```bash
python -m pip install -r requirements.txt
python run.py
```

Open http://127.0.0.1:8000. On Windows `launch_windows.bat` can also start the app. For Docker users, `docker compose up --build` starts the app and persists saved experiments in the `optera-data` volume. The web interface is accessible at http://localhost:8000.

## v0.8 — Dynamic staffing and enterprise data bridge

- **Real staff-choice decision:** an operation may select one qualified operator from a pool while reserving primary equipment and other fixed supports. A person cannot be double-booked. Skills are mapped from an industry-neutral contract.
- **ERP-style CSV imports without ERP claims:** browser or `planning_workflow.py` loads resources, orders, operations and optional unavailability; invalid links, duplicate columns and unsupported business constraints are rejected.
- **SQL/BI reporting:** separately validated schedules export normalized order KPIs, operation timelines, resource bookings and run summaries as CSV; CLI additionally persists the fact tables in relational SQLite.
- **Reproducible workforce experiment:** 24 seeded synthetic scenarios (144 orders), fixed staffing MILP **967** versus dynamically selectable staffing MILP **645** weighted tardiness (**33.30% lower**), with both optima proven in 24/24. This is NOT real-world cost saving.

Reproduce with `python staffing_lab.py --count 24 --seed-start 1000 --time-limit 2 --out artifacts/staffing_lab` and `python planning_workflow.py --data-dir samples/enterprise/field_service --name Service --industry Service --time-unit minute --out artifacts/service`.

See [`docs/ENTERPRISE_DATA_BRIDGE.md`](docs/ENTERPRISE_DATA_BRIDGE.md) and [`docs/CAREER_EVIDENCE.md`](docs/CAREER_EVIDENCE.md) for input contract, verified claims and explicit limits.

## Features currently implemented

- Synthetic factory scenario selection and editable JSON input.
- Four transparent dispatching baselines and a held-out benchmark laboratory against the strongest rule per factory.
- Counterfactual machine downtime what-if editing, with non-destructive original input.
- **Non-preemptive machine allocation and scheduling:** operations must follow order precedence and respect releases, maintenance outages and eligible machines.
- MILP engine with an explicit registry ready for additional solvers; invalid or unsupported solvers are rejected.
- Independent feasibility checker and weighted tardiness, total tardiness, late jobs and makespan KPIs.
- Interactive machine Gantt schedule and EDD-vs-MILP comparison with solver-status/optimality evidence.
- **Local experiment history**: versioned SQLite archive, checksummed results, history retrieval and online backup, disabled on public demo.
- CI across three Python versions, reproducible benchmark suite, Docker health check, security/dependency update processes.

## Reproduce measured results

```bash
python -m pytest -q
python benchmark.py samples/assembly_cell.json --time-limit 10
python benchmark_suite.py --count 20 --jobs 5 --time-limit 2
python benchmark_lab.py --count 60 --jobs 5 --start-seed 100 --time-limit 2
```

| Synthetic factory | EDD weighted tardiness | Optimized weighted tardiness | Relative reduction |
|---|---:|---:|---:|
| Assembly Cell (5 jobs) | 39 | 15 | **61.54%** |
| Precision Workshop (6 jobs) | 14 | 13 | **7.14%** |
| 20 generated small instances (aggregate) | 214 | 95 | **55.61%** |

Weighted tardiness is **weighted hours, not money saved**. Results are small *synthetic* scenarios, not real production cost reductions or claims about past employers. 20/20 generated instances previously achieved proven optimality at the stated setup; each fresh run reports its own status. See `docs/EXPERIMENTS.md` for the initial report and `docs/benchmarks/README.md` for the stronger held-out benchmark.

## Stronger 60-instance held-out benchmark (v0.4)

Evaluated **60** additional synthetic instances (seeds 100–159; 300 orders / 900 operations) against the **best of EDD, FIFO, SPT and WSPT per instance**. The MILP plan reduced pooled weighted tardiness **404 → 238 (41.09%)**, improving 21 instances and tying 39, with optimality proven for all 60. This is a strictly tougher baseline than the initial EDD-only report and **not a real factory cost or delivery improvement**. The generator is still synthetic and narrow in scope; outside benchmark families remain future work.

All per-seed results, methodology, exact commands and checksum are published in [`docs/benchmarks`](docs/benchmarks/README.md). Frontend also supports a non-destructive planned downtime what-if edit; each new scenario can be re-optimized but already executed tasks are not frozen.

## v0.5 engineering milestone — beyond a scheduling demo

**Two distinct objectives:** weighted job tardiness for business service levels, and makespan for classical job-shop research. The math must use the same objective as its reference benchmark. The new `/api/reschedule` freezes finished/in-progress non-preemptive work at a simulated planning clock, rejects outages that intersect ongoing tasks, and optimizes only work that has not started. The UI supports rolling replan after an initial run. Schedule stability (changed future tasks, machine switches, total start shift) is measured, **not yet an optimization objective**.

**External benchmark:** JSPLIB `ft06` (36 operations): OPTERA finds **55** vs. 71 from the strongest classical rule, and proves model optimality; published optimum = 55. JSPLIB `la01` (50 operations): **666** vs. 1078 heuristic, matching the published optimum of 666 but **not proving it within 15 seconds**. These are *arbitrary benchmark time units*, not factory hours. Benchmarks in `benchmarks/jsplib/`, results under `docs/benchmarks/`.

**20 rolling disruption trials:** 20 synthetic small workshops, aggregate weighted tardiness **833 → 563 (32.41%)** vs feasible rolling EDD, with 20/20 solver proofs. This is simulated research, not claimed production savings. Disruption changes many future tasks; plan stability requires future engineering improvements.

Reproduce with:

```bash
python public_benchmark.py --instance ft06 --time-limit 15
python public_benchmark.py --instance la01 --time-limit 15
python disruption_lab.py --count 20 --start-seed 300 --time-limit 3
```

Read the [engineering case study](docs/ENGINEERING_CASE_STUDY.md) for assumptions, limitations, source attribution and results. The public demo intentionally does not solve large benchmark instances because it enforces low resource limits; use Codespaces or local CLI for external benchmarks.

## Model and limitations

- MILP uses integer-hour start times, binary machine assignment, ordering constraints, non-overlap with tasks and machine maintenance, weighted tardiness first and makespan tie-break.
- Time-limited optimization may return a feasible incumbent without proof; if no better plan is available the application retains the feasible EDD plan and labels it as fallback.
- In this version there are **no sequence-dependent changeovers, staffing shifts, material constraints, stochastic breakdowns, or multi-user access**. The what-if downtime editor is a deterministic planning counterfactual from time zero; it does **not** freeze already-started work. Larger schedules can be slow due to quadratic pairwise ordering.
- More complex constraints are only introduced with matched solver constraints, independent validation rules, tests and a schema migration.

## How to keep your work safe

Source code and experiment data are separate. GitHub stores **source**, while experiment history is saved locally at `~/.optera/experiments.sqlite3` or `OPTERA_DATA_DIR` (old archives remain readable, see [migration notes](docs/REBRAND_AND_DATA_MIGRATION.md)); databases, secrets and personal inputs are intentionally excluded from Git commits. Public demos **do not** retain history.

Create a verified SQLite backup to a new file:

```bash
python backup.py --out ~/optera-backups/optera-2026-11-13.sqlite3
```

Keep an additional copy on another drive and test restore procedures. Follow [`docs/RECOVERY.md`](docs/RECOVERY.md). Docker `compose.yaml` uses a persistent named volume, but volumes alone are not backups.

## Engineering discipline

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — design contracts and future modules.
- [`docs/QUALITY_GATES.md`](docs/QUALITY_GATES.md) — changes/tests/CI merge gates.
- [`docs/RECOVERY.md`](docs/RECOVERY.md) — GitHub and database disaster recovery.
- [`docs/MODEL.md`](docs/MODEL.md) — mathematical formulation.
- [`docs/GITHUB_AND_DEPLOYMENT.md`](docs/GITHUB_AND_DEPLOYMENT.md) — GitHub, Codespaces and hosted demo.
- [`SECURITY.md`](SECURITY.md) — secrets and public demo risk boundaries.
- [`CHANGELOG.md`](CHANGELOG.md) — version-by-version changes.

## Project layout

```text
optera/         optimization, validation, orchestration, archive, API
static/         browser client and Gantt UI
samples/        synthetic scenario definitions (schema v1)
tests/          functional, regression, data safety and API tests
docs/           mathematical model and operating procedures
.github/        CI, benchmark proof, Docker smoke and dependency PRs
.devcontainer/  Codespaces development environment
Dockerfile + compose.yaml   deployment and local persistent volume
benchmark*.py   reproducible research scripts
backup.py       SQLite online backup utility
```

**Repository:** `erenaltunx/optera` after the GitHub repository is renamed in Settings. Application rename and repository slug rename are separate steps. See [migration notes](docs/REBRAND_AND_DATA_MIGRATION.md).
