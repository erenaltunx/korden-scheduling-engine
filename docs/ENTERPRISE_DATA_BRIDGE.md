# Enterprise planning data bridge — v0.8

## What this does

KORDEN now supports a complete **CSV → validated universal domain model → mathematical optimizer → independently checked schedules → relational reporting** workflow. It is a reproducible adapter inspired by real enterprise extracts, **not a licensed SAP connector or proof of SAP proficiency**. Both the data-ingestion contract and solver operate without cloud tokens or external services.

### Source tables

Supply three mandatory UTF-8 CSVs: `resources.csv`, `orders.csv`, `steps.csv`. Optionally supply `unavailability.csv`. The exact header contract is enforced by `korden/data_pipeline.py`; extra columns, unknown references, duplicated identifiers, impossible skill requirements, unsupported constraints, and invalid step orders fail closed. `capabilities`, `requires_all`, and staff pools use `;` as list separators.

| CSV | Column names |
|---|---|
| resources.csv | resource_id, name, kind, capabilities |
| orders.csv | order_id, name, available_at, due_at, priority |
| steps.csv | order_id, sequence, step_id, name, duration, requires_all, eligible_resources, reserve_resources, choose_one_support_from, choose_one_support_with |
| unavailability.csv | resource_id, start, end |

Select **either** a list of support resource IDs in `choose_one_support_from` **or** desired skills in `choose_one_support_with` (e.g. `certified`). The solver assigns **exactly one** qualified support resource to that step for its whole duration, in addition to the primary resource. Fixed `reserve_resources` still work. This is **not** multi-person/variable-size team optimization. All resource capacities are one.

Time is nonnegative **integer hour or minute** as declared for the whole scenario. Different units must never be aggregated in a single sum. Operations are sequential within an order, non-preemptive, and require exclusive occupation of the primary resource and chosen support resource.

### Run independently of the web interface

```
python planning_workflow.py --data-dir samples/enterprise/field_service --name "Service pilot" --industry "Service" --time-unit minute --time-limit 5 --out artifacts/service_pilot
python planning_workflow.py --data-dir samples/enterprise/manufacturing_flexible_crew --name "Machining pilot" --industry "Manufacturing" --time-unit hour --time-limit 5 --out artifacts/machining_pilot
python planning_workflow.py --data-dir samples/enterprise/warehouse_flexible_crew --name "Fulfillment pilot" --industry "Warehouse" --time-unit minute --time-limit 5 --out artifacts/fulfillment_pilot
```

Outputs: four Power BI / Excel-ready normalized CSV files plus a SQLite database. The database contains `experiments`, `run_summary`, `order_kpis`, `operation_schedule`, `resource_bookings`. Foreign keys link every reporting fact to the immutable experiment ID. Different runs append rather than deleting history; one ID cannot be accidentally overwritten. `docs/sql/korden_kpi_queries.sql` provides executable SQL business questions.

The browser can import the source CSVs from **Enterprise Data Bridge**, run the same core optimizer, then download a ZIP containing independently verified report CSVs. It does not require writing JSON. Imported inputs are not saved by the import operation. Do not upload proprietary customer data to public demo instances.

### Metrics and evidence

`weighted_tardiness = Σ priority_j × max(0, completion_j − due_j)`. Its unit is *priority-weighted time*, **not EUR/HUF saved**. `makespan = maximum end time`. A resource booking is an exclusive occupation interval; its busy duration is **not** a payroll/time-sheet measure. The pooled improvement must use the same metric, time unit, input set and baseline policy. Each exported schedule is checked independently before reporting. No data cleaning should silently discard rows.

### Known gaps and nonclaims

- No live SAP S/4HANA, Oracle, Kinaxis, WMS or MES credentials/connection.
- No Power BI `.pbix` project, DAX measure suite, or full PL-300 proof yet; CSV/SQL tables **are** ready for importing into Power Query.
- No shift-specific overtime cost, travel-time network, materials, changeover setup or stochastic disruption optimizer yet.
- No solver capacity above the v0.8 bounds (12 exclusive resources / 65 sequential steps); data modeling portability is not evidence of infinite scalability.
- No production deployment, multi-tenant authentication or real business savings. Validate a customer's data under explicit consent and confidentiality controls before any pilot.

### Reproducibility commands

```
python -m pytest -q
python staffing_lab.py --count 24 --seed-start 1000 --time-limit 2 --out artifacts/staffing_lab
python -m compileall -q korden
node --check static/app.js
```
