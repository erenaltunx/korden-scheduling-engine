"""Independent correctness/proof tests for applied scheduling neighborhood search."""
import pytest
from optera.baseline import POLICIES,dispatch,dispatch_job_order
from optera.evaluation import evaluate,check_schedule
from optera.hybrid import hybrid_optimize
from optera.local_search import improve_schedule
from optera.service import compare
from research_lab import make_factory
from hybrid_lab import study,save_study


@pytest.mark.parametrize('profile',['single_cell','two_stage','flexible_cell','congested_cell'])
def test_search_is_feasible_and_never_worse_than_best_of_four(profile):
    data=make_factory(profile,230011)
    baseline=min(evaluate(data,dispatch(data,p))['weighted_tardiness'] for p in POLICIES)
    result=improve_schedule(data,110)
    assert result['weighted_tardiness']<=baseline
    assert not result['optimality_proven']
    assert 4<=result['evaluations']<=110
    assert check_schedule(data,result['schedule'])==[]


def test_order_dispatch_validates_exact_permutation():
    data=make_factory('single_cell',230011)
    ids=[j['id'] for j in data['jobs']]
    assert not check_schedule(data,dispatch_job_order(data,ids[::-1]))
    with pytest.raises(ValueError,match='permutation'):
        dispatch_job_order(data,ids[:-1])
    with pytest.raises(ValueError,match='permutation'):
        dispatch_job_order(data,ids[:-1]+[ids[0]])


def test_hybrid_with_tight_milp_is_feasible_and_metadata_is_fair():
    data=make_factory('congested_cell',230011)
    out=hybrid_optimize(data,time_limit=.7,max_evaluations=120)
    assert not check_schedule(data,out['schedule'])
    assert out['solver']['selected_algorithm'] in {'milp_highs','local_search'}
    assert out['solver']['local_search_evaluations']<=120
    assert out['solver']['total_wall_seconds']>=out['solver']['local_search_seconds']
    assert out['solver']['optimality_proven'] is False


def test_makespan_hybrid_is_disallowed():
    with pytest.raises(ValueError,match='weighted_tardiness'):
        hybrid_optimize(make_factory('single_cell',120),1,objective='makespan')


def test_end_to_end_service_uses_hybrid_engine():
    data=make_factory('single_cell',230011)
    out=compare(data,2,engine='hybrid_search_highs')
    assert out['engine']=='hybrid_search_highs'
    assert check_schedule(data,out['optimized']['schedule'])==[]
    assert out['solver']['selected_algorithm'] in {'milp_highs','local_search'}


def test_benchmark_exports_full_audit(tmp_path):
    results=study(count=2,seed=1200,limit=.5,evaluations=40,profiles=('two_stage','congested_cell'))
    assert results['summary']['instances']==4
    assert all(r['hybrid_weighted_tardiness']<=r['baseline_weighted_tardiness'] for r in results['rows'])
    paths=save_study(results,tmp_path/'hybrid')
    assert paths[0].exists() and paths[1].exists()


def test_invalid_search_budget_rejected():
    with pytest.raises(ValueError):improve_schedule(make_factory('single_cell',120),3)
