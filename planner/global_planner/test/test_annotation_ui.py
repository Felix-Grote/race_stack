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


def _has_pinned_kernel():
    """True when the exact pinned optimizer stack is importable.

    Mirrors the headless/ROS split: full-validation tests only run where
    the optimizer kernel exists, and skip by design elsewhere.
    """
    try:
        from global_planner.iqp_route_adapter import _helpers
        _helpers()
        return True
    except Exception:
        return False


needs_pinned = pytest.mark.skipif(
    not _has_pinned_kernel(), reason='requires pinned optimizer stack')


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


def test_html_endpoint_and_cache_contract():
    """Double-click keeps its endpoint (no blind splice of two points);
    the cached map image is keyed by actual image bytes (digest of the
    data URL), not just name and dimensions; stroke selection measures
    point-to-segment distance; boundary edits refresh extraction."""
    html = UI_HTML.read_text(encoding='utf-8')
    # A dblclick fires two clicks for its endpoint: collapse only that
    # double-fired tail instead of dropping two operator points.
    assert 'splice(-2)' not in html
    assert 'double-fired' in html
    # Same name+size with different pixels must not reuse the cached img.
    assert 'imgDigest' in html
    assert 'hashStr' in html
    assert 'map_png_data_url' in html
    # Nearest segment, not nearest stored vertex.
    assert 'segDist' in html
    # Completed boundary edits recompute extraction without manual steps.
    assert 'refreshExtraction' in html
    assert "getElementById('extract').onclick=refreshExtraction" in html


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


def test_suggest_rejects_direction_conflict_on_baku(backend):
    """A ridge fallback that would reverse the drawn travel direction is
    refused with a reason instead of silently flipping the route."""
    from global_planner.annotation_core import _signed_area
    srv = backend
    _open_drawn(srv, strokes=(), route=False, map='baku')
    track_map = srv.STATE['map']
    outer, inner = extract_boundaries(track_map, [], 5)
    seed = _midline_seed(outer, inner)
    if _signed_area(seed) < 0:
        seed = seed[::-1]
    assert _signed_area(seed) > 0  # CCW hint; baku ridge runs opposite
    srv.op_update({'field': 'route_px', 'value': seed})
    with pytest.raises(AnnotationError, match='direction'):
        srv.op_suggest({})


@needs_pinned
def test_validate_selects_first_full_pass_on_test(backend):
    """Explicit offline validation on the ordinary flow: test wins at the
    default thinning, records it in the session identity, and the locked
    configuration previews, approves and exports."""
    srv = backend
    _open_drawn(srv)
    assert 'suggest seed' in srv.op_suggest({})['message']
    res = srv.op_validate({})
    assert res['status'] == 'PASS'
    assert res['chain_dp_epsilon_m'] == 0.02
    assert res['artifact_H']
    assert srv.STATE['session']['chain_dp_epsilon_m'] == 0.02
    assert srv.STATE['session']['approval'] == 'none'
    assert srv.STATE['candidate_digest'] is None
    prev = srv.op_preview({})
    assert prev['status'] == 'VALIDATED'
    assert prev['candidate_digest'] == geometry_digest(
        srv.STATE['session'], srv.STATE['map'])
    srv.op_approve({'approval_digest': prev['candidate_digest']})
    exp = srv.op_export({})
    assert exp['status'] == 'VALIDATED'
    assert exp['route_digest'] == prev['route_digest']


@needs_pinned
def test_validate_unlocks_baku_full_pass(backend):
    """Baku ordinary flow needs the envelope-edge thinning: the default
    fails the full gate, 0.03 passes, and the locked export matches the
    documented reference hash."""
    srv = backend
    _open_drawn(srv, strokes=(), route=False, map='baku')
    assert 'ridge seed' in srv.op_suggest({})['message']
    res = srv.op_validate({})
    assert res['status'] == 'PASS'
    assert res['chain_dp_epsilon_m'] == 0.03
    assert [a[:7] for a in res['attempts']] == ['eps 0.0']
    prev = srv.op_preview({})
    assert prev['status'] == 'VALIDATED'
    srv.op_approve({'approval_digest': prev['candidate_digest']})
    exp = srv.op_export({})
    assert exp['status'] == 'VALIDATED'
    assert exp['route_digest'] == (
        '82f9b533ce50ad3e7b974187f19e9c40d944ca8b87115d21eb34e5fb41ac03f0')


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


SYN_CUT = [[20.0, 60.0], [60.0, 20.0]]  # diagonal across the outer corner
SYN_RING = [100, 170]  # free pixel on the annulus bottom arm


@pytest.fixture
def syn_backend(tmp_path):
    """Backend serving a synthetic square annulus for cut tests."""
    import cv2
    maps = tmp_path / 'maps'
    maps.mkdir()
    img = np.zeros((200, 200), np.uint8)
    cv2.rectangle(img, (20, 20), (180, 180), 255, -1)
    cv2.rectangle(img, (70, 70), (130, 130), 0, -1)
    cv2.imwrite(str(maps / 'syn.png'), img)
    (maps / 'syn.yaml').write_text(
        'image: syn.png\nresolution: 0.05\norigin: [0, 0, 0]\nnegate: 0\n'
        'occupied_thresh: 0.65\nfree_thresh: 0.196\n')
    saved = dict(server.STATE)
    server.configure(str(maps), str(tmp_path / 'out'))
    server.STATE.update(map=None, session=None, extraction=None,
                        candidate_digest=None)
    yield server
    server.STATE.clear()
    server.STATE.update(saved)


def test_select_region_server_flow(syn_backend):
    """Cut, fragmented report, select, candidate, bad clicks keep state."""
    srv = syn_backend
    srv.op_open({'map': 'syn'})
    upd = srv.op_update({'field': 'boundary_strokes_px', 'value': [SYN_CUT]})
    assert upd['session']['region']['free_regions'] == 2
    with pytest.raises(AnnotationError, match='NEEDS_REGION_SELECTION'):
        srv.op_extract({})
    rev = srv.STATE['session']['revision']
    res = srv.op_update({'field': 'retained_region_px', 'value': SYN_RING})
    assert res['status'] == 'PASS'
    assert srv.STATE['session']['revision'] == rev + 1
    assert srv.STATE['session']['approval'] == 'none'
    region = res['session']['region']
    assert region['retained_region_px'] == SYN_RING
    assert len(region['excluded']) == 1
    assert region['excluded_png_data_url'].startswith('data:image/png;base64,')
    assert srv.op_extract({})['status'] == 'CANDIDATE'
    # Occupied, pocket, out-of-bounds and non-integer clicks are
    # rejected without overwriting the stored selection.
    for bad in ([100, 100], [30, 30], [-1, 0], [10.5, 3]):
        with pytest.raises(AnnotationError):
            srv.op_update({'field': 'retained_region_px', 'value': bad})
    assert srv.STATE['session']['retained_region_px'] == SYN_RING
    # Clearing drops the overlay but keeps the strokes.
    cleared = srv.op_update({'field': 'retained_region_px', 'value': None})
    assert cleared['session']['region']['excluded'] == []
    assert srv.STATE['session']['boundary_strokes_px'] == [SYN_CUT]
    with pytest.raises(AnnotationError, match='NEEDS_REGION_SELECTION'):
        srv.op_extract({})


def test_boundary_edit_clears_selection(syn_backend):
    """Undo and width changes drop the seed; the mask is recomputed."""
    srv = syn_backend
    srv.op_open({'map': 'syn'})
    srv.op_update({'field': 'boundary_strokes_px', 'value': [SYN_CUT]})
    srv.op_update({'field': 'retained_region_px', 'value': SYN_RING})
    srv.op_undo({})
    assert srv.STATE['session']['retained_region_px'] is None
    srv.op_update({'field': 'boundary_strokes_px', 'value': [SYN_CUT]})
    srv.op_update({'field': 'retained_region_px', 'value': SYN_RING})
    srv.op_update({'field': 'stroke_width_px', 'value': 9})
    assert srv.STATE['session']['retained_region_px'] is None


def test_selection_approval_cycle_binds_seed(backend):
    """Preview/approve/export run on the retained component, and a
    selection change revokes the approval bound to the old geometry."""
    srv = backend
    _open_drawn(srv)
    track_map = srv.STATE['map']
    free = track_map.image > 128
    ys, xs = np.nonzero(free)
    pixel = [int(xs[len(xs) // 2]), int(ys[len(ys) // 2])]
    srv.op_update({'field': 'retained_region_px', 'value': pixel})
    prev = srv.op_preview({})
    assert prev['status'] == 'VALIDATED'
    srv.op_approve({'approval_digest': prev['candidate_digest']})
    exp = srv.op_export({})
    assert exp['status'] == 'VALIDATED'
    assert exp['route_digest'] == prev['route_digest']
    assert (Path(srv.STATE['out_dir'])
            / export_name(track_map)).exists()
    # The retained component is the whole track here, so seeded
    # extraction matches the unselected baseline exactly (same mask
    # means same strict walls; the corridor ribbons are inset by
    # design and must not be compared to the raw boundary here).
    strokes = srv.STATE['session']['boundary_strokes_px']
    base_outer, base_inner = extract_boundaries(track_map, strokes, 5)
    sel_outer, sel_inner = extract_boundaries(track_map, strokes, 5, pixel)
    assert np.array_equal(sel_outer, base_outer)
    assert np.array_equal(sel_inner, base_inner)
    # Clearing the selection revokes the approval bound to it.
    srv.op_update({'field': 'retained_region_px', 'value': None})
    with pytest.raises(AnnotationError, match='no fresh preview'):
        srv.op_approve({'approval_digest': prev['candidate_digest']})
    with pytest.raises(AnnotationError, match='not .operator-approved'):
        srv.op_export({})


# Diagonal across the top-left corner pocket of the test map.
TEST_CUT = [[[130.16427660290194, 3.890151624735724],
             [48.83572339709805, 100.10984837526428]]]
TEST_CUT_SEED = [125, 230]


def test_preview_on_kinked_cut_fails_closed(backend):
    """A cut whose sharp corner folds the corridor charts grants no
    candidate: extraction selects the component, preview reports the
    failure instead of passing silently."""
    srv = backend
    srv.op_open({'map': 'test'})
    srv.op_update({'field': 'boundary_strokes_px', 'value': TEST_CUT})
    srv.op_update({'field': 'retained_region_px', 'value': TEST_CUT_SEED})
    assert srv.op_extract({})['status'] == 'CANDIDATE'
    track_map = srv.STATE['map']
    outer, inner = extract_boundaries(track_map, TEST_CUT, 5, TEST_CUT_SEED)
    srv.op_update({'field': 'route_px', 'value': _midline_seed(outer, inner)})
    with pytest.raises(AnnotationError, match='smoothing level'):
        srv.op_preview({})
    assert srv.STATE['candidate_digest'] is None
    with pytest.raises(AnnotationError, match='no fresh preview'):
        srv.op_approve({'approval_digest': 'anything'})
    with pytest.raises(AnnotationError, match='not .operator-approved'):
        srv.op_export({})


def _dev(chain, ref):
    """Max deviation of a pixel chain from a reference chain (px)."""
    import numpy as _np
    chain, ref = _np.asarray(chain, float), _np.asarray(ref, float)
    return float(_np.linalg.norm(
        chain[:, None, :] - ref[None, :, :], axis=2).min(axis=1).max())


def test_html_bucket_control_contract():
    """Bucket button, clear control, excluded layer and overlay wiring."""
    html = UI_HTML.read_text(encoding='utf-8')
    for element in ('bucketBtn', 'clearRegionBtn', 'lay-excluded'):
        assert f'id="{element}"' in html, f'missing #{element}'
    assert 'Keep legal track' in html
    assert 'retained_region_px' in html
    assert 'drawImage(exclImg,v.ox' in html
    assert 'excluded pockets' in html
