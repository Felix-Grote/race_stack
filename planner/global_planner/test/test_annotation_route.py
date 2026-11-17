# Copyright 2026 ForzaETH
"""Route-manifest contract tests against the live PR #10 package.

Pins reference lap geometry and in-run determinism for unedited maps,
genuine operator corner cuts on Baku (strokes + bucket seed through
the full pipeline), canonical start-zone containment for generated
routes, NUC5 car zones and approval-bound metadata. Exact digests are
not asserted across machines: the float pipeline legitimately lands
on different last-ulp branches per CPU/BLAS build; within one
environment it is deterministic, which is what approval binds.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))

from conftest import MAPS, midline_seed  # noqa: E402
from global_planner.annotation_core import (  # noqa: E402
    AnnotationError, TrackMap, build_candidate, build_route,
    check_payload, effective_free_mask, extract_boundaries,
    free_components, geometry_digest, new_session, patched_free_mask)
from global_planner.car import Car  # noqa: E402
from global_planner.route.manifest import load_route, validate_route  # noqa: E402

REPO = Path(__file__).parents[3]
NUC5 = REPO / 'stack_master' / 'config' / 'NUC5' / 'car_model.yaml'

BAKU_CUTS = [[[316.0, 584.0], [284.0, 482.0]],
             [[201.0, 294.0], [319.0, 298.0]],
             [[362.0, 187.0], [309.0, 81.0]],
             [[100.0, 308.0], [190.0, 297.0]]]
BAKU_SEED = [179, 25]
TEST_CUT = [[[130.16427660290194, 3.890151624735724],
             [48.83572339709805, 100.10984837526428]]]
TEST_CUT_SEED = [125, 230]

REFERENCE_LAP_M = {'test': 85.868, 'baku': 122.77,
                   'baku_1cut': 121.844, 'baku_4cut': 120.071}


def _session(track_map, strokes=(), seed=None):
    """Session with the given strokes/bucket seed and a midline guide."""
    session = new_session(track_map)
    session['boundary_strokes_px'] = [list(map(list, s)) for s in strokes]
    session['retained_region_px'] = seed
    outer, inner = extract_boundaries(track_map, strokes, 5, seed)
    session['route_px'] = midline_seed(outer, inner)
    return session


@pytest.mark.parametrize('name,key', [('test/test', 'test'),
                                      ('baku/baku', 'baku')])
def test_reference_lap_and_roundtrip(name, key, tmp_path):
    """Unedited maps build reference geometry deterministically; the
    exported file reloads to the same digest it was built with."""
    track_map = TrackMap(MAPS / f'{name}.yaml')
    session = _session(track_map)
    payload, route, receipt, _ = build_candidate(track_map, session)
    assert receipt['lap_length_m'] == pytest.approx(
        REFERENCE_LAP_M[key], abs=0.1)
    _, again, _, _ = build_candidate(track_map, session)
    assert again.digest == route.digest
    path = tmp_path / 'route.json'
    path.write_text(json.dumps(payload, indent=1), encoding='utf-8')
    assert load_route(path).digest == route.digest
    assert set(payload) == {'name', 'map', 'start', 'sections'}
    assert set(payload['map']) == {'frame_id', 'sha256'}
    assert payload['map']['sha256'] == track_map.sha256
    assert set(payload['start']) == {'heading_range_rad', 'zone'}
    for section in payload['sections']:
        assert set(section) == {'uid', 'surface', 'max_speed_mps',
                                'left', 'right'}
    assert receipt['stages']['manifest'] == 'PASS'
    assert receipt['stages']['car_zones'].startswith('NOT_CHECKED')
    assert receipt['not_checked']  # optimizer/dynamics named, not implied


def test_baku_cuts_need_selection_then_shorten_lap():
    """Corner cuts fragment the mask; with the bucket seed the lap
    shortens, pockets stay excluded and car zones pass."""
    track_map = TrackMap(MAPS / 'baku/baku.yaml')
    regions = free_components(patched_free_mask(track_map, BAKU_CUTS, 5))
    assert len(regions) == 5
    with pytest.raises(AnnotationError, match='NEEDS_REGION_SELECTION'):
        extract_boundaries(track_map, BAKU_CUTS, 5, None)
    car = Car.load(NUC5, margin_m=0.05)
    for cuts, key in ((BAKU_CUTS[:1], 'baku_1cut'), (BAKU_CUTS, 'baku_4cut')):
        session = _session(track_map, cuts, BAKU_SEED)
        payload, route, receipt, _ = build_candidate(
            track_map, session, car=car)
        assert receipt['lap_length_m'] == pytest.approx(
            REFERENCE_LAP_M[key], abs=0.1)
        assert receipt['lap_length_m'] < REFERENCE_LAP_M['baku']
        assert receipt['stages']['vector_legal']['annexed_m2'] == 0.0
        assert receipt['stages']['car_zones'] == 'PASS'
        assert validate_route(payload).digest == route.digest


def test_reversed_guide_validates_with_swapped_walls():
    """Reversal contract: the reversed guide builds a valid route with
    a different digest (left/right ownership follows reversed travel)
    over the same lap; both directions pass every check."""
    track_map = TrackMap(MAPS / 'test/test.yaml')
    fwd_session = _session(track_map)
    rev_session = _session(track_map)
    route = rev_session['route_px']  # exactly closed midline loop
    body = route[:-1] if route[0] == route[-1] else route
    rev_session['route_px'] = [body[0]] + body[1:][::-1] + [body[0]]
    fwd_payload, fwd_route, fwd_receipt, _ = build_candidate(
        track_map, fwd_session)
    rev_payload, rev_route, rev_receipt, _ = build_candidate(
        track_map, rev_session)
    assert rev_route.digest != fwd_route.digest
    assert rev_receipt['lap_length_m'] == pytest.approx(
        fwd_receipt['lap_length_m'], abs=0.5)
    # Travel flipped: the start heading points the other way.
    assert rev_payload['start']['heading_range_rad'] != \
        fwd_payload['start']['heading_range_rad']


def test_test_map_kinked_cut_validates():
    """The old kinked corner cut builds under wall-derived centrelines."""
    track_map = TrackMap(MAPS / 'test/test.yaml')
    session = _session(track_map, TEST_CUT, TEST_CUT_SEED)
    _, _, receipt, _ = build_candidate(track_map, session)
    assert receipt['stages']['manifest'] == 'PASS'


def test_start_zone_containment_contract():
    """Generated zones satisfy canonical containment on real maps; an
    off-road zone fails at the manifest stage, never silently."""
    from shapely.geometry import Polygon
    for name in ('test/test', 'baku/baku', 'spa/spa', 'zuri/zuri'):
        track_map = TrackMap(MAPS / f'{name}.yaml')
        session = _session(track_map)
        payload, _ = build_route(
            track_map, *extract_boundaries(track_map), session['route_px'],
            legal_mask=effective_free_mask(track_map, [], 5))
        first = payload['sections'][0]
        section0 = Polygon(list(first['right'])
                           + list(reversed(first['left'])))
        assert section0.covers(Polygon(payload['start']['zone'])), name
        validate_route(payload)
    track_map = TrackMap(MAPS / 'test/test.yaml')
    session = _session(track_map)
    legal = effective_free_mask(track_map, [], 5)
    payload, _ = build_route(
        track_map, *extract_boundaries(track_map), session['route_px'],
        legal_mask=legal)
    payload['start']['zone'] = [[-8.0, -5.0], [-6.0, -5.0],
                                [-6.0, -3.0], [-8.0, -3.0]]
    with pytest.raises(AnnotationError, match='MANIFEST_VALID'):
        check_payload(payload, track_map, legal)


def test_car_zones_for_nuc5():
    """Vehicle stages run only for an explicitly supplied car."""
    track_map = TrackMap(MAPS / 'baku/baku.yaml')
    session = _session(track_map)
    car = Car.load(NUC5, margin_m=0.05)
    _, _, receipt, _ = build_candidate(track_map, session, car=car)
    assert receipt['stages']['car_zones'] == 'PASS'
    assert receipt['car']['name'] == 'NUC5'
    absurd = Car.load(NUC5, margin_m=50.0)
    with pytest.raises(AnnotationError, match='VEHICLE_ZONES_READY'):
        build_candidate(track_map, session, car=absurd)


def test_metadata_edits_change_digest_and_payload():
    """Name/surface/speed are approval-bound manifest fields."""
    track_map = TrackMap(MAPS / 'test/test.yaml')
    session = _session(track_map)
    before = geometry_digest(session, track_map)
    session['max_speed_mps'] = 3.5
    session['surface'] = 'asphalt'
    session['route_name'] = 'test_edited'
    assert geometry_digest(session, track_map) != before
    payload, _, _, _ = build_candidate(track_map, session)
    assert payload['name'] == 'test_edited'
    assert {s['surface'] for s in payload['sections']} == {'asphalt'}
    assert {s['max_speed_mps'] for s in payload['sections']} == {3.5}
    for field, bad in (('max_speed_mps', 0), ('surface', ' padded'),
                       ('route_name', '')):
        with pytest.raises(AnnotationError):
            build_candidate(track_map, dict(session, **{field: bad}))
