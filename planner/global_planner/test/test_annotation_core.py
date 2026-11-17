# Copyright 2026 ForzaETH
"""Deployment tests: map loading, extraction, approval, transports.

Kept deliberately small: every test pins an operational invariant
(real maps load and validate, gray cells never become road, topology
fails closed, approval binds the previewed geometry, drafts recover).
Geometry exactness has its own oracle suite in
``test_annotation_legality.py``; manifest contracts in
``test_annotation_route.py``.
"""
import json
from pathlib import Path

import numpy as np
import pytest

from conftest import MAPS, annulus_image, midline_seed, write_map
from global_planner.annotation_core import (  # noqa: E402
    AnnotationError, TrackMap, build_candidate, build_route, check_payload,
    check_session_map, effective_free_mask, export_name,
    extract_boundaries, free_components, geometry_digest, load_session,
    new_session, patched_free_mask, require_approved, save_session)
from global_planner.route.manifest import load_route  # noqa: E402


def _build(track_map, outer, inner, route_px, strokes=(), width=5,
           seed=None, **kwargs):
    legal = effective_free_mask(track_map, strokes, width, seed)
    payload, info = build_route(track_map, outer, inner, route_px,
                                legal_mask=legal, **kwargs)
    route, receipt = check_payload(payload, track_map, legal)
    return payload, route, receipt, info


@pytest.mark.parametrize('name', ['test/test', 'baku/baku'])
def test_real_map_end_to_end_validates(name):
    """Extracted loops + directed guide -> route checks PASS."""
    track_map = TrackMap(MAPS / f'{name}.yaml')
    outer, inner = extract_boundaries(track_map)
    payload, route, receipt, info = _build(
        track_map, outer, inner, midline_seed(outer, inner))
    assert len(route.sections) == 4
    assert receipt['stages']['samples'] > 100
    assert payload['map']['sha256'] == track_map.sha256
    assert receipt['stages']['vector_legal']['annexed_m2'] == 0.0


@pytest.mark.parametrize('name,seed', [
    ('GLC_smile_small', None), ('glc_ot_ez', [54, 383]),
    ('hangar_1905_v0', None)])
def test_grayscale_forzaeth_maps_validate(name, seed):
    """Existing grayscale maps load conservatively and validate.

    Gray (uncertain) cells are never free; the retained component is
    the operator's bucket choice (glc_ot_ez carries a 4-px speck, so
    it needs the seed, exactly like a corner-cut pocket).
    """
    track_map = TrackMap(MAPS / f'{name}/{name}.yaml')
    gray = (track_map.image > 0) & (track_map.image < 255)
    assert gray.any()  # the fixture really is grayscale
    prob = (255.0 - track_map.image.astype(float)) / 255.0
    mask = patched_free_mask(track_map, [])
    assert (mask[prob >= track_map.free_thresh] == 0).all()
    assert (mask[prob < track_map.free_thresh] == 255).all()
    outer, inner = extract_boundaries(track_map, [], 5, seed)
    session = new_session(track_map)
    session['retained_region_px'] = seed
    session['route_px'] = midline_seed(outer, inner)
    _, route, receipt, _ = build_candidate(track_map, session)
    assert len(route.sections) == 4
    assert receipt['stages']['vector_legal']['annexed_m2'] == 0.0


def test_gray_cells_stay_occupied_and_negate_inverts(tmp_path):
    """A gray cell in the road is occupied; negate:1 swaps the reading."""
    img = annulus_image()
    img[170, 100] = 128  # uncertain cell inside the road
    gray_map = write_map(tmp_path, img, name='gray.png')
    assert patched_free_mask(gray_map, [])[170, 100] == 0
    src = TrackMap(MAPS / 'test/test.yaml')
    outer, inner = extract_boundaries(src, [])
    inv_map = write_map(tmp_path, 255 - src.image, name='inv.png',
                        origin=(-8.4, -5.35, 0.0), negate=1)
    outer_n, inner_n = extract_boundaries(inv_map, [])
    assert len(outer) == len(outer_n) and len(inner) == len(inner_n)


def test_map_yaml_validation(tmp_path):
    """PyYAML parsing: real layouts pass, bad interpretation fails clear."""
    import shutil
    shutil.copy(MAPS / 'test/test.png', tmp_path / 'm.png')
    good = ('image: "m.png"  # the test map\nresolution: 0.05\n'
            'origin:\n- -8.4\n- -5.35\n- 0\nnegate: 0\n'
            'ot_interpolator:\n  ros__parameters:\n    n_sectors: 3\n')
    (tmp_path / 'm.yaml').write_text(good, encoding='utf-8')
    track_map = TrackMap(tmp_path / 'm.yaml')
    assert track_map.png_path.name == 'm.png'
    assert track_map.origin == (-8.4, -5.35)
    for bad, match in (
            ('image: m.png\nresolution: 0\norigin: [0, 0, 0]\n',
             'resolution'),
            ('image: m.png\nresolution: x\norigin: [0, 0, 0]\n',
             'resolution'),
            ('image: m.png\nresolution: 0.05\norigin: [0, nan, 0]\n',
             'origin'),
            ('image: m.png\nresolution: 0.05\norigin: [0, 0]\n', 'origin'),
            ('image: m.png\nresolution: 0.05\norigin: [0, 0, 0]\n'
             'negate: 2\n', 'negate'),
            ('image: m.png\nresolution: 0.05\norigin: [0, 0, 0]\n'
             'mode: raw\n', 'mode.*trinary'),
            ('image: m.png\nresolution: 0.05\norigin: [0, 0, 0]\n'
             'mode: scale\n', 'mode.*trinary'),
            ('image: m.png\nresolution: 0.05\norigin: [0, 0, 0]\n'
             'free_thresh: 0.9\noccupied_thresh: 0.65\n', 'thresholds'),
            ('resolution: 0.05\norigin: [0, 0, 0]\n', 'image'),
            ('image: [unclosed\n', 'not valid YAML')):
        (tmp_path / 'm.yaml').write_text(bad, encoding='utf-8')
        with pytest.raises(AnnotationError, match=match):
            TrackMap(tmp_path / 'm.yaml')
    # Explicit trinary is accepted, like no mode at all (good case above).
    (tmp_path / 'm.yaml').write_text(
        good + 'mode: trinary\n', encoding='utf-8')
    assert TrackMap(tmp_path / 'm.yaml').png_path.name == 'm.png'
    # Nonzero yaw is unsupported, never approximated.
    (tmp_path / 'm.yaml').write_text(
        'image: m.png\nresolution: 0.05\norigin: [0, 0, 0.5]\n',
        encoding='utf-8')
    with pytest.raises(AnnotationError, match='yaw'):
        TrackMap(tmp_path / 'm.yaml')


def test_pixel_world_roundtrip():
    """Pixel<->world is an exact inverse pair (flip convention)."""
    track_map = TrackMap(MAPS / 'test/test.yaml')
    for uv in [(0, 0), (100, 50), (435, 441), (217, 220)]:
        back = track_map.world_to_pixel(track_map.pixel_to_world(uv))
        assert back == pytest.approx(uv, abs=1e-9)


def test_session_roundtrip_and_map_identity(tmp_path):
    """Save/reopen works; reinterpreted maps and old versions rejected."""
    track_map = TrackMap(MAPS / 'test/test.yaml')
    session = new_session(track_map)
    session['route_px'] = [[1, 2], [3, 4], [5, 6]]
    path = tmp_path / 'draft.json'
    save_session(session, path)
    assert load_session(path, track_map)['route_px'] == session['route_px']
    check_session_map(session, track_map)
    other = TrackMap(MAPS / 'baku/baku.yaml')
    with pytest.raises(AnnotationError, match='identity mismatch'):
        load_session(path, other)
    for key, bad in (('resolution', track_map.resolution + 0.01),
                     ('origin', [0.0, 0.0]), ('negate', 1),
                     ('free_thresh', 0.5)):
        with pytest.raises(AnnotationError, match='identity mismatch'):
            check_session_map(dict(session, **{key: bad}), track_map)
    stale = dict(session, version=3)
    path.write_text(json.dumps(stale), encoding='utf-8')
    with pytest.raises(AnnotationError, match='unsupported session version'):
        load_session(path, track_map)
    path.write_text('[1, 2]', encoding='utf-8')
    with pytest.raises(AnnotationError, match='cannot load session'):
        load_session(path, track_map)


def test_free_thresh_changes_map_namespace(tmp_path):
    """Same PNG under different free_thresh gets distinct file slots."""
    import cv2
    from global_planner.annotation_core import draft_name, export_name, \
        map_namespace
    cv2.imwrite(str(tmp_path / 'm.png'), annulus_image())
    base = ('image: m.png\nresolution: 0.05\norigin: [0, 0, 0]\n'
            'negate: 0\noccupied_thresh: 0.65\nfree_thresh: %s\n')
    (tmp_path / 'a.yaml').write_text(base % 0.196, encoding='utf-8')
    (tmp_path / 'b.yaml').write_text(base % 0.5, encoding='utf-8')
    low = TrackMap(tmp_path / 'a.yaml')
    high = TrackMap(tmp_path / 'b.yaml')
    assert low.sha256 == high.sha256 and low.png_path == high.png_path
    assert map_namespace(low) != map_namespace(high)
    assert draft_name(low) != draft_name(high)
    assert export_name(low) != export_name(high)


def test_source_map_never_modified():
    """Extraction/patching work on copies; the PNG bytes are untouched."""
    track_map = TrackMap(MAPS / 'test/test.yaml')
    before = Path(track_map.png_path).read_bytes()
    extract_boundaries(track_map, [[[0, 0], [50, 50]]], stroke_width_px=5)
    patched_free_mask(track_map, [[[0, 0], [50, 50]]])
    assert Path(track_map.png_path).read_bytes() == before
    assert track_map.sha256 == __import__('hashlib').sha256(before).hexdigest()
    assert json.dumps(new_session(track_map))  # session is JSON-safe


def test_failed_atomic_save_keeps_old_draft(tmp_path, monkeypatch):
    """A failed draft save keeps the old draft and leaves no tmp file."""
    import os
    target = tmp_path / 'draft.json'
    save_session({'a': 1}, target)

    def _boom(*args):
        raise OSError('simulated replace failure')
    monkeypatch.setattr(os, 'replace', _boom)
    with pytest.raises(OSError, match='simulated replace failure'):
        save_session({'a': 2}, target)
    assert json.loads(target.read_text(encoding='utf-8')) == {'a': 1}
    assert list(tmp_path.glob('draft.json.tmp*')) == []


def _maxmin(a, b):
    """Hausdorff-style max of min distances between two polylines (px)."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    return float(np.linalg.norm(
        a[:, None, :] - b[None, :, :], axis=2).min(axis=1).max())


def test_boundary_stroke_repairs_outer_gap(tmp_path):
    """A pocket broken in the outer wall detours visibly; a tangent
    boundary stroke overlapping intact wall restores the loops."""
    src = TrackMap(MAPS / 'test/test.yaml')
    img = src.image.copy()
    img[5:11, 219:232] = 255  # pocket across the outer wall
    gap_map = write_map(tmp_path, img, name='gap.png',
                        origin=(-8.4, -5.35, 0.0))
    outer0, inner0 = extract_boundaries(src, [])
    outer, inner = extract_boundaries(gap_map, [])
    assert _maxmin(outer, outer0) > 2.0  # detour is real, not silent
    assert _maxmin(inner, inner0) < 1.0  # far side untouched
    stroke = [[[211.0, 7.5], [239.0, 7.5]]]
    fixed_outer, fixed_inner = extract_boundaries(
        gap_map, stroke, stroke_width_px=5)
    assert _maxmin(fixed_outer, outer0) < 8.0
    assert _maxmin(fixed_inner, inner0) < 2.0


def test_unsupported_topology_fails_closed(tmp_path):
    """Speck, infield chord and frame contact are rejected, not guessed."""
    src = TrackMap(MAPS / 'test/test.yaml')
    import cv2
    img = src.image.copy()
    cv2.circle(img, (248, 226), 5, 255, -1)  # speck inside the infield
    speck = write_map(tmp_path, img, name='speck.png',
                      origin=(-8.4, -5.35, 0.0))
    with pytest.raises(AnnotationError, match='separate regions'):
        extract_boundaries(speck, [])
    img = src.image.copy()
    img[223:230, 180:320] = 255  # chord severing the infield
    chord = write_map(tmp_path, img, name='chord.png',
                      origin=(-8.4, -5.35, 0.0))
    with pytest.raises(AnnotationError, match='inner boundary|regions'):
        extract_boundaries(chord, [])
    img = annulus_image()
    cv2.circle(img, (100, 100), 60, 255, -1)
    cv2.circle(img, (100, 100), 25, 0, -1)
    img[0:45, 100] = 255  # channel from the track to the frame
    frame = write_map(tmp_path, img, name='frame.png')
    with pytest.raises(AnnotationError, match='frame'):
        extract_boundaries(frame, [])


TL_CUT = [[20.0, 60.0], [60.0, 20.0]]  # diagonal across the outer corner
RING_PX = [100, 170]  # free pixel on the annulus bottom arm


def test_retained_region_selection(tmp_path):
    """Cut fragments refuse without a seed; the seed keeps one region."""
    track_map = write_map(tmp_path, annulus_image(), name='annulus.png')
    base_outer, base_inner = extract_boundaries(track_map)
    regions = free_components(patched_free_mask(track_map, [TL_CUT]))
    assert len(regions) == 2
    with pytest.raises(AnnotationError, match='NEEDS_REGION_SELECTION'):
        extract_boundaries(track_map, [TL_CUT])
    legal = effective_free_mask(track_map, [TL_CUT], 5, RING_PX)
    free = patched_free_mask(track_map, [TL_CUT])
    pocket = int(((free > 0) & (legal == 0)).sum())
    assert pocket == min(r['area_px'] for r in regions)
    assert int((legal > 0).sum()) + pocket == int((free > 0).sum())
    outer, inner = extract_boundaries(track_map, [TL_CUT], 5, RING_PX)
    assert _maxmin(inner, base_inner) < 1.0  # far boundary untouched
    assert _maxmin(outer, base_outer) > 2.0  # new diagonal is followed


def test_retained_region_seed_validation(tmp_path):
    """Bad seeds fail closed; the seed binds approval and persists."""
    track_map = write_map(tmp_path, annulus_image(), name='annulus.png')
    for bad, match in (([100, 100], 'occupied'), ([30, 30], 'boundary'),
                       ([-1, 0], 'outside the map'), ([10.5, 3], 'integer'),
                       ('x', 'null or'), ([1, 2, 3], 'null or'),
                       ([float('inf'), 0], 'null or')):
        with pytest.raises(AnnotationError, match=match):
            extract_boundaries(track_map, [TL_CUT], 5, bad)
    test_map = TrackMap(MAPS / 'test/test.yaml')
    session = new_session(test_map)
    plain = geometry_digest(session, test_map)
    session['retained_region_px'] = [100, 170]
    assert geometry_digest(session, test_map) != plain
    session['approval'] = 'operator-approved'
    session['approval_digest'] = geometry_digest(session, test_map)
    session['preview_route_digest'] = 'a' * 64
    session['approval_route_digest'] = 'a' * 64
    require_approved(session, test_map)
    path = tmp_path / 'sel.json'
    save_session(session, path)
    assert load_session(path, test_map)['retained_region_px'] == [100, 170]
    session['retained_region_px'] = [1, 2, 3]
    save_session(session, path)
    with pytest.raises(AnnotationError, match='null or'):
        load_session(path, test_map)


def test_approval_bound_to_geometry_and_thinning():
    """require_approved refuses drafts, stale digests and re-thinning."""
    track_map = TrackMap(MAPS / 'test/test.yaml')
    session = new_session(track_map)
    with pytest.raises(AnnotationError, match='not .operator-approved'):
        require_approved(session, track_map)
    session['approval'] = 'operator-approved'
    session['approval_digest'] = 'stale'
    with pytest.raises(AnnotationError, match='changed since approval'):
        require_approved(session, track_map)
    session['approval_digest'] = geometry_digest(session, track_map)
    session['preview_route_digest'] = 'a' * 64
    session['approval_route_digest'] = 'a' * 64
    require_approved(session, track_map)  # exact geometry: allowed
    session['chain_dp_epsilon_m'] = 0.03  # thinning is approval-bound
    with pytest.raises(AnnotationError, match='changed since approval'):
        require_approved(session, track_map)
    session['chain_dp_epsilon_m'] = 0.02
    session['boundary_strokes_px'] = [[[0, 0], [10, 10]]]
    with pytest.raises(AnnotationError, match='changed since approval'):
        require_approved(session, track_map)


def test_simplification_envelope_and_shared_endcaps():
    """eps/res > 0.6 fails closed; section caps are exact and shared."""
    track_map = TrackMap(MAPS / 'test/test.yaml')
    outer, inner = extract_boundaries(track_map)
    with pytest.raises(AnnotationError, match='raster cells'):
        build_route(track_map, outer, inner, midline_seed(outer, inner),
                    legal_mask=effective_free_mask(track_map, [], 5),
                    chain_dp_epsilon_m=0.05)
    from global_planner.annotation_core import suggest_route
    payload, route, _, _ = _build(track_map, outer, inner,
                                  suggest_route(outer, inner))
    sections = payload['sections']
    for k, section in enumerate(sections):
        nxt = sections[(k + 1) % len(sections)]
        assert section['left'][-1] == nxt['left'][0]
        assert section['right'][-1] == nxt['right'][0]
        gate = route.portals[k].gate
        assert [list(gate[0]), list(gate[1])] == [section['right'][-1],
                                                  section['left'][-1]]


def test_suggest_follows_operator_direction():
    """The suggestion runs in the operator's drawn direction."""
    from global_planner.annotation_core import _signed_area, suggest_route
    track_map = TrackMap(MAPS / 'test/test.yaml')
    outer, inner = extract_boundaries(track_map)
    guide = midline_seed(outer, inner)
    fwd = suggest_route(outer, inner, guide)
    rev = suggest_route(outer, inner, guide[::-1])
    assert _signed_area(fwd) * _signed_area(guide) > 0
    assert _signed_area(rev) * _signed_area(guide) < 0


def test_malformed_strokes_and_widths_fail_closed(tmp_path):
    """Non-numeric strokes and bad widths raise AnnotationError."""
    track_map = write_map(tmp_path, annulus_image(), name='annulus.png')
    with pytest.raises(AnnotationError, match='pixel pairs'):
        patched_free_mask(track_map, [[['x', 0]]])
    with pytest.raises(AnnotationError, match='integer 1..31'):
        patched_free_mask(track_map, [TL_CUT], 32)
    with pytest.raises(AnnotationError, match='magnitude'):
        patched_free_mask(track_map, [[[1e18, 0], [0, 0]]])


# ---------------------------------------------------------------------------
# Transports: server ops, headless CLI, HTTP, ROS adapter (same core)
# ---------------------------------------------------------------------------

def _draw_test_route(server):
    """Open the test map and draw a stroke + seed route; return track map."""
    server.op_open({'map': 'test'})
    server.op_update({'field': 'boundary_strokes_px',
                      'value': [[[211.0, 7.5], [239.0, 7.5]]]})
    track_map = server.STATE['map']
    outer, inner = extract_boundaries(
        track_map, server.STATE['session']['boundary_strokes_px'], 5)
    server.op_update({'field': 'route_px',
                      'value': midline_seed(outer, inner)})
    return track_map


def test_server_preview_approve_export_cycle(backend):
    """Preview shows the candidate; approve binds it; export writes it."""
    import os
    server = backend
    track_map = _draw_test_route(server)
    rev_before = server.STATE['session']['revision']
    prev = server.op_preview({})
    assert prev['status'] == 'VALIDATED'
    assert prev['candidate_digest'] == geometry_digest(
        server.STATE['session'], track_map)
    assert len(prev['validated_route_px']) == 4
    # Preview is read-only: no approval, no revision bump, no file.
    assert server.STATE['session']['approval'] == 'none'
    assert server.STATE['session']['revision'] == rev_before
    assert not os.path.exists(os.path.join(
        server.STATE['out_dir'], export_name(server.STATE['map'])))
    with pytest.raises(AnnotationError, match='not .operator-approved'):
        server.op_export({})
    server.op_approve({'approval_digest': prev['candidate_digest']})
    exp = server.op_export({})
    assert exp['status'] == 'VALIDATED'
    assert exp['route_digest'] == prev['route_digest']
    assert exp['validated_route_px'] == prev['validated_route_px']
    assert os.path.exists(os.path.join(
        server.STATE['out_dir'], export_name(server.STATE['map'])))


def test_server_edits_revoke_approval(backend):
    """Stale-preview approval, undo and bad updates all fail closed."""
    server = backend
    _draw_test_route(server)
    prev = server.op_preview({})
    with pytest.raises(AnnotationError, match='preview the candidate first'):
        server.op_approve({'approval_digest': 'wrong-digest'})
    server.op_update({'field': 'stroke_width_px', 'value': 9})
    with pytest.raises(AnnotationError, match='no fresh preview'):
        server.op_approve({'approval_digest': prev['candidate_digest']})
    prev = server.op_preview({})
    server.op_approve({'approval_digest': prev['candidate_digest']})
    rev = server.STATE['session']['revision']
    server.op_undo({})
    assert server.STATE['session']['approval'] == 'none'
    assert server.STATE['session']['revision'] > rev
    assert server.STATE['extraction'] is None
    with pytest.raises(AnnotationError, match='unknown editable field'):
        server.op_update({'field': 'nope', 'value': []})
    with pytest.raises(AnnotationError, match='at least 3 points'):
        server.op_update({'field': 'route_px', 'value': [[0, 0]]})
    with pytest.raises(AnnotationError, match='limit 20000'):
        server.op_update({'field': 'route_px',
                          'value': [[0.0, 0.0]] * 20001})
    with pytest.raises(AnnotationError, match='finite'):
        server.op_update({'field': 'route_px', 'value': [
            [0.0, 0.0], [1.0, 1.0], [float('nan'), 0.0]]})
    cleared = server.op_update({'field': 'route_px', 'value': []})
    assert cleared['status'] == 'PASS'
    assert server.STATE['session']['route_px'] == []


def test_drafts_namespaced_per_map(backend, tmp_path):
    """Same-stem maps keep independent drafts; reopening is per-map."""
    from PIL import Image, PngImagePlugin

    def copy_map(dirname, tag):
        d = tmp_path / 'maps' / dirname / 'same'
        d.mkdir(parents=True)
        img = Image.open(MAPS / 'test' / 'test.png')
        info = PngImagePlugin.PngInfo()
        info.add_text('tag', tag)
        img.save(d / 'same.png', pnginfo=info)
        (d / 'same.yaml').write_text(
            (MAPS / 'test/test.yaml').read_text(encoding='utf-8')
            .replace('test.png', 'same.png'), encoding='utf-8')

    copy_map('c1', 'first')
    copy_map('c2', 'second')
    server = backend
    server.configure(str(tmp_path / 'maps'), str(tmp_path / 'out'))
    route = [[100, 100], [200, 100], [200, 200]]
    for name, rt in (('c1/same', route), ('c2/same', [[300, 300]] * 3)):
        server.op_open({'map': name})
        server.op_update({'field': 'route_px', 'value': rt})
        server.op_save({})
    drafts = sorted(p.name for p in Path(server.STATE['out_dir']).iterdir())
    assert len(drafts) == 2 and 'same_annotation.json' not in drafts
    assert server.op_open({'map': 'c1/same'})['message'] == \
        'reopened saved draft'
    assert server.STATE['session']['route_px'] == route
    # Map paths cannot escape the maps directory.
    for bad in ('/etc/hostname', '../maps/test', ''):
        with pytest.raises(AnnotationError, match='escapes|nonempty|found'):
            server.op_open({'map': bad})


def test_cli_preview_approve_export_cycle(tmp_path):
    """Headless CLI mirrors the server's fresh-preview binding."""
    from global_planner import annotation_tool as tool
    track_map = TrackMap(MAPS / 'test/test.yaml')
    outer, inner = extract_boundaries(track_map, [], 5)
    session = new_session(track_map)
    session['route_px'] = midline_seed(outer, inner)
    session_path = tmp_path / 'session.json'
    save_session(session, session_path)
    out = tmp_path / 'cli_out'
    base = ['--map', str(track_map.yaml_path),
            '--session', str(session_path), '--out', str(out)]
    assert tool.main(['export'] + base) == 1  # no approval yet
    candidate = geometry_digest(session, track_map)
    assert tool.main(['approve'] + base + ['--candidate', candidate]) == 1
    assert tool.main(['preview'] + base) == 0
    assert not (out / export_name(track_map)).exists()
    assert tool.main(['approve'] + base + ['--candidate', 'wrong']) == 1
    assert tool.main(['approve'] + base + ['--candidate', candidate]) == 0
    assert tool.main(['export'] + base) == 0
    payload = json.loads((out / export_name(track_map)).read_text())
    assert set(payload) == {'name', 'map', 'start', 'sections'}
    assert load_route(out / export_name(track_map)).digest
    # CLI region selection: select, extract, clear, extract refuses.
    annulus = write_map(tmp_path, annulus_image(), name='cli.png')
    cut_session = new_session(annulus)
    cut_session['boundary_strokes_px'] = [TL_CUT]
    cut_path = tmp_path / 'cli_sel.json'
    save_session(cut_session, cut_path)
    sel = ['--map', str(annulus.yaml_path), '--session', str(cut_path)]
    assert tool.main(['select-region'] + sel + ['--pixel', '100,100']) == 1
    assert tool.main(['select-region'] + sel + ['--pixel', '100,170']) == 0
    assert tool.main(['extract'] + sel + ['--out', str(out)]) == 0
    assert tool.main(['select-region'] + sel + ['--clear']) == 0
    assert tool.main(['extract'] + sel + ['--out', str(out)]) == 1


def test_cli_open_guide_refused(tmp_path):
    """The headless CLI cannot preview/approve/export an OPEN guide."""
    from global_planner import annotation_tool as tool
    track_map = TrackMap(MAPS / 'test/test.yaml')
    outer, inner = extract_boundaries(track_map, [], 5)
    session = new_session(track_map)
    session['route_px'] = midline_seed(outer, inner)[:-6]  # open tail
    session_path = tmp_path / 'open.json'
    save_session(session, session_path)
    base = ['--map', str(track_map.yaml_path),
            '--session', str(session_path),
            '--out', str(tmp_path / 'out')]
    assert tool.main(['preview'] + base) == 1
    assert tool.main(['approve'] + base + ['--candidate', 'x']) == 1
    assert tool.main(['export'] + base) == 1


def test_http_transport_fails_closed(backend, monkeypatch):
    """Malformed/oversized/backend-error posts get JSON FAIL, server lives."""
    import http.client
    import threading
    from http.server import HTTPServer
    from global_planner import annotation_server as server_module
    from global_planner.annotation_server import Handler, MAX_BODY_BYTES
    server = backend
    server.op_open({'map': 'test'})
    httpd = HTTPServer(('127.0.0.1', 0), Handler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    def post(body, path='/api/session/state'):
        conn = http.client.HTTPConnection('127.0.0.1', port, timeout=30)
        conn.request('POST', path, body=body,
                     headers={'Content-Type': 'application/json'})
        resp = conn.getresponse()
        return resp.status, json.loads(resp.read())

    try:
        assert post(b'{not json')[0] == 400
        assert post(b'[1, 2, 3]')[0] == 400
        status, payload = post(b'x' * (MAX_BODY_BYTES + 1))
        assert status == 413 and payload['status'] == 'FAIL'
        status, payload = post(b'{}')  # still serving after oversize
        assert status == 200 and payload['status'] == 'PASS'

        def boom(body):
            raise RuntimeError('simulated geometry failure')
        monkeypatch.setitem(server_module.OPS, '/api/session/extract', boom)
        status, payload = post(b'{}', '/api/session/extract')
        assert status == 400 and 'simulated geometry failure' in \
            payload['message']
    finally:
        httpd.shutdown()
        httpd.server_close()


def _headless_node(tmp_path):
    """Drive the ROS adapter headlessly through its stub publisher."""
    from global_planner import annotation_node as node_mod

    class Pub:
        def __init__(self):
            self.sent = []

        def publish(self, msg):
            self.sent.append(json.loads(msg.data))

    node = node_mod.AnnotationNode(maps_dir=str(MAPS),
                                   out_dir=str(tmp_path / 'node_out'))
    pub = Pub()
    node._pub = pub

    def send(op, request_id=None, **fields):
        body = dict(op=op, **fields)
        if request_id is not None:
            body['request_id'] = request_id

        class Msg:
            data = json.dumps(body)
        node._on_command(Msg())
        return pub.sent[-1]
    return node, send


def _has_rclpy():
    try:
        import rclpy
        return rclpy is not None
    except ImportError:
        return False


headless_only = pytest.mark.skipif(
    _has_rclpy(), reason='headless adapter path (rclpy present)')
needs_ros = pytest.mark.skipif(
    not _has_rclpy(), reason='requires ROS 2 rclpy')


@headless_only
def test_node_adapter_contract(tmp_path):
    """Relative topics, isolation gate, bounded dedup, retry correlation."""
    from global_planner import annotation_node as node_mod
    assert node_mod.AnnotationNode.COMMAND_TOPIC == \
        'planner_annotation/command'
    assert node_mod.AnnotationNode.STATE_TOPIC == 'planner_annotation/state'
    assert not node_mod._isolation_ok('0', '/')
    assert not node_mod._isolation_ok(' 0 ', '/')
    assert not node_mod._isolation_ok('abc', '/')
    assert node_mod._isolation_ok('42', '/')
    assert node_mod._isolation_ok('0', '/annot')
    with pytest.raises(AnnotationError, match='maps directory not found'):
        node_mod.AnnotationNode(maps_dir='/nonexistent-dir-xyz',
                                out_dir=str(tmp_path))
    node, send = _headless_node(tmp_path)
    for i in range(node._SEEN_CAP + 10):
        node._remember(f'id-{i}')
    assert len(node._seen) <= node._SEEN_CAP
    opened = send('open', request_id='r1', map='test')
    assert opened['status'] == 'PASS' and opened['request_id'] == 'r1'
    failed = send('nope', request_id='r2')  # failures stay retryable
    assert failed['status'] == 'FAIL' and failed['request_id'] == 'r2'
    assert send('state', request_id='r2')['status'] == 'PASS'
    dup = send('open', request_id='r1', map='test')
    assert dup['status'] == 'DUPLICATE' and dup['revision'] == opened['revision']


@needs_ros
def test_node_ros_namespaced_roundtrip(tmp_path):
    """With rclpy the adapter round-trips on namespaced topics."""
    import time
    rclpy = pytest.importorskip('rclpy')
    String = pytest.importorskip('std_msgs.msg').String
    from global_planner import annotation_node as node_mod
    assert node_mod.rclpy is not None
    rclpy.init(args=['--ros-args', '-r', '__ns:=/annot'])
    node = helper = None
    try:
        node = node_mod.AnnotationNode(maps_dir=str(MAPS),
                                       out_dir=str(tmp_path / 'ros_out'))
        assert node.get_namespace() == '/annot'
        names = dict(node.get_topic_names_and_types())
        assert '/annot/planner_annotation/command' in names
        assert '/annot/planner_annotation/state' in names
        from rclpy.executors import SingleThreadedExecutor
        from rclpy.node import Node
        helper = Node('annot_probe')
        cmd_pub = helper.create_publisher(
            String, 'planner_annotation/command', 10)
        replies = []
        helper.create_subscription(
            String, 'planner_annotation/state', replies.append, 10)
        probe = String()
        probe.data = json.dumps({'op': 'open', 'map': 'test',
                                 'request_id': 'ros1'})
        executor = SingleThreadedExecutor()
        executor.add_node(node)
        executor.add_node(helper)
        cmd_pub.publish(probe)
        deadline = time.monotonic() + 15.0
        while not replies and time.monotonic() < deadline:
            executor.spin_once(timeout_sec=0.2)
        assert replies, 'no state reply on the namespaced topic'
        reply = json.loads(replies[-1].data)
        assert reply['status'] == 'PASS'
        assert reply['request_id'] == 'ros1'
        assert reply['revision'] == 1
    finally:
        if node is not None:
            node.destroy_node()
        if helper is not None:
            helper.destroy_node()
        rclpy.shutdown()
