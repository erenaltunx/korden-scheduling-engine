"""Paired experiment, evidence provenance and misleading-claim regression gates."""
import json
import pytest
import solver_budget_lab as lab


def stub_run(profile, seed, budget):
    baseline = 20
    raw = 18 if budget > 1 else 22
    return {
        'profile': profile, 'seed': seed, 'input_sha256': f'const-seed-{seed}',
        'jobs': 5, 'operations': 10, 'resources': 3, 'best_rule': 'edd',
        'baseline_weighted_tardiness': baseline, 'baseline_makespan': 30,
        'baseline_late_jobs': 2, 'baseline_setup_time': 2,
        'milp_weighted_tardiness': raw, 'milp_makespan': 30, 'milp_setup_time': 2,
        'recommended_weighted_tardiness': min(baseline,raw),
        'recommended_makespan': 30, 'recommended_setup_time': 2,
        'selection': 'milp' if raw <= baseline else 'baseline_fallback',
        'solver_status': 'time_limit_with_solution',
        'optimality_proven': False, 'solve_seconds': budget,
        'relative_mip_gap': 0.5,
    }


def test_pairs_same_seed_and_no_baseline_inflation(monkeypatch):
    monkeypatch.setattr(lab, 'run_instance', stub_run)
    study = lab.run_study(count=3, budgets=(.7, 2.0))
    assert len(study['rows']) == 6
    assert study['summary_by_budget']['0.7']['baseline_weighted_tardiness'] == 60
    assert study['summary_by_budget']['0.7']['recommended_weighted_tardiness'] == 60
    assert study['summary_by_budget']['2.0']['recommended_weighted_tardiness'] == 54
    assert study['summary_by_budget']['0.7']['fallbacks'] == 3
    assert len(study['transitions']) == 3
    assert all(t['longer_budget_improved'] for t in study['transitions'])
    assert study['metadata']['warm_start'] is False


def test_not_monotonic_across_independent_run_budgets(monkeypatch):
    def backwards(profile, seed, budget):
        row=stub_run(profile,seed,budget)
        if budget >= 2.0:
            row['milp_weighted_tardiness']=25
            row['selection']='baseline_fallback'
            row['recommended_weighted_tardiness']=20
        else:
            row['milp_weighted_tardiness']=10
            row['selection']='milp'
            row['recommended_weighted_tardiness']=10
        return row
    monkeypatch.setattr(lab, 'run_instance', backwards)
    study=lab.run_study(count=1,budgets=(.7,2.0))
    assert study['transitions'][0]['longer_budget_worsened'] is True


def test_rejects_mismatched_workload(monkeypatch):
    def drift(profile,seed,budget):
        row=stub_run(profile,seed,budget)
        row['input_sha256']+=str(budget)
        return row
    monkeypatch.setattr(lab,'run_instance',drift)
    with pytest.raises(AssertionError,match='inputs changed'):
        lab.run_study(count=1,budgets=(.7,2.))


def test_rejects_invalid_result(monkeypatch):
    def invalid(profile,seed,budget):
        row=stub_run(profile,seed,budget)
        row['recommended_weighted_tardiness']=999
        return row
    monkeypatch.setattr(lab,'run_instance',invalid)
    with pytest.raises(AssertionError,match='regressed'):
        lab.run_study(count=1,budgets=(.7,))


@pytest.mark.parametrize('bad', ['', '.3,2', '2,1', '1,1', 'nan', 'inf', '1,b', '0.5,61'])
def test_bad_budgets_rejected(bad):
    with pytest.raises(ValueError):
        lab.parse_budgets(bad)


@pytest.mark.parametrize('bad', [0, 21, True, 1.5])
def test_bad_counts_rejected(monkeypatch,bad):
    monkeypatch.setattr(lab,'run_instance',stub_run)
    with pytest.raises(ValueError):
        lab.run_study(count=bad)


def test_export_csv_and_json(tmp_path,monkeypatch):
    monkeypatch.setattr(lab,'run_instance',stub_run)
    result=lab.run_study(count=2,budgets=(.7,2.))
    js,cs=lab.write_study(result,tmp_path/'nested'/'study')
    assert json.loads(js.read_text())['summary_by_budget']==result['summary_by_budget']
    assert len(cs.read_text().splitlines())==5
    assert result['summary_by_budget']['0.7']['proved_optimal']==0


def test_actual_optimization_smoke():
    # Production code path and real independent schedule verification.
    report=lab.run_study(count=1,seed_base=230011,budgets=(.7,))
    assert len(report['rows'])==1
    assert report['rows'][0]['baseline_weighted_tardiness']>=report['rows'][0]['recommended_weighted_tardiness']
    assert report['rows'][0]['operations']>=18
