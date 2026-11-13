"""Non-destructive counterfactual downtime injection.

This models a revised planning problem from time zero, NOT an in-progress
shop-floor execution reschedule. It does not freeze work already started.
"""
from __future__ import annotations
from copy import deepcopy
from .model import validate_scenario


def add_outage(data: dict, machine_id: str, start: int, end: int) -> dict:
    validate_scenario(data)
    if not isinstance(machine_id, str) or machine_id not in {m["id"] for m in data["machines"]}:
        raise ValueError("Unknown machine identifier")
    if type(start) is not int or type(end) is not int or not (0 <= start < end <= 10000):
        raise ValueError("Outage start/end must be integer hours with 0 <= start < end <= 10000")
    scenario = deepcopy(data)
    machine = next(m for m in scenario["machines"] if m["id"] == machine_id)
    intervals = sorted([(w["start"], w["end"]) for w in machine.get("downtime", [])] + [(start,end)])
    merged: list[list[int]] = []
    for a,b in intervals:
        if not merged or a > merged[-1][1]:
            merged.append([a,b])
        else:
            merged[-1][1] = max(merged[-1][1],b)
    machine["downtime"] = [{"start": a, "end": b} for a,b in merged]
    scenario["factory_name"] = data.get("factory_name", "Factory") + f" | outage on {machine_id} {start}–{end}h"
    validate_scenario(scenario)
    return scenario
