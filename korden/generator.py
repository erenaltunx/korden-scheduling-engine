"""Deterministic synthetic factory instances for reproducible benchmark research."""
import random


def generate_factory(seed: int, job_count: int = 5) -> dict:
    if type(seed) is not int or type(job_count) is not int or not 2 <= job_count <= 12:
        raise ValueError('Seed must be int; job_count must be 2–12')
    rng = random.Random(seed)
    jobs = []
    for n in range(job_count):
        cut = rng.randint(2, 7)
        mill = rng.randint(2, 9)
        pack = rng.randint(1, 3)
        release = rng.randint(0, 7)
        due = release + cut + mill + pack + rng.randint(2, 19)
        weight = rng.randint(1, 5)
        jobs.append({
            'id': f'J{n+1:02d}', 'release': release, 'due': due, 'weight': weight,
            'operations': [
                {'id': 'Cut', 'duration': cut, 'machines': ['CUT']},
                {'id': 'Mill', 'duration': mill, 'machines': ['CNC-A', 'CNC-B']},
                {'id': 'Pack', 'duration': pack, 'machines': ['PACK']},
            ]
        })
    return {
        'schema_version': 1,
        'factory_name': f'Generated workshop | seed {seed} | {job_count} orders',
        'machines': [
            {'id': 'CUT', 'downtime': []},
            {'id': 'CNC-A', 'downtime': [{'start': 9, 'end': 12}] if seed % 3 == 0 else []},
            {'id': 'CNC-B', 'downtime': [{'start': 15, 'end': 18}] if seed % 4 == 0 else []},
            {'id': 'PACK', 'downtime': [{'start': 18, 'end': 21}] if seed % 5 == 0 else []},
        ],
        'jobs': jobs,
    }
