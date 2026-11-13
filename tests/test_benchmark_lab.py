"""Independent policy, held-out benchmarking and what-if regressions."""
import copy
import json
from pathlib import Path
import pytest
from benchmark_lab import run_lab
from korden.baseline import POLICIES, dispatch, dispatch_edd
from korden.evaluation import check_schedule, evaluate
from korden.generator import generate_factory
from korden.service import compare
from korden.whatif import add_outage

ROOT = Path(__file__).resolve().parent.parent


def example():
    return json.loads((ROOT / "samples" / "assembly_cell.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("policy", list(POLICIES))
def test_all_policies_produce_valid_schedule(policy):
    data=generate_factory(108,6)
    schedule=dispatch(data,policy)
    assert check_schedule(data,schedule)==[]
    assert len(schedule)==18
    assert evaluate(data,schedule)["makespan"] > 0


def test_edd_is_backward_compatible():
    data=example()
    assert dispatch_edd(data)==dispatch(data,"edd")
    assert evaluate(data,dispatch(data,"edd"))["weighted_tardiness"]==39


def test_policy_is_validated():
    with pytest.raises(ValueError,match="Unknown baseline policy"):
        dispatch(example(),"magic")


@pytest.mark.parametrize("policy",["fifo","spt","wspt"])
def test_service_selects_policy_and_never_worsens(policy):
    result=compare(example(),time_limit=5,baseline_policy=policy)
    assert result["baseline_policy"]==policy
    assert result["baseline"]["name"]==POLICIES[policy]
    assert (result["optimized"]["metrics"]["weighted_tardiness"],result["optimized"]["metrics"]["makespan"]) <= (result["baseline"]["metrics"]["weighted_tardiness"],result["baseline"]["metrics"]["makespan"])


def test_whatif_is_non_mutating_and_merges_outages():
    original=example();copy_original=copy.deepcopy(original)
    machine=original["machines"][0]["id"]
    changed=add_outage(original,machine,5,10)
    assert changed!=original
    assert original==copy_original
    changed_again=add_outage(changed,machine,8,13)
    outages=next(m for m in changed_again["machines"] if m["id"]==machine)["downtime"]
    assert any(w["start"]<=5 and w["end"]>=13 for w in outages)
    assert check_schedule(changed_again,dispatch(changed_again,"edd"))==[]


@pytest.mark.parametrize("start,end",[(9,9),(-1,4),(5,10001),(2.5,8)])
def test_whatif_rejects_bad_times(start,end):
    with pytest.raises(ValueError,match="Outage start/end"):
        add_outage(example(),example()["machines"][0]["id"],start,end)


def test_whatif_rejects_unknown_machine():
    with pytest.raises(ValueError,match="Unknown machine"):
        add_outage(example(),"UNKNOWN",4,9)


def test_research_lab_reproducible_and_nonnegative_gains():
    x=run_lab(count=3,jobs=5,time_limit=3,start_seed=110)
    y=run_lab(count=3,jobs=5,time_limit=3,start_seed=110)
    assert x["summary"]["instances"]==3
    assert x["summary"]["total_operations"]==45
    assert x["summary"]["pooled_improvement_percent"]==y["summary"]["pooled_improvement_percent"]
    assert x["summary"]["wins"]+x["summary"]["ties"]==3
    assert all(row["delivered_weighted_tardiness"]<=row["best_policy_weighted_tardiness"] for row in x["rows"])
    assert set(x["methodology"]["policies"])==set(POLICIES)


def test_api_accepts_baseline_policy_and_rejects_invalid():
    from fastapi.testclient import TestClient
    from korden.api import app
    client=TestClient(app)
    payload={"scenario":example(),"time_limit":3,"baseline_policy":"spt"}
    resp=client.post("/api/run",json=payload)
    assert resp.status_code==200, resp.text
    assert resp.json()["baseline_policy"]=="spt"
    payload["baseline_policy"]="nonsense"
    assert client.post("/api/run",json=payload).status_code==422
