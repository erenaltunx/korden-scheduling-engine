"""Quality gates for transparent, multi-complexity portfolio evidence."""
import pytest

import research_lab
from optera.baseline import POLICIES, dispatch
from optera.evaluation import check_schedule


@pytest.mark.parametrize('profile', research_lab.PROFILES)
def test_generated_inputs_are_deterministic_and_feasible(profile):
    first = research_lab.make_factory(profile, 140)
    second = research_lab.make_factory(profile, 140)
    assert first == second
    assert research_lab._digest(first) == research_lab._digest(second)
    assert all(not check_schedule(first, dispatch(first, p)) for p in POLICIES)


def test_profiles_are_genuinely_different():
    a = research_lab.make_factory('single_cell', 141)
    b = research_lab.make_factory('two_stage', 141)
    c = research_lab.make_factory('flexible_cell', 141)
    assert len(a['machines']) == 1 and all(len(j['operations']) == 1 for j in a['jobs'])
    assert len(b['machines']) == 2 and all(len(j['operations']) == 2 for j in b['jobs'])
    assert len(c['machines']) == 3 and all(len(j['operations']) == 2 for j in c['jobs'])
    assert any(len(op['machines']) == 2 for j in c['jobs'] for op in j['operations'])
    d = research_lab.make_factory('congested_cell', 141)
    assert len(d['jobs']) >= 9 and len(d['machines']) == 3


def test_input_rejection():
    with pytest.raises(ValueError):
        research_lab.make_factory('impossible', 10)
    with pytest.raises(ValueError):
        research_lab.make_factory('single_cell', '10')
    for n, limit in [(0, 2), (51, 2), (2, .2), (1, 32)]:
        with pytest.raises(ValueError):
            research_lab.run_study(count_per_profile=n, time_limit=limit)


def test_no_magic_improvement_when_solver_fails(monkeypatch):
    def out_of_time(*args, **kwargs):
        return {'schedule': None, 'solver': {'status': 'time_limit', 'optimality_proven': False, 'solve_seconds': 0.15}}
    monkeypatch.setattr(research_lab, 'optimize', out_of_time)
    row = research_lab.run_instance('single_cell', 102, .5)
    assert row['selection'] == 'baseline_fallback'
    assert row['milp_weighted_tardiness'] is None
    assert row['recommended_weighted_tardiness'] == row['baseline_weighted_tardiness']
    assert not row['optimality_proven']


def test_invalid_solver_schedule_is_rejected(monkeypatch):
    def invalid(*args, **kwargs):
        return {'schedule': [{'key': 'bogus', 'machine': 'CNC', 'start': 0, 'end': 1}],
                'solver': {'status': 'optimal', 'optimality_proven': True, 'solve_seconds': 0.2}}
    monkeypatch.setattr(research_lab, 'optimize', invalid)
    with pytest.raises(AssertionError, match='invalid plan'):
        research_lab.run_instance('single_cell', 102, .5)


def test_paired_analysis_counts_and_zero_denominator():
    rows = [dict(profile='single_cell', seed=i, baseline_weighted_tardiness=0,
                 recommended_weighted_tardiness=0, selection='baseline_fallback',
                 milp_weighted_tardiness=None, optimality_proven=False,
                 jobs=1, operations=1, solve_seconds=0.1,
                 baseline_setup_time=0, recommended_setup_time=0,
                 baseline_makespan=2, recommended_makespan=2) for i in range(2)]
    summ = research_lab._summary(rows)
    assert summ['relative_reduction_percent'] is None
    assert summ['improved'] == 0 and summ['equal'] == 2
    assert summ['fallbacks'] == 2 and summ['proven_optima'] == 0


def test_auditable_export_roundtrip(tmp_path):
    run = research_lab.run_study(count_per_profile=1, seed_base=123, time_limit=1, stress_count=1)
    saved, csv_path = research_lab.write_study(run, tmp_path/'research')
    import json, csv
    assert json.loads(saved.read_text())['summary'] == run['summary']
    with csv_path.open(newline='', encoding='utf-8') as f:
        assert len(list(csv.DictReader(f))) == 4
    assert run['summary']['instances'] == 4
    assert all(r['recommended_weighted_tardiness'] <= r['baseline_weighted_tardiness'] for r in run['rows'])
