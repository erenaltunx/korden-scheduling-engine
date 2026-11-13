"""Explicit optimizer registry; new engines must implement the documented contract.

Do not load engines from user-provided paths or arbitrary imports.
"""
from __future__ import annotations
from collections.abc import Callable
from .optimizer import optimize

# A solver must return {"schedule": list[dict] | None, "solver": metadata}.
# All returned schedules pass through the independent checker in service.compare.
ENGINES: dict[str, Callable[[dict, float], dict]] = {"milp_highs": optimize}


def optimize_with(engine: str, scenario: dict, time_limit: float) -> dict:
    if engine not in ENGINES:
        raise ValueError(f"Unsupported optimizer engine: {engine}")
    return ENGINES[engine](scenario, time_limit)
