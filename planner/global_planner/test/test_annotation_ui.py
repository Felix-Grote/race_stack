# Copyright 2026 ForzaETH
"""Operator-flow tests: server state machine behind the browser UI.

Pins no-stale-display on failure, exact preview layers, the
edit -> re-preview -> re-approve lifecycle, bucket selection through
the server, persisted previews across restarts, and the static HTML
contract the single-page frontend relies on.
"""
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


def test_html_contract():
    """Static frontend contract: layers, bucket, digest-guarded approve."""
    html = UI_HTML.read_text(encoding='utf-8')
    for element in ('lay-map', 'lay-strokes', 'lay-extracted',
                    'lay-corridor', 'lay-center', 'lay-excluded',
                    'selectBtn', 'removeStroke', 'strokeList', 'sessinfo',
                    'bucketBtn', 'clearRegionBtn'):
        assert f'id="{element}"' in html, f'missing #{element}'
    assert 'Keep legal track' in html
    assert 'retained_region_px' in html
    assert 'drawImage(mapImg,v.ox' in html  # aspect fit, never stretched
    assert 'drawImage(img,0,0,cv.width,cv.height)' not in html
    assert 'outside the map (letterbox)' in html
    move = html.split("addEventListener('mousemove'")[1].split('});')[0]
    assert 'api(' not in move and 'fetch(' not in move  # hover is local
    assert 'preview a candidate first' in html  # digest-guarded approve
    assert 'nearestStroke' in html and 'segDist' in html
    assert 'refreshExtraction' in html
    assert 'imgDigest' in html  # cache keyed by image bytes, not name
    assert 'splice(-2)' not in html  # dblclick keeps its endpoint
    assert 'approval ${S.approval}' in html
    assert 'backend unreachable' in html
    assert html.count('candidate=null') >= 4  # edits clear the candidate
