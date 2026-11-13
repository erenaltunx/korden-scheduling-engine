"""Safety-critical rolling replay and disruption regression cases."""
import json
from copy import deepcopy
from pathlib import Path
import pytest
from korden.evaluation import check_schedule
from korden.service import compare
from korden.reschedule import prepare_rolling, reschedule, rolling_dispatch
from korden.whatif import add_outage

ROOT = Path(__file__).resolve().parent.parent


def example():
    return json.loads((ROOT/'samples'/'assembly_cell.json').read_text())


def prior():
    scenario=example()
    return scenario, compare(scenario, 5)['optimized']['schedule']


def test_rolling_preserves_started_work_and_replans_future():
    scenario, previous=prior()
    now=2
    outcome=reschedule(scenario, previous, now, 'DRILL', 12, 17, 5)
    assert outcome['type']=='rolling_reschedule'
    revised=outcome['revised_scenario']
    result=outcome['optimized']['schedule']
    assert check_schedule(revised,result)==[]
    old={r['key']:r for r in previous}
    new={r['key']:r for r in result}
    assert outcome['stability']['frozen_operations'] > 0
    for key,record in old.items():
        if record['start'] < now:
            assert record == new[key]
        else:
            assert new[key]['start'] >= now
    assert outcome['optimized']['metrics']['weighted_tardiness'] <= outcome['baseline']['metrics']['weighted_tardiness']
    assert scenario == example(), 'replay must not mutate original scenario'


def test_explicitly_reject_interruption_of_started_task():
    scenario, schedule=prior()
    active=next(s for s in schedule if s['duration'] >= 3 and s['start'] < s['end']-1)
    now=active['start']+1
    with pytest.raises(ValueError, match='cannot interrupt work in progress'):
        reschedule(scenario,schedule,now,active['machine'],now,active['end'],2)


def test_prior_schedule_is_validated_before_freezing():
    scenario, schedule=prior()
    wrong=deepcopy(schedule)
    wrong.pop()
    with pytest.raises(ValueError, match='Invalid committed schedule'):
        reschedule(scenario,wrong,2,'DRILL',12,17,2)


def test_reject_outage_in_the_past_relative_to_clock():
    scenario, schedule=prior()
    with pytest.raises(ValueError,match='at or after'):
        reschedule(scenario,schedule,10,'DRILL',9,12,2)


def test_all_work_already_completed_can_be_frozen():
    scenario, schedule=prior()
    now=max(s['end'] for s in schedule)+1
    # No effects on previously completed operations.
    answer=reschedule(scenario,schedule,now,'DRILL',now+1,now+3,2)
    assert answer['stability']['remaining_operations']==0
    assert answer['optimized']['schedule']==schedule or sorted(answer['optimized']['schedule'],key=lambda r:(r['start'],r['machine'],r['key']))==sorted(schedule,key=lambda r:(r['start'],r['machine'],r['key']))


def test_rolling_baseline_waits_until_clock_after_frozen_prefix():
    scenario, schedule=prior()
    now=7
    revised=add_outage(scenario, 'DRILL', 20, 23)
    frozen=prepare_rolling(scenario,schedule,now,revised)
    baseline=rolling_dispatch(revised,frozen,now)
    assert check_schedule(revised,baseline)==[]
    for task in baseline:
        if task['key'] not in frozen:
            assert task['start']>=now


def test_rolling_is_deterministic_for_fixed_heuristic():
    scenario, schedule=prior()
    revised=add_outage(scenario,'DRILL',12,17)
    frozen=prepare_rolling(scenario,schedule,2,revised)
    assert rolling_dispatch(revised,frozen,2)==rolling_dispatch(revised,frozen,2)
