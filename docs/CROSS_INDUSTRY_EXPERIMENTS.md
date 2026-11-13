# Cross-industry scheduling smoke benchmark — v0.6

The same solver + independent schedule validator were used for three completely different **fictional** workloads. This exercises the universal schema and capability matching; it does **not** establish that KORDEN is ready to manage real businesses.

### Reproduction

```bash
python -m pytest -q
python universal_benchmark.py --dataset-dir samples/archives/v06 --limit 8 --out artifacts/cross_industry_v06
```

The benchmark selects the strongest of four classical policies (EDD, FIFO, SPT, WSPT) **per scenario** and compares the optimized schedule with that policy using the same integer time unit. Both baseline and optimized schedules are validated by the independent feasibility checker. Tests assess constraints, APIs and fail-closed unknown fields, not just numeric outcomes.

| Example workload | Orders | Steps | Resource count | Best-of-four weighted tardiness | HiGHS weighted tardiness | Relative improvement |
|---|---:|---:|---:|---:|---:|---:|
| Discrete manufacturing | 5 | 10 | 3 | 41 | 25 | 39.02% |
| Field service | 5 | 7 | 3 | 10 | 2 | 80.00% |
| Warehouse operations | 6 | 12 | 4 | 200 | 176 | 12.00% |

These are **weighted units of lateness**, not currency. Manufacturing/service use hours, warehouse uses minutes. **Never aggregate different units across sectors.** HiGHS reported proven optimality for all three illustrative inputs in the initial 8-second run. A new environment may return a feasible incumbent without proof within the time limit and its actual status must always be reported.

**Limitations:** only three small manually authored examples, not a statistical sample, no stochastic effects, travel or materials, and the selected baselines may already be optimal. These figures are not a forecast of savings at a real business, nor an advertised general cross-industry performance percentage. Use the 60-instance synthetic benchmark and independent JSPLib study separately, with their own objectives and caveats.

Historical v0.6 inputs, frozen before concurrent-resource upgrades: `samples/archives/v06/*.json`; detailed per-policy results: `docs/benchmarks/cross_industry_v06.json` and `.csv`.
