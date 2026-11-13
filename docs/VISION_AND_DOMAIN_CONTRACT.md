# KORDEN vision — a cross-industry operations scheduling engine

## The problem and the product boundary

Different industries share one operational problem: a finite set of **exclusive resources**, a queue of **work orders**, ordered **processing steps**, due times, competencies and periods when resources cannot be used. A spreadsheet or a dashboard can explain yesterday's bottleneck; KORDEN computes a candidate plan that satisfies the modeled constraints and quantifies tradeoffs versus transparent dispatching policies.

**Core aspiration:** a decision operations platform with four separated layers:

1. **Connect / Translate**: versioned adapters for MES/ERP, WMS, field-service and other operational systems. Domain objects are translated to a canonical capability-and-resource graph with explicit data provenance.
2. **Constrain / Validate**: one independently checked mathematical feasibility contract; unsupported physical constraints MUST fail closed. Differences between a *model-feasible plan* and a *business-deployable plan* must be visible.
3. **Solve / Simulate**: modular engines (HiGHS today, CP-SAT and large-scale methods later), reproducible baseline evaluations, rescheduling, robust plans and scenario stress tests.
4. **Explain / Operate**: accessible configuration, Gantt, bottleneck explanations, experiments with immutable versions, approval-based export to downstream systems, incident recovery and audit trails.

**KORDEN is not yet a production MES, WMS, dispatch platform or clinical scheduling system.** It does not autonomously write to operational systems. The domain-neutral adapter is a bounded, meaningful first step toward this vision—not evidence of complete industry support.

## What version 0.6 actually models

- **Resources:** exclusive (capacity 1), each with an ID, name, kind, a set of capabilities and fixed intervals of unavailability.
- **Work orders:** when work can start, when work is due, and an integer priority weight.
- **Steps:** positive integer processing duration, ordered sequentially within an order. Each step requires all specified skills and is assigned to **one** eligible resource.
- **Time:** either integer *hours* or integer *minutes*, declared per scenario; the engine does not silently convert units or infer time zones.
- **Objective:** weighted tardiness (priority × lateness) or overall makespan; MILP/HiGHS is time-bounded and only claims optimality when proven.
- **Independent feasibility:** no resource overlap, operation precedence, release times, resource eligibility and resource-unavailability windows.

### Explicitly NOT modeled

Simultaneous assignment of operator and machine; multiple staff per task; capacity >1 / batching; travel and routing; inventory/material availability; setup/changeover times; non-linear costs; cross-order dependency networks; timezone/DST calendars; probabilistic disruptions; fatigue; contractual/labor/regulatory rules; reservations of external third-party resources. If the input tries to specify an unknown constraint, the adapter **rejects the request**, instead of silently ignoring the rule and generating a deceptively feasible plan.

## Scenarios and modeled resource capability

| Industry example | What an order means | Resources | Sample capabilities | Not included |
|---|---|---|---|---|
| Discrete manufacturing | component batch | CNC mills, QC bench | `milling`, `inspection` | material shortages, combined machinist + CNC |
| Field service | maintenance ticket | qualified technicians | `mechanical`, `electrical`, `diagnostics` | travel times, customer site locations |
| Warehouse | fulfillment batch | picking and packing stations | `pick`, `pack` | simultaneous human + station, parcel carriers |

All samples are **fictional illustrations**. An additional healthcare/laboratory adapter must not be described as clinically safe without workflow-specific validation and governance.

## Guardrails for future extensions

- Version `schema_version` and migrate explicitly; old examples must still load unchanged.
- Each new constraint requires a *model encoding + independent feasibility check + negative test + baseline support + benchmark*, all in one PR. Do not add front-end controls that do not change the mathematical model.
- Reserve stable operation keys (`work_order_id::step_index`) across all adapters; reject duplicates and unknown constraints.
- Keep industry adapters outside the optimizer and do not introduce arbitrary plugin imports.
- New engines implement the existing `ENGINES` registry contract and are compared on matched objectives and equal time budgets.
- Keep user data separate from GitHub source. Real operational data must not be sent to a public demo or committed.
- Changes land on a feature branch, through CI, before merging to `main`.

## Milestone sequence

- **v0.6 — Universal resource contract:** 3 sectors, API, guided edits, synthetic benchmarks, strict capability matching and explicit scope limitations.
- **v0.7 — Hard constraint depth:** simultaneous resource occupancy (e.g. machine + operator), shifts/calendars, setup/changeover, rigorous independent validator and CP-SAT feasibility comparison.
- **v0.8 — Planning under change:** disruption handling for canonical scenarios, commitment stability vs tardiness trade-offs, robust scenarios and pause/approve/restore behavior.
- **v0.9 — Real integrations:** explicit CSV/ERP adapter contracts, data quality checks, versioned snapshots and provenance; multi-tenant authentication/security review before handling sensitive records.
- **v1.0 — Case study:** independent benchmarks, reproducible scripts, latency/scaling experiments, explainable trade-offs, hosted synthetic demo, operator validation and a documented set of honest claims.
