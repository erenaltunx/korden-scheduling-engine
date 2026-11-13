"""Independent, seeded sensitivity study: fixed roster vs flexible qualified staffing.

All input conditions are identical except choice flexibility; both alternatives
are solved with the same MILP engine to avoid conflating solver and policy.
"""
from __future__ import annotations
import argparse, csv, json, random
from pathlib import Path
from korden.model import validate_scenario
from korden.optimizer import optimize
from korden.evaluation import evaluate


def staffing_instance(seed: int) -> tuple[dict,dict]:
    r=random.Random(seed)
    machines=[dict(id=f'WORKSTATION_{i}',downtime=[]) for i in range(3)]
    for i in range(3):
        start=r.randint(0,6)
        machines.append(dict(id=f'STAFF_{i}',downtime=[{'start':start,'end':start+r.randint(2,5)}]))
    jobs=[]
    for i in range(6):
        duration=r.randint(2,6)
        due=r.randint(4,20)
        jobs.append(dict(id=f'ORDER_{i}',release=r.randint(0,3),due=due,weight=r.randint(1,7),
            operations=[dict(id='serve',duration=duration,machines=[f'WORKSTATION_{i%3}'],
                             support_options=[f'STAFF_{j}' for j in range(3)])]))
    flexible=dict(schema_version=1,factory_name=f'Seeded staffing {seed}',machines=machines,jobs=jobs)
    fixed=json.loads(json.dumps(flexible))
    for i,job in enumerate(fixed['jobs']):
        op=job['operations'][0]
        op['support_resources']=[op.pop('support_options')[i%3]]
    validate_scenario(flexible);validate_scenario(fixed)
    return fixed,flexible


def run_lab(count: int=24, time_limit:float=2, seed_start:int=1000):
    details=[]
    for seed in range(seed_start,seed_start+count):
        fixed,flex=staffing_instance(seed)
        base=optimize(fixed,time_limit)
        adaptive=optimize(flex,time_limit)
        if base['schedule'] is None or adaptive['schedule'] is None:
            raise RuntimeError(f'No feasible solution for seed {seed}')
        base_score=evaluate(fixed,base['schedule'])['weighted_tardiness']
        adaptive_score=evaluate(flex,adaptive['schedule'])['weighted_tardiness']
        # Optimum results across both models are necessary for attribution.
        if not base['solver']['optimality_proven'] or not adaptive['solver']['optimality_proven']:
            raise RuntimeError(f'Unable to certify both staffing optima for seed {seed}')
        if adaptive_score>base_score:
            raise AssertionError(f'Flexible roster worsened optimum for seed {seed}')
        details.append(dict(seed=seed,jobs=len(fixed['jobs']),operations=sum(len(j['operations']) for j in fixed['jobs']),
                            fixed_score=base_score,flexible_score=adaptive_score,
                            delta=base_score-adaptive_score,
                            fixed_solve_seconds=base['solver']['solve_seconds'],
                            flexible_solve_seconds=adaptive['solver']['solve_seconds'],
                            proven_optimal=1))
    a=sum(row['fixed_score'] for row in details);b=sum(row['flexible_score'] for row in details)
    summary=dict(experiment='Fixed preassignment vs MILP-selected staff from identical three-person qualified pool',
                 seed_start=seed_start,count=count,total_jobs=sum(x['jobs'] for x in details),
                 total_operations=sum(x['operations'] for x in details),
                 fixed_total=a,flexible_total=b,
                 relative_reduction_pct=round((a-b)*100/a,2) if a else None,
                 improved=sum(x['delta']>0 for x in details),
                 tied=sum(x['delta']==0 for x in details),both_optimal=sum(x['proven_optimal'] for x in details),
                 statement='Synthetic test only. Fixed staffing is a constrained policy, not an independent real factory outcome.')
    return summary,details


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--count',type=int,default=24)
    parser.add_argument('--seed-start',type=int,default=1000)
    parser.add_argument('--time-limit',type=float,default=2)
    parser.add_argument('--out',type=Path,default=Path('artifacts/staffing_lab'))
    args=parser.parse_args()
    summary,details=run_lab(args.count,args.time_limit,args.seed_start)
    args.out.parent.mkdir(exist_ok=True,parents=True)
    args.out.with_suffix('.json').write_text(json.dumps(dict(summary=summary,instances=details),indent=2)+'\n')
    with args.out.with_suffix('.csv').open('w',newline='') as file:
        writer=csv.DictWriter(file,fieldnames=details[0]);writer.writeheader();writer.writerows(details)
    print(json.dumps(summary,indent=2))

if __name__=='__main__':
    main()
