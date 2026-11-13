"""API smoke tests for the public portfolio demo constraints."""
import json
from pathlib import Path
from fastapi.testclient import TestClient
import optera.api as optera_api

ROOT = Path(__file__).resolve().parent.parent
client = TestClient(optera_api.app)


def example():
    return json.loads((ROOT / 'samples' / 'assembly_cell.json').read_text())


def test_home_and_api_have_expected_routes():
    page = client.get('/')
    assert page.status_code == 200
    assert 'OPTERA' in page.text
    assert client.get('/api/health').json()['status'] == 'ok'
    assert client.get('/api/config').json()['max_solver_seconds'] in (5, 60)


def test_public_demo_rejects_expensive_requests(monkeypatch):
    monkeypatch.setattr(optera_api, 'PUBLIC_DEMO', True)
    scenario = example()
    r = client.post('/api/run', json={'scenario': scenario, 'time_limit': 10})
    assert r.status_code == 422
    assert '5 seconds' in r.json()['detail']


def test_public_demo_accepts_normal_factory(monkeypatch):
    monkeypatch.setattr(optera_api, 'PUBLIC_DEMO', True)
    r = client.post('/api/run', json={'scenario': example(), 'time_limit': 3})
    assert r.status_code == 200
    assert r.json()['optimized']['metrics']['weighted_tardiness'] == 15


def test_public_demo_caps_number_of_orders(monkeypatch):
    monkeypatch.setattr(optera_api, 'PUBLIC_DEMO', True)
    scenario = example()
    template = scenario['jobs'][0]
    while len(scenario['jobs']) <= 8:
        new = json.loads(json.dumps(template))
        new['id'] = f'job-{len(scenario["jobs"])}'
        scenario['jobs'].append(new)
    r = client.post('/api/run', json={'scenario': scenario, 'time_limit': 2})
    assert r.status_code == 422
    assert '8 orders' in r.json()['detail']
