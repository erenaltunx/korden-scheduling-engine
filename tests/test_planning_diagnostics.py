"""Conservative scheduling diagnostics never invent a proof of infeasibility."""
from copy import deepcopy

from fastapi.testclient import TestClient

from optera.api import app
from optera.diagnostics import (
    _max_continuous_available,
    explain_scheduling_error,
)
from optera.baseline import dispatch

CLIENT = TestClient(app)


def scenario():
    return {
        "schema_version": 1,
        "factory_name": "Diagnostic trial",
        "machines": [
            {
                "id": "CNC-1", "downtime": [],
                "working_windows": [{"start": 8, "end": 12},
                                    {"start": 16, "end": 21}],
            }
        ],
        "jobs": [
            {
                "id": "ORDER-17", "release": 0, "due": 12, "weight": 3,
                "operations": [
                    {"id": "MILLING", "duration": 6, "machines": ["CNC-1"]}
                ],
            }
        ],
    }


def call(data, path="/api/run"):
    return CLIENT.post(path, json={"scenario": data, "time_limit": 1})


def test_structural_shift_shortage_is_human_readable_and_backward_compatible():
    response = call(scenario())
    assert response.status_code == 422
    result = response.json()
    assert isinstance(result["detail"], str)
    assert "No feasible working period" in result["detail"]
    hint = result["diagnostic"]
    assert hint["code"] == "WORK_PERIOD_TOO_SHORT"
    assert hint["title"] and hint["next_step"]
    assert hint["duration"] == 6
    assert hint["longest_open_period"] == 5
    assert hint["job_id"] == "ORDER-17"
    assert hint["operation_id"] == "MILLING"
    assert hint["machine_ids"] == ["CNC-1"]
    assert "6 uninterrupted" in hint["explanation"]
    assert "5 time units" in hint["explanation"]


def test_fixed_support_resource_can_be_the_real_work_window_bottleneck():
    data = scenario()
    data["machines"][0]["working_windows"] = [{"start": 8, "end": 30}]
    data["machines"].append({
        "id": "OPERATOR", "downtime": [],
        "working_windows": [{"start": 8, "end": 12}],
    })
    data["jobs"][0]["operations"][0]["support_resources"] = ["OPERATOR"]
    response = call(data)
    assert response.status_code == 422
    diagnostic = response.json()["diagnostic"]
    assert diagnostic["code"] == "WORK_PERIOD_TOO_SHORT"
    assert diagnostic["longest_open_period"] == 4
    assert "OPERATOR" in diagnostic["explanation"]


def test_alternative_machine_with_enough_time_is_not_misdiagnosed():
    data = scenario()
    data["machines"].append({
        "id": "CNC-2", "downtime": [],
        "working_windows": [{"start": 8, "end": 30}],
    })
    data["jobs"][0]["operations"][0]["machines"].append("CNC-2")
    response = call(data)
    assert response.status_code == 200
    assert response.json()["optimized"]["schedule"][0]["machine"] == "CNC-2"


def test_dispatch_failure_does_not_claim_mathematical_infeasibility():
    data = scenario()
    data["jobs"] = []
    for i in range(3):
        data["jobs"].append({
            "id": f"ORDER-{i}", "release": 0, "due": 20 + i,
            "weight": 1,
            "operations": [{"id": "MILLING", "duration": 3, "machines": ["CNC-1"]}],
        })
    response = call(data)
    assert response.status_code == 422
    diag = response.json()["diagnostic"]
    assert diag["code"] == "DISPATCH_CALENDAR_CONFLICT"
    assert "could" in diag["explanation"]
    assert "does not prove every possible schedule is infeasible" in diag["next_step"]
    assert "infeasible" not in diag["title"].lower()


def test_overlapping_shift_intervals_have_an_actionable_diagnostic():
    data = scenario()
    data["machines"][0]["working_windows"] = [
        {"start": 8, "end": 15}, {"start": 12, "end": 18}
    ]
    result = call(data)
    assert result.status_code == 422
    diag = result.json()["diagnostic"]
    assert diag["code"] == "INVALID_WORK_CALENDAR"
    assert "overlap" in diag["next_step"]


def test_unknown_machine_id_is_explained_without_guessing():
    data = scenario()
    data["jobs"][0]["operations"][0]["machines"] = ["CNC-TYPO"]
    result = call(data)
    assert result.status_code == 422
    diag = result.json()["diagnostic"]
    assert diag["code"] == "UNKNOWN_MACHINE"
    assert "machine" in diag["title"].lower()


def test_bad_duration_is_explained_without_giving_fake_capacity_metrics():
    data = scenario()
    data["jobs"][0]["operations"][0]["duration"] = 0
    result = call(data)
    assert result.status_code == 422
    diag = result.json()["diagnostic"]
    assert diag["code"] == "INVALID_DURATION"
    assert "longest_open_period" not in diag


def test_bad_universal_payload_returns_structured_error():
    result = call({}, "/api/universal/run")
    assert result.status_code == 422
    diag = result.json()["diagnostic"]
    assert diag["code"] == "INVALID_PLAN_INPUT"
    assert isinstance(result.json()["detail"], str)


def test_valid_scenario_still_has_no_diagnostic_and_a_feasible_schedule():
    data = scenario()
    data["jobs"][0]["operations"][0]["duration"] = 2
    result = call(data)
    assert result.status_code == 200
    assert "diagnostic" not in result.json()
    assert result.json()["optimized"]["schedule"]


def test_available_period_calculator_handles_overlap_and_clipping():
    # Blackouts are allowed to overlap internally (maintenance + closed shifts).
    assert _max_continuous_available(
        [(0, 8), (10, 13), (12, 15), (18, 30)], 0, 30
    ) == 3
    assert _max_continuous_available(
        [(0, 100)], 40, 80
    ) == 0
    assert _max_continuous_available([], 10, 20) == 10


def test_unknown_error_uses_safe_generic_guidance():
    result = explain_scheduling_error(ValueError("Unsupported profile"), {})
    assert result["code"] == "INVALID_PLAN_INPUT"
    assert "review" in result["next_step"].lower()


def test_order_id_is_not_interpreted_as_program_markup():
    data = scenario()
    data["jobs"][0]["id"] = "ORDER<script>alert(1)</script>"
    with_error = None
    try:
        dispatch(data)
    except ValueError as error:
        with_error = error
    assert with_error is not None
    diag = explain_scheduling_error(with_error, data)
    assert diag["job_id"] == data["jobs"][0]["id"]
    assert diag["code"] == "WORK_PERIOD_TOO_SHORT"
