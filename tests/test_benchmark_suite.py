"""Benchmark generation and aggregation reproducibility checks."""
from optera.generator import generate_factory
from optera.model import validate_scenario
from benchmark_suite import run_suite


def test_generator_is_deterministic():
    a = generate_factory(13)
    b = generate_factory(13)
    assert a == b
    assert a != generate_factory(14)
    assert len(a['jobs']) == 5
    validate_scenario(a)


def test_three_seed_suite_proves_optimum():
    result = run_suite(count=3, jobs=5, time_limit=3)
    assert result['summary']['instances'] == 3
    assert result['summary']['optimality_proven_count'] == 3
    assert all(x['optimized_weighted_tardiness'] <= x['baseline_weighted_tardiness'] for x in result['rows'])
    assert result['summary']['combined_optimized_weighted_tardiness'] <= result['summary']['combined_baseline_weighted_tardiness']
