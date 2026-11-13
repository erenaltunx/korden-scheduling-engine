"""OPTERA HTTP adapter: core solver is imported, but never coupled to HTTP or DB."""
from __future__ import annotations
import json
import os
import io
import zipfile
from pathlib import Path
from threading import BoundedSemaphore
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Literal
from .baseline import POLICIES
from .service import compare
from .reschedule import reschedule
from .public_benchmarks import PUBLIC_INSTANCES, load_jsplib
from .universal import normalize_universal, describe_universal
from .data_pipeline import import_planning_csv, reporting_tables, make_csv, REPORT_COLUMNS
from .storage import get_experiment, list_experiments, save_experiment

ROOT = Path(__file__).resolve().parent.parent
PUBLIC_DEMO = os.getenv("OPTERA_PUBLIC_DEMO", "0").lower() in {"1", "true", "yes"}
# Public demo is not multi-tenant: it must NEVER expose or persist private experiments.
MAX_REQUEST_BYTES = 128 * 1024
PUBLIC_SOLVER_SLOTS = BoundedSemaphore(value=2)
app = FastAPI(title="OPTERA — Cross-Industry Resource Optimization", version="0.12.0")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


class RunRequest(BaseModel):
    scenario: dict
    time_limit: float = Field(default=8.0, ge=0.5, le=60)
    engine: str = Field(default="milp_highs", max_length=40)
    baseline_policy: Literal["edd", "fifo", "spt", "wspt"] = "edd"
    objective: Literal["weighted_tardiness", "makespan"] = "weighted_tardiness"


class UniversalValidateRequest(BaseModel):
    scenario: dict


class CSVImportRequest(BaseModel):
    tables: dict[str,str]
    name: str = Field(min_length=1, max_length=100)
    industry: str = Field(min_length=1, max_length=100)
    time_unit: Literal['minute','hour'] = 'hour'


class BIExportRequest(BaseModel):
    scenario: dict
    result: dict


class RescheduleRequest(BaseModel):
    scenario: dict
    prior_schedule: list[dict]
    now: int = Field(ge=0, le=10000)
    machine_id: str = Field(min_length=1, max_length=100)
    outage_start: int = Field(ge=0, le=10000)
    outage_end: int = Field(ge=1, le=10000)
    time_limit: float = Field(default=8.0, ge=0.5, le=60)
    baseline_policy: Literal["edd", "fifo", "spt", "wspt"] = "edd"
    objective: Literal["weighted_tardiness", "makespan"] = "weighted_tardiness"
    stability_policy: Literal["off", "preserve"] = "off"
    max_added_tardiness: int = Field(default=0, ge=0, le=100)


def public_solver_check(scenario: dict, time_limit: float):
    if not PUBLIC_DEMO:
        return
    jobs = scenario.get('jobs', [])
    if time_limit > 5:
        raise HTTPException(status_code=422, detail='Public demo solver limit is 5 seconds')
    if not isinstance(jobs, list) or len(jobs) > 8:
        raise HTTPException(status_code=422, detail='Public demo supports at most 8 orders')
    if sum(len(j.get('operations', [])) for j in jobs if isinstance(j, dict)) > 24:
        raise HTTPException(status_code=422, detail='Public demo supports at most 24 operations')


def acquire_public_slot():
    if PUBLIC_DEMO and not PUBLIC_SOLVER_SLOTS.acquire(blocking=False):
        raise HTTPException(status_code=429, detail='Solver busy. Please try again shortly.')


@app.middleware("http")
async def protective_headers_and_size_limit(request: Request, call_next):
    if request.url.path.startswith("/api/") and request.method in {"POST", "PUT", "PATCH"}:
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > MAX_REQUEST_BYTES:
                    return JSONResponse({"detail": "Request exceeds 128 KiB limit"}, status_code=413)
            except ValueError:
                return JSONResponse({"detail": "Invalid content-length"}, status_code=400)
        # Cap the actual request body too; content-length alone is not sufficient.
        # Public deployment must ALSO configure a size limit at the ingress/proxy.
        raw = await request.body()
        if len(raw) > MAX_REQUEST_BYTES:
            return JSONResponse({"detail": "Request exceeds 128 KiB limit"}, status_code=413)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
    return response


@app.get("/")
def home():
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/api/health")
def health():
    return {"status": "ok", "application": "OPTERA", "version": "0.12.0"}


@app.get("/api/config")
def config():
    return {"public_demo": PUBLIC_DEMO, "max_solver_seconds": 5 if PUBLIC_DEMO else 60,
            "max_orders": 8 if PUBLIC_DEMO else 30, "schema_version": 1,
            "archive_enabled": not PUBLIC_DEMO, "baseline_policies": POLICIES,
            "objectives": ['weighted_tardiness', 'makespan'],
            "universal_schema_version": 1}


@app.get("/api/scenarios")
def scenarios():
    return [{"id": f.stem, "name": json.loads(f.read_text(encoding="utf-8"))["factory_name"]}
            for f in sorted((ROOT / "samples").glob("*.json"))]


@app.get("/api/scenarios/{scenario_id}")
def load_scenario(scenario_id: str):
    if not scenario_id.replace("_", "").isalnum():
        raise HTTPException(status_code=404, detail="Unknown scenario")
    path = ROOT / "samples" / f"{scenario_id}.json"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Unknown scenario")
    return json.loads(path.read_text(encoding="utf-8"))


@app.post("/api/run")
def run_schedule(payload: RunRequest):
    public_solver_check(payload.scenario, payload.time_limit)
    acquire_public_slot()
    try:
        try:
            result = compare(payload.scenario, payload.time_limit, engine=payload.engine,
                             baseline_policy=payload.baseline_policy, objective=payload.objective)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        if PUBLIC_DEMO:
            return {**result, "persisted": False}
        # The local archive is durable and versioned; DB exceptions must not be swallowed.
        run_id = save_experiment(payload.scenario, result)
        return {**result, "run_id": run_id, "persisted": True}
    finally:
        if PUBLIC_DEMO:
            PUBLIC_SOLVER_SLOTS.release()


@app.get("/api/history")
def history(limit: int = Query(default=20, ge=1, le=100)):
    if PUBLIC_DEMO:
        raise HTTPException(status_code=404, detail="Not available on public demo")
    return list_experiments(limit)


@app.get("/api/history/{run_id}")
def history_item(run_id: str):
    if PUBLIC_DEMO:
        raise HTTPException(status_code=404, detail="Not available on public demo")
    record = get_experiment(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Unknown experiment")
    return record


@app.post('/api/reschedule')
def run_rolling_reschedule(payload: RescheduleRequest):
    """Non-preemptive real-time replay; refuses to rewrite execution history."""
    public_solver_check(payload.scenario, payload.time_limit)
    acquire_public_slot()
    try:
        try:
            output = reschedule(payload.scenario, payload.prior_schedule, payload.now,
                                payload.machine_id, payload.outage_start, payload.outage_end,
                                payload.time_limit, payload.baseline_policy, payload.objective,
                                payload.stability_policy, payload.max_added_tardiness)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        if PUBLIC_DEMO:
            return {**output, 'persisted': False}
        run_id = save_experiment(output['revised_scenario'], output)
        return {**output, 'persisted': True, 'run_id': run_id}
    finally:
        if PUBLIC_DEMO:
            PUBLIC_SOLVER_SLOTS.release()


@app.get('/api/public-benchmarks')
def public_benchmarks():
    return [{'id': x, 'name': f'JSPLIB {x.upper()} — published optimum {opt}h',
             'known_optimum_makespan': opt} for x,opt in PUBLIC_INSTANCES.items()]


@app.get('/api/public-benchmarks/{name}')
def get_public_benchmark(name: str):
    if name not in PUBLIC_INSTANCES:
        raise HTTPException(status_code=404, detail='Unknown benchmark')
    return load_jsplib(name)


UNIVERSAL_TEMPLATE_DIR = ROOT / 'samples' / 'universal'


@app.get('/api/universal/templates')
def universal_templates():
    result = []
    for path in sorted(UNIVERSAL_TEMPLATE_DIR.glob('*.json')):
        source = json.loads(path.read_text(encoding='utf-8'))
        result.append({'id': path.stem, **describe_universal(source)})
    return result


@app.get('/api/universal/templates/{template_id}')
def universal_template(template_id: str):
    if not template_id.isascii() or not template_id.replace('_', '').isalnum():
        raise HTTPException(status_code=404, detail='Unknown sector template')
    path = UNIVERSAL_TEMPLATE_DIR / (template_id + '.json')
    if not path.is_file():
        raise HTTPException(status_code=404, detail='Unknown sector template')
    return json.loads(path.read_text(encoding='utf-8'))


@app.post('/api/universal/validate')
def universal_validate(payload: UniversalValidateRequest):
    try:
        normalized = normalize_universal(payload.scenario)
        return {'valid': True, 'profile': describe_universal(payload.scenario),
                'normalized_scenario': normalized}
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post('/api/universal/run')
def universal_run(payload: RunRequest):
    try:
        normalized = normalize_universal(payload.scenario)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    public_solver_check(normalized, payload.time_limit)
    acquire_public_slot()
    try:
        result = compare(normalized, payload.time_limit, engine=payload.engine,
                         baseline_policy=payload.baseline_policy, objective=payload.objective)
        result['domain'] = describe_universal(payload.scenario)
        result['normalized_scenario'] = normalized
        result['note'] = ('Scenario-based cross-industry resource planning. '
                          'One primary and optional optimizer-selected support resource; no travel, variable-size teams or verified real-world savings.')
        if PUBLIC_DEMO:
            return {**result, 'persisted': False}
        run_id = save_experiment(payload.scenario, result)
        return {**result, 'run_id': run_id, 'persisted': True}
    finally:
        if PUBLIC_DEMO:
            PUBLIC_SOLVER_SLOTS.release()


@app.post('/api/enterprise/import-csv')
def enterprise_import_csv(payload: CSVImportRequest):
    """Safe, fail-closed CSV ingestion; does not persist user inputs."""
    try:
        source=import_planning_csv(payload.tables,name=payload.name,
                                   industry=payload.industry,time_unit=payload.time_unit)
        return {'scenario':source,'profile':describe_universal(source),
                'normalized_scenario':normalize_universal(source)}
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post('/api/enterprise/export-bi')
def enterprise_export_bi(payload: BIExportRequest):
    """Validate all schedules independently before producing safe Power BI-ready CSVs."""
    try:
        tables=reporting_tables(payload.scenario,payload.result,experiment_id='browser-export')
        archive=io.BytesIO()
        with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
            for name,rows in tables.items():
                z.writestr(f'{name}.csv',make_csv(rows,REPORT_COLUMNS[name]))
        archive.seek(0)
        return StreamingResponse(archive,media_type='application/zip',headers={
            'Content-Disposition':'attachment; filename="optera-bi-export.zip"',
            'Cache-Control':'no-store'})
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
