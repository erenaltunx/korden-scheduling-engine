"""Regression tests for the mathematical engine and input contracts."""
import copy
import json
from pathlib import Path
import pytest
from korden.baseline import dispatch_edd, earliest_slot
from korden.evaluation import check_schedule, evaluate
from korden.model import horizon, validate_scenario
from korden.optimizer import optimize
from korden.service import compare

ROOT = Path(__file__).resolve().parent.parent


def fixture(name):
    return json.loads((ROOT / 'samples' / f'{name}.json').read_text(encoding='utf-8'))


@pytest.mark.parametrize('name', ['assembly_cell', 'precision_workshop'])
def test_edd_is_feasible(name):
    data = fixture(name)
    schedule = dispatch_edd(data)
    assert check_schedule(data, schedule) == []
    assert len(schedule) == sum(len(j['operations']) for j in data['jobs'])


@pytest.mark.parametrize('name', ['assembly_cell', 'precision_workshop'])
def test_milp_is_feasible_and_improves_objective(name):
    data = fixture(name)
    baseline = evaluate(data, dispatch_edd(data))
    result = optimize(data, time_limit=6)
    assert result['solver']['optimality_proven'] is True
    assert result['solver']['relative_mip_gap'] < 0.001
    assert check_schedule(data, result['schedule']) == []
    advanced = evaluate(data, result['schedule'])
    assert (advanced['weighted_tardiness'], advanced['makespan']) <= (baseline['weighted_tardiness'], baseline['makespan'])
    assert all(s['end'] <= horizon(data) for s in result['schedule'])


def test_reproducible_assembly_cell_metrics():
    outcome = compare(fixture('assembly_cell'), 6)
    assert outcome['baseline']['metrics']['weighted_tardiness'] == 39
    assert outcome['optimized']['metrics']['weighted_tardiness'] == 15
    assert outcome['optimized']['metrics']['makespan'] == 27
    assert outcome['improvement_percent'] == 61.54


def test_earliest_slot_respects_maintenance_and_busy():
    assert earliest_slot(0, 4, [(2, 6), (6, 8), (12, 14)]) == 8
    assert earliest_slot(8, 4, [(2, 6), (6, 8), (12, 14)]) == 8
    assert earliest_slot(9, 4, [(2, 6), (6, 8), (12, 14)]) == 14


def test_checker_catches_machine_overlap():
    data = fixture('assembly_cell')
    schedule = dispatch_edd(data)
    # Force job C first operation on same machine at time zero, overlapping job A.
    target = next(s for s in schedule if s['key'] == 'C::0')
    target['machine'] = 'LATHE'
    target['start'] = 0
    target['end'] = target['duration']
    assert any('overlap' in err.lower() for err in check_schedule(data, schedule))


def test_checker_catches_downtime():
    data = fixture('assembly_cell')
    schedule = dispatch_edd(data)
    target = next(s for s in schedule if s['key'] == 'C::0')
    target['start'] = 10
    target['end'] = 14
    assert any('maintenance' in err.lower() for err in check_schedule(data, schedule))


def test_reject_duplicate_machine():
    data = fixture('assembly_cell')
    data['machines'].append(copy.deepcopy(data['machines'][0]))
    with pytest.raises(ValueError, match='Duplicate machine'):
        validate_scenario(data)


def test_reject_invalid_machine_eligibility():
    data = fixture('assembly_cell')
    data['jobs'][0]['operations'][0]['machines'] = ['NOT-REAL']
    with pytest.raises(ValueError, match='machine'):
        validate_scenario(data)


def test_reject_negative_release_and_zero_duration():
    data = fixture('assembly_cell')
    data['jobs'][0]['release'] = -2
    with pytest.raises(ValueError, match='release'):
        validate_scenario(data)
    data['jobs'][0]['release'] = 0
    data['jobs'][0]['operations'][0]['duration'] = 0
    with pytest.raises(ValueError, match='duration'):
        validate_scenario(data)


def test_optimizer_picks_alternative_machine_around_maintenance():
    data = {
        'factory_name': 'Machine alternatives',
        'machines': [{'id': 'A', 'downtime': [{'start': 0, 'end': 20}]},
                     {'id': 'B', 'downtime': []}],
        'jobs': [{'id': 'X', 'release': 0, 'due': 10, 'weight': 2,
                  'operations': [{'id': 'Step', 'duration': 5, 'machines': ['A', 'B']}]}]
    }
    answer = optimize(data, 4)
    assert answer['solver']['optimality_proven']
    assert answer['schedule'][0]['machine'] == 'B'
    assert answer['schedule'][0]['start'] == 0


def test_lateness_objective_overrides_makespan():
    # Weighted tardiness is lexicographically prior to makespan.
    data = {
        'machines': [{'id': 'M', 'downtime': []}],
        'jobs': [
            {'id': 'long', 'release': 0, 'due': 1, 'weight': 1,
             'operations': [{'id': 'op', 'duration': 6, 'machines': ['M']}]},
            {'id': 'critical', 'release': 0, 'due': 2, 'weight': 100,
             'operations': [{'id': 'op', 'duration': 2, 'machines': ['M']}]},
        ]}
    result = optimize(data, 4)
    assert result['solver']['optimality_proven']
    assert next(t for t in result['schedule'] if t['job']=='critical')['start'] == 0


def test_allows_just_touching_maintenance_window():
    data = {
        'machines': [{'id': 'M', 'downtime': [{'start': 5, 'end': 9}]}],
        'jobs': [{'id': 'one', 'release': 0, 'due': 4, 'weight': 1,
                  'operations': [{'id': 'first', 'duration': 5, 'machines': ['M']}]}]
    }
    result = optimize(data, 3)
    assert result['solver']['optimality_proven']
    assert result['schedule'][0]['start'] == 0
    assert result['schedule'][0]['end'] == 5


def test_api_health_and_scenarios():
    try:
        from fastapi.testclient import TestClient
        from korden.api import app
        client = TestClient(app)
    except ImportError:
        pytest.skip('httpx not installed (optional API integration test)')
    assert client.get('/api/health').json()['status'] == 'ok'
    assert client.get('/api/scenarios').status_code == 200
    data = fixture('assembly_cell')
    result = client.post('/api/run', json={'scenario': data, 'time_limit': 4})
    assert result.status_code == 200
    assert result.json()['optimized']['metrics']['weighted_tardiness'] == 15
