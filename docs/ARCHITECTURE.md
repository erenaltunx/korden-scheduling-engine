# KORDEN technical architecture / stable extension contracts

```text
Browser (static/)
    | JSON /api/run  or  /api/reschedule
HTTP boundary (korden/api.py)  -> request caps, demo mode, security headers
    | validated scenario
Application service (korden/service.py)
    |-> Four classical reference plans (baseline.py)
    |-> Rolling-horizon execution safety (reschedule.py)
    |-> Strict public JSP importer (public_benchmarks.py)
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
2. **One stable solver contract:** `solver(scenario: dict, time_limit: float, *, options) -> {"schedule": list|None, "solver": metadata}`. Rolling mode receives fixed-operation assignments and earliest future start; normal calls retain backwards-compatible defaults. Every non-null schedule must pass `evaluation.check_schedule` **before** it can appear in results or be archived.
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

## v0.5 execution snapshots and benchmark boundaries

- Rolling horizon uses `start < planning_clock` to freeze operations and their machine/start/end. Non-preemptive work crossing the clock stays fixed, so an outage that interrupts it is rejected, not silently cut or reassigned.
- All future operations start at/after the clock; every schedule (solver or fallback baseline) is checked against *revised* downtime and original job precedence.
- A reference schedule must pass the original scenario's independent feasibility checker before it is accepted. Job and machine definitions cannot change during disruption replay.
- Research benchmarks use **makespan** and public source provenance; business delay experiments use **weighted tardiness**. Mixing objective outcomes is prohibited.
- Stability is instrumentation, not a minimization term yet. A change to the objective requires an explicit versioned methodology and independent regression tests.


## v0.6 cross-industry adapter, not a duplicated optimizer

`korden/universal.py` accepts strictly versioned `resources` and `work_orders` and maps them onto the existing validated machine/job primitive. Resource skills are evaluated against the complete set of required capabilities. Resource availability windows are copied into the engine's downtime constraints. Sector-specific names, kinds, and time-unit metadata remain with the source scenario. The universal API results contain the compiled scenario and model-scope statement for auditability.

The adapter is limited to **exactly one exclusive resource per step, sequential steps per work order**. It rejects unknown keys (including attempted capacity, simultaneous-worker, inventory or travel constraints). This is essential: a solver cannot claim feasibility for rules it did not encode. Future adapters should be separate, versioned modules and support constraint coverage reports with negative tests.

The browser's guided editor only changes the canonical JSON via the API's validation endpoint. Resource-kind labels and industries never affect solver semantics; capabilities and unavailability do. See `VISION_AND_DOMAIN_CONTRACT.md` for the intended end-state and explicit non-goals.


## v0.7 synchronized primary and support reservations

A task may have `support_resources` (legacy/internal optimizer) / `reserve_resources` (universal source). The core model creates a fixed one-valued assignment for each support resource. Disjunctive non-overlap constraints apply uniformly to *primary assignments and fixed support reservations*. Heuristic baselines search the earliest slot available simultaneously across all occupied resources. The independent verifier separately checks support-resource overlap and downtime. Rolling replanning keeps all started reservations intact and refuses outages that intersect them. Existing no-support source remains backward-compatible.

Support selection is still fixed by input, not combinatorial staff assignment; resource capacity is exactly one. Historical reports use archived inputs to prevent silent benchmark drift.
