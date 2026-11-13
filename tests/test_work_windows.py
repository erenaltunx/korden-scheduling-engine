"""Finite work calendar correctness and intentionally infeasible scenarios."""
import pytest
from fastapi.testclient import TestClient

from optera.api import app
from optera.model import validate_scenario, downtime_by_machine
from optera.baseline import POLICIES, dispatch
from optera.optimizer import optimize
from optera.evaluation import check_schedule, evaluate
from shift_lab import run_demo


def scenario():
    return {
        "schema_version": 1,
        "factory_name": "Two separate working periods",
        "machines": [{"id": "CNC", "downtime": [],
                      "working_windows": [{"start": 8, "end": 12},
                                          {"start": 16, "end": 21}]}],
        "jobs": [
            {"id": "A", "release": 0, "due": 13, "weight": 5,
             "operations": [{"id": "mill", "duration": 3, "machines": ["CNC"]}]},
            {"id": "B", "release": 0, "due": 20, "weight": 1,
             "operations": [{"id": "mill", "duration": 3, "machines": ["CNC"]}]}
        ]}


def test_closed_shifts_are_respected_by_all_dispatch_rules_and_milp():
    data = scenario()
    assert downtime_by_machine(data)["CNC"][:2] == [(0, 8), (12, 16)]
    for rule in POLICIES:
        plan = dispatch(data, rule)
        assert not check_schedule(data, plan)
        assert all((8 <= r["start"] and r["end"] <= 12) or
                   (16 <= r["start"] and r["end"] <= 21) for r in plan)
    solution = optimize(data, time_limit=4)
    assert solution["schedule"] is not None
    assert not check_schedule(data, solution["schedule"])
    assert evaluate(data, solution["schedule"])["weighted_tardiness"] <= evaluate(data, dispatch(data))["weighted_tardiness"]


def test_operation_crossing_closed_shift_fails_independent_verifier():
    data = scenario()
    plan = dispatch(data)
    plan[0]["start"], plan[0]["end"] = 10, 13
    assert any("closed shift" in e for e in check_schedule(data, plan))


@pytest.mark.parametrize("periods", [
    [], "8-16", [{"start": 8, "end": 8}],
    [{"start": -1, "end": 16}], [{"start": True, "end": 16}],
    [{"start": 8, "end": 10001}],
    [{"start": 8, "end": 16}, {"start": 15, "end": 24}],
])
def test_invalid_work_calendar_fails_closed(periods):
    data = scenario()
    data["machines"][0]["working_windows"] = periods
    with pytest.raises(ValueError, match="working"):
        validate_scenario(data)


def test_support_operator_must_be_on_shift_too():
    data = scenario()
    data["machines"] = [
        {"id": "CNC", "downtime": []},
        {"id": "OPERATOR", "downtime": [],
         "working_windows": [{"start": 8, "end": 12}, {"start": 16, "end": 21}]}
    ]
    data["jobs"] = data["jobs"][:1]
    data["jobs"][0]["operations"][0]["support_resources"] = ["OPERATOR"]
    for plan in (dispatch(data), optimize(data, time_limit=3)["schedule"]):
        assert plan is not None and not check_schedule(data, plan)
        assert plan[0]["start"] == 8


def test_impossible_calendar_returns_http_422_not_a_fake_shift():
    data = scenario()
    data["jobs"] = data["jobs"][:1]
    data["jobs"][0]["operations"][0]["duration"] = 6
    with pytest.raises(ValueError, match="No feasible working period"):
        dispatch(data)
    response = TestClient(app).post("/api/run", json={"scenario": data, "time_limit": 1})
    assert response.status_code == 422
    assert "working period" in response.json()["detail"]


def test_backward_compatibility_without_working_periods():
    data = scenario()
    del data["machines"][0]["working_windows"]
    assert downtime_by_machine(data)["CNC"] == []
    plan = dispatch(data)
    assert plan[0]["start"] == 0
    assert not check_schedule(data, plan)


def test_shift_lab_demo_is_validated():
    r = run_demo()
    assert r["synthetic"] and r["shift_aware"]
    assert r["baseline_feasible"] and r["optimized_feasible"]
    assert r["optimized_weighted_tardiness"] <= r["baseline_weighted_tardiness"]
