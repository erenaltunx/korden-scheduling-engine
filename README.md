# KORDEN — Industrial Scheduling & Optimization Engine

**Plan smarter. Produce better.**

KORDEN is an independent, local-first **operations research** project that solves production scheduling problems rather than merely showing dashboards. It builds an Earliest Due Date (EDD) baseline and a real mixed-integer (MILP/HiGHS) plan, checks both schedules independently for feasibility, and reports fair, reproducible KPIs. No AI subscription, API key, or company data required.

**Version:** 0.3.0 — versioned engineering prototype. **Not an authenticated, production-grade MES.**

## Run with no ZIP or local installation — once published on GitHub

Go to **GitHub repository → Code → Codespaces → Create codespace**. Its preconfigured development container installs dependencies, starts the application and forwards port **8000**. Open the forwarded port to use the application. Hosted demonstration can be deployed via `render.yaml` separately; GitHub Pages cannot execute the Python solver.

The public Render demo sets `KORDEN_PUBLIC_DEMO=1`: stricter solver limits, **no persistence**, and no private experiment history. It is intended for synthetic test data only.

## Local development (optional)

**Requires Python 3.12** for the tested deployment environment.

```bash
python -m pip install -r requirements.txt
python run.py
```

Open http://127.0.0.1:8000. On Windows `launch_windows.bat` can also start the app. For Docker users, `docker compose up --build` starts the app and persists saved experiments in the `korden-data` volume. The web interface is accessible at http://localhost:8000.

## Features currently implemented

- Synthetic factory scenario selection and editable JSON input.
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
```

| Synthetic factory | EDD weighted tardiness | Optimized weighted tardiness | Relative reduction |
|---|---:|---:|---:|
| Assembly Cell (5 jobs) | 39 | 15 | **61.54%** |
| Precision Workshop (6 jobs) | 14 | 13 | **7.14%** |
| 20 generated small instances (aggregate) | 214 | 95 | **55.61%** |

Weighted tardiness is **weighted hours, not money saved**. Results are small *synthetic* scenarios, not real production cost reductions or claims about past employers. 20/20 generated instances previously achieved proven optimality at the stated setup; each fresh run reports its own status. See `docs/EXPERIMENTS.md`.

## Model and limitations

- MILP uses integer-hour start times, binary machine assignment, ordering constraints, non-overlap with tasks and machine maintenance, weighted tardiness first and makespan tie-break.
- Time-limited optimization may return a feasible incumbent without proof; if no better plan is available the application retains the feasible EDD plan and labels it as fallback.
- In this version there are **no sequence-dependent changeovers, staffing shifts, material constraints, stochastic breakdowns, or multi-user access**. Larger schedules can be slow due to quadratic pairwise ordering.
- More complex constraints are only introduced with matched solver constraints, independent validation rules, tests and a schema migration.

## How to keep your work safe

Source code and experiment data are separate. GitHub stores **source**, while experiment history is saved locally at `~/.korden/experiments.sqlite3` or `KORDEN_DATA_DIR`; databases, secrets and personal inputs are intentionally excluded from Git commits. Public demos **do not** retain history.

Create a verified SQLite backup to a new file:

```bash
python backup.py --out ~/korden-backups/korden-2026-11-13.sqlite3
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
korden/         optimization, validation, orchestration, archive, API
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

**Repository target:** `erenaltunx/korden-scheduling-engine`. Do not assume GitHub publication or hosted deployment is complete until verified.