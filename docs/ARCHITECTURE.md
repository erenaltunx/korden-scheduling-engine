# KORDEN technical architecture / stable extension contracts

```text
Browser (static/)
    | JSON /api/run
HTTP boundary (korden/api.py)  -> request caps, demo mode, security headers
    | validated scenario
Application service (korden/service.py)
    |-> EDD reference plan (baseline.py)
    |-> Explicit solver registry (engines.py)
    |      |-> MILP / HiGHS (optimizer.py)
    |-> Independent feasibility checker & metrics (evaluation.py)
    |-> versioned scenario contract (model.py)
    |-> optional local storage (storage.py)
    |      SQLite WAL, transactional writes, SHA-256, migrations, backups
    v
validated experiment + schema version + solver evidence
```

## Design rules for future features

1. **Mathematical solver never imports FastAPI, SQLite, or UI code.** `optimize` is pure relative to input data. New solvers are registered explicitly in `korden/engines.py`, not dynamically imported from request strings.
2. **One stable solver contract:** `solver(scenario: dict, time_limit: float) -> {"schedule": list|None, "solver": metadata}`. Every non-null schedule must pass `evaluation.check_schedule` **before** it can appear in results or be archived.
3. **Versioned schemas:** scenario JSON has `schema_version: 1`. Unversioned historical scenarios are read as v1; unsupported future versions are rejected, not silently misread. Changing the schema needs a migration + regression fixture.
4. **Stable KPI meanings:** weighted tardiness is sum of max(0, completion-due) × weight, units weighted-hours. Never reinterpret as money or real savings.
5. **A failed optimizer may keep the valid EDD plan**, but metadata MUST say fallback; never call a fallback mathematically optimal.
6. **API is an adapter:** no solver/business rules in the frontend. Keep `/api/run` response compatible or introduce `/api/v2` with a migration.
7. **Storage boundaries:** persistent history is local-only (`KORDEN_PUBLIC_DEMO=0`). The public demo has no private DB endpoints and never archives scenarios. DB changes require forward-only migrations; refuse newer versions.
8. **No silent upgrades:** change dependencies on a branch, run the full CI matrix and benchmark, review the diff, then merge; tag releases after CI.
9. **Data recovery:** SQLite is not tracked in Git. Back it up using the SQLite online backup API; test actual restoration; see `RECOVERY.md`.
10. **Performance security:** public solver time and size limits are not a substitute for infrastructure limits.

## Proposed feature folders

Future shift calendars, setups and disruptions should be separate focused modules plus schema migration, validator rules and explicit tests. Add one feature per pull request, first with a failing test. The exact mathematical model must remain independently checkable.
