# Copyright 2026 ForzaETH
"""Operator-flow tests: server state machine behind the browser UI.

Pins no-stale-display on failure, exact preview layers, the
edit -> re-preview -> re-approve lifecycle, bucket selection through
the server, persisted previews across restarts, and the static HTML
contract the single-page frontend relies on.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))

from conftest import midline_seed  # noqa: E402
from global_planner.annotation_core import (  # noqa: E402
    AnnotationError, build_route, effective_free_mask, export_name,
    extract_boundaries, geometry_digest, load_session, save_session)
from global_planner.route.manifest import validate_route  # noqa: E402

UI_HTML = Path(__file__).parents[1] / 'global_planner' / 'annotation_ui.html'

KILLER = [[100.0, 0.0], [100.0, 442.0]]  # full-height cut: splits the ring
BENIGN_A = [[211.0, 7.5], [239.0, 7.5]]
BENIGN_B = [[239.0, 7.5], [245.0, 7.5]]  # eastward extension of A
SYN_CUT = [[20.0, 60.0], [60.0, 20.0]]  # diagonal across the outer corner
SYN_RING = [100, 170]  # free pixel on the annulus bottom arm


def _open_drawn(srv, strokes=(BENIGN_A,), route=True, map='test'):
    srv.op_open({'map': map})
    srv.op_update({'field': 'boundary_strokes_px',
                   'value': [list(s) for s in strokes]})
    if route:
        track_map = srv.STATE['map']
        outer, inner = extract_boundaries(
            track_map, srv.STATE['session']['boundary_strokes_px'], 5)
        srv.op_update({'field': 'route_px',
                       'value': midline_seed(outer, inner)})
    return srv.STATE['map']


def test_failures_clear_stale_display_keep_edits(backend):
    """Breaking strokes/routes drop overlays + candidate, keep edits."""
    srv = backend
    _open_drawn(srv)
    assert srv.op_extract({})['status'] == 'CANDIDATE'
    srv.op_update({'field': 'boundary_strokes_px',
                   'value': [BENIGN_A, KILLER]})
    with pytest.raises(AnnotationError, match='separate regions'):
        srv.op_extract({})
    assert srv.STATE['session']['boundary_strokes_px'] == [BENIGN_A, KILLER]
    assert srv.STATE['extraction'] is None
    assert srv.STATE['candidate_digest'] is None
    srv.op_update({'field': 'boundary_strokes_px', 'value': [BENIGN_A]})
    prev = srv.op_preview({})
    stale = prev['candidate_digest']
    srv.op_update({'field': 'route_px',
                   'value': [[10 + 5 * np.cos(a), 10 + 5 * np.sin(a)]
                             for a in np.linspace(0, 2 * np.pi, 24)]})
    with pytest.raises((AnnotationError, ValueError)):
        srv.op_preview({})
    assert srv.STATE['extraction'] is not None  # boundaries still valid
    assert srv.STATE['candidate_digest'] is None
    with pytest.raises(AnnotationError, match='no fresh preview'):
        srv.op_approve({'approval_digest': stale})
    with pytest.raises(AnnotationError, match='separate regions'):
        _open_drawn(srv, strokes=(BENIGN_A, KILLER), route=False)
        srv.op_suggest({})
    assert srv.STATE['extraction'] is None


def test_receipt_carries_exact_final_corridor_layers(backend):
    """Preview layers are the manifest's own walls/centrelines/gates;
    the export receipt is bit-identical to the previewed candidate."""
    srv = backend
    track_map = _open_drawn(srv)
    prev = srv.op_preview({})
    assert prev['status'] == 'VALIDATED'
    assert len(prev['validated_route_px']) == 4
    assert len(prev['validated_left_px']) == 4
    assert len(prev['gates_px']) == 4
    outer, inner = extract_boundaries(
        track_map, srv.STATE['session']['boundary_strokes_px'], 5)
    session = srv.STATE['session']
    payload, _ = build_route(
        track_map, outer, inner, session['route_px'],
        legal_mask=effective_free_mask(
            track_map, session['boundary_strokes_px'],
            session.get('stroke_width_px', 5),
            session.get('retained_region_px')),
        name=session.get('route_name'),
        chain_dp_epsilon_m=session.get('chain_dp_epsilon_m', 0.02))
    route = validate_route(payload)
    assert prev['route_digest'] == route.digest
    for k, section in enumerate(payload['sections']):
        for key, chain in (('validated_left_px', section['left']),
                           ('validated_right_px', section['right']),
                           ('validated_route_px',
                            route.sections[k].centreline)):
            want = [[float(v) for v in track_map.world_to_pixel(pt)]
                    for pt in chain]
            assert np.allclose(prev[key][k], want, atol=1e-9)
    srv.op_approve({'approval_digest': prev['candidate_digest']})
    exp = srv.op_export({})
    assert exp['route_digest'] == prev['route_digest']
    assert exp['validated_left_px'] == prev['validated_left_px']
    assert exp['validated_route_px'] == prev['validated_route_px']


def test_edit_rerun_approve_revised_cycle(backend):
    """Continue drawing after approval: stale candidate refused, the
    revised geometry re-previews, re-approves and exports."""
    import os
    srv = backend
    _open_drawn(srv, strokes=(BENIGN_A, BENIGN_B))
    prev = srv.op_preview({})
    srv.op_approve({'approval_digest': prev['candidate_digest']})
    rev = srv.STATE['session']['revision']
    remaining = srv.STATE['session']['boundary_strokes_px'][1:]
    srv.op_update({'field': 'boundary_strokes_px', 'value': remaining})
    assert srv.STATE['session']['approval'] == 'none'
    assert srv.STATE['session']['revision'] == rev + 1
    assert srv.STATE['candidate_digest'] is None
    with pytest.raises(AnnotationError, match='no fresh preview'):
        srv.op_approve({'approval_digest': prev['candidate_digest']})
    revised = srv.op_preview({})
    assert revised['candidate_digest'] != prev['candidate_digest']
    srv.op_approve({'approval_digest': revised['candidate_digest']})
    exp = srv.op_export({})
    assert exp['route_digest'] == revised['route_digest']
    assert os.path.exists(os.path.join(srv.STATE['out_dir'],
                                       export_name(srv.STATE['map'])))


def test_suggest_and_validate_ops(backend):
    """Suggest fills the pencil (operator direction kept); validate
    locks the first passing thinning into the session identity."""
    from global_planner.annotation_core import _signed_area
    srv = backend
    _open_drawn(srv, strokes=(), route=False, map='baku')
    track_map = srv.STATE['map']
    outer, inner = extract_boundaries(track_map, [], 5)
    hint = midline_seed(outer, inner)
    if _signed_area(hint) < 0:
        hint = hint[::-1]
    srv.op_update({'field': 'route_px', 'value': hint})
    res = srv.op_suggest({})
    assert res['status'] == 'PASS'
    assert _signed_area(srv.STATE['session']['route_px']) > 0
    val = srv.op_validate({})
    assert val['status'] == 'PASS' and val['chain_dp_epsilon_m'] == 0.02
    assert srv.STATE['session']['approval'] == 'none'
    prev = srv.op_preview({})
    assert prev['candidate_digest'] == geometry_digest(
        srv.STATE['session'], srv.STATE['map'])
    srv.op_approve({'approval_digest': prev['candidate_digest']})
    assert srv.op_export({})['route_digest'] == prev['route_digest']


def test_select_region_server_flow(syn_backend):
    """Cut, fragmented report, select, candidate; bad clicks keep state."""
    srv = syn_backend
    srv.op_open({'map': 'syn'})
    upd = srv.op_update({'field': 'boundary_strokes_px', 'value': [SYN_CUT]})
    assert upd['session']['region']['free_regions'] == 2
    with pytest.raises(AnnotationError, match='NEEDS_REGION_SELECTION'):
        srv.op_extract({})
    res = srv.op_update({'field': 'retained_region_px', 'value': SYN_RING})
    assert res['status'] == 'PASS'
    region = res['session']['region']
    assert region['retained_region_px'] == SYN_RING
    assert len(region['excluded']) == 1
    assert region['excluded_png_data_url'].startswith(
        'data:image/png;base64,')
    assert srv.op_extract({})['status'] == 'CANDIDATE'
    for bad in ([100, 100], [30, 30], [-1, 0], [10.5, 3]):
        with pytest.raises(AnnotationError):
            srv.op_update({'field': 'retained_region_px', 'value': bad})
    assert srv.STATE['session']['retained_region_px'] == SYN_RING
    # Float-encoded clicks store canonical ints (digest survives reload).
    srv.op_update({'field': 'retained_region_px',
                   'value': [float(SYN_RING[0]), float(SYN_RING[1])]})
    assert srv.STATE['session']['retained_region_px'] == SYN_RING
    track_map = srv.STATE['map']
    digest = geometry_digest(srv.STATE['session'], track_map)
    path = Path(srv.STATE['out_dir']) / 'seed.json'
    save_session(srv.STATE['session'], path)
    assert geometry_digest(load_session(path, track_map),
                           track_map) == digest
    # Clearing drops the overlay but keeps the strokes; boundary edits
    # and undo clear the selection.
    cleared = srv.op_update({'field': 'retained_region_px', 'value': None})
    assert cleared['session']['region']['excluded'] == []
    assert srv.STATE['session']['boundary_strokes_px'] == [SYN_CUT]
    srv.op_update({'field': 'retained_region_px', 'value': SYN_RING})
    srv.op_update({'field': 'stroke_width_px', 'value': 9})
    assert srv.STATE['session']['retained_region_px'] is None
    srv.op_update({'field': 'retained_region_px', 'value': SYN_RING})
    srv.op_undo({})
    assert srv.STATE['session']['retained_region_px'] is None


def test_selection_approval_cycle_and_restart(backend, tmp_path):
    """Seeded preview/approve/export bind the seed; a saved preview
    authorizes approve/export after a simulated restart."""
    srv = backend
    _open_drawn(srv)
    track_map = srv.STATE['map']
    ys, xs = np.nonzero(track_map.image > 128)
    pixel = [int(xs[len(xs) // 2]), int(ys[len(ys) // 2])]
    srv.op_update({'field': 'retained_region_px', 'value': pixel})
    prev = srv.op_preview({})
    srv.op_approve({'approval_digest': prev['candidate_digest']})
    exp = srv.op_export({})
    assert exp['route_digest'] == prev['route_digest']
    assert (Path(srv.STATE['out_dir']) / export_name(track_map)).exists()
    srv.op_update({'field': 'retained_region_px', 'value': None})
    with pytest.raises(AnnotationError, match='not .operator-approved'):
        srv.op_export({})
    # Restart: in-memory state dropped, draft reopened from disk.
    _open_drawn(srv)
    prev = srv.op_preview({})
    assert srv.op_save({})['status'] == 'PASS'
    srv.STATE.update(map=None, session=None, extraction=None,
                     candidate_digest=None)
    reopened = srv.op_open({'map': 'test'})
    assert reopened['session']['candidate_digest'] == \
        prev['candidate_digest']
    assert srv.op_approve(
        {'approval_digest': prev['candidate_digest']})['status'] == 'PASS'
    assert srv.op_export({})['route_digest'] == prev['route_digest']


def test_preview_on_pinched_road_fails_closed(backend):
    """A stroke pinching the road to a slit grants no candidate."""
    srv = backend
    srv.op_open({'map': 'test'})
    srv.op_update({'field': 'stroke_width_px', 'value': 3})
    pinch = [[[109.0, 74.0], [73.12, 32.6]]]
    srv.op_update({'field': 'boundary_strokes_px', 'value': pinch})
    assert srv.op_extract({})['status'] == 'CANDIDATE'
    track_map = srv.STATE['map']
    outer, inner = extract_boundaries(track_map, pinch, 3)
    srv.op_update({'field': 'route_px', 'value': midline_seed(outer, inner)})
    with pytest.raises(AnnotationError, match='zero width'):
        srv.op_preview({})
    assert srv.STATE['candidate_digest'] is None
    with pytest.raises(AnnotationError, match='not .operator-approved'):
        srv.op_export({})


def test_browser_shows_loaded_snapshot_not_reread_file(syn_backend):
    """Replacing the PNG on disk after open does not change the view."""
    import base64
    srv = syn_backend
    srv.op_open({'map': 'syn'})
    track_map = srv.STATE['map']
    assert track_map.png_bytes == Path(track_map.png_path).read_bytes()
    Path(track_map.png_path).write_bytes(b'not the loaded png')
    view = srv.op_state({})['session']
    shown = base64.b64decode(view['map_png_data_url'].split(',', 1)[1])
    assert shown == track_map.png_bytes
    assert shown != b'not the loaded png'
    assert 'map_view_error' not in view


# Exact OPEN guide from the PR13 phase-2 investigation (R4b): every
# 2nd point of the suggested test-map guide, a 95.5% lap whose 86.27px
# endpoint gap previewed VALIDATED and reached operator-approved
# before the closure gate existed. Do not regenerate or round it.
R4B_OPEN_ROUTE = json.loads(
    '[[206.21333333333334, 39.460765787760415], [190.00666666666666, 38.72409912109375], [174.53666666666666, 37.250765787760415], [158.32999999999998, 35.77743245442708], [142.85999999999999, 35.77743245442708], [128.86333333333332, 36.51409912109375], [114.86666666666666, 38.72409912109375], [103.08, 43.88076578776042], [92.76666666666667, 51.98409912109375], [85.39999999999999, 61.56076578776042], [82.45333333333333, 74.08409912109374], [83.92666666666666, 86.60743245442708], [89.08333333333333, 98.39409912109375], [97.18666666666667, 107.97076578776041], [107.5, 115.33743245442707], [120.02333333333333, 120.49409912109374], [134.01999999999998, 124.17743245442708], [149.48999999999998, 126.38743245442707], [164.95999999999998, 128.59743245442706], [180.42999999999998, 130.07076578776042], [195.89999999999998, 131.54409912109375], [210.63333333333333, 133.01743245442708], [225.36666666666665, 135.96409912109374], [238.62666666666667, 138.9107657877604], [251.88666666666666, 142.59409912109373], [263.67333333333335, 147.7507657877604], [274.7233333333333, 153.64409912109375], [284.3, 161.74743245442707], [293.14, 171.32409912109375], [300.50666666666666, 182.37409912109374], [306.4, 196.3707657877604], [310.82, 211.8407657877604], [313.03, 228.04743245442708], [313.76666666666665, 244.9907657877604], [311.5566666666667, 260.4607657877604], [307.13666666666666, 275.19409912109376], [299.77, 287.71743245442707], [290.1933333333333, 297.2940991210937], [279.88, 303.9240991210937], [268.83, 306.13409912109375], [258.51666666666665, 303.9240991210937], [248.20333333333332, 297.2940991210937], [237.89, 289.1907657877604], [227.57666666666665, 278.8774324544271], [216.52666666666667, 268.56409912109376], [206.21333333333334, 258.25076578776043], [194.42666666666665, 249.4107657877604], [183.37666666666667, 241.30743245442707], [170.85333333333332, 234.67743245442708], [158.32999999999998, 229.5207657877604], [145.07, 227.3107657877604], [131.81, 226.57409912109375], [117.81333333333333, 228.78409912109373], [104.55333333333333, 232.46743245442707], [91.29333333333332, 239.09743245442706], [79.50666666666666, 247.20076578776042], [69.92999999999999, 257.51409912109375], [63.3, 269.3007657877604], [58.879999999999995, 283.29743245442705], [57.406666666666666, 297.2940991210937], [58.14333333333333, 312.02743245442707], [61.82666666666666, 326.7607657877604], [66.98333333333333, 340.0207657877604], [74.35, 352.5440991210937], [83.19, 362.85743245442706], [93.50333333333333, 370.9607657877604], [105.28999999999999, 377.5907657877604], [117.81333333333333, 383.4840991210937], [131.07333333333332, 387.16743245442706], [145.07, 390.8507657877604], [159.06666666666666, 393.79743245442705], [173.06333333333333, 395.2707657877604], [187.79666666666665, 397.4807657877604], [201.79333333333332, 398.21743245442707], [215.79, 398.95409912109375], [230.5233333333333, 399.6907657877604], [245.25666666666666, 398.95409912109375], [259.99, 398.95409912109375], [273.9866666666667, 397.4807657877604], [288.71999999999997, 396.0074324544271], [303.4533333333333, 393.79743245442705], [317.45, 390.1140991210937], [330.71, 385.69409912109376], [343.2333333333333, 379.8007657877604], [355.02, 372.4340991210937], [365.3333333333333, 363.59409912109373], [374.1733333333333, 353.2807657877604], [382.2766666666666, 341.4940991210937], [388.9066666666666, 328.2340991210937], [394.0633333333333, 314.23743245442705], [397.7466666666666, 300.2407657877604], [400.69333333333327, 286.2440991210937], [402.16666666666663, 272.2474324544271], [402.90333333333325, 258.25076578776043], [402.16666666666663, 244.25409912109373], [401.42999999999995, 230.25743245442706], [399.9566666666666, 216.26076578776042], [399.2199999999999, 202.26409912109375], [397.7466666666666, 187.5307657877604], [397.7466666666666, 172.79743245442708], [397.7466666666666, 157.32743245442708], [398.4833333333333, 141.1207657877604], [399.2199999999999, 125.6507657877604], [399.9566666666666, 110.18076578776041], [398.4833333333333, 95.44743245442707], [396.27333333333326, 82.18743245442708], [391.8533333333333, 70.40076578776042], [384.4866666666666, 60.08743245442708], [374.90999999999997, 52.72076578776041], [363.12333333333333, 46.09076578776042], [349.86333333333334, 41.670765787760416], [335.8666666666667, 38.72409912109375], [321.1333333333333, 36.51409912109375], [306.4, 35.77743245442708], [292.4033333333333, 35.77743245442708]]')


def _reversed_guide(route):
    """Mirror of the UI's reversedGuide(): keep start, reverse order,
    preserve the input's closure representation (a true involution)."""
    pts = [list(p) for p in route]
    if len(pts) < 3:
        return None
    closed = len(pts) > 1 and pts[0] == pts[-1]
    body = pts[:-1] if closed else pts
    if len(body) < 3:
        return None
    rev = [body[0]] + body[1:][::-1]
    if closed:
        rev.append(body[0])
    return rev


def test_reversed_guide_closure_classes():
    """Exact, near-closed and open guides: double reversal is the
    identity on the stored representation in every class."""
    exact = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]
    near = [[0, 0], [10, 0], [10, 10], [2, 2]]  # tail 2.8px from start
    open_ = [[0, 0], [10, 0], [10, 10], [0, 10]]
    for route in (exact, near, open_):
        rev = _reversed_guide(route)
        assert rev[0] == route[0]  # start preserved
        assert rev != route
        assert _reversed_guide(rev) == route
    assert _reversed_guide(exact)[-1] == exact[0]  # stays closed
    assert _reversed_guide(near)[-1] != near[0]  # stays open-class
    assert _reversed_guide([[0, 0], [1, 1]]) is None


def test_open_guide_cannot_be_approved(backend):
    """D2 regression (exact R4b array): an OPEN guide is refused at
    preview, validate, approve and export - on the server, and for a
    forged legacy approval at export time."""
    from global_planner.annotation_core import (
        GUIDE_CLOSE_TOLERANCE_PX, geometry_digest)
    srv = backend
    srv.op_open({'map': 'test'})
    srv.op_update({'field': 'route_px', 'value': R4B_OPEN_ROUTE})
    with pytest.raises(AnnotationError, match='OPEN'):
        srv.op_preview({})
    with pytest.raises(AnnotationError, match='OPEN'):
        srv.op_validate({})
    assert srv.STATE['candidate_digest'] is None
    assert srv.STATE['session']['approval'] == 'none'
    # Forged legacy state: approval fields consistent with the open
    # guide (as pre-gate code could have persisted). Export must
    # still refuse at candidate generation, not trust the digests.
    session = srv.STATE['session']
    session['approval'] = 'operator-approved'
    digest = geometry_digest(session, srv.STATE['map'])
    session['approval_digest'] = digest
    session['preview_digest'] = digest
    session['preview_route_digest'] = 'a' * 64
    session['approval_route_digest'] = 'a' * 64
    srv.STATE['candidate_digest'] = digest
    with pytest.raises(AnnotationError, match='OPEN'):
        srv.op_export({})
    # The gate constant is the one shared contract.
    assert GUIDE_CLOSE_TOLERANCE_PX == 8.0


def test_open_guide_persisted_approval_refused(backend, tmp_path):
    """Defect A (C3 A4): persisted preview/approval digests for the
    verbatim R4b OPEN guide must not yield approval on any path."""
    from global_planner.annotation_core import (
        draft_name, geometry_digest, load_session, save_session)
    srv = backend
    srv.op_open({'map': 'test'})
    srv.op_update({'field': 'route_px', 'value': R4B_OPEN_ROUTE})
    session = srv.STATE['session']
    track_map = srv.STATE['map']
    # Genuine persisted binding (geometry_digest is fix-stable).
    digest = geometry_digest(session, track_map)
    session['preview_digest'] = digest
    session['preview_route_digest'] = 'a' * 64
    srv.STATE['candidate_digest'] = digest
    with pytest.raises(AnnotationError, match='OPEN'):
        srv.op_approve({'approval_digest': digest})
    assert srv.STATE['session']['approval'] == 'none'
    # Legacy draft already marked approved: reopening revokes the
    # invalid approval, restores no candidacy, keeps the guide.
    session['approval'] = 'operator-approved'
    session['approval_digest'] = digest
    session['approval_route_digest'] = 'a' * 64
    draft = Path(srv.STATE['out_dir']) / draft_name(track_map)
    save_session(session, draft)
    srv.STATE.update(map=None, session=None, extraction=None,
                     candidate_digest=None)
    reopened = srv.op_open({'map': 'test'})
    assert reopened['session']['approval'] == 'none'
    assert srv.STATE['session']['route_px'] == R4B_OPEN_ROUTE
    assert srv.STATE['candidate_digest'] is None
    with pytest.raises(AnnotationError):
        srv.op_export({})
    assert list(Path(srv.STATE['out_dir']).glob('*_legal_route.json')) == []
    loaded = load_session(draft, track_map)
    assert loaded['approval'] == 'none'


def test_legacy_near_closed_reopens_canonical(backend):
    """Defect B (C3 A3): a legacy near-closed draft is canonicalized
    at load; double reversal then restores the stored array exactly."""
    from global_planner.annotation_core import draft_name, save_session
    srv = backend
    srv.op_open({'map': 'test'})
    srv.op_suggest({})
    closed = [list(p) for p in srv.STATE['session']['route_px']]
    legacy = [list(p) for p in closed]
    legacy[-1] = [closed[0][0] + 3.0, closed[0][1] + 4.0]  # 5px gap
    track_map = srv.STATE['map']
    draft = Path(srv.STATE['out_dir']) / draft_name(track_map)
    legacy_session = dict(srv.STATE['session'], route_px=legacy,
                          approval='operator-approved',
                          approval_digest='stale')
    save_session(legacy_session, draft)
    srv.STATE.update(map=None, session=None, extraction=None,
                     candidate_digest=None)
    srv.op_open({'map': 'test'})
    stored = srv.STATE['session']['route_px']
    assert stored[-1] == stored[0]  # exactly closed after load
    assert stored == legacy[:-1] + [list(legacy[0])]
    assert srv.STATE['session']['approval'] == 'none'  # snap revoked it
    rev = _reversed_guide(stored)
    srv.op_update({'field': 'route_px', 'value': rev})
    assert srv.op_preview({})['status'] == 'VALIDATED'
    srv.op_update({'field': 'route_px', 'value': _reversed_guide(rev)})
    assert srv.STATE['session']['route_px'] == stored


def test_guide_closure_boundaries(backend):
    """D1/D2 boundary cases: exact, near-closed (snapped at commit),
    tolerance-edge, and clearly open stored guides."""
    from global_planner.annotation_core import snapped_guide
    srv = backend
    srv.op_open({'map': 'test'})
    srv.op_suggest({})
    closed = [list(p) for p in srv.STATE['session']['route_px']]
    # Near-closed (5px gap): snapped to exact closure when stored.
    near = closed[:-1] + [[closed[0][0] + 3.0, closed[0][1] + 4.0]]
    srv.op_update({'field': 'route_px', 'value': near})
    stored = srv.STATE['session']['route_px']
    assert stored[-1] == stored[0] and stored != near
    assert srv.op_preview({})['status'] == 'VALIDATED'
    # Exactly at tolerance (8.0px): still snapped; beyond: stored
    # as-is (draft) but preview refuses.
    edge = closed[:-1] + [[closed[0][0] + 8.0, closed[0][1]]]
    srv.op_update({'field': 'route_px', 'value': edge})
    assert srv.STATE['session']['route_px'][-1] == closed[0]
    beyond = closed[:-1] + [[closed[0][0] + 8.5, closed[0][1]]]
    srv.op_update({'field': 'route_px', 'value': beyond})
    assert srv.STATE['session']['route_px'] == beyond
    with pytest.raises(AnnotationError, match='OPEN'):
        srv.op_preview({})
    # snapped_guide is pure: exact and open inputs pass through.
    assert snapped_guide(closed) == closed
    assert snapped_guide(R4B_OPEN_ROUTE) == R4B_OPEN_ROUTE


def test_reverse_direction_flow(backend):
    """Reverse Direction through the existing update path: the stored
    guide flips, approval is revoked, re-preview validates with a new
    digest, and reversing twice restores the original guide."""
    srv = backend
    _open_drawn(srv, strokes=(), route=False)
    srv.op_suggest({})
    original = [list(p) for p in srv.STATE['session']['route_px']]
    assert original[0] == original[-1]  # suggested guide is closed
    prev = srv.op_preview({})
    srv.op_approve({'approval_digest': prev['candidate_digest']})
    rev = _reversed_guide(original)
    assert rev[0] == original[0] and rev[-1] == original[-1]
    assert rev != original
    res = srv.op_update({'field': 'route_px', 'value': rev})
    assert res['status'] == 'PASS'
    assert srv.STATE['session']['route_px'] == rev
    assert srv.STATE['session']['approval'] == 'none'  # revoked
    with pytest.raises(AnnotationError, match='not .operator-approved'):
        srv.op_export({})
    rev_prev = srv.op_preview({})
    assert rev_prev['status'] == 'VALIDATED'
    assert rev_prev['route_digest'] != prev['route_digest']
    srv.op_approve({'approval_digest': rev_prev['candidate_digest']})
    assert srv.op_export({})['status'] == 'VALIDATED'
    # Double reversal recovers the original ordered guide exactly.
    srv.op_update({'field': 'route_px',
                   'value': _reversed_guide(rev)})
    assert srv.STATE['session']['route_px'] == original
    # Near-closed manual guide (tail within the 8px closure
    # tolerance, no exact closing point): the commit boundary snaps
    # it to exact closure, reversal validates, and double reversal
    # restores the stored (snapped) list byte-for-byte.
    manual = original[:-1] + [[original[0][0] + 2.0, original[0][1] + 2.0]]
    srv.op_update({'field': 'route_px', 'value': manual})
    stored = srv.STATE['session']['route_px']
    assert stored == manual[:-1] + [list(manual[0])]  # snapped at commit
    rev_manual = _reversed_guide(stored)
    srv.op_update({'field': 'route_px', 'value': rev_manual})
    assert srv.STATE['session']['route_px'] == rev_manual
    assert srv.op_preview({})['status'] == 'VALIDATED'
    srv.op_update({'field': 'route_px',
                   'value': _reversed_guide(rev_manual)})
    assert srv.STATE['session']['route_px'] == stored


def test_tool_state_synchronization():
    """Visible active tool == click behavior: bucket mode must not
    strip the pencil highlight (it is a one-click gesture over the
    still-active pencil), and any tool transition cancels the
    unfinished draft so it can never commit under the wrong tool."""
    html = UI_HTML.read_text(encoding='utf-8')
    tool_block = html.split("querySelectorAll('.tool')")[1] \
        .split("bucketBtn').onclick")[0]
    assert 'draft=[]' in tool_block  # switch/deselect cancels draft
    bucket_block = html.split("getElementById('bucketBtn').onclick")[1] \
        .split('clearRegionBtn')[0]
    assert 'draft=[]' in bucket_block  # entering bucket cancels draft
    assert "'.tool'" not in bucket_block  # pencil highlight untouched
    assert "classList.toggle('on',x.dataset.tool===tool)" in html
    # D4: the bucket button (not an SVG child) carries the active
    # class; clicks on the icon must not toggle state onto the icon.
    assert "e.currentTarget.classList.toggle('on',bucket)" in html
    assert "e.target.classList.toggle('on',bucket)" not in html


def test_html_contract():
    """Static frontend contract (Doc 23 UI-01..UI-07): grouped layout,
    preferred labels, help panel, direction arrows, Reverse Direction,
    no select-stroke mode, stage chip, digest-guarded approve."""
    html = UI_HTML.read_text(encoding='utf-8')
    for element in ('lay-map', 'lay-strokes', 'lay-extracted',
                    'lay-corridor', 'lay-center', 'lay-excluded',
                    'removeStroke', 'strokeList', 'sessinfo',
                    'bucketBtn', 'clearRegionBtn', 'reverseBtn'):
        assert f'id="{element}"' in html, f'missing #{element}'
    assert 'id="selectBtn"' not in html  # UI-06: mode removed
    assert 'nearestStroke' not in html and 'selecting' not in html
    for label in ('Annotation Tool', 'Boundary Pencil', 'Route Pencil',
                  'Select Drivable Region', 'Clear Region Selection',
                  'Suggest Route', 'Reverse Direction', 'Preview Route',
                  'Approve Route', 'Export Route', 'Save Draft',
                  'Fit Map', 'How to use', 'Controls &amp; safety',
                  'Stage: ${stageText()}'):
        assert label in html, f'missing label {label!r}'
    # Paint-bucket pictogram (inline SVG) + honest tooltip (UI-01).
    assert '<svg' in html and 'does not paint new free space' in html
    assert 'retained_region_px' in html
    assert 'drawImage(mapImg,v.ox' in html  # aspect fit, never stretched
    assert 'drawImage(img,0,0,cv.width,cv.height)' not in html
    assert 'outside the map (letterbox)' in html
    move = html.split("addEventListener('mousemove'")[1].split('});')[0]
    assert 'api(' not in move and 'fetch(' not in move  # hover is local
    assert 'Preview Route first, then Approve Route' in html
    assert 'refreshExtraction' in html
    assert 'imgDigest' in html  # cache keyed by image bytes, not name
    assert 'splice(-2)' not in html  # dblclick keeps its endpoint
    assert 'approval ${S.approval}' in html
    assert 'backend unreachable' in html
    # Candidate invalidation is centralized: one helper clears the
    # candidate token and validated overlays, used by every edit path.
    assert 'function invalidateCandidate()' in html
    assert html.count('invalidateCandidate()') >= 8
    assert html.count('candidate=null') == 2  # declaration + the helper
    # Direction: normalize nested section polylines before any length
    # test, place arrows by arc length, mark the start (UI-04).
    assert 'function flatLine(pts)' in html
    assert 'nextAt+=80' in html  # arc-length spacing, not point index
    assert 'function startMarker(pts,color,label)' in html
    # Reverse Direction reverses the stored guide via the update path.
    assert 'function reversedGuide(route)' in html
    assert "getElementById('reverseBtn').disabled=!closed" in html
    assert "e.code==='Escape'" in html  # cancel unfinished stroke
    # Inspect is the default, pencils toggle, clicks agree with the
    # highlighted tool (no hidden drawing mode).
    assert 'S=null, tool=null' in html
    assert 'Inspect: clicks do not draw' in html
    # Start markers: generated start is the lettered authority, the
    # guide start a hollow reference only.
    assert "startMarker(validated.route||[],'#4f4','S')" in html
    assert "startMarker(S.route_px||[],'#fd4','')" in html
    assert 'generated route start (authoritative' in html
    # Viewport: content-box mouse math (no border bias), one affine
    # view, cursor zoom, space/middle pan, fit reset.
    assert 'cv.clientLeft' in html and 'cv.clientWidth' in html
    assert "addEventListener('wheel'" in html
    assert 'fitScale()' in html and 'fitView()' in html
    assert "getElementById('fitBtn')" in html
    assert 'suppressClick' in html  # a pan never adds/finishes points
