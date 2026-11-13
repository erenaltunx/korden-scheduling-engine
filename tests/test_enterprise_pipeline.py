"""CSV -> normalized model -> MILP -> BI export / SQL, including API and adversarial inputs."""
from pathlib import Path
import csv
from io import StringIO
import sqlite3
from copy import deepcopy
import pytest
from fastapi.testclient import TestClient
from korden.api import app
from korden.data_pipeline import (load_planning_directory, import_planning_csv,
    export_reporting, reporting_tables, make_csv)
from korden.universal import normalize_universal
from korden.service import compare
from staffing_lab import run_lab


ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'samples'/'enterprise'/'field_service'


def source():
    return load_planning_directory(DATA,name='Customer maintenance planning',industry='Service',time_unit='minute')


def tables():
    return {p.stem:p.read_text() for p in DATA.glob('*.csv')}


def test_ingest_and_milp_end_to_end():
    raw=source();sol=compare(normalize_universal(raw),4)
    assert raw['industry']=='Service'
    assert sol['solver']['optimality_proven']
    assert sol['optimized']['metrics']['weighted_tardiness']==16
    assert sol['optimized']['metrics']['late_jobs']==1


def test_sql_and_bi_exports_reconcile_to_optimizer(tmp_path):
    raw=source();result=compare(normalize_universal(raw),4)
    exported=export_reporting(raw,result,tmp_path,experiment_id='contract1')
    assert exported['rows']=={'run_summary':2,'order_kpis':4,'operation_schedule':4,'resource_bookings':8}
    con=sqlite3.connect(exported['files']['sqlite'])
    try:
        summary=con.execute('SELECT plan, weighted_tardiness FROM run_summary ORDER BY plan').fetchall()
        assert summary==[('baseline',16),('optimized',16)]
        for label, score in summary:
            assert con.execute('SELECT SUM(weighted_tardiness) FROM order_kpis WHERE plan=?',(label,)).fetchone()[0]==score
        bookings=con.execute('SELECT COUNT(*) FROM resource_bookings WHERE role=?',('support',)).fetchone()[0]
        assert bookings==4
        assert con.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    finally:
        con.close()
    with open(exported['files']['operation_schedule']) as f:
        assert sum(1 for _ in csv.DictReader(f))==4


def test_export_is_append_only_and_uses_unique_run_identifier(tmp_path):
    raw=source();result=compare(normalize_universal(raw),4)
    export_reporting(raw,result,tmp_path,experiment_id='one')
    export_reporting(raw,result,tmp_path,experiment_id='two')
    with sqlite3.connect(tmp_path/'planning_analytics.sqlite3') as con:
        assert con.execute('SELECT COUNT(*) FROM experiments').fetchone()[0]==2
        assert con.execute('SELECT COUNT(*) FROM order_kpis').fetchone()[0]==8
        with pytest.raises(sqlite3.IntegrityError):
            export_reporting(raw,result,tmp_path,experiment_id='one')


def test_csv_missing_duplicate_and_unknown_column_rejected():
    raw=tables()
    raw['steps']=raw['steps'].replace('order_id,sequence,', 'order_id,sequence,other_column,',1)
    with pytest.raises(ValueError,match='columns'):
        import_planning_csv(raw,name='x',industry='y',time_unit='hour')
    raw=tables()
    raw['resources']=raw['resources'].replace('resource_id,name,', 'resource_id,resource_id,',1)
    with pytest.raises(ValueError,match='columns'):
        import_planning_csv(raw,name='x',industry='y',time_unit='hour')


def test_csv_cross_table_keys_and_sequence_rejected():
    raw=tables();raw['steps']=raw['steps'].replace('B,1,repair','Z,1,repair')
    with pytest.raises(ValueError,match='Unknown order'):
        import_planning_csv(raw,name='x',industry='y',time_unit='hour')
    raw=tables();raw['steps']=raw['steps'].replace('B,1,repair','B,2,repair')
    with pytest.raises(ValueError,match='sequence'):
        import_planning_csv(raw,name='x',industry='y',time_unit='hour')


def test_csv_formula_injection_is_escaped():
    output=make_csv([{'id':'=1+2','label':'  @SUM(A1:A2)'}],['id','label'])
    values=list(csv.DictReader(StringIO(output)))[0]
    assert values['id'].startswith("'=")
    assert values['label'].startswith("'  @")


def test_invalid_schedule_never_reaches_bi_report():
    raw=source();result=compare(normalize_universal(raw),4)
    corrupted=deepcopy(result)
    corrupted['optimized']['schedule'][1]['start']=corrupted['optimized']['schedule'][0]['start']
    corrupted['optimized']['schedule'][1]['end']=corrupted['optimized']['schedule'][0]['end']
    corrupted['optimized']['schedule'][1]['support_resources']=corrupted['optimized']['schedule'][0]['support_resources']
    with pytest.raises(ValueError,match='Infeasible'):
        reporting_tables(raw,corrupted,experiment_id='test')


def test_csv_api_import_and_report_download():
    client=TestClient(app)
    response=client.post('/api/enterprise/import-csv',json={
        'tables':tables(),'name':'Customer maintenance planning',
        'industry':'Service','time_unit':'minute'})
    assert response.status_code==200,response.text
    raw=response.json()['scenario']
    run=client.post('/api/universal/run',json={'scenario':raw,'time_limit':3})
    assert run.status_code==200,run.text
    archive=client.post('/api/enterprise/export-bi',json={'scenario':raw,'result':run.json()})
    assert archive.status_code==200,archive.text
    assert archive.headers['content-type']=='application/zip'
    import io,zipfile
    with zipfile.ZipFile(io.BytesIO(archive.content)) as z:
        assert sorted(z.namelist())==sorted(f'{x}.csv' for x in ['run_summary','order_kpis','operation_schedule','resource_bookings'])


def test_csv_import_api_fails_closed():
    client=TestClient(app)
    invalid=tables();invalid['steps']=invalid['steps'].replace(',certified',',unlicensed')
    r=client.post('/api/enterprise/import-csv',json={
       'tables':invalid,'name':'x','industry':'y','time_unit':'hour'})
    assert r.status_code==422


def test_dynamic_staffing_benchmark_is_seeded_and_reproducible():
    first,rows=run_lab(count=3,time_limit=3,seed_start=1000)
    second,_=run_lab(count=3,time_limit=3,seed_start=1000)
    assert first['fixed_total']==second['fixed_total']
    assert first['flexible_total']==second['flexible_total']
    assert first['both_optimal']==3
    assert all(r['flexible_score']<=r['fixed_score'] for r in rows)


@pytest.mark.parametrize('sector', ['manufacturing_flexible_crew','warehouse_flexible_crew'])
def test_industry_csv_roundtrip_with_skill_pool_and_feasibility(sector):
    from korden.evaluation import check_schedule
    raw=load_planning_directory(ROOT/'samples'/'enterprise'/sector,name='Imported '+sector,
      industry='Manufacturing' if sector.startswith('manufacturing') else 'Warehouse',
      time_unit='hour' if sector.startswith('manufacturing') else 'minute')
    compiled=normalize_universal(raw)
    assert any('support_options' in op for job in compiled['jobs'] for op in job['operations'])
    answer=compare(compiled,5)
    assert check_schedule(compiled,answer['optimized']['schedule'])==[]
    assert answer['optimized']['metrics']['weighted_tardiness']<=answer['baseline']['metrics']['weighted_tardiness']
