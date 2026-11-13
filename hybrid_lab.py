"""Reproducible performance benchmark for hybrid vs classical vs time-limited MILP.

All results independently validated; reports proof only when HiGHS establishes
it. No actual factory cost or speed-up claims. Solver clock and total wall clock
are reported separately because local search adds computation.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import statistics
from pathlib import Path
from time import perf_counter

import scipy

from optera.baseline import POLICIES, dispatch
from optera.evaluation import check_schedule, evaluate
from optera.hybrid import hybrid_optimize
from research_lab import make_factory


def run_case(profile: str, seed: int, limit: float, evaluations: int) -> dict:
    factory = make_factory(profile,seed)
    digest=hashlib.sha256(json.dumps(factory,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    choices=[]
    for p in POLICIES:
        schedule=dispatch(factory,p)
        if check_schedule(factory,schedule):raise AssertionError(f'Invalid classical plan {p}')
        m=evaluate(factory,schedule)
        choices.append((m['weighted_tardiness'],m['makespan'],p))
    base,b_makespan,rule=min(choices)
    t0=perf_counter()
    result=hybrid_optimize(factory,time_limit=limit,max_evaluations=evaluations)
    total=perf_counter()-t0
    if check_schedule(factory,result['schedule']):raise AssertionError('Invalid hybrid plan')
    hybrid=evaluate(factory,result['schedule'])
    if (hybrid['weighted_tardiness'], hybrid['makespan']) > (base,b_makespan):
        raise AssertionError('Hybrid fell behind strongest classical baseline')
    solver=result['solver']
    return {'profile':profile,'seed':seed,'input_sha256':digest,
            'orders':len(factory['jobs']),'operations':sum(len(j['operations']) for j in factory['jobs']),
            'baseline_policy':rule,'baseline_weighted_tardiness':base,
            'local_search_weighted_tardiness':solver['heuristic_weighted_tardiness'],
            'raw_milp_weighted_tardiness':solver['milp_weighted_tardiness'],
            'hybrid_weighted_tardiness':hybrid['weighted_tardiness'],
            'selected_algorithm':solver['selected_algorithm'],
            'optimality_proven':solver['optimality_proven'],
            'relative_mip_gap':solver['relative_mip_gap'],
            'solver_seconds':solver['solve_seconds'],
            'local_search_seconds':solver['local_search_seconds'],
            'full_wall_seconds':round(total,3),
            'evaluated_priority_orders':solver['local_search_evaluations']}


def study(*, count:int=10, seed:int=230011, limit:float=.7, evaluations:int=150,
          profiles:tuple[str,...]=('congested_cell',)) -> dict:
    if type(count) is not int or not 1<=count<=25:raise ValueError('count must be 1..25')
    if type(seed) is not int or not 0<=seed<=1000000000:raise ValueError('seed must be nonnegative int')
    if not .5<=limit<=20:raise ValueError('limit must be 0.5..20')
    if type(evaluations) is not int or not 4<=evaluations<=2000:raise ValueError('evaluations must be 4..2000')
    allowed={'single_cell','two_stage','flexible_cell','congested_cell'}
    if not profiles or set(profiles)-allowed or len(profiles)!=len(set(profiles)):
        raise ValueError('invalid profiles')
    rows=[run_case(profile,seed+i,limit,evaluations) for profile in profiles for i in range(count)]
    base=sum(r['baseline_weighted_tardiness'] for r in rows)
    local=sum(r['local_search_weighted_tardiness'] for r in rows)
    milp=[r for r in rows if r['raw_milp_weighted_tardiness'] is not None]
    chosen=sum(r['hybrid_weighted_tardiness'] for r in rows)
    def reduction(value):return round(100*(base-value)/base,2) if base else None
    return {'metadata':{'synthetic':True,'research':'Optera hybrid algorithm ablation',
                        'profiles':list(profiles),'count_per_profile':count,'seed_base':seed,
                        'time_limit_seconds_for_milp':limit,'local_search_max_evaluations':evaluations,
                        'python':platform.python_version(),'scipy':scipy.__version__,
                        'note':'Independent matched-input comparison. Full wall includes the heuristic and solver; not real factory savings.'},
            'summary':{'instances':len(rows),'work_orders':sum(r['orders'] for r in rows),
                       'operations':sum(r['operations'] for r in rows),
                       'baseline_total':base,'local_search_total':local,'hybrid_total':chosen,
                       'local_search_reduction_percent':reduction(local),
                       'hybrid_reduction_percent':reduction(chosen),
                       'milp_feasible':len(milp),
                       'hybrid_improved':sum(r['hybrid_weighted_tardiness']<r['baseline_weighted_tardiness'] for r in rows),
                       'local_search_selected':sum(r['selected_algorithm']=='local_search' for r in rows),
                       'proven_optima':sum(r['optimality_proven'] for r in rows),
                       'p50_total_wall_seconds':round(statistics.median(r['full_wall_seconds'] for r in rows),3)},
            'rows':rows}


def save_study(data:dict,path:Path):
    path.parent.mkdir(parents=True,exist_ok=True)
    json_path=path.with_suffix('.json');csv_path=path.with_suffix('.csv')
    json_path.write_text(json.dumps(data,indent=2,ensure_ascii=False,sort_keys=True)+'\n',encoding='utf-8')
    with csv_path.open('w',newline='',encoding='utf-8') as out:
        w=csv.DictWriter(out,fieldnames=list(data['rows'][0]));w.writeheader();w.writerows(data['rows'])
    return json_path,csv_path


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--count',type=int,default=10)
    p.add_argument('--seed',type=int,default=230011)
    p.add_argument('--limit',type=float,default=.7)
    p.add_argument('--evaluations',type=int,default=150)
    p.add_argument('--profiles',default='congested_cell',help='Comma-separated selected workshop profiles')
    p.add_argument('--out',type=Path,default=Path('artifacts/hybrid_lab'))
    a=p.parse_args()
    data=study(count=a.count,seed=a.seed,limit=a.limit,evaluations=a.evaluations,
               profiles=tuple(a.profiles.split(',')))
    js,cs=save_study(data,a.out)
    print(json.dumps({'summary':data['summary'],'json':str(js),'csv':str(cs)},indent=2))


if __name__=='__main__':main()
