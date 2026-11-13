"""KORDEN HTTP adapter: core solver is imported, but never coupled to HTTP or DB."""
from __future__ import annotations
import json
import os
from pathlib import Path
from threading import BoundedSemaphore
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from .service import compare
from .storage import get_experiment, list_experiments, save_experiment

ROOT = Path(__file__).resolve().parent.parent
PUBLIC_DEMO = os.getenv("KORDEN_PUBLIC_DEMO", "0").lower() in {"1", "true", "yes"}
# Public demo is not multi-tenant: it must NEVER expose or persist private experiments.
MAX_REQUEST_BYTES = 128 * 1024
PUBLIC_SOLVER_SLOTS = BoundedSemaphore(value=2)
app = FastAPI(title="KORDEN — Industrial Scheduling & Optimization", version="0.3.0")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


class RunRequest(BaseModel):
    scenario: dict
    time_limit: float = Field(default=8.0, ge=0.5, le=60)
    engine: str = Field(default="milp_highs", max_length=40)


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
    return {"status": "ok", "application": "KORDEN", "version": "0.3.0"}


@app.get("/api/config")
def config():
    return {"public_demo": PUBLIC_DEMO, "max_solver_seconds": 5 if PUBLIC_DEMO else 60,
            "max_orders": 8 if PUBLIC_DEMO else 30, "schema_version": 1,
            "archive_enabled": not PUBLIC_DEMO}


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
    if PUBLIC_DEMO:
        jobs = payload.scenario.get("jobs", [])
        if payload.time_limit > 5:
            raise HTTPException(status_code=422, detail="Public demo solver limit is 5 seconds")
        if not isinstance(jobs, list) or len(jobs) > 8:
            raise HTTPException(status_code=422, detail="Public demo supports at most 8 orders")
        if sum(len(j.get("operations", [])) for j in jobs if isinstance(j, dict)) > 24:
            raise HTTPException(status_code=422, detail="Public demo supports at most 24 operations")
        if not PUBLIC_SOLVER_SLOTS.acquire(blocking=False):
            raise HTTPException(status_code=429, detail="Solver busy. Please try again shortly.")
    try:
        try:
            result = compare(payload.scenario, payload.time_limit, engine=payload.engine)
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
