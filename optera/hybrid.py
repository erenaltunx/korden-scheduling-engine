"""Combined finite-capacity planner: deterministic local search plus MILP/HiGHS.

Unlike a naive 'best of two' claim, this wrapper validates both candidate
schedules and reports a mathematical optimum only when HiGHS proves it.
Local search optimizes weighted tardiness; makespan remains MILP-only.
"""
from __future__ import annotations

from time import perf_counter

from .evaluation import check_schedule, evaluate
from .local_search import improve_schedule
from .model import validate_scenario
from .optimizer import optimize


def hybrid_optimize(data: dict, time_limit: float = 8.0, *,
                    objective: str = 'weighted_tardiness',
                    max_evaluations: int = 150) -> dict:
    validate_scenario(data)
    if objective != 'weighted_tardiness':
        raise ValueError('Hybrid mode supports weighted_tardiness only; use milp_highs for makespan')
    # Keep the HiGHS solve-time budget unmodified and expose the additional
    # heuristic runtime instead of hiding it under the solver time limit.
    t0 = perf_counter()
    heuristic = improve_schedule(data, max_evaluations=max_evaluations)
    candidate = optimize(data, time_limit=time_limit, formulation='tight')
    if check_schedule(data, heuristic['schedule']):
        raise AssertionError('Local-search schedule is infeasible')
    options = [(heuristic['weighted_tardiness'], heuristic['metrics']['makespan'],
                'local_search', heuristic['schedule'])]
    if candidate['schedule'] is not None:
        problems = check_schedule(data, candidate['schedule'])
        if problems:
            raise AssertionError(f'MILP schedule is infeasible: {problems}')
        measure = evaluate(data, candidate['schedule'])
        options.append((measure['weighted_tardiness'], measure['makespan'],
                        'milp_highs', candidate['schedule']))
    chosen = min(options, key=lambda x:(x[0],x[1],x[2]))
    proven = bool(candidate['solver']['optimality_proven']) and candidate['schedule'] is not None
    if proven:
        exact = next(o for o in options if o[2]=='milp_highs')
        if (chosen[0], chosen[1]) < (exact[0],exact[1]):
            raise AssertionError('A heuristic beat an MILP solution reported as mathematically optimal')
    metadata = {
        **candidate['solver'],
        'solver':'Hybrid (deterministic local search + MILP/HiGHS)',
        'status':'optimal' if proven else 'feasible_unproven',
        'selected_algorithm':chosen[2],
        'optimality_proven':proven,
        'local_search_evaluations':heuristic['evaluations'],
        'local_search_seconds':heuristic['elapsed_seconds'],
        'heuristic_weighted_tardiness':heuristic['weighted_tardiness'],
        'milp_weighted_tardiness':(next((o[0] for o in options if o[2]=='milp_highs'),None)),
        'total_wall_seconds':round(perf_counter()-t0,3),
    }
    return {'schedule':chosen[3], 'solver':metadata}
