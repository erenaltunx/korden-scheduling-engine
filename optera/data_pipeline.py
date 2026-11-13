"""Strict enterprise CSV ingestion and deterministic BI-ready reporting contracts.

All inputs are demo/export files, not credentials or live ERP access. Tables are
sector-neutral. Never silently drop unknown columns or unsupported constraints.
"""
from __future__ import annotations
import csv
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
import sqlite3
import json
import uuid
from .universal import normalize_universal
from .evaluation import evaluate

TABLE_FIELDS = {
    'resources': ('resource_id', 'name', 'kind', 'capabilities'),
    'orders': ('order_id', 'name', 'available_at', 'due_at', 'priority'),
    'steps': ('order_id', 'sequence', 'step_id', 'name', 'duration', 'requires_all',
              'eligible_resources', 'reserve_resources', 'choose_one_support_from', 'choose_one_support_with'),
    'unavailability': ('resource_id', 'start', 'end'),
}
REQUIRED_FIELDS = {
    'resources': {'resource_id', 'name', 'kind', 'capabilities'},
    'orders': {'order_id', 'name', 'available_at', 'due_at', 'priority'},
    'steps': {'order_id','sequence','step_id','name','duration','requires_all'},
    'unavailability': {'resource_id','start','end'},
}


def _read_csv(text: str, table: str) -> list[dict]:
    if not isinstance(text, str) or len(text.encode('utf-8')) > 128 * 1024:
        raise ValueError(f'{table} CSV text must be UTF-8 and at most 128 KiB')
    source = StringIO(text.lstrip('\ufeff'))
    reader = csv.DictReader(source, strict=True)
    headers = reader.fieldnames
    if not headers or len(headers) != len(set(headers)) or set(headers)-set(TABLE_FIELDS[table]) or not REQUIRED_FIELDS[table].issubset(headers):
        raise ValueError(f'{table} CSV has missing, duplicate or unknown columns')
    rows = []
    try:
        for line, row in enumerate(reader, 2):
            if None in row or any(v is None for v in row.values()):
                raise ValueError(f'{table} row {line} has unexpected/missing cells')
            if any(len(str(v)) > 500 for v in row.values()):
                raise ValueError(f'{table} row {line} has overlong values')
            rows.append({key: value.strip() for key,value in row.items()})
            if len(rows) > 500:
                raise ValueError(f'{table} CSV supports at most 500 rows')
    except csv.Error as error:
        raise ValueError(f'{table} has malformed CSV formatting: {error}') from error
    return rows


def _integer(value: str, field: str) -> int:
    if not value or not value.isdecimal():
        raise ValueError(f'{field} must contain a nonnegative integer')
    return int(value)


def _tags(value: str) -> list[str]:
    return [item.strip() for item in value.split(';') if item.strip()]


def import_planning_csv(tables: dict[str, str], *, name: str, industry: str, time_unit: str) -> dict:
    """Convert resources/orders/steps/unavailability CSVs to universal contract.

    The adapter validates through the normalizing solver, so unsupported business
    constraints cannot be silently lost during ingestion.
    """
    if not isinstance(tables, dict) or set(tables) - set(TABLE_FIELDS) or not {'resources','orders','steps'}.issubset(tables):
        raise ValueError('CSV tables must include resources, orders and steps; unavailability is optional')
    rows = {key: _read_csv(value, key) for key, value in tables.items()}
    resources = []
    resource_by_id = {}
    for row in rows['resources']:
        resource = {'id':row['resource_id'], 'name':row['name'], 'kind':row['kind'],
                    'capabilities':_tags(row['capabilities']), 'unavailable':[]}
        if resource['id'] in resource_by_id:
            raise ValueError(f"Duplicate resource in CSV: {resource['id']}")
        resources.append(resource)
        resource_by_id[resource['id']] = resource
    for row in rows.get('unavailability', []):
        resource = resource_by_id.get(row['resource_id'])
        if resource is None:
            raise ValueError(f"Unavailability has unknown resource {row['resource_id']}")
        resource['unavailable'].append({'start':_integer(row['start'],'start'),
                                        'end':_integer(row['end'],'end')})
    orders=[]; orders_by_id={}
    for row in rows['orders']:
        record={'id':row['order_id'],'name':row['name'],
                'available_at':_integer(row['available_at'],'available_at'),
                'due_at':_integer(row['due_at'],'due_at'),
                'priority':_integer(row['priority'],'priority'),'steps':[]}
        if record['id'] in orders_by_id:
            raise ValueError(f"Duplicate order in CSV: {record['id']}")
        orders.append(record);orders_by_id[record['id']]=record
    indexed_steps={key:[] for key in orders_by_id}
    for row in rows['steps']:
        order_id=row['order_id']
        if order_id not in indexed_steps:
            raise ValueError(f'Unknown order in steps table: {order_id}')
        seq=_integer(row['sequence'],'sequence')
        step={'id':row['step_id'],'name':row['name'],
              'duration':_integer(row['duration'],'duration'),
              'requires_all':_tags(row['requires_all'])}
        for field in ('eligible_resources','reserve_resources','choose_one_support_from','choose_one_support_with'):
            if row.get(field):
                step[field]=_tags(row[field])
        indexed_steps[order_id].append((seq, step))
    for record in orders:
        steps=sorted(indexed_steps[record['id']],key=lambda pair:pair[0])
        if [seq for seq,_ in steps] != list(range(1,len(steps)+1)):
            raise ValueError(f"Non-contiguous or duplicate step sequence in order {record['id']}")
        record['steps']=[step for _,step in steps]
    source={'schema_version':1,'name':name,'industry':industry,'time_unit':time_unit,
            'resources':resources,'work_orders':orders}
    normalize_universal(source)
    return source


def load_planning_directory(path: str | Path, *, name: str, industry: str, time_unit: str) -> dict:
    path=Path(path)
    allowed={key:(path/f'{key}.csv') for key in TABLE_FIELDS}
    tables={key:file.read_text(encoding='utf-8-sig') for key,file in allowed.items() if file.is_file()}
    return import_planning_csv(tables,name=name,industry=industry,time_unit=time_unit)


def _csv_safe(value):
    """Prevent spreadsheet formula injection when a user opens exported CSV in Excel."""
    text=str(value if value is not None else '')
    if text.lstrip().startswith(('=', '+', '-', '@', '\t', '\r', '\n')):
        return "'"+text
    return text


def make_csv(rows: list[dict], headers: list[str]) -> str:
    io=StringIO(newline='');writer=csv.DictWriter(io,fieldnames=headers,lineterminator='\n')
    writer.writeheader()
    for row in rows:
        writer.writerow({header:_csv_safe(row.get(header,'')) for header in headers})
    return io.getvalue()


def reporting_tables(source: dict, result: dict, *, experiment_id: str) -> dict[str,list[dict]]:
    compiled = normalize_universal(source)
    if not isinstance(result,dict) or not isinstance(result.get('baseline'),dict) or not isinstance(result.get('optimized'),dict):
        raise ValueError('Optimization result must contain baseline and optimized schedules')
    jobs={j['id']:j for j in compiled['jobs']}
    tables={'run_summary':[], 'order_kpis':[], 'operation_schedule':[], 'resource_bookings':[]}
    for label in ('baseline','optimized'):
        schedule=result[label].get('schedule')
        if not isinstance(schedule,list):
            raise ValueError(f'{label} missing schedule')
        metrics=evaluate(compiled,schedule) # independent feasibility and KPI check
        tables['run_summary'].append(dict(experiment_id=experiment_id,plan=label,
            scenario=source['name'],industry=source['industry'],time_unit=source['time_unit'],
            orders=len(jobs),operations=len(schedule),
            weighted_tardiness=metrics['weighted_tardiness'],
            total_tardiness=metrics['total_tardiness'],late_orders=metrics['late_jobs'],
            makespan=metrics['makespan']))
        for job in compiled['jobs']:
            completion=metrics['job_completion_hours'][job['id']]
            tardiness=max(0,completion-job['due'])
            tables['order_kpis'].append(dict(experiment_id=experiment_id,plan=label,order_id=job['id'],
                release=job['release'],due=job['due'],priority=job['weight'],
                completion=completion,tardiness=tardiness,weighted_tardiness=tardiness*job['weight'],
                late=int(tardiness>0),time_unit=source['time_unit']))
        for step in schedule:
            tables['operation_schedule'].append(dict(experiment_id=experiment_id,plan=label,
                order_id=step['job'],operation_id=step['operation'],step_key=step['key'],
                primary_resource=step['machine'],start=step['start'],end=step['end'],
                duration=step['duration'],time_unit=source['time_unit']))
            for resource, role in [(step['machine'],'primary'), *[(x,'support') for x in step.get('support_resources',[])]]:
                tables['resource_bookings'].append(dict(experiment_id=experiment_id,plan=label,
                    step_key=step['key'],resource_id=resource,role=role,
                    start=step['start'],end=step['end'],duration=step['duration'],time_unit=source['time_unit']))
    return tables


REPORT_COLUMNS={
    'run_summary':['experiment_id','plan','scenario','industry','time_unit','orders','operations',
                   'weighted_tardiness','total_tardiness','late_orders','makespan'],
    'order_kpis':['experiment_id','plan','order_id','release','due','priority','completion',
                  'tardiness','weighted_tardiness','late','time_unit'],
    'operation_schedule':['experiment_id','plan','order_id','operation_id','step_key',
                          'primary_resource','start','end','duration','time_unit'],
    'resource_bookings':['experiment_id','plan','step_key','resource_id','role',
                         'start','end','duration','time_unit'],
}


def export_reporting(source:dict, result:dict, folder: str | Path, *, experiment_id: str|None=None):
    """Export BI-ready CSVs and a relational SQLite database with stable keys."""
    experiment_id=experiment_id or uuid.uuid4().hex
    if not experiment_id.isalnum() or len(experiment_id)>64:
        raise ValueError('experiment_id must be alphanumeric and at most 64 characters')
    tables=reporting_tables(source,result,experiment_id=experiment_id)
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    files={}
    for name,records in tables.items():
        path=folder/f'{name}.csv'
        path.write_text(make_csv(records,REPORT_COLUMNS[name]),encoding='utf-8')
        files[name]=str(path)
    database=folder/'planning_analytics.sqlite3'
    connection=sqlite3.connect(database)
    try:
        with connection:
            connection.execute('PRAGMA foreign_keys=ON')
            connection.execute('CREATE TABLE IF NOT EXISTS experiments (experiment_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, source_industry TEXT NOT NULL, time_unit TEXT NOT NULL)')
            connection.execute('INSERT INTO experiments VALUES (?, ?, ?, ?)',
                (experiment_id,datetime.now(timezone.utc).isoformat(),source['industry'],source['time_unit']))
            for name,records in tables.items():
                columns=REPORT_COLUMNS[name]
                # Stable table names and columns are code constants, not user supplied SQL.
                definition=', '.join(f'{col} {"INTEGER" if col in {"orders","operations","weighted_tardiness","total_tardiness","late_orders","makespan","release","due","priority","completion","tardiness","late","start","end","duration"} else "TEXT"}' for col in columns)
                connection.execute(f'CREATE TABLE IF NOT EXISTS {name} ({definition}, FOREIGN KEY(experiment_id) REFERENCES experiments(experiment_id))')
                sql=f'INSERT INTO {name} ({", ".join(columns)}) VALUES ({", ".join("?" for _ in columns)})'
                connection.executemany(sql,[[record.get(col) for col in columns] for record in records])
            connection.execute('CREATE INDEX IF NOT EXISTS idx_bookings_resource ON resource_bookings(experiment_id, resource_id, plan)')
            connection.execute('CREATE INDEX IF NOT EXISTS idx_orders_plan ON order_kpis(experiment_id, plan)')
    finally:
        connection.close()
    files['sqlite']=str(database)
    return {'experiment_id':experiment_id,'files':files,
            'rows':{name:len(rows) for name,rows in tables.items()}}
