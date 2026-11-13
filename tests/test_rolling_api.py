"""HTTP integration and public-demo isolation for disruption replay."""
from pathlib import Path
from fastapi.testclient import TestClient
import optera.api as module
from optera.service import compare

client=TestClient(module.app)


def original():
    return client.get('/api/scenarios/assembly_cell').json()


def request_body():
    src=original()
    return {'scenario':src,'prior_schedule':compare(src,4)['optimized']['schedule'],
            'now':2,'machine_id':'DRILL','outage_start':12,'outage_end':17,
            'time_limit':4,'baseline_policy':'edd'}


def test_rolling_api_saves_validated_replay_locally(tmp_path, monkeypatch):
    monkeypatch.setenv('OPTERA_DATA_DIR',str(tmp_path))
    monkeypatch.setattr(module,'PUBLIC_DEMO',False)
    r=client.post('/api/reschedule',json=request_body())
    assert r.status_code==200, r.text
    body=r.json()
    assert body['stability']['frozen_operations']>0
    assert body['persisted'] is True
    assert client.get('/api/history/'+body['run_id']).status_code==200


def test_public_demo_does_not_save_disruption_history(monkeypatch):
    monkeypatch.setattr(module,'PUBLIC_DEMO',True)
    r=client.post('/api/reschedule',json=request_body())
    assert r.status_code==200, r.text
    assert r.json()['persisted'] is False
    assert client.get('/api/history').status_code==404


def test_public_demo_rejects_oversized_disruption_solver(monkeypatch):
    monkeypatch.setattr(module,'PUBLIC_DEMO',True)
    body=request_body();body['time_limit']=8
    r=client.post('/api/reschedule',json=body)
    assert r.status_code==422


def test_bad_history_is_rejected_before_reoptimization(monkeypatch):
    monkeypatch.setattr(module,'PUBLIC_DEMO',True)
    body=request_body();body['prior_schedule'].pop()
    r=client.post('/api/reschedule',json=body)
    assert r.status_code==422
    assert 'Invalid committed schedule' in r.json()['detail']
