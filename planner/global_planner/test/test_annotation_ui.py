# Copyright 2026 ForzaETH
"""UI-focused tests for the annotation browser frontend + server contract.

Covers task section 4 (WP1): immediate cheap feedback, no stale display
on failure, exact final-corridor layers in the preview receipt, two
pencils + undo + remove-selected + continue/rerun/re-approve, aspect-fit
cursor mapping, and digest-bound preview/approve/export.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))

from global_planner.annotation_core import (  # noqa: E402
    AnnotationError, TrackMap, build_and_validate, export_name,
    extract_boundaries, geometry_digest)
from global_planner import annotation_server as server  # noqa: E402

MAPS = Path(__file__).parents[3] / 'stack_master' / 'maps'
UI_HTML = Path(__file__).parents[1] / 'global_planner' / 'annotation_ui.html'


@pytest.fixture
def backend(tmp_path):
    """Configured shared backend with STATE restored afterwards."""
    saved = dict(server.STATE)
    server.configure(str(MAPS), str(tmp_path / 'out'))
    server.STATE.update(map=None, session=None, extraction=None,
                        candidate_digest=None)
    yield server
    server.STATE.clear()
    server.STATE.update(saved)


def _midline_seed(outer, inner, count=120):
    step = max(1, len(outer) // count)
    seed = []
    for p in outer[::step]:
        j = int(np.argmin(np.linalg.norm(inner - p, axis=1)))
        seed.append(((p + inner[j]) / 2).tolist())
    return seed


KILLER = [[100.0, 0.0], [100.0, 442.0]]  # full-height cut: splits the annulus
BENIGN_A = [[211.0, 7.5], [239.0, 7.5]]
# Eastward extension of A; the pair keeps strict validation green.
# (Westward extensions from x=211 pinch the corridor and fail closed.)
BENIGN_B = [[239.0, 7.5], [245.0, 7.5]]


def _open_drawn(srv, strokes=(BENIGN_A,), route=True, map='test'):
    srv.op_open({'map': map})
    srv.op_update({'field': 'boundary_strokes_px',
                   'value': [list(s) for s in strokes]})
    if route:
        track_map = srv.STATE['map']
        outer, inner = extract_boundaries(
            track_map, srv.STATE['session']['boundary_strokes_px'], 5)
        srv.op_update({'field': 'route_px',
                       'value': _midline_seed(outer, inner)})
    return srv.STATE['map']


def test_extract_failure_clears_stale_display_retains_edits(backend):
    """A breaking stroke reports a diagnostic, keeps the strokes, and
    drops the previously shown overlay + candidate (no stale display)."""
    srv = backend
    _open_drawn(srv)
    ok = srv.op_extract({})
    assert ok['status'] == 'CANDIDATE'
    assert srv.STATE['extraction'] is not None
    # Break the topology with a track-cutting stroke.
    srv.op_update({'field': 'boundary_strokes_px',
                   'value': [BENIGN_A, KILLER]})
    with pytest.raises(AnnotationError, match='separate regions'):
        srv.op_extract({})
    # Strokes retained for repair; stale overlays gone.
    assert srv.STATE['session']['boundary_strokes_px'] == [BENIGN_A, KILLER]
    assert srv.STATE['extraction'] is None
    assert srv.STATE['candidate_digest'] is None
    # Repair (drop the killer) extracts again.
    srv.op_update({'field': 'boundary_strokes_px', 'value': [BENIGN_A]})
    assert srv.op_extract({})['status'] == 'CANDIDATE'


def test_preview_failure_clears_candidate_keeps_valid_extraction(backend):
    """A bad route clears the candidate but keeps the valid boundary
    overlay; approval of the stale candidate is refused."""
    srv = backend
    _open_drawn(srv)
    prev = srv.op_preview({})
    assert prev['status'] == 'VALIDATED'
    stale = prev['candidate_digest']
    srv.op_update({'field': 'route_px',
                   'value': [[10 + 5 * np.cos(a), 10 + 5 * np.sin(a)]
                             for a in np.linspace(0, 2 * np.pi, 24)]})
    with pytest.raises((AnnotationError, ValueError)):
        srv.op_preview({})
    assert srv.STATE['extraction'] is not None  # boundaries still valid
    assert srv.STATE['candidate_digest'] is None  # but nothing to approve
    with pytest.raises(AnnotationError, match='no fresh preview'):
        srv.op_approve({'approval_digest': stale})


def test_suggest_failure_clears_stale_overlay(backend):
    """A failed suggestion drops the old overlay instead of showing it."""
    srv = backend
    _open_drawn(srv, route=False)
    assert srv.op_extract({})['status'] == 'CANDIDATE'
    srv.op_update({'field': 'boundary_strokes_px',
                   'value': [BENIGN_A, KILLER]})
    with pytest.raises(AnnotationError, match='separate regions'):
        srv.op_suggest({})
    assert srv.STATE['extraction'] is None
    assert srv.STATE['candidate_digest'] is None
    assert srv.STATE['session']['boundary_strokes_px'] == [BENIGN_A, KILLER]


def test_receipt_carries_exact_final_corridor_layers(backend):
    """Preview exposes the manifest's own left/right walls + directed
    seeds per occurrence; export shows bit-identical layers."""
    srv = backend
    track_map = _open_drawn(srv)
    prev = srv.op_preview({})
    assert prev['status'] == 'VALIDATED'
    assert len(prev['validated_route_px']) == 4
    assert len(prev['validated_left_px']) == 4
    assert len(prev['validated_right_px']) == 4
    # Layers match the manifest payload exactly (pixel roundtrip).
    outer, inner = extract_boundaries(
        track_map, srv.STATE['session']['boundary_strokes_px'], 5)
    payload, _, _, _ = build_and_validate(
        track_map, outer, inner, srv.STATE['session']['route_px'],
        approval='operator-approved')
    for k, occ in enumerate(payload['occurrences']):
        for key in ('validated_route_px', 'validated_left_px',
                    'validated_right_px'):
            chain = {'validated_route_px': 'seed',
                     'validated_left_px': 'left',
                     'validated_right_px': 'right'}[key]
            want = [[float(v) for v in track_map.world_to_pixel(pt)]
                    for pt in occ[chain]]
            assert np.allclose(prev[key][k], want, atol=1e-9)
    # Left/right are real walls, not copies of the seed.
    for k in range(4):
        left = np.asarray(prev['validated_left_px'][k])
        center = np.asarray(prev['validated_route_px'][k])
        assert left.shape != center.shape or not np.allclose(left, center)
    # Export receipt is bit-identical to the previewed candidate.
    srv.op_approve({'approval_digest': prev['candidate_digest']})
    exp = srv.op_export({})
    assert exp['route_digest'] == prev['route_digest']
    assert exp['validated_left_px'] == prev['validated_left_px']
    assert exp['validated_right_px'] == prev['validated_right_px']
    assert exp['validated_route_px'] == prev['validated_route_px']


def test_remove_selected_stroke_is_an_edit(backend):
    """Dropping one stroke by index keeps the other, bumps the revision,
    revokes approval and clears the candidate."""
    srv = backend
    _open_drawn(srv, strokes=(BENIGN_A, BENIGN_B))
    prev = srv.op_preview({})
    srv.op_approve({'approval_digest': prev['candidate_digest']})
    assert srv.STATE['session']['approval'] == 'operator-approved'
    rev = srv.STATE['session']['revision']
    # Remove the first stroke (what the UI sends for "remove selected").
    remaining = [s for i, s in
                 enumerate(srv.STATE['session']['boundary_strokes_px'])
                 if i != 0]
    res = srv.op_update({'field': 'boundary_strokes_px', 'value': remaining})
    assert res['status'] == 'PASS'
    assert srv.STATE['session']['boundary_strokes_px'] == [BENIGN_B]
    assert srv.STATE['session']['revision'] == rev + 1
    assert srv.STATE['session']['approval'] == 'none'
    assert srv.STATE['candidate_digest'] is None
    assert srv.STATE['extraction'] is None


def test_continue_after_extraction_rerun_approve_revised(backend):
    """Extract -> keep drawing -> stale candidate refused -> re-preview
    -> approve revised -> export writes the revised geometry."""
    import os
    srv = backend
    _open_drawn(srv)
    assert srv.op_extract({})['status'] == 'CANDIDATE'
    first = srv.op_preview({})
    srv.op_approve({'approval_digest': first['candidate_digest']})
    # Continue editing after extraction/approval: strokes extend.
    srv.op_update({'field': 'boundary_strokes_px',
                   'value': [BENIGN_A, BENIGN_B]})
    assert srv.STATE['session']['approval'] == 'none'
    assert srv.STATE['extraction'] is None
    with pytest.raises(AnnotationError, match='no fresh preview'):
        srv.op_approve({'approval_digest': first['candidate_digest']})
    # Rerun the loop on the revised geometry.
    assert srv.op_extract({})['status'] == 'CANDIDATE'
    revised = srv.op_preview({})
    assert revised['candidate_digest'] != first['candidate_digest']
    assert revised['candidate_digest'] == geometry_digest(
        srv.STATE['session'], srv.STATE['map'])
    srv.op_approve({'approval_digest': revised['candidate_digest']})
    exp = srv.op_export({})
    assert exp['status'] == 'VALIDATED'
    assert exp['route_digest'] == revised['route_digest']
    assert os.path.exists(os.path.join(srv.STATE['out_dir'],
                                       export_name(srv.STATE['map'])))


def test_html_layers_toggles_aspect_digest_contract():
    """The single-page UI (no frameworks) exposes layer toggles, an
    aspect-preserving fit with letterbox-aware cursor mapping, a local
    hover preview with no server roundtrip, and a digest-guarded
    approve path."""
    html = UI_HTML.read_text(encoding='utf-8')
    for element in ('lay-map', 'lay-strokes', 'lay-extracted',
                    'lay-corridor', 'lay-center', 'selectBtn',
                    'removeStroke', 'strokeList', 'sessinfo'):
        assert f'id="{element}"' in html, f'missing #{element}'
    assert 'no frameworks' in html.lower() or 'no frameworks' in html
    # Aspect fit: map drawn into a centered rect, never stretched full
    # canvas; clicks outside the map rect are rejected.
    assert 'drawImage(mapImg,v.ox' in html
    assert 'drawImage(img,0,0,cv.width,cv.height)' not in html
    assert 'outside the map (letterbox)' in html
    # Hover preview is canvas-local: the mousemove handler issues no fetch.
    move = html.split("addEventListener('mousemove'")[1].split('});')[0]
    assert 'api(' not in move
    assert 'fetch(' not in move
    # Approve is digest-bound client-side too: no candidate, no request.
    assert 'preview a candidate first' in html
    # Select/remove affordance for individual strokes.
    assert 'nearestStroke' in html
    # Every edit path funnels through applied()/fail() which clear the
    # local candidate and validated overlays.
    assert html.count('candidate=null') >= 4


def test_html_shows_digest_and_approval_state():
    """Session line exposes map/revision/approval/candidate for the
    operator to bind what they approve to what they saw."""
    html = UI_HTML.read_text(encoding='utf-8')
    assert 'approval ${S.approval}' in html
    assert 'candidate ${(S.candidate_digest' in html
    assert 'rev ${S.revision}' in html


def test_suggest_keeps_suggest_seed_on_test(backend):
    """Ordinary flow unchanged where suggest validates: first method wins,
    route closed, preview accepts."""
    srv = backend
    _open_drawn(srv, route=False)
    res = srv.op_suggest({})
    assert res['status'] == 'PASS'
    assert 'suggest seed' in res['message']
    route = srv.STATE['session']['route_px']
    assert route[0] == route[-1]
    assert srv.op_preview({})['status'] == 'VALIDATED'


def test_suggest_falls_back_to_ridge_on_baku(backend):
    """Same ordinary flow on baku without map-specific settings: suggest
    fails strict, ridge wins, preview accepts the fallback seed."""
    srv = backend
    _open_drawn(srv, strokes=(), route=False, map='baku')
    res = srv.op_suggest({})
    assert res['status'] == 'PASS'
    assert 'ridge seed' in res['message']
    assert srv.op_preview({})['status'] == 'VALIDATED'


def test_source_map_bytes_untouched_by_ui_ops(backend, tmp_path):
    """UI-covered ops (update/undo/extract/suggest/preview) never write
    the source map: no free-space brush, maps immutable."""
    srv = backend
    _open_drawn(srv)
    before = Path(srv.STATE['map'].png_path).read_bytes()
    srv.op_extract({})
    srv.op_suggest({})
    srv.op_preview({})
    srv.op_undo({})
    assert Path(srv.STATE['map'].png_path).read_bytes() == before
    assert json.dumps(srv.STATE['session'])  # session stays JSON-safe
