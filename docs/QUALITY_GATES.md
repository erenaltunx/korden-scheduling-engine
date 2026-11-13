# Quality gates — no merge without evidence

Checklist for each new algorithm, extra production constraint, or API feature:

- [ ] A minimal failing test describes the intended change.
- [ ] All previous scenarios remain valid and weighted-tardiness KPI meaning is unchanged.
- [ ] Every new scheduling constraint is checked by the **independent** feasibility checker, not just the optimizer.
- [ ] Solver status accurately distinguishes optimal, time limit, fallback, and errors.
- [ ] Public demo caps, data non-persistence and private-history isolation are tested.
- [ ] Database migration is forward-compatible and a restore from backup has been tested.
- [ ] Unit, API, Windows runtime, integration, benchmark and Docker smoke checks pass in GitHub Actions.
- [ ] New settings have safe defaults and are documented in `.env.example`.
- [ ] No credentials, customer data, cache, experiment database or compiled files are committed.
- [ ] Performance changes compare the **same** scenario seeds, baseline and solver limits.
- [ ] Release is tagged only after CI passes; no force push to `main`.

## Local developer validation

```bash
python -m pip install -r requirements.txt
python -m pip check
python -m pytest -q
python benchmark_suite.py --count 10 --jobs 5 --time-limit 4 --out artifacts/ci_suite
python -m compileall -q korden
```

For every claimed improvement, keep exact dataset, machine conditions, software version, baseline, seed and solver status with the numbers. Test data does not imply real-factory savings.
