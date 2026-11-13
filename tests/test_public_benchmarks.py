"""Published external instances: independent reference optimum, objective separation."""
import pytest
from fastapi.testclient import TestClient
from optera.api import app
from optera.public_benchmarks import load_jsplib, parse_jobshop
from optera.baseline import dispatch
from optera.evaluation import evaluate, check_schedule
from optera.optimizer import optimize
from optera.service import compare


def test_ft06_reference_problem_reaches_published_optimum():
    scenario=load_jsplib('ft06')
    answer=optimize(scenario,5,objective='makespan')
    assert check_schedule(scenario,answer['schedule'])==[]
    assert evaluate(scenario,answer['schedule'])['makespan']==55
    assert answer['solver']['optimality_proven'] is True
    assert answer['solver']['objective']=='makespan'


def test_la01_is_imported_correctly_with_50_operations():
    scenario=load_jsplib('la01')
    assert len(scenario['jobs'])==10
    assert sum(len(j['operations']) for j in scenario['jobs'])==50
    assert scenario['benchmark_known_optimum_makespan']==666
    assert not check_schedule(scenario,dispatch(scenario,'edd'))


def test_baseline_and_optimizer_compared_on_the_same_objective():
    data=load_jsplib('ft06')
    result=compare(data,5,objective='makespan')
    assert result['target_metric']=='makespan'
    assert result['optimized']['metrics']['makespan']==55
    assert result['improvement_percent']>0
    assert result['solver']['objective']=='makespan'


@pytest.mark.parametrize('wrong', [
    '6 6\n1 2',
    '1 2\n0 2 0 3',
    '1 1\n0 -4',
    '1 1\n4 2',
    'not integers',
])
def test_reject_malformed_public_benchmark(wrong):
    with pytest.raises(ValueError,match='Invalid JSP'):
        parse_jobshop(wrong)


def test_public_api_provides_vetted_instances_only():
    client=TestClient(app)
    assert len(client.get('/api/public-benchmarks').json())==2
    assert client.get('/api/public-benchmarks/ft06').json()['benchmark_known_optimum_makespan']==55
    assert client.get('/api/public-benchmarks/../../secrets').status_code in (400,404)
    assert client.get('/api/public-benchmarks/unknown').status_code==404
