# Held-out baseline audit — 60 synthetic factories

**Version:** KORDEN v0.4.0 | **Run date:** 2026-11-13 | **Distribution:** synthetic deterministic workshops | **Held-out seeds:** 100–159 | **Jobs:** 5 per factory, 3 operations/job | **Solver:** SciPy MILP/HiGHS | **Time cap:** 2 seconds/instance.

- Across **60** synthetic instances, **300** orders, **900** operations.
- Mathematical optimality proven for **60 of 60** under the specified MILP model; larger instances are not covered.
- Compared with the **best of four classical baselines per instance** (EDD, FIFO, SPT, WSPT).
- Pooled weighted tardiness: **404** (strongest heuristic per instance) → **238** (MILP), a **41.09% relative reduction**.
- **21 improvements, 39 ties, zero regressions**; 30 of 60 baseline instances already had zero weighted tardiness.
- All 60 solution schedules pass independent feasibility validation.
- No monetary savings, real production factory claim, or randomized independent third-party benchmark is implied.

Reproduce results:

```bash
python benchmark_lab.py --count 60 --jobs 5 --start-seed 100 --time-limit 2 --out artifacts/heldout_60
```

`heldout_60.csv` SHA-256: `88c76d80e3b25178fed48766453fb22b722e7153b431131a536fdd774848d7c4`. The JSON includes full per-seed metrics and explicit methodology.

**Limitations:** Synthetic generator created and used by the same project; narrow scenario distribution; integer-hour scheduling; no shift availability, sequence-dependent setup or live equipment states. Solver runtimes vary by computer. These numbers should remain labeled *synthetic benchmark results* in any CV or interview.
