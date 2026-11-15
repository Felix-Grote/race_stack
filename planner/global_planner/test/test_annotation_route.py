# Copyright 2026 ForzaETH
"""Route-manifest contract tests: annotation output against live PR #10.

These pin what the migration must prove and the raster/UI suites do
not: the exact ``global_planner.route`` payload shape, reference
geometry for the unedited maps, genuine operator corner cuts on
Baku (strokes + bucket selection through the full check pipeline),
final-polygon legality failures, car portal zones, metadata binding
and the v3 -> v4 session migration.

Corner-cut fixture provenance: no recorded operator session existed,
so the strokes below are reconstructed operator-equivalent actions -
each is a straight boundary stroke between two points on the inner
wall of the Baku map (found by search, 2026-11-15), cutting off one
corner pocket; BAKU_SEED is the bucket click in the retained main
component. The coordinates are frozen here as the fixture.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))

from global_planner.annotation_core import (  # noqa: E402
    AnnotationError, TrackMap, build_candidate, build_route,
    check_payload, effective_free_mask, extract_boundaries,
    free_components, geometry_digest, load_session, new_session,
    patched_free_mask, save_session)
from global_planner.car import Car  # noqa: E402
from global_planner.route.manifest import load_route, validate_route  # noqa: E402

REPO = Path(__file__).parents[3]
MAPS = REPO / 'stack_master' / 'maps'
NUC5 = REPO / 'stack_master' / 'config' / 'NUC5' / 'car_model.yaml'

BAKU_CUTS = [[[316.0, 584.0], [284.0, 482.0]],
             [[201.0, 294.0], [319.0, 298.0]],
             [[362.0, 187.0], [309.0, 81.0]],
             [[100.0, 308.0], [190.0, 297.0]]]
BAKU_SEED = [179, 25]
# The old stack's kinked corner cut on the test map (was a hard
# failure under corridor-chart validation; see the test below).
TEST_CUT = [[[130.16427660290194, 3.890151624735724],
             [48.83572339709805, 100.10984837526428]]]
TEST_CUT_SEED = [125, 230]

# Reference geometry measured on the development machine (CPython
# 3.14, opencv 5.0.0, numpy 2.5.4). Exact Route.digests are *not*
# asserted: the float geometry pipeline (resampling, RDP keep/drop at
# the epsilon boundary) lands on different last-ulp branches across
# CPU/BLAS builds, so identical input yields a different - equally
# valid - digest on other runners (observed in CI). What approval
# actually needs, and what is asserted, is determinism within one
# environment plus the recorded lap geometry within tolerance.
REFERENCE_LAP_M = {'test': 85.868, 'baku': 122.77,
                   'baku_1cut': 121.844, 'baku_4cut': 120.071}
REFERENCE_DIGEST = {
    'test': '7d420739fb56aa573ae9fbaada3d9df59e27c4a982a74e3adb15cf09bee7005b',
    'baku': 'a9f848f60dc23c2b5830214145702ebbee05b3657622b67ff140cbbfef825adc',
    'baku_1cut': '508c12e0af53a8e4df677af625fca1c9b19b3aa949be0fb46d683b39cdff921b',
    'baku_4cut': '1cea27a03d4f05890d1be8ef87a3e8ff60335b991bf02e9070f98b3d04b0b111',
}


def _midline_seed(outer, inner, count=120):
    step = max(1, len(outer) // count)
    seed = []
    for p in outer[::step]:
        j = int(np.argmin(np.linalg.norm(inner - p, axis=1)))
        seed.append(((p + inner[j]) / 2).tolist())
    return seed


def _session(track_map, strokes=(), seed=None):
    """Session with the given strokes/bucket seed and a midline guide."""
    session = new_session(track_map)
    session['boundary_strokes_px'] = [list(map(list, s)) for s in strokes]
    session['retained_region_px'] = seed
    outer, inner = extract_boundaries(track_map, strokes, 5, seed)
    session['route_px'] = _midline_seed(outer, inner)
    return session


@pytest.mark.parametrize('name,key', [('test/test', 'test'),
                                      ('baku/baku', 'baku')])
def test_golden_digest_and_roundtrip(name, key, tmp_path):
    """Unedited maps build reference geometry deterministically; the
    exported file reloads to the same digest it was built with."""
    track_map = TrackMap(MAPS / f'{name}.yaml')
    session = _session(track_map)
    payload, route, receipt, _ = build_candidate(track_map, session)
    assert receipt['lap_length_m'] == pytest.approx(
        REFERENCE_LAP_M[key], abs=0.1)
    # Deterministic in this environment: rebuilding changes nothing.
    _, again, _, _ = build_candidate(track_map, session)
    assert again.digest == route.digest
    path = tmp_path / 'route.json'
    path.write_text(json.dumps(payload, indent=1), encoding='utf-8')
    assert load_route(path).digest == route.digest
    # Exact live schema shape: nothing extra, nothing missing.
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


def test_baku_four_cuts_need_region_selection_first():
    """Four cuts fragment the mask into 5 regions; without the bucket
    seed extraction refuses instead of picking a component itself."""
    track_map = TrackMap(MAPS / 'baku/baku.yaml')
    regions = free_components(patched_free_mask(track_map, BAKU_CUTS, 5))
    assert len(regions) == 5
    with pytest.raises(AnnotationError, match='NEEDS_REGION_SELECTION'):
        extract_boundaries(track_map, BAKU_CUTS, 5, None)


@pytest.mark.parametrize('cuts,key', [(BAKU_CUTS[:1], 'baku_1cut'),
                                      (BAKU_CUTS, 'baku_4cut')])
def test_baku_corner_cuts_shorten_lap_and_validate(cuts, key):
    """Real shortened Baku corners: pockets excluded by the bucket,
    final polygons legal, full route pipeline green, lap shorter."""
    track_map = TrackMap(MAPS / 'baku/baku.yaml')
    base_area = int((effective_free_mask(track_map, [], 5) > 0).sum())
    session = _session(track_map, cuts, BAKU_SEED)
    legal_area = int((effective_free_mask(
        track_map, cuts, 5, BAKU_SEED) > 0).sum())
    assert legal_area < base_area - 1000 * len(cuts) // 2
    car = Car.load(NUC5, margin_m=0.05)
    payload, route, receipt, _ = build_candidate(
        track_map, session, car=car)
    assert route.digest != REFERENCE_DIGEST['baku']
    assert receipt['lap_length_m'] == pytest.approx(
        REFERENCE_LAP_M[key], abs=0.1)
    assert receipt['lap_length_m'] < 122.77  # unedited lap
    assert receipt['stages']['vector_legal']['status'] == 'PASS'
    assert receipt['stages']['vector_legal']['annexed_m2'] == 0.0
    assert receipt['stages']['car_zones'] == 'PASS'
    assert validate_route(payload).digest == route.digest


def test_test_map_kinked_cut_now_passes():
    """Behavior change, pinned: the old corridor-chart stack rejected
    this kinked cut at every smoothing level; the wall-derived
    centreline accepts it, so preview now grants a candidate. The
    spline-between-knots containment question belongs to the future
    trajectory checker and stays in the receipt's not_checked list."""
    track_map = TrackMap(MAPS / 'test/test.yaml')
    session = _session(track_map, TEST_CUT, TEST_CUT_SEED)
    _, route, receipt, _ = build_candidate(track_map, session)
    assert receipt['stages']['manifest'] == 'PASS'
    assert route.digest != REFERENCE_DIGEST['test']


def test_vector_legality_rejects_offroad_start_zone():
    """The route schema cannot see the raster; an off-road start zone
    must fail here, not in a later planner stage."""
    track_map = TrackMap(MAPS / 'test/test.yaml')
    session = _session(track_map)
    legal = effective_free_mask(track_map, [], 5)
    payload, _ = build_route(
        track_map, *extract_boundaries(track_map), session['route_px'],
        legal_mask=legal)
    payload['start']['zone'] = [[-8.0, -5.0], [-6.0, -5.0],
                                [-6.0, -3.0], [-8.0, -3.0]]
    with pytest.raises(AnnotationError, match='VECTOR_LEGAL'):
        check_payload(payload, track_map, legal)


def test_vector_legality_rejects_annexed_wall():
    """Moving one wall outward must fail the final-polygon gate even
    though the payload is otherwise the valid golden route."""
    track_map = TrackMap(MAPS / 'test/test.yaml')
    session = _session(track_map)
    legal = effective_free_mask(track_map, [], 5)
    payload, _ = build_route(
        track_map, *extract_boundaries(track_map), session['route_px'],
        legal_mask=legal)
    wall = payload['sections'][1]['left']
    mid = len(wall) // 2
    for i in range(mid - 3, mid + 4):
        wall[i] = [wall[i][0], wall[i][1] + 0.6]
    with pytest.raises(AnnotationError, match='VECTOR_LEGAL'):
        check_payload(payload, track_map, legal)


@pytest.mark.parametrize('margin', [0.0, 0.05, 0.1])
def test_car_zones_pass_for_nuc5(margin):
    """Vehicle stages run only for an explicitly supplied car."""
    track_map = TrackMap(MAPS / 'baku/baku.yaml')
    session = _session(track_map)
    car = Car.load(NUC5, margin_m=margin)
    _, _, receipt, _ = build_candidate(track_map, session, car=car)
    assert receipt['stages']['car_zones'] == 'PASS'
    assert receipt['car']['name'] == 'NUC5'
    assert receipt['car']['margin_m'] == margin


def test_car_zones_reject_absurd_reach():
    """A car whose reach spans whole sections fails closed at the
    vehicle stage while the manifest itself stays valid."""
    track_map = TrackMap(MAPS / 'baku/baku.yaml')
    session = _session(track_map)
    car = Car.load(NUC5, margin_m=50.0)
    with pytest.raises(AnnotationError, match='VEHICLE_ZONES_READY'):
        build_candidate(track_map, session, car=car)


def test_metadata_edits_change_digest_and_payload():
    """Name/surface/speed are approval-bound manifest fields."""
    track_map = TrackMap(MAPS / 'test/test.yaml')
    session = _session(track_map)
    before = geometry_digest(session, track_map)
    session['max_speed_mps'] = 3.5
    session['surface'] = 'asphalt'
    session['route_name'] = 'test_edited'
    assert geometry_digest(session, track_map) != before
    payload, route, _, _ = build_candidate(track_map, session)
    assert payload['name'] == 'test_edited'
    assert {s['surface'] for s in payload['sections']} == {'asphalt'}
    assert {s['max_speed_mps'] for s in payload['sections']} == {3.5}
    assert route.digest != REFERENCE_DIGEST['test']
    for field, bad in (('max_speed_mps', 0), ('max_speed_mps', -1),
                       ('surface', ' padded'), ('route_name', '')):
        broken = dict(session, **{field: bad})
        with pytest.raises(AnnotationError):
            build_candidate(track_map, broken)


def test_v3_session_migrates_with_approval_revoked(tmp_path):
    """A v3 draft (old schema-v1 approval) reopens as v4, unapproved,
    with manifest metadata defaulted and preview bindings cleared."""
    track_map = TrackMap(MAPS / 'test/test.yaml')
    session = new_session(track_map)
    session['version'] = 3
    for key in ('route_name', 'surface', 'max_speed_mps',
                'approval_route_digest', 'preview_route_digest'):
        del session[key]
    session['approval'] = 'operator-approved'
    session['approval_digest'] = 'a' * 64
    session['preview_digest'] = 'a' * 64
    path = tmp_path / 'v3.json'
    path.write_text(json.dumps(session), encoding='utf-8')
    loaded = load_session(path, track_map)
    assert loaded['version'] == 4
    assert loaded['approval'] == 'none'
    assert loaded['approval_digest'] is None
    assert loaded['preview_digest'] is None
    assert loaded['preview_route_digest'] is None
    assert loaded['route_name'] == 'test'
    assert loaded['surface'] == 'ground'
    assert loaded['max_speed_mps'] == 2.5
    save_session(loaded, path)  # round-trips as a clean v4 draft
    assert load_session(path, track_map)['version'] == 4
