"""Run external job-shop instances against published Cmax optima, no cherry-picking.

Usage: python public_benchmark.py --instance ft06 --time-limit 20
"""
import argparse
import json
from pathlib import Path
from korden.public_benchmarks import PUBLIC_INSTANCES, load_jsplib
from korden.baseline import POLICIES, dispatch
from korden.evaluation import evaluate, check_schedule
from korden.optimizer import optimize


def evaluate_public(name: str, time_limit: float) -> dict:
    scenario = load_jsplib(name)
    rules = {p: evaluate(scenario, dispatch(scenario, p))['makespan'] for p in POLICIES}
    answer = optimize(scenario, time_limit, objective='makespan')
    schedule = answer['schedule']
    if schedule is not None:
        errors = check_schedule(scenario, schedule)
        if errors:
            raise RuntimeError('Public benchmark schedule violates model: '+ '; '.join(errors))
        makespan = evaluate(scenario, schedule)['makespan']
    else:
        makespan = None
    known = PUBLIC_INSTANCES[name]
    if makespan is not None and makespan < known:
        raise RuntimeError('Computed schedule beats published optimum: inspect model and parser')
    return {
        'instance': name, 'proven_known_optimum_makespan': known,
        'num_jobs': len(scenario['jobs']), 'num_operations': sum(len(j['operations']) for j in scenario['jobs']),
        'baseline_makespans': rules, 'best_baseline_makespan': min(rules.values()),
        'solver_makespan': makespan, 'gap_to_known_optimum_pct': round(100*(makespan-known)/known,2) if makespan else None,
        'solver': answer['solver'],
        'proven_optimality_matches_reference': answer['solver']['optimality_proven'] and makespan==known,
        'source': f'https://github.com/tamy0612/JSPLIB/blob/master/instances/{name}',
        'warning': 'Published JSP synthetic benchmark, minimizing makespan; not factory savings or tardiness performance.'
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--instance', choices=sorted(PUBLIC_INSTANCES), default='ft06')
    parser.add_argument('--time-limit', type=float, default=15)
    parser.add_argument('--out', type=Path)
    opts=parser.parse_args()
    report=evaluate_public(opts.instance,opts.time_limit)
    content=json.dumps(report,indent=2)
    if opts.out:
        opts.out.parent.mkdir(parents=True,exist_ok=True)
        opts.out.write_text(content+'\n',encoding='utf-8')
    print(content)

if __name__=='__main__':
    main()
