# Mathematical model — v0.1

## Sets and input

- `J` orders, each with an ordered route of operations `O_j`.
- `M` machines; operation `o` has a set of eligible machines `E_o`.
- `p_o` fixed operation duration, in integer hours.
- `r_j` earliest release, `d_j` due date, `w_j >= 1` due-date weight.
- `D_m` unavailable (maintenance) intervals for machine `m`.

## Decisions

- `s_o`: integer operation start time.
- `x_om`: binary assignment to machine `m`.
- `z_abm`: binary sequence of tasks `a,b` if both use `m`.
- `q_omk`: binary task-before-maintenance selector for maintenance window `k`.
- `T_j`: integer positive tardiness.
- `C_max`: integer schedule makespan.

## Objective

Minimize `(H + 1) * sum(w_j * T_j) + C_max`, with `H` the safe upper bound on all possible makespans. Since `C_max <= H`, this is equivalent to lexicographic minimization of weighted tardiness followed by makespan, for integer time values.

## Constraints

1. `sum_{m in E_o} x_om = 1` for all operations `o`.
2. `s_(j,k+1) >= s_(j,k) + p_(j,k)` for each job's consecutive operations.
3. `s_(j,0) >= r_j`.
4. `0 <= s_o <= H - p_o` and all starts integer.
5. If tasks `a,b` are both assigned to the same machine `m`, either `s_a + p_a <= s_b` or `s_b + p_b <= s_a`; implemented by big-M disjunctions with binary sequence selector `z_abm`. When either task is not assigned to `m`, constraints deactivate.
6. If operation `o` is assigned to `m`, it must lie fully before or fully after every maintenance window `[start,end)` on that machine. Implemented using big-M constraints and binary selectors.
7. `T_j >= s_(j,last) + p_(j,last) - d_j`, `T_j >= 0`.
8. `C_max >= s_o + p_o` for all operations.

`H` is calculated as latest release/maintenance end + sum of all processing times + 1. A sequential schedule starting after the last release or maintenance window always fits inside this bound; therefore the horizon is safe, though not necessarily tight.

The pairwise big-M formulation is generally not the strongest possible relaxation; future releases can replace or strengthen it with CP-SAT intervals / tighter order bounds.

## Baseline

Earliest Due Date (EDD) sorts orders ascending by due date, breaks ties by descending weight and order ID, schedules each order's operations as early as possible on an eligible machine, and selects the eligible machine with the earliest completion time.

EDD is a **heuristic**, not an optimized gold standard, and it has no guarantee of optimality. Improvement percentages are relative to this explicit baseline only.

## Validation

Every computed plan is independently checked for:

- exactly one execution for each operation;
- permitted machine assignment and correct duration;
- all order release dates and operation precedence;
- no machine overlaps, including machine downtime;
- KPI consistency from schedules rather than solver objective values.

## Caveats

Deterministic, non-preemptive finite-horizon model. No shift calendars, demand uncertainty, worker resources, lot sizing, material availability, sequence-dependent setups, or energy costs. These are prospective extensions only.
