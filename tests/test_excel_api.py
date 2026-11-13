"""Real frontend-oriented Excel example, import, normalisation and API validation."""
import base64
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from openpyxl import load_workbook

from optera.api import app

client = TestClient(app)
ROOT = Path(__file__).resolve().parents[1]


def payload(workbook: bytes) -> dict:
    return {
        'workbook_base64': base64.b64encode(workbook).decode('ascii'),
        'name': 'CNC case from Excel', 'industry': 'Manufacturing', 'time_unit': 'hour',
    }


def test_template_download_and_excel_import():
    download = client.get('/api/enterprise/template-xlsx')
    assert download.status_code == 200, download.text
    assert download.headers['content-type'].startswith('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    assert 'attachment' in download.headers['content-disposition']
    workbook = load_workbook(BytesIO(download.content), read_only=True)
    assert {'resources', 'orders', 'steps'}.issubset(set(workbook.sheetnames))
    workbook.close()

    imported = client.post('/api/enterprise/import-xlsx', json=payload(download.content))
    assert imported.status_code == 200, imported.text
    result = imported.json()
    assert result['scenario']['industry'] == 'Manufacturing'
    assert len(result['normalized_scenario']['jobs']) >= 2
    assert result['profile']['steps'] >= len(result['normalized_scenario']['jobs'])


def test_excel_formula_rejected_with_location():
    original = client.get('/api/enterprise/template-xlsx').content
    workbook = load_workbook(BytesIO(original))
    workbook['steps']['E2'] = '=2+3'
    target = BytesIO();workbook.save(target)
    refused = client.post('/api/enterprise/import-xlsx', json=payload(target.getvalue()))
    assert refused.status_code == 422
    assert 'steps!E2' in refused.json()['detail']
    assert 'formula' in refused.json()['detail']


def test_bad_base64_is_rejected():
    bad = payload(b'fake')
    bad['workbook_base64'] = '&not-base64%'
    refused = client.post('/api/enterprise/import-xlsx', json=bad)
    assert refused.status_code == 422
