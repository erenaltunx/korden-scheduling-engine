"""Dynamic, skill-based staffing: actual MILP decision, independent checks, replay."""
from copy import deepcopy
import pytest
from optera.universal import normalize_universal
from optera.model import validate_scenario
from optera.baseline import dispatch
from optera.optimizer import optimize
from optera.evaluation import check_schedule, evaluate
from optera.reschedule import prepare_rolling, rolling_dispatch


def staffing_case():
    # Two simultaneous repair calls; technicians are interchangeable but not double bookable.
    return dict(schema_version=1, name='Mobile service crew', industry='Service', time_unit='minute',
       resources=[dict(id='VAN_A', name='Van A', kind='vehicle', capabilities=['van']),
                  dict(id='VAN_B', name='Van B', kind='vehicle', capabilities=['van']),
                  dict(id='TECH_A', name='Technician A', kind='person', capabilities=['certified']),
                  dict(id='TECH_B', name='Technician B', kind='person', capabilities=['certified'],
                       unavailable=[dict(start=0,end=6)])],
       work_orders=[dict(id='A', name='Urgent call A', available_at=0, due_at=4, priority=5,
          steps=[dict(id='drive', name='repair', duration=4, requires_all=['van'],
                      choose_one_support_with=['certified'])]),
          dict(id='B', name='Urgent call B', available_at=0, due_at=4, priority=4,
          steps=[dict(id='drive', name='repair', duration=4, requires_all=['van'],
                      choose_one_support_with=['certified'])])])


def test_skill_pool_is_translated_to_valid_resources():
    compiled=normalize_universal(staffing_case())
    assert compiled['jobs'][0]['operations'][0]['support_options']==['TECH_A','TECH_B']
    assert compiled['jobs'][0]['operations'][0]['machines']==['VAN_A','VAN_B']


def test_optimized_staffing_is_feasible_and_proven_optimal():
    data=normalize_universal(staffing_case())
    result=optimize(data, 8)
    assert result['solver']['optimality_proven'], result['solver']
    assert check_schedule(data,result['schedule'])==[]
    assert all(len(s['support_resources'])==1 for s in result['schedule'])
    assert evaluate(data,result['schedule'])['makespan']>=8
    assert all(s['support_resources'][0] == 'TECH_A' for s in result['schedule'] if s['start']<6)


def test_baseline_dynamic_staffing_is_valid():
    data=normalize_universal(staffing_case())
    assert check_schedule(data,dispatch(data))==[]


def test_validator_blocks_staff_double_booking():
    data=normalize_universal(staffing_case())
    schedule=dispatch(data)
    altered=deepcopy(schedule)
    altered[1]['start']=altered[0]['start'];altered[1]['end']=altered[0]['end']
    altered[1]['support_resources']=altered[0]['support_resources']
    assert any('overlap' in e.lower() for e in check_schedule(data,altered))


def test_staffing_rejects_fake_skill_and_unsupported_keys():
    bad=staffing_case()
    bad['work_orders'][0]['steps'][0]['choose_one_support_with']=['not-trained']
    with pytest.raises(ValueError,match='no eligible supporting resource'):
        normalize_universal(bad)
    bad=staffing_case();bad['work_orders'][0]['steps'][0]['simultaneous_humans']=2
    with pytest.raises(ValueError,match='unsupported'):
        normalize_universal(bad)


def test_replay_preserves_committed_staff():
    data=normalize_universal(staffing_case())
    prior=dispatch(data)
    fixed=prepare_rolling(data,prior,now=1,revised=data)
    new=rolling_dispatch(data,fixed,now=1)
    assert check_schedule(data,new)==[]
    assert next(x for x in new if x['key']=='A::0')==next(x for x in prior if x['key']=='A::0')


def test_fixed_staffing_is_preserved_in_milp():
    data=normalize_universal(staffing_case()); prior=dispatch(data)
    fixed=prepare_rolling(data,prior,now=1,revised=data)
    optimized=optimize(data,6,fixed_operations=fixed,not_before=1)['schedule']
    assert check_schedule(data,optimized)==[]
    for key,task in fixed.items():
        assert next(s for s in optimized if s['key']==key)==task


def test_raw_validator_rejects_primary_or_fixed_as_optional_staff():
    data=normalize_universal(staffing_case())
    data['jobs'][0]['operations'][0]['support_options']=['VAN_A']
    with pytest.raises(ValueError,match='primary'):
        validate_scenario(data)
