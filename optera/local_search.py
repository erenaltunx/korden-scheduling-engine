"""Deterministic feasible job-order neighborhood search for high-mix machining cells.

Engineering scope: swap/insertion local search over complete job priority lists.
This is a heuristic incumbent builder, NOT a mathematical optimum certificate.
Every proposed plan is built by the same resource-capacity and changeover
mechanics used by the classical baselines and independently checked.
"""
from __future__ import annotations

from time import perf_counter

from .baseline import POLICIES, dispatch_job_order, policy_priority
from .evaluation import check_schedule, evaluate
from .model import validate_scenario


def improve_schedule(data: dict, max_evaluations: int = 180) -> dict:
    validate_scenario(data)
    if type(max_evaluations) is not int or not 4 <= max_evaluations <= 2000:
        raise ValueError('max_evaluations must be 4..2000')
    start=perf_counter()
    orderings = [tuple(j['id'] for j in sorted(data['jobs'], key=lambda j: policy_priority(j, p)))
                 for p in POLICIES]
    history: dict[tuple[str, ...], tuple[tuple[int, int], list[dict]]] = {}

    def evaluate_order(order: tuple[str, ...]):
        if order not in history:
            scheduled=dispatch_job_order(data,order)
            invalid=check_schedule(data,scheduled)
            if invalid:
                raise AssertionError(f'Generated invalid schedule: {invalid}')
            kpis=evaluate(data,scheduled)
            history[order]=((kpis['weighted_tardiness'],kpis['makespan']),scheduled)
        return history[order]

    # All four conventional dispatch policies receive an identical feasible
    # schedule evaluation; choose lexicographically best value at initialization.
    for order in orderings:
        evaluate_order(order)
    initial_order=min(orderings,key=lambda o:(history[o][0],o))
    best=initial_order
    passes=0
    while len(history)<max_evaluations:
        champion=best
        champion_metrics=history[best][0]
        n=len(best)
        # Improvement via swapping or insertion of jobs; no hidden RNG.
        for i in range(n):
            if len(history)>=max_evaluations:break
            for j in range(i+1,n):
                if len(history)>=max_evaluations:break
                trial=list(best);trial[i],trial[j]=trial[j],trial[i]
                trial=tuple(trial)
                metrics,_=evaluate_order(trial)
                if (metrics,trial)<(champion_metrics,champion):
                    champion=trial;champion_metrics=metrics
        if len(history)<max_evaluations:
            for i in range(n):
                if len(history)>=max_evaluations:break
                for j in range(n):
                    if len(history)>=max_evaluations:break
                    if i==j:continue
                    trial=list(best)
                    moved=trial.pop(i);trial.insert(j,moved)
                    trial=tuple(trial)
                    metrics,_=evaluate_order(trial)
                    if (metrics,trial)<(champion_metrics,champion):
                        champion=trial;champion_metrics=metrics
        if champion==best:break
        best=champion
        passes+=1
    metric,schedule=history[best]
    return {'schedule':schedule,'metrics':evaluate(data,schedule),
            'algorithm':'Deterministic job-order local search',
            'optimality_proven':False,
            'evaluations':len(history), 'improvement_passes':passes,
            'initial_weighted_tardiness':history[initial_order][0][0],
            'weighted_tardiness':metric[0], 'job_priority':list(best),
            'elapsed_seconds':round(perf_counter()-start,4)}
