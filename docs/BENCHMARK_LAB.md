# KORDEN Benchmark Lab — comparison against four competing policies

## Aim
Test whether the scheduling optimizer outperforms the **best** classical baseline per instance, rather than a potentially weak single EDD policy. Results are on synthetic scheduling problems, not measured real-world savings.

## Methods
- Four job-level priority policies: EDD (earliest due date), FIFO (earliest release date), SPT (shortest total processing time), WSPT (total processing time divided by job priority weight).
- Each policy assigns a job's operations in precedence order to the earliest completion slot on eligible machines, avoiding both downtime and existing tasks.
- MILP minimizes weighted tardiness first, then makespan; respects the same input constraints.
- Every generated baseline and solver schedule is independently checked for feasibility.
- Held-out deterministic seeds default to `100..159`, keeping the first report's `0..19` as a development comparison.
- Recommended outcome is the feasible solver schedule unless it loses to the best classical plan; in that case the best classical plan is explicitly retained and the fallback is counted.
- A proven mathematical optimum applies only to the modeled MILP; an incumbent may be suboptimal when solver times out.
- Pooled improvement = (sum(best classical weighted tardiness) - sum(delivered weighted tardiness)) / sum(best classical weighted tardiness); undefined when denominator is zero.
- Zero-delay instances remain in pooled totals. Percentage gains for individual zero-baseline cases are null (not 100%).
- Machine scheduling uses integer-hour time grid. Synthetic priority weights are not financial currency.

## Run
```bash
python benchmark_lab.py --count 60 --jobs 5 --start-seed 100 --time-limit 2 --out artifacts/heldout_60
```
This produces CSV + JSON reports with every seed, heuristic score, solver status, optimality proof, and solve-time.

## Limits
The generator is synthetic and scenario distribution specific; independent public benchmark datasets are needed for externally robust evidence. No staffing, shift, stochastic failures, setup/changeover times or shop-floor live execution integration. Solver timings vary by hardware. No real factory KPI or monetary savings is claimed.
