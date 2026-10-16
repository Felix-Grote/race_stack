"""A01 strict parsing, legal topology and deterministic identity oracles."""
import copy
from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import subprocess
import sys

import pytest

from global_planner.route_input import RouteError, canonical_bytes, load_route, validate_route

FIX = Path(__file__).parent / 'fixtures' / 'project_a'


def payload(name='s0_route'):
    return json.loads((FIX / (name + '.json')).read_text())


@pytest.mark.parametrize('name', ['s0_route', 's0_reverse_route', 's0_rotated_route',
                                  's2_upper_route', 's2_lower_route', 's3_surfaces_route'])
def test_selected_cycles(name):
    r = load_route(FIX / (name + '.json'))
    assert len(r.occurrences) == len(r.portals) == 4
    assert len(r.digest) == 64
    assert r.encoded == canonical_bytes(r.payload)


def test_separate_branches_and_overlapping_surfaces():
    upper, lower = (validate_route(payload('s2_' + s + '_route')) for s in ('upper', 'lower'))
    assert upper.digest != lower.digest
    assert upper.occurrences[-1].seed == lower.occurrences[-1].seed
    r = validate_route(payload('s3_surfaces_route'))
    a, b = r.occurrences[0], r.occurrences[2]
    assert a.surface_id != b.surface_id
    assert a.seed[16] == pytest.approx(b.seed[16], abs=1e-14)
    assert (a.id, b.id) not in [(p.source, p.target) for p in r.portals]


@pytest.mark.parametrize('mutation', [
    lambda p: p.update(schema_version=2), lambda p: p.update(units='cm'),
    lambda p: p.update(extra_field=1), lambda p: p['occurrences'][0].update(id=True),
    lambda p: p['occurrences'][1].update(id='o0'),
    lambda p: p['occurrences'][0].update(surface_id='absent'),
    lambda p: p['occurrences'][0]['seed'].__setitem__(1, p['occurrences'][0]['seed'][0]),
    lambda p: p['occurrences'][0]['seed'][2].__setitem__(0, float('nan')),
    lambda p: p['occurrences'][0].update(left=p['occurrences'][0]['right']),
    lambda p: p['occurrences'][0]['left'].__setitem__(3, [999, 999]),
    lambda p: p['occurrences'][0]['caps'][0].update(max_speed_mps=-1),
    lambda p: p['occurrences'][0]['caps'][0].update(at_m=1),
    lambda p: p['transitions'].pop(), lambda p: p['transitions'].append(p['transitions'][0]),
    lambda p: p['transitions'][0].update(to='o2'),
    lambda p: p['transitions'][0]['gate'].reverse(),
    lambda p: p['transitions'][0]['gate'][0].__setitem__(0, 999),
    lambda p: p['transitions'][0].update(after_m=-1),
    lambda p: p['gate_sequence'].reverse(), lambda p: p.update(finish='p0'),
    lambda p: p['initialization'].update(occurrence_id='o1'),
    lambda p: p['physical_map'].update(sha256='not a digest'),
    lambda p: p['surfaces'].append(p['surfaces'][0]),
])
def test_semantic_adversaries(mutation):
    p = payload()
    mutation(p)
    with pytest.raises(RouteError):
        validate_route(p)


@pytest.mark.parametrize('raw', [
    '{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}',
    '{"x":1e999}', '{"x":null}', '{"x":false}', '{bad',
])
def test_malformed_json(tmp_path, raw):
    f = tmp_path / 'bad.json'
    f.write_text(raw)
    with pytest.raises(RouteError):
        load_route(f)


def test_canonical_immutable_and_provenance_identity():
    p = payload()
    before = copy.deepcopy(p)
    r = validate_route(p)
    assert p == before
    assert validate_route(dict(reversed(list(p.items())))).digest == r.digest
    p['physical_map']['registration'] = [-0.0, 0.0, 0]
    assert validate_route(p).digest == r.digest
    for change in ('border', 'surface', 'cap', 'approval', 'map'):
        q = payload()
        if change == 'border':
            q['occurrences'][0]['left'][5][0] += .001
        if change == 'surface':
            q['surfaces'][0]['provenance']['revision'] = 'changed'
        if change == 'cap':
            q['occurrences'][0]['caps'][0]['max_speed_mps'] += .1
        if change == 'approval':
            q['provenance']['revision'] = 'changed'
        if change == 'map':
            q['physical_map']['coverage'] = 'partial'
        assert validate_route(q).digest != r.digest
    with pytest.raises(FrozenInstanceError):
        r.occurrences[0].id = 'mutated'
    q = r.payload
    q['occurrences'][0]['seed'][0][0] = 999
    assert r.payload == before


def test_pure_import():
    subprocess.run([sys.executable, '-c',
                    'import sys; import global_planner.route_input; '
                    'assert "rclpy" not in sys.modules; '
                    'assert "trajectory_planning_helpers" not in sys.modules'], check=True)


@pytest.mark.parametrize('mutation', [
    lambda p: p['physical_map'].update(registration=[0, 'bad', 0]),
    lambda p: p['occurrences'][0]['caps'][0].update(at_m='zero'),
    lambda p: p['occurrences'][0]['caps'][0].update(max_speed_mps=[4]),
    lambda p: p['transitions'][0].update(before_m='bad'),
    lambda p: p['transitions'][0].update(after_m=[]),
    lambda p: p['initialization'].update(seed_interval_m=[0, 'bad']),
    lambda p: p['initialization'].update(heading_interval_rad=[0, []]),
])
def test_wrong_numeric_types_reject_consistently(mutation):
    p = payload()
    mutation(p)
    with pytest.raises(RouteError):
        validate_route(p)


def test_translation_stable_polygon_predicate():
    from global_planner._route_geometry import signed_area_twice, simple_polygon
    # A small valid square near the documented maximum coordinate magnitude.
    p = ((99999., 99999.), (99999.0001, 99999.),
         (99999.0001, 99999.0001), (99999., 99999.0001))
    assert simple_polygon(p)
    assert signed_area_twice(p) == pytest.approx(2e-8, abs=3e-15)


def test_seed_cannot_recross_ownership_end_cap():
    p = payload()
    # A legal-side-contained detour revisits the starting cap inside occurrence 0.
    # End caps separate declared ownership; this is not another legal portal.
    p['occurrences'][0]['seed'].insert(2, [6.1, 0])
    with pytest.raises(RouteError, match='ownership end cap'):
        validate_route(p)
