"""Strict importer for the classic JSP text format used by JSPLIB.

These benchmarks minimize Cmax (makespan), NOT tardiness. They are not
interchangeable with KORDEN's original business-oriented tardiness benchmark.
"""
from __future__ import annotations
from pathlib import Path
from .model import validate_scenario

PUBLIC_INSTANCES = {'ft06': 55, 'la01': 666}


def parse_jobshop(text: str, name: str = 'Job shop benchmark') -> dict:
    if not isinstance(text, str) or len(text) > 100_000:
        raise ValueError('Invalid jobshop source text')
    lines = [line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith('#')]
    if not lines:
        raise ValueError('Missing JSP header')
    try:
        header = [int(x) for x in lines[0].split()]
        if len(header) != 2:
            raise ValueError('Expected job and machine counts')
        job_count, machine_count = header
        if not 1 <= job_count <= 30 or not 1 <= machine_count <= 12:
            raise ValueError('Instance exceeds the current model limits')
        if len(lines) != job_count + 1:
            raise ValueError('Incorrect number of job rows')
        jobs = []
        for j, line in enumerate(lines[1:]):
            values = [int(x) for x in line.split()]
            if len(values) != machine_count * 2:
                raise ValueError(f'Job {j+1} has incorrect machine-duration pairs')
            mids = values[0::2]
            durations = values[1::2]
            if sorted(mids) != list(range(machine_count)):
                raise ValueError(f'Job {j+1} must visit each machine exactly once')
            if any(t <= 0 or t > 1000 for t in durations):
                raise ValueError('Invalid operation duration')
            jobs.append({'id': f'J{j+1:02}', 'release': 0, 'due': 0, 'weight': 1,
                         'operations': [{'id': f'O{k+1:02}', 'duration': dur, 'machines': [f'M{mid:02}']}
                                        for k, (mid, dur) in enumerate(zip(mids, durations))]})
    except (ValueError, TypeError) as error:
        raise ValueError(f'Invalid JSP instance: {error}') from error
    data = {'schema_version': 1, 'factory_name': name,
            'machines': [{'id': f'M{m:02}', 'downtime': []} for m in range(machine_count)],
            'jobs': jobs}
    validate_scenario(data)
    return data


def load_jsplib(name: str) -> dict:
    if name not in PUBLIC_INSTANCES:
        raise ValueError('Only vetted bundled public benchmark instances are allowed')
    path = Path(__file__).resolve().parent.parent/'benchmarks'/'jsplib'/f'{name}.txt'
    data = parse_jobshop(path.read_text(encoding='utf-8'), f'JSPLIB public benchmark: {name}')
    data['benchmark_known_optimum_makespan'] = PUBLIC_INSTANCES[name]
    data['benchmark_source'] = f'https://github.com/tamy0612/JSPLIB/blob/master/instances/{name}'
    return data
