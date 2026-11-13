"""Concurrent exclusive-resource invariants in model, baseline, MILP and replay."""
from copy import deepcopy
import pytest

from optera.baseline import dispatch
from optera.evaluation import check_schedule, evaluate
from optera.model import validate_scenario
from optera.optimizer import optimize
from optera.universal import normalize_universal
from optera.reschedule import prepare_rolling, rolling_dispatch


def double_resource_scenario():
    return {'schema_version': 1, 'factory_name': 'CNC machine AND operator',
            'machines': [{'id':'CNC_A','downtime':[]},
                         {'id':'CNC_B','downtime':[]},
                         {'id':'OPERATOR','downtime':[]}],
            'jobs': [{'id':name, 'release':0, 'due':3, 'weight':1,
                      'operations':[{'id':'cut','duration':3,
                                     'machines':[machine],
                                     'support_resources':['OPERATOR']}]} for name,machine in [('A','CNC_A'),('B','CNC_B')] ]}


def test_concurrent_support_prevents_two_independent_machines_from_double_booking_one_operator():
    data=double_resource_scenario()
    for schedule in (dispatch(data), optimize(data,5)['schedule']):
        assert check_schedule(data, schedule) == []
        assert evaluate(data,schedule)['makespan'] >= 6
        assert all(row['support_resources']==['OPERATOR'] for row in schedule)
        intervals=sorted((row['start'],row['end']) for row in schedule)
        assert intervals[0][1] <= intervals[1][0]


def test_independent_checker_rejects_support_collision():
    data=double_resource_scenario()
    schedule=dispatch(data)
    bad=deepcopy(schedule)
    bad[1]['start']=bad[0]['start']
    bad[1]['end']=bad[0]['end']
    assert any('OPERATOR' in error and 'overlap' in error.lower() for error in check_schedule(data,bad))


def test_independent_checker_rejects_missing_support_booking():
    data=double_resource_scenario()
    schedule=dispatch(data)
    del schedule[0]['support_resources']
    assert any('support resource' in error for error in check_schedule(data, schedule))


def test_support_downtime_is_mandatory_even_if_primary_machine_free():
    data=double_resource_scenario()
    data['machines'][2]['downtime']=[{'start':0,'end':5}]
    for schedule in (dispatch(data), optimize(data,5)['schedule']):
        assert check_schedule(data,schedule)==[]
        assert all(s['start'] >= 5 for s in schedule)


def test_wrong_support_reservations_rejected_before_solving():
    data=double_resource_scenario()
    data['jobs'][0]['operations'][0]['support_resources']=['OPERATOR', 'CNC_A']
    with pytest.raises(ValueError, match='cannot also be candidate'):
        validate_scenario(data)


def test_universal_adapter_stores_simultaneous_resource_requirement():
    source={'schema_version':1,'name':'Cross-domain resource example','industry':'Field service','time_unit':'minute',
            'resources':[{'id':'TECH','name':'Qualified technician','kind':'technician','capabilities':['repair']},
                         {'id':'VAN','name':'Shared van','kind':'vehicle','capabilities':['vehicle']}],
            'work_orders':[{'id':'CASE','name':'Urgent callout','available_at':0,'due_at':8,'priority':4,
                            'steps':[{'id':'service','name':'Repair equipment','duration':5,
                                      'requires_all':['repair'],'reserve_resources':['VAN']}]}]}
    compiled=normalize_universal(source)
    assert compiled['jobs'][0]['operations'][0]['machines']==['TECH']
    assert compiled['jobs'][0]['operations'][0]['support_resources']==['VAN']
    assert check_schedule(compiled, optimize(compiled,3)['schedule'])==[]


def test_universal_rejects_support_that_can_be_primary():
    source={'schema_version':1,'name':'Invalid service','industry':'Service','time_unit':'hour',
            'resources':[{'id':'ONE','name':'Only resource','kind':'machine','capabilities':['step']}],
            'work_orders':[{'id':'job','name':'Order','available_at':0,'due_at':10,'priority':1,
                            'steps':[{'id':'step','name':'Step','duration':2,
                                      'requires_all':['step'],'reserve_resources':['ONE']}]}]}
    with pytest.raises(ValueError, match='cannot also be primary'):
        normalize_universal(source)


def test_rolling_replay_freezes_support_reservations_and_refuses_outage_on_started_work():
    scenario=double_resource_scenario()
    old=dispatch(scenario)
    revised=deepcopy(scenario)
    revised['machines'][2]['downtime']=[{'start':1,'end':2}]
    with pytest.raises(ValueError,match='OPERATOR'):
        prepare_rolling(scenario,old,now=2,revised=revised)
    frozen=prepare_rolling(scenario,old,now=1,revised=scenario)
    updated=rolling_dispatch(scenario,frozen,now=1)
    assert check_schedule(scenario,updated)==[]
    assert updated[0] == old[0]


def test_industry_archival_reproduction_does_not_drift():
    from pathlib import Path
    from universal_benchmark import benchmark_sector
    archive=Path(__file__).resolve().parents[1]/'samples'/'archives'/'v06'
    assert benchmark_sector('manufacturing',5,archive)['best_baseline']['weighted_tardiness']==41
    assert benchmark_sector('field_service',5,archive)['best_baseline']['weighted_tardiness']==10
    assert benchmark_sector('warehouse',5,archive)['best_baseline']['weighted_tardiness']==200
