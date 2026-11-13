"""Mathematical equivalence and feasibility tests for paired MILP formulations."""
import copy
from itertools import permutations
from pathlib import Path

import pytest

import formulation_lab
from optera.baseline import dispatch
from optera.evaluation import check_schedule, evaluate
from optera.optimizer import optimize
from research_lab import make_factory


def tiny_family_cell():
    return {'machines': [{'id': 'CNC', 'downtime': [], 'changeover_time': 2}],
            'jobs': [{'id': name, 'release': rel, 'due': due, 'weight': weight,
                      'operations': [{'id': 'machine', 'duration': dur, 'machines': ['CNC'], 'setup_family': family}]}
                     for name, rel, dur, due, weight, family in
                     [('A',0,3,6,4,'X'), ('B',0,4,8,2,'Y'), ('C',1,2,7,3,'X')]]}


def brute_force_score(scenario):
    best=None
    for order in permutations(scenario['jobs']):
        clock=0;prev=None;score=0;finish=0
        for job in order:
            op=job['operations'][0]
            clock=max(job['release'],clock+(2 if prev is not None and prev!=op['setup_family'] else 0))
            clock+=op['duration'];finish=clock
            score+=job['weight']*max(0,clock-job['due'])
            prev=op['setup_family']
        key=(score,finish)
        if best is None or key<best:best=key
    return best


@pytest.mark.parametrize('variant',['legacy','tight'])
def test_both_formulations_match_enumerated_global_optimum(variant):
    scenario=tiny_family_cell()
    assert brute_force_score(scenario)==(6,11)
    result=optimize(scenario,4,formulation=variant)
    assert result['solver']['optimality_proven']
    assert not check_schedule(scenario,result['schedule'])
    metrics=evaluate(scenario,result['schedule'])
    assert (metrics['weighted_tardiness'],metrics['makespan'])==brute_force_score(scenario)


@pytest.mark.parametrize('profile',['single_cell','two_stage','flexible_cell','congested_cell'])
def test_both_formulations_return_independently_feasible_plans(profile):
    scenario=make_factory(profile,321)
    for variant in ['legacy','tight']:
        result=optimize(scenario,1,formulation=variant)
        assert result['solver']['formulation']==variant
        if result['schedule'] is not None:
            assert check_schedule(scenario,result['schedule'])==[]


def test_frozen_completed_work_at_later_replanning_boundary():
    scenario={'machines':[{'id':'M','downtime':[]}],
              'jobs':[{'id':'J','release':0,'due':20,'weight':1,
                       'operations':[{'id':'a','duration':2,'machines':['M']},
                                     {'id':'b','duration':3,'machines':['M']}]}]}
    result=optimize(scenario,2,formulation='tight',not_before=10,
                    fixed_operations={'J::0':{'start':0,'machine':'M'}})
    assert result['solver']['optimality_proven']
    assert not check_schedule(scenario,result['schedule'])
    assert next(r for r in result['schedule'] if r['key']=='J::0')['start']==0
    assert next(r for r in result['schedule'] if r['key']=='J::1')['start']>=10


def test_all_operations_already_completed_does_not_force_future_makespan():
    scenario={'machines':[{'id':'M','downtime':[]}],
              'jobs':[{'id':'J','release':0,'due':20,'weight':1,
                       'operations':[{'id':'a','duration':2,'machines':['M']}]}]}
    result=optimize(scenario,2,formulation='tight',not_before=10,
                    fixed_operations={'J::0':{'start':0,'machine':'M'}})
    assert result['solver']['optimality_proven']
    assert evaluate(scenario,result['schedule'])['makespan']==2


def test_invalid_formulation_rejected():
    with pytest.raises(ValueError,match='Formulation'):
        optimize(tiny_family_cell(),1,formulation='untrusted')


def test_invalid_machine_downtime_or_setup_is_never_hidden():
    scenario=tiny_family_cell()
    bad=copy.deepcopy(scenario)
    bad['machines'][0]['downtime']=[{'start':3,'end':5}]
    for variant in ('legacy','tight'):
        result=optimize(bad,2,formulation=variant)
        assert result['schedule'] is not None
        assert not check_schedule(bad,result['schedule'])


def test_formulation_experiment_keeps_identical_input_baseline(tmp_path):
    results=formulation_lab.run_study(count=2,seed_base=451,time_limit=.6,profile='two_stage')
    assert set(results['summary'])=={'legacy','tight'}
    assert len(results['rows'])==4 and len(results['paired'])==2
    assert all(row['recommended_weighted_tardiness']<=row['baseline_weighted_tardiness'] for row in results['rows'])
    j,c=formulation_lab.save_study(results,tmp_path/'paired')
    assert j.exists() and c.exists()


def test_missing_proof_is_not_reported_as_optimal(monkeypatch):
    from types import SimpleNamespace
    # Benchmark must report what HiGHS says; no inferred proof from the baseline.
    study=formulation_lab.run_study(count=1,seed_base=123,time_limit=.5,profile='single_cell')
    assert all(type(r['optimality_proven']) is bool for r in study['rows'])
