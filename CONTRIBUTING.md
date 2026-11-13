# Contributing to KORDEN

KORDEN is an educational operations-research project. Contributions must retain
transparent experimental reporting and independently validated schedules.

1. Create a branch and make a narrowly scoped change.
2. Install `requirements.txt` with Python 3.11–3.13.
3. Run `python -m pytest -q` and `python benchmark_suite.py --count 10 --jobs 5 --time-limit 4`.
4. Add regression tests when changing constraints, objective, data parsing or schedule validation.
5. State whether test data are synthetic, public benchmark data, or verified industrial data.
6. Report baseline, benchmark selection, solver, gap and time limit; never report synthetic cost savings as company results.

Proposed milestones are listed in [`docs/ROADMAP.md`](docs/ROADMAP.md).

For future modules, read `docs/ARCHITECTURE.md` and `docs/QUALITY_GATES.md`.
Do not bypass the independent validator or change scenario semantics silently.
Back up experiment data before schema changes; make upgrades on separate PR branches.