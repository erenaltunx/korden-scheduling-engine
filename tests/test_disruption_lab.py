"""Statistical replay stability and reproducibility tests."""
from disruption_lab import run_disruption_lab


def test_disruption_lab_replay_and_no_worse_plan():
    report = run_disruption_lab(count=5, start_seed=300, time_limit=2)
    rows = report['rows']
    assert report['summary']['instances'] == 5
    assert all(r['frozen_operations'] >= 1 for r in rows)
    assert all(r['rolling_optimizer_weighted_tardiness'] <= r['rolling_edd_weighted_tardiness'] for r in rows)
    assert all(r['solver_status'] for r in rows)
    assert all(r['start_shift_hours'] >= 0 for r in rows)
    assert [r['seed'] for r in rows] == list(range(300,305))


def test_disruption_lab_is_reproducible_except_timing():
    a=run_disruption_lab(count=2,start_seed=333,time_limit=2)
    b=run_disruption_lab(count=2,start_seed=333,time_limit=2)
    for x,y in zip(a['rows'],b['rows']):
        for key in ('rolling_edd_weighted_tardiness','rolling_optimizer_weighted_tardiness',
                    'frozen_operations','changed_future_operations','outage_start'):
            assert x[key] == y[key]
