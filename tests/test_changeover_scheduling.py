"""Regression and mathematical audit of uniform product-family changeovers."""
import copy
import itertools
import json
from pathlib import Path

import pytest

from optera.baseline import dispatch, earliest_slot_with_changeover
from optera.evaluation import check_schedule, evaluate
from optera.model import horizon, validate_scenario
from optera.optimizer import optimize
from optera.reschedule import prepare_rolling, rolling_dispatch
from optera.service import compare
from optera.universal import normalize_universal

ROOT = Path(__file__).resolve().parent.parent


def scenario():
    return json.loads((ROOT / 'samples/setup_cell.json').read_text())


def test_invalid_changeover_parameters_rejected():
    for invalid in [-1, 121, 2.5, True, '4']:
        s = scenario()
        s['machines'][0]['changeover_time'] = invalid
        with pytest.raises(ValueError, match='changeover_time'):
            validate_scenario(s)


def test_missing_family_on_changeover_machine_rejected():
    s = scenario()
    s['jobs'][0]['operations'][0].pop('setup_family')
    with pytest.raises(ValueError, match='setup_family'):
        validate_scenario(s)


def test_invalid_family_rejected():
    for invalid in ['', 'x'*41, 12]:
        s = scenario()
        s['jobs'][0]['operations'][0]['setup_family'] = invalid
        with pytest.raises(ValueError, match='setup_family'):
            validate_scenario(s)


def test_setup_gap_inflation_and_horizon():
    s = scenario()
    assert horizon(s) >= 4*2 + 3*4
    assert earliest_slot_with_changeover(2, 2, [(0, 2)], [(0, 2, 'A')], 'B', 4) == 6
    assert earliest_slot_with_changeover(2, 2, [(0, 2)], [(0, 2, 'A')], 'A', 4) == 2


def test_independent_checker_rejects_missing_gap():
    s = scenario()
    rows = [
        {'key':j['id']+'::0','job':j['id'],'operation':'mill',
         'machine':'CNC_1','start':k*2,'end':(k+1)*2,'duration':2}
        for k,j in enumerate(s['jobs'])
    ]
    assert not any('overlap' in e for e in check_schedule(s, rows))
    assert any('Changeover violation' in e for e in check_schedule(s, rows))
    with pytest.raises(ValueError, match='Changeover'):
        evaluate(s, rows)


def test_solver_reduces_real_modelled_changeover_overhead():
    s = scenario()
    outcome = compare(s, 8)
    assert outcome['solver']['optimality_proven']
    assert not check_schedule(s, outcome['optimized']['schedule'])
    assert outcome['baseline']['metrics']['weighted_tardiness'] == 27
    assert outcome['optimized']['metrics']['weighted_tardiness'] == 12
    assert outcome['baseline']['metrics']['setup_time_units'] == 12
    assert outcome['optimized']['metrics']['setup_time_units'] == 4
    assert outcome['baseline']['metrics']['changeover_count'] == 3
    assert outcome['optimized']['metrics']['changeover_count'] == 1


def test_optimizer_matches_enumerated_optimum_on_four_jobs():
    s = scenario()
    observed = optimize(s, 8)
    assert observed['solver']['optimality_proven']
    optimum = float('inf')
    for ordering in itertools.permutations(s['jobs']):
        now, previous, completion, setup_units = 0, None, {}, 0
        for job in ordering:
            family = job['operations'][0]['setup_family']
            if previous is not None and family != previous:
                now += s['machines'][0]['changeover_time']
                setup_units += 4
            now += job['operations'][0]['duration']
            completion[job['id']] = now
            previous = family
        objective = sum(j['weight']*max(0, completion[j['id']]-j['due']) for j in s['jobs'])
        optimum = min(optimum, objective)
    assert optimum == evaluate(s, observed['schedule'])['weighted_tardiness'] == 12


def test_every_dispatch_policy_is_feasible_under_setups():
    for policy in ('edd','fifo','spt','wspt'):
        s = scenario()
        rows = dispatch(s, policy)
        assert check_schedule(s, rows) == []


def test_universal_compiler_preserves_setup_rules():
    raw = json.loads((ROOT/'samples/universal/setup_cell.json').read_text())
    compiled = normalize_universal(raw)
    assert compiled['machines'][0]['changeover_time'] == 4
    assert {op['setup_family'] for j in compiled['jobs'] for op in j['operations']} == {'A','B'}
    r = optimize(compiled, 6)
    assert r['solver']['optimality_proven']
    assert not check_schedule(compiled, r['schedule'])


def test_universal_rejects_missing_setup_family():
    raw = json.loads((ROOT/'samples/universal/setup_cell.json').read_text())
    raw['work_orders'][0]['steps'][0].pop('setup_family')
    with pytest.raises(ValueError, match='setup_family'):
        normalize_universal(raw)


def test_rolling_preserves_executed_work_and_changeover():
    s = scenario()
    old = dispatch(s)
    frozen = prepare_rolling(s, old, 1, s)
    rows = rolling_dispatch(s, frozen, 1, 'edd')
    assert check_schedule(s, rows) == []
    assert next(x for x in rows if x['key']=='A1::0') == frozen['A1::0']
    solved = optimize(s, 6, fixed_operations=frozen, not_before=1)
    assert solved['schedule'] is not None
    assert check_schedule(s, solved['schedule']) == []


def test_support_reservation_does_not_incur_primary_setup():
    s = scenario()
    s['machines'].append({'id':'TECH','downtime':[]})
    for job in s['jobs']:
        job['operations'][0]['support_resources']=['TECH']
    # Technician reserved with every operation but must never trigger product-family setup.
    solved = optimize(s, 6)
    assert solved['schedule'] is not None
    assert not check_schedule(s, solved['schedule'])


def test_old_scenario_keeps_existing_metrics_and_schedule():
    s=json.loads((ROOT/'samples/assembly_cell.json').read_text())
    outcome=compare(s,6)
    assert outcome['baseline']['metrics']['weighted_tardiness']==39
    assert outcome['optimized']['metrics']['weighted_tardiness']==15
    assert outcome['optimized']['metrics']['changeover_count']==0
    assert outcome['optimized']['metrics']['setup_time_units']==0
