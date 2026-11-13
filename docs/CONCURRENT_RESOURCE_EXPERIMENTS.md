# v0.7 — Simultaneous support-resource benchmark

The original manufacturing, field-service and warehouse demo scenarios were extended with one **fixed shared supporting resource**: a CNC-qualified operator, a service vehicle, or a packing worker. Every qualifying task occupies **both** its primary machine/technician/station and that supporting resource at the same time. The same independent checker tests all resource conflicts.

These are still **fictional small scenarios**. They prove model behavior and observable objective differences, not business savings.

```bash
python -m pytest -q
python universal_benchmark.py --limit 8 --out artifacts/v07
# Reproduce original v0.6 results using immutable historical fixtures:
python universal_benchmark.py --dataset-dir samples/archives/v06 --limit 8 --out artifacts/v06
```

| Example | Orders | Steps | Primary + supporting resources | Best classical policy weighted tardiness | HiGHS weighted tardiness | Relative reduction |
|---|---:|---:|---:|---:|---:|---:|
| Manufacturing | 5 | 10 | 4 | 121 | 121 | 0.00% |
| Field service | 5 | 7 | 4 | 31 | 18 | 41.94% |
| Warehouse operations | 6 | 12 | 5 | 484 | 272 | 43.80% |

All three solver solutions were proven optimal within the 8-second time cap in the initial local run. The **manufacturing baseline itself was optimal**, so it would be misleading to force a nonzero improvement claim. Results are in distinct weighted-time units (hours for manufacturing/field service, minutes for warehouse), and **must not be combined into one percentage**.

The v0.6 original benchmark is separately reproducible using `samples/archives/v06`, yielding 41→25, 10→2, 200→176. The change in results is due to newly imposed *physical resource constraints*, not changing the optimizer objective or removing hard cases.

This capability still assumes **fixed supporting resource IDs** from the input. It cannot choose a substitute employee or allocate a flexible crew; no real route, material, contractual or fatigue constraints are modeled.
