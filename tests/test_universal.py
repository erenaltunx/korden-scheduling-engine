"""Cross-industry contract and API regression; ensure no constraints disappear."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from korden.api import app
from korden.universal import describe_universal, normalize_universal
from korden.service import compare
from korden.evaluation import check_schedule

ROOT = Path(__file__).resolve().parents[1]


def template(name):
    return json.loads((ROOT / 'samples' / 'universal' / f'{name}.json').read_text())


@pytest.mark.parametrize('name', ['manufacturing', 'field_service', 'warehouse'])
def test_cross_industry_same_core_solver(name):
    source = template(name)
    normalized = normalize_universal(source)
    assert len(normalized['jobs']) == len(source['work_orders'])
    assert len(normalized['machines']) == len(source['resources'])
    result = compare(normalized, 8)
    assert check_schedule(normalized, result['optimized']['schedule']) == []
    assert result['optimized']['metrics']['weighted_tardiness'] <= result['baseline']['metrics']['weighted_tardiness']
    assert describe_universal(source)['time_unit'] == source['time_unit']


def test_all_capabilities_required_for_eligibility():
    data = template('field_service')
    step = data['work_orders'][0]['steps'][0]
    step['requires_all'] = ['diagnostics', 'mechanical']
    output = normalize_universal(data)
    assert output['jobs'][0]['operations'][0]['machines'] == ['TECH_B']


def test_empty_capability_match_is_refused():
    data = template('warehouse')
    data['work_orders'][0]['steps'][0]['requires_all'] = ['forklift_certification']
    with pytest.raises(ValueError, match='no resource'):
        normalize_universal(data)


@pytest.mark.parametrize('invalid', [
    {'path': ['work_orders', 0, 'steps', 0], 'key': 'requires_two_operators', 'value': True},
    {'path': ['resources', 0], 'key': 'capacity', 'value': 3},
    {'path': [], 'key': 'travel_times', 'value': []},
])
def test_unsupported_constraints_fail_closed(invalid):
    data = template('warehouse')
    obj = data
    for item in invalid['path']:
        obj = obj[item]
    obj[invalid['key']] = invalid['value']
    with pytest.raises(ValueError, match='unsupported'):
        normalize_universal(data)


def test_invalid_time_unit_not_silently_converted():
    data = template('field_service')
    data['time_unit'] = 'seconds'
    with pytest.raises(ValueError, match='time_unit'):
        normalize_universal(data)


def test_duplicate_resources_rejected():
    data = template('warehouse')
    data['resources'].append(deepcopy(data['resources'][0]))
    with pytest.raises(ValueError, match='Duplicate resource'):
        normalize_universal(data)


def test_unavailability_copied_without_mutating_source():
    data = template('field_service')
    old = deepcopy(data)
    normalized = normalize_universal(data)
    assert normalized['machines'][0]['downtime'] == [{'start': 8, 'end': 10}]
    normalized['machines'][0]['downtime'][0]['end'] = 100
    assert data == old


def test_eligible_resource_must_exist():
    data = template('field_service')
    data['work_orders'][0]['steps'][0]['eligible_resources'] = ['NOT_A_TECHNICIAN']
    with pytest.raises(ValueError, match='known resources'):
        normalize_universal(data)


def test_http_template_validation_and_run(tmp_path, monkeypatch):
    monkeypatch.setenv('KORDEN_DATA_DIR', str(tmp_path))
    client = TestClient(app)
    r = client.get('/api/universal/templates')
    assert r.status_code == 200
    assert {x['id'] for x in r.json()} == {'manufacturing', 'field_service', 'warehouse'}
    assert client.get('/api/universal/templates/../../bad').status_code == 404
    source = client.get('/api/universal/templates/field_service').json()
    validated = client.post('/api/universal/validate', json={'scenario': source})
    assert validated.status_code == 200
    assert validated.json()['profile']['industry'] == 'Field service'
    result = client.post('/api/universal/run', json={'scenario': source, 'time_limit': 4})
    assert result.status_code == 200, result.text
    body = result.json()
    assert body['domain']['industry'] == 'Field service'
    assert check_schedule(body['normalized_scenario'], body['optimized']['schedule']) == []


def test_http_rejects_unsupported_domain_constraint():
    client = TestClient(app)
    source = template('warehouse')
    source['work_orders'][0]['steps'][0]['requires_two_operators'] = True
    response = client.post('/api/universal/run', json={'scenario': source, 'time_limit': 1})
    assert response.status_code == 422
    assert 'unsupported' in response.json()['detail']


def test_batch_cross_industry_benchmark(tmp_path):
    from universal_benchmark import run
    report = run(['manufacturing', 'field_service', 'warehouse'], 6, tmp_path / 'industry_run')
    assert len(report) == 3
    assert all(row['feasible_schedule'] for row in report)
    assert all(row['optimized_weighted_tardiness'] <= row['best_baseline']['weighted_tardiness'] for row in report)
    assert (tmp_path / 'industry_run.csv').exists()
    assert (tmp_path / 'industry_run.json').exists()


def test_legacy_scenario_version_is_unchanged():
    from korden.service import compare
    example = json.loads((ROOT / 'samples' / 'assembly_cell.json').read_text())
    result = compare(example, 5)
    assert result['optimized']['metrics']['weighted_tardiness'] == 15
    assert result['schema_version'] == 1


def test_public_cross_industry_run_has_no_history(monkeypatch):
    import korden.api as api
    monkeypatch.setattr(api, 'PUBLIC_DEMO', True)
    client = TestClient(app)
    source = template('manufacturing')
    response = client.post('/api/universal/run', json={'scenario': source, 'time_limit': 3})
    assert response.status_code == 200, response.text
    assert response.json()['persisted'] is False
    assert response.json()['domain']['time_unit'] == 'hour'
    assert client.get('/api/history').status_code == 404
    monkeypatch.setattr(api, 'PUBLIC_DEMO', False)


def test_public_cross_industry_limits_are_enforced(monkeypatch):
    import korden.api as api
    monkeypatch.setattr(api, 'PUBLIC_DEMO', True)
    client = TestClient(app)
    source = template('warehouse')
    response = client.post('/api/universal/run', json={'scenario': source, 'time_limit': 7})
    assert response.status_code == 422
    assert '5 seconds' in response.json()['detail']
    monkeypatch.setattr(api, 'PUBLIC_DEMO', False)
