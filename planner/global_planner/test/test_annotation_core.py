# Copyright 2026 ForzaETH
"""Tests for the minimal Project A annotation tool (MVP1)."""
import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))

from global_planner.annotation_core import (  # noqa: E402
    AnnotationError, MAX_DP_EPS_PER_CELL, TrackMap, atomic_write_text,
    build_and_validate,
    build_manifest, check_session_map, draft_name, export_name,
    extract_boundaries, geometry_digest, load_session, map_namespace,
    new_session, patched_free_mask, require_approved, resolve_draft,
    ridge_seed, save_session, suggest_route)
from global_planner.route_input import RouteError, validate_route  # noqa: E402

MAPS = Path(__file__).parents[3] / 'stack_master' / 'maps'


def _midline_seed(outer, inner, count=120):
    step = max(1, len(outer) // count)
    seed = []
    for p in outer[::step]:
        j = int(np.argmin(np.linalg.norm(inner - p, axis=1)))
        seed.append(((p + inner[j]) / 2).tolist())
    return seed


@pytest.mark.parametrize('name', ['test/test', 'baku/baku'])
def test_real_map_end_to_end_validates(name):
    """Extracted loops + directed seed -> strict PASS + prepared corridor."""
    track_map = TrackMap(MAPS / f'{name}.yaml')
    outer, inner = extract_boundaries(track_map)
    payload, route, prepared, info = build_and_validate(
        track_map, outer, inner, _midline_seed(outer, inner),
        approval='operator-approved')
    assert len(route.occurrences) == 4
    assert len(prepared.samples) > 100
    assert payload['physical_map']['sha256'] == track_map.sha256
    assert info['seed_samples'] > 100
    assert info['max_correction_m'] >= 0.0


def test_pixel_world_roundtrip():
    """Pixel<->world is an exact inverse pair (flip convention)."""
    track_map = TrackMap(MAPS / 'test/test.yaml')
    for uv in [(0, 0), (100, 50), (435, 441), (217, 220)]:
        back = track_map.world_to_pixel(track_map.pixel_to_world(uv))
        assert back == pytest.approx(uv, abs=1e-9)


def test_session_roundtrip_and_map_identity():
    """Save/reopen works; a different map is rejected, not rebound."""
    track_map = TrackMap(MAPS / 'test/test.yaml')
    session = new_session(track_map)
    session['route_px'] = [[1, 2], [3, 4], [5, 6]]
    path = Path('/tmp/annotation_test_session.json')
    save_session(session, path)
    assert load_session(path, track_map)['route_px'] == session['route_px']
    other = TrackMap(MAPS / 'baku/baku.yaml')
    with pytest.raises(AnnotationError, match='identity mismatch'):
        load_session(path, other)


def _write_map_copy(tmp_path, image, name='gap.png'):
    """Write a derived PNG+YAML pair reusing the test map registration."""
    import cv2
    png = tmp_path / name
    cv2.imwrite(str(png), image)
    yaml = tmp_path / (Path(name).stem + '.yaml')
    yaml.write_text('image: %s\nresolution: 0.05\n'
                    'origin: [-8.4, -5.35, 0]\nnegate: 0\n'
                    'occupied_thresh: 0.65\nfree_thresh: 0.196\n' % name)
    return TrackMap(yaml)


def _maxmin(a, b):
    """Hausdorff-style max of min distances between two polylines (px)."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    return float(np.linalg.norm(
        a[:, None, :] - b[None, :, :], axis=2).min(axis=1).max())


def test_outer_gap_bay_detours_then_stroke_restores(tmp_path):
    """A pocket broken in the outer wall must visibly detour, then repair.

    Site (test map): straight horizontal outer wall at file rows 7/8,
    track below, sea above. The whitened rect spans the wall, so the
    extractor still finds one annulus (no rejection possible), but the
    outer loop must detour around the pocket instead of silently matching
    the original. A tangent boundary stroke overlapping intact wall on
    both sides must restore the original loops.
    """
    src = TrackMap(MAPS / 'test/test.yaml')
    img = src.image.copy()
    img[5:11, 219:232] = 255  # pocket across the outer wall
    gap_map = _write_map_copy(tmp_path, img)
    outer0, inner0 = extract_boundaries(src, [])
    outer, inner = extract_boundaries(gap_map, [])
    assert _maxmin(outer, outer0) > 2.0  # detour is real, not a silent match
    assert _maxmin(inner, inner0) < 1.0  # far side untouched
    stroke = [[[211.0, 7.5], [239.0, 7.5]]]
    fixed_outer, fixed_inner = extract_boundaries(
        gap_map, stroke, stroke_width_px=5)
    assert _maxmin(fixed_outer, outer0) < 8.0
    assert _maxmin(fixed_inner, inner0) < 2.0


def test_isolated_free_speck_rejected(tmp_path):
    """A white speck fully inside the infield is a second free region."""
    import cv2
    src = TrackMap(MAPS / 'test/test.yaml')
    img = src.image.copy()
    cv2.circle(img, (248, 226), 5, 255, -1)  # deep inside the black infield
    speck_map = _write_map_copy(tmp_path, img, name='speck.png')
    with pytest.raises(AnnotationError, match='2 separate regions'):
        extract_boundaries(speck_map, [])


def test_chord_across_infield_rejected(tmp_path):
    """A whitened chord splitting the infield is not one annulus."""
    src = TrackMap(MAPS / 'test/test.yaml')
    img = src.image.copy()
    # Row band y=223..229 crosses track-hole-track at this latitude, so the
    # black infield is severed into two bounded parts (0 or 2 holes).
    img[223:230, 180:320] = 255
    chord_map = _write_map_copy(tmp_path, img, name='chord.png')
    with pytest.raises(AnnotationError, match='inner boundary|separate regions'):
        extract_boundaries(chord_map, [])


def test_reversed_direction_also_valid_but_distinct():
    """Direction is semantic: reversed lap validates with a new digest."""
    track_map = TrackMap(MAPS / 'test/test.yaml')
    outer, inner = extract_boundaries(track_map)
    seed = _midline_seed(outer, inner)
    fwd, _, _, _ = build_and_validate(track_map, outer, inner, seed,
                                      approval='operator-approved')
    rev, _, _, _ = build_and_validate(track_map, outer, inner, seed[::-1],
                                      approval='operator-approved')
    assert fwd != rev


def test_route_outside_track_rejected():
    """A loop drawn outside the boundaries is rejected, never clamped in."""
    track_map = TrackMap(MAPS / 'test/test.yaml')
    outer, inner = extract_boundaries(track_map)
    bogus = [[10 + 20 * math.cos(a), 10 + 20 * math.sin(a)]
             for a in np.linspace(0, 2 * math.pi, 24)]
    with pytest.raises((AnnotationError, RouteError, ValueError)):
        build_and_validate(track_map, outer, inner, bogus,
                           approval='operator-approved')


def test_unapproved_export_payload_is_marked():
    """Draft approval state is recorded verbatim in provenance."""
    track_map = TrackMap(MAPS / 'test/test.yaml')
    outer, inner = extract_boundaries(track_map)
    payload, _, _, _ = build_and_validate(
        track_map, outer, inner, _midline_seed(outer, inner),
        approval='none')
    assert payload['provenance']['approval'] == 'none'
    validate_route(payload)  # syntax still strict; approval is separate


def test_source_map_never_modified(tmp_path):
    """Extraction/patching work on copies; the PNG bytes are untouched."""
    track_map = TrackMap(MAPS / 'test/test.yaml')
    before = Path(track_map.png_path).read_bytes()
    extract_boundaries(track_map, [[[0, 0], [50, 50]]], stroke_width_px=5)
    patched_free_mask(track_map, [[[0, 0], [50, 50]]])
    assert Path(track_map.png_path).read_bytes() == before
    assert json.dumps(new_session(track_map))  # session is JSON-safe


@pytest.fixture
def backend(tmp_path):
    """Configured shared backend with STATE restored afterwards."""
    from global_planner import annotation_server as server
    saved = dict(server.STATE)
    server.configure(str(MAPS), str(tmp_path / 'out'))
    server.STATE.update(map=None, session=None, extraction=None,
                        candidate_digest=None)
    yield server
    server.STATE.clear()
    server.STATE.update(saved)


def test_approval_is_bound_to_geometry_digest():
    """require_approved refuses drafts and post-approval edits alike."""
    track_map = TrackMap(MAPS / 'test/test.yaml')
    session = new_session(track_map)
    with pytest.raises(AnnotationError, match='not .operator-approved'):
        require_approved(session, track_map)
    session['approval'] = 'operator-approved'
    session['approval_digest'] = 'stale'
    with pytest.raises(AnnotationError, match='changed since approval'):
        require_approved(session, track_map)
    session['approval_digest'] = geometry_digest(session, track_map)
    require_approved(session, track_map)  # exact geometry: allowed
    session['boundary_strokes_px'] = [[[0, 0], [10, 10]]]
    with pytest.raises(AnnotationError, match='changed since approval'):
        require_approved(session, track_map)


def test_session_rejects_reinterpreted_map():
    """Same PNG under another resolution/origin/negate is not rebound."""
    track_map = TrackMap(MAPS / 'test/test.yaml')
    session = new_session(track_map)
    check_session_map(session, track_map)
    for key, bad in (('resolution', track_map.resolution + 0.01),
                     ('origin', [0.0, 0.0]),
                     ('negate', 1)):
        mutated = dict(session, **{key: bad})
        with pytest.raises(AnnotationError, match='identity mismatch'):
            check_session_map(mutated, track_map)


def test_v1_session_migrates_with_approval_revoked(tmp_path):
    """Old drafts reopen, but a v1 approval never carries forward."""
    track_map = TrackMap(MAPS / 'test/test.yaml')
    session = new_session(track_map)
    session['version'] = 1
    session['approval'] = 'operator-approved'
    del session['approval_digest']
    path = tmp_path / 'v1.json'
    path.write_text(json.dumps(session), encoding='utf-8')
    loaded = load_session(path, track_map)
    assert loaded['version'] == 2
    assert loaded['approval'] == 'none'
    with pytest.raises(AnnotationError, match='not .operator-approved'):
        require_approved(loaded, track_map)


def test_nonbinary_map_rejected(tmp_path):
    """Gray unknown cells are rejected, never read as free space."""
    import cv2
    src = TrackMap(MAPS / 'test/test.yaml')
    img = src.image.copy()
    cv2.circle(img, (248, 226), 5, 128, -1)  # unknown gray in the infield
    gray_map = _write_map_copy(tmp_path, img, name='gray.png')
    with pytest.raises(AnnotationError, match='not binary'):
        extract_boundaries(gray_map, [])


def test_negate_one_inverts_occupancy(tmp_path):
    """negate:1 reads the same track with swapped black/white levels."""
    import cv2
    src = TrackMap(MAPS / 'test/test.yaml')
    inv = 255 - src.image
    png = tmp_path / 'inv.png'
    cv2.imwrite(str(png), inv)
    yaml = tmp_path / 'inv.yaml'
    yaml.write_text('image: inv.png\nresolution: 0.05\n'
                    'origin: [-8.4, -5.35, 0]\nnegate: 1\n'
                    'occupied_thresh: 0.65\nfree_thresh: 0.196\n')
    inv_map = TrackMap(yaml)
    outer, inner = extract_boundaries(src, [])
    outer_n, inner_n = extract_boundaries(inv_map, [])
    assert len(outer) == len(outer_n) and len(inner) == len(inner_n)
    _, route, _, _ = build_and_validate(
        inv_map, outer_n, inner_n, _midline_seed(outer_n, inner_n),
        approval='operator-approved')
    assert len(route.occurrences) == 4


def _draw_test_route(server):
    """Open the test map and draw a stroke + seed route; return track map."""
    server.op_open({'map': 'test'})
    assert server.STATE['extraction'] is None
    server.op_update({'field': 'boundary_strokes_px',
                      'value': [[[211.0, 7.5], [239.0, 7.5]]]})
    track_map = server.STATE['map']
    outer, inner = extract_boundaries(
        track_map, server.STATE['session']['boundary_strokes_px'], 5)
    server.op_update({'field': 'route_px',
                      'value': _midline_seed(outer, inner)})
    return track_map


def test_server_preview_approve_export_cycle(backend):
    """Preview shows the transformed candidate; approve binds it; export
    writes exactly that candidate. Export without approval is refused."""
    import os
    server = backend
    track_map = _draw_test_route(server)
    rev_before_preview = server.STATE['session']['revision']
    prev = server.op_preview({})
    assert prev['status'] == 'VALIDATED'
    assert prev['candidate_digest'] == geometry_digest(
        server.STATE['session'], track_map)
    assert prev['validated_route_px'] and len(prev['validated_route_px']) == 4
    assert prev['max_correction_m'] >= 0.0
    # Preview is read-only: no approval, no revision bump, no file.
    assert server.STATE['session']['approval'] == 'none'
    assert server.STATE['session']['approval_digest'] is None
    assert server.STATE['session']['revision'] == rev_before_preview
    assert not os.path.exists(
        os.path.join(server.STATE['out_dir'],
        export_name(server.STATE['map'])))
    # Export without approval is refused by design.
    with pytest.raises(AnnotationError, match='not .operator-approved'):
        server.op_export({})
    appr = server.op_approve({'approval_digest': prev['candidate_digest']})
    assert appr['status'] == 'PASS'
    assert server.STATE['session']['approval'] == 'operator-approved'
    exp = server.op_export({})
    assert exp['status'] == 'VALIDATED'
    # Previewed and exported outputs are demonstrably identical.
    assert exp['route_digest'] == prev['route_digest']
    assert exp['validated_route_px'] == prev['validated_route_px']
    assert os.path.exists(
        os.path.join(server.STATE['out_dir'],
        export_name(server.STATE['map'])))


def test_server_approve_rejects_stale_preview(backend):
    """Approval binds the previewed digest; edits invalidate it."""
    server = backend
    _draw_test_route(server)
    prev = server.op_preview({})
    with pytest.raises(AnnotationError, match='preview the candidate first'):
        server.op_approve({'approval_digest': 'wrong-digest'})
    with pytest.raises(AnnotationError, match='approve refused'):
        server.op_approve({})
    # An edit after preview invalidates the candidate: approve must fail.
    server.op_update({'field': 'stroke_width_px', 'value': 9})
    with pytest.raises(AnnotationError, match='no fresh preview'):
        server.op_approve({'approval_digest': prev['candidate_digest']})


def test_server_undo_revokes_approval(backend):
    """Undo is an edit: it revokes approval and bumps the revision."""
    server = backend
    _draw_test_route(server)
    prev = server.op_preview({})
    server.op_approve({'approval_digest': prev['candidate_digest']})
    rev_before_undo = server.STATE['session']['revision']
    assert server.STATE['session']['approval'] == 'operator-approved'
    undone = server.op_undo({})
    assert undone['status'] == 'PASS'
    assert server.STATE['session']['approval'] == 'none'
    assert server.STATE['session']['approval_digest'] is None
    assert server.STATE['session']['revision'] > rev_before_undo
    assert server.STATE['extraction'] is None
    assert server.STATE['candidate_digest'] is None


def test_server_state_op_recovers_canonical_state(backend):
    """The state op reports canonical state without mutating anything."""
    server = backend
    _draw_test_route(server)
    rev = server.STATE['session']['revision']
    res = server.op_state({})
    assert res['status'] == 'PASS'
    assert res['revision'] == rev
    assert res['session']['revision'] == rev
    # Read-only: revision and approval untouched.
    assert server.STATE['session']['revision'] == rev
    assert server.STATE['session']['approval'] == 'none'


def test_server_update_validation_and_clear(backend):
    """Bad fields/widths are rejected; clearing the route is allowed."""
    server = backend
    server.op_open({'map': 'test'})
    with pytest.raises(AnnotationError, match='unknown editable field'):
        server.op_update({'field': 'nope', 'value': []})
    with pytest.raises(AnnotationError, match='at least 3 points'):
        server.op_update({'field': 'route_px', 'value': [[0, 0]]})
    with pytest.raises(AnnotationError, match='stroke_width_px'):
        server.op_update({'field': 'stroke_width_px', 'value': 99})
    rev = server.STATE['session']['revision']
    cleared = server.op_update({'field': 'route_px', 'value': []})
    assert cleared['status'] == 'PASS'
    assert server.STATE['session']['route_px'] == []
    assert server.STATE['session']['revision'] == rev + 1
    widened = server.op_update({'field': 'stroke_width_px', 'value': 9})
    assert server.STATE['session']['stroke_width_px'] == 9
    assert 'unapproved' in widened['message']


def test_server_requires_configuration():
    """Opening a map on an unconfigured backend fails explicitly."""
    from global_planner import annotation_server as server
    saved = dict(server.STATE)
    server.STATE.update(maps_dir=None, out_dir=None, map=None,
                        session=None, extraction=None)
    try:
        with pytest.raises(AnnotationError, match='not configured'):
            server.op_open({'map': 'test'})
    finally:
        server.STATE.clear()
        server.STATE.update(saved)


def test_cli_export_refuses_stale_approval(tmp_path):
    """The headless CLI honors only digest-bound approvals."""
    from global_planner import annotation_tool as tool
    track_map = TrackMap(MAPS / 'test/test.yaml')
    outer, inner = extract_boundaries(track_map, [], 5)
    session = new_session(track_map)
    session['route_px'] = _midline_seed(outer, inner)
    session['approval'] = 'operator-approved'
    session['approval_digest'] = geometry_digest(session, track_map)
    session_path = tmp_path / 'session.json'
    save_session(session, session_path)
    out = tmp_path / 'cli_out'
    assert tool.main(['export', '--map', str(track_map.yaml_path),
                      '--session', str(session_path),
                      '--out', str(out)]) == 0
    assert (out / export_name(track_map)).exists()
    # An edit after approval (saved without re-approval) must be refused.
    stale = load_session(session_path, track_map)
    stale['boundary_strokes_px'] = [[[0, 0], [50, 50]]]
    save_session(stale, session_path)
    assert tool.main(['export', '--map', str(track_map.yaml_path),
                      '--session', str(session_path),
                      '--out', str(out)]) == 1


def test_cli_preview_approve_export_cycle(tmp_path):
    """Headless preview -> approve -> export writes the previewed digest."""
    import json as _json
    from global_planner import annotation_tool as tool
    track_map = TrackMap(MAPS / 'test/test.yaml')
    outer, inner = extract_boundaries(track_map, [], 5)
    session = new_session(track_map)
    session['route_px'] = _midline_seed(outer, inner)
    session_path = tmp_path / 'session.json'
    save_session(session, session_path)
    out = tmp_path / 'cli_out'
    # Export before approval is refused.
    assert tool.main(['export', '--map', str(track_map.yaml_path),
                      '--session', str(session_path),
                      '--out', str(out)]) == 1
    assert not (out / export_name(track_map)).exists()
    # Preview is read-only: prints the candidate digest, writes nothing.
    assert tool.main(['preview', '--map', str(track_map.yaml_path),
                      '--session', str(session_path),
                      '--out', str(out)]) == 0
    assert not (out / export_name(track_map)).exists()
    candidate = geometry_digest(
        load_session(session_path, track_map), track_map)
    # Approve needs the previewed candidate digest.
    assert tool.main(['approve', '--map', str(track_map.yaml_path),
                      '--session', str(session_path),
                      '--out', str(out)]) == 1
    assert tool.main(['approve', '--map', str(track_map.yaml_path),
                      '--session', str(session_path),
                      '--out', str(out),
                      '--candidate', 'wrong-digest']) == 1
    assert tool.main(['approve', '--map', str(track_map.yaml_path),
                      '--session', str(session_path),
                      '--out', str(out),
                      '--candidate', candidate]) == 0
    assert tool.main(['export', '--map', str(track_map.yaml_path),
                      '--session', str(session_path),
                      '--out', str(out)]) == 0
    assert (out / export_name(track_map)).exists()
    payload = _json.loads((out / export_name(track_map)).read_text())
    assert payload['provenance']['approval'] == 'operator-approved'


def _headless_node(tmp_path):
    """Drive the ROS adapter headlessly with a stub publisher."""
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


def test_node_retry_ack_correlation(tmp_path):
    """Failed commands stay retryable; successes dedup; every reply is
    correlated with request_id and the authoritative revision."""
    from global_planner import annotation_node as node_mod
    assert node_mod.rclpy is None  # headless env: documents the ROS blocker
    _, send = _headless_node(tmp_path)
    opened = send('open', request_id='r1', map='test')
    assert opened['status'] == 'PASS'
    assert opened['request_id'] == 'r1'
    rev1 = opened['revision']
    # Unknown op fails WITH correlation and stays retryable: the same
    # id with a valid op must execute, not report DUPLICATE.
    failed = send('nope', request_id='r2')
    assert failed['status'] == 'FAIL'
    assert failed['request_id'] == 'r2'
    assert failed['revision'] == rev1
    recovered = send('state', request_id='r2')
    assert recovered['status'] == 'PASS'
    assert recovered['request_id'] == 'r2'
    assert recovered['revision'] == rev1
    # Repeating a successful id is a DUPLICATE with correlation + revision.
    dup = send('open', request_id='r1', map='test')
    assert dup['status'] == 'DUPLICATE'
    assert dup['request_id'] == 'r1'
    assert dup['revision'] == rev1
    # A state fetch after (simulated) reconnect recovers canonical state.
    state = send('state')
    assert state['status'] == 'PASS'
    assert state['revision'] == rev1
    assert 'request_id' not in state


@pytest.mark.parametrize('name', ['test/test', 'baku/baku'])
def test_ridge_seed_validates(name):
    """DT-ridge seeds validate strictly on supported maps.

    Unlike the crude correspondence midline, the ridge seed is derived
    from the free-space distance transform, so it stays centered through
    bends without a nearest-pairing flip.
    """
    track_map = TrackMap(MAPS / f'{name}.yaml')
    outer, inner = extract_boundaries(track_map)
    seed = ridge_seed(track_map, outer, inner)
    _, route, prepared, info = build_and_validate(
        track_map, outer, inner, seed, approval='operator-approved')
    assert len(route.occurrences) == 4
    assert len(prepared.samples) > 100
    assert info['seed_samples'] > 100


def test_ridge_seed_confined_and_deterministic():
    """Ridge seeds never leave free space and are exactly repeatable."""
    import cv2
    track_map = TrackMap(MAPS / 'test/test.yaml')
    outer, inner = extract_boundaries(track_map)
    first = ridge_seed(track_map, outer, inner)
    second = ridge_seed(track_map, outer, inner)
    assert first == second
    free = patched_free_mask(track_map, [], 5)
    dist = cv2.distanceTransform(free, cv2.DIST_L2, 3)
    assert len(first) > 50
    for p in first:
        assert dist[int(round(p[1])), int(round(p[0]))] > 0


@pytest.mark.parametrize('name', ['spa/spa', 'zuri/zuri'])
def test_hairpin_map_extraction_topology(name):
    """Hairpin maps extract a clean annulus; route preparation needs an
    operator-drawn seed (programmatic seeds are rejected fail-closed)."""
    track_map = TrackMap(MAPS / f'{name}.yaml')
    outer, inner = extract_boundaries(track_map)
    assert len(outer) > 1000 and len(inner) > 1000


def _signed_area(pts):
    pts = np.asarray(pts, float)
    return 0.5 * float(np.sum(pts[:, 0] * np.roll(pts[:, 1], -1)
                               - np.roll(pts[:, 0], -1) * pts[:, 1]))


def test_suggest_route_follows_operator_direction():
    """The suggestion is a smooth centerline in the operator's direction."""
    track_map = TrackMap(MAPS / 'test/test.yaml')
    outer, inner = extract_boundaries(track_map)
    seed = suggest_route(outer, inner)
    assert len(seed) == 240
    op_route = _midline_seed(outer, inner)
    fwd = suggest_route(outer, inner, op_route)
    rev = suggest_route(outer, inner, op_route[::-1])
    assert len(fwd) == len(rev) == 240
    # The suggestion tracks the operator's loop orientation.
    assert _signed_area(fwd) * _signed_area(op_route) > 0
    assert _signed_area(rev) * _signed_area(op_route) < 0


def test_server_suggest_then_export_cycle(backend):
    """Suggest -> preview -> approve -> export is a strict PASS."""
    server = backend
    server.op_open({'map': 'test'})
    res = server.op_suggest({})
    assert res['status'] == 'PASS'
    # 240 spline points plus the explicit closing point.
    assert len(server.STATE['session']['route_px']) == 241
    assert server.STATE['session']['route_px'][0] == \
        server.STATE['session']['route_px'][-1]
    prev = server.op_preview({})
    assert prev['status'] == 'VALIDATED'
    assert len(prev['validated_route_px']) == 4
    server.op_approve({'approval_digest': prev['candidate_digest']})
    exp = server.op_export({})
    assert exp['status'] == 'VALIDATED'
    assert exp['route_digest'] == prev['route_digest']


def test_build_defaults_thin_walls_and_big_zone():
    """Pipeline defaults: RDP-thinned walls fit checker budgets and the
    init zone is the 2.0 x 1.6 m start box (input convention)."""
    import math
    track_map = TrackMap(MAPS / 'test/test.yaml')
    outer, inner = extract_boundaries(track_map)
    seed = suggest_route(outer, inner)
    payload, _, _, _ = build_and_validate(
        track_map, outer, inner, seed, approval='operator-approved')
    total = sum(len(o['left']) + len(o['right'])
                for o in payload['occurrences'])
    assert total < 1000  # dense extraction is ~1626 vertices
    zone = payload['initialization']['zone']
    edges = [math.dist(zone[k], zone[(k + 1) % 4]) for k in range(4)]
    assert sorted(edges) == pytest.approx([1.6, 1.6, 2.0, 2.0], abs=1e-9)


def test_node_suggest_roundtrip(tmp_path):
    """The ROS adapter exposes the suggest op on the same reply path."""
    _, send = _headless_node(tmp_path)
    opened = send('open', request_id='s1', map='test')
    assert opened['status'] == 'PASS' and opened['revision'] == 1
    res = send('suggest', request_id='s2')
    assert res['status'] == 'PASS'
    assert res['request_id'] == 's2'
    assert len(res['session']['route_px']) == 241
    assert res['revision'] == 2
    assert res['session']['approval'] == 'none'


def _synthetic_map(tmp_path, name, image, resolution=0.05):
    """Write a PNG+YAML fixture map into tmp_path; return the yaml path."""
    import cv2 as _cv2
    png = tmp_path / f'{name}.png'
    _cv2.imwrite(str(png), image)
    (tmp_path / f'{name}.yaml').write_text(
        'image: %s.png\nresolution: %s\norigin: [0.0, 0.0, 0.0]\n'
        'negate: 0\noccupied_thresh: 0.65\nfree_thresh: 0.196\n'
        % (name, resolution), encoding='utf-8')
    return tmp_path / f'{name}.yaml'


def test_frame_gap_rejected(tmp_path):
    """Free space touching the image frame is an open outer wall."""
    import cv2 as _cv2
    img = np.zeros((80, 80), np.uint8)
    _cv2.circle(img, (40, 40), 30, 255, -1)
    _cv2.circle(img, (40, 40), 15, 0, -1)
    yaml_path = _synthetic_map(tmp_path, 'ring', img)
    track_map = TrackMap(yaml_path)
    outer, inner = extract_boundaries(track_map)
    assert len(outer) > 50 and len(inner) > 20
    # One-pixel channel from the track to row 0: the frame becomes the
    # "outer boundary" and must be rejected, not silently accepted.
    img[0:12, 40] = 255
    yaml_path = _synthetic_map(tmp_path, 'ring_gap', img)
    with pytest.raises(AnnotationError, match='frame'):
        extract_boundaries(TrackMap(yaml_path))


def test_frame_gap_real_map_rejected_and_repaired(tmp_path):
    """Rows 0:11 whitened on the test map: rejected; repaired: accepted."""
    import cv2 as _cv2
    import shutil
    src = MAPS / 'test/test.png'
    png = tmp_path / 'gap.png'
    shutil.copy(src, png)
    img = _cv2.imread(str(png), _cv2.IMREAD_GRAYSCALE)
    img[0:11, 219:232] = 255
    _cv2.imwrite(str(png), img)
    (tmp_path / 'gap.yaml').write_text(
        (MAPS / 'test/test.yaml').read_text(
            encoding='utf-8').replace('test.png', 'gap.png'),
        encoding='utf-8')
    track_map = TrackMap(tmp_path / 'gap.yaml')
    with pytest.raises(AnnotationError, match='frame'):
        extract_boundaries(track_map)
    # A stroke closing the gap at the frame restores a valid extraction
    # and even strict validation.
    outer, inner = extract_boundaries(
        track_map, [[[211.0, 5.5], [239.0, 5.5]]], 13)
    seed = _midline_seed(outer, inner)
    _, route, prepared, _ = build_and_validate(
        track_map, outer, inner, seed, approval='operator-approved')
    assert len(route.occurrences) == 4
    assert len(prepared.samples) > 100


def test_rdp_never_expands_corridor():
    """A 15 mm occupied tooth must survive simplification (2 mm raster)."""
    from global_planner.annotation_core import (
        _chord_stays_free, _douglas_peucker)
    res = 0.002
    wall = [[x / 1000.0, 0.0] for x in range(0, 61, 5)]
    wall.insert(6, [0.030, 0.015])  # apex between (25,0) and (30,0)
    mask = np.zeros((40, 60), np.uint8)
    for u in range(60):
        for v in range(40):
            x, y = u * res, (39 - v) * res
            inside = y > 0 and not (
                0.0 <= x <= 0.060
                and y <= 0.015 * (1 - abs(x - 0.030) / 0.030))
            mask[v, u] = 255 if inside else 0
    # Same construction as build_manifest: one-cell dilation = grid quantum.
    import cv2
    mask = cv2.dilate(mask, np.ones((3, 3), np.uint8))

    def to_px(pt):
        return (pt[0] / res, 39 - pt[1] / res)

    def dist_to_poly(pt, poly):
        """Distance from a point to a polyline (metres)."""
        pt = np.array(pt, float)
        best = float('inf')
        for a, b in zip(poly[:-1], poly[1:]):
            a, b = np.array(a, float), np.array(b, float)
            seg = b - a
            t = min(1.0, max(0.0, float(np.dot(pt - a, seg))
                             / max(1e-18, float(np.dot(seg, seg)))))
            best = min(best, float(np.linalg.norm(pt - (a + t * seg))))
        return best

    apex = [0.030, 0.015]
    plain = _douglas_peucker(wall, 0.02)
    assert len(plain) == 2  # old behavior drops the apex (the bug)
    # The dropped 15 mm tooth becomes corridor: illegal gain.
    assert dist_to_poly(apex, plain) >= 0.010
    fixed = _douglas_peucker(wall, 0.02, _chord_ok=lambda a, b:
                             _chord_stays_free(a, b, mask, to_px, res))
    assert any(p[1] > 0.01 for p in fixed)  # apex survives: no gain
    assert len(fixed) < len(wall)  # straight runs still decimate
    assert dist_to_poly(apex, fixed) <= 0.001  # tip stays on the wall
    # Straight runs still collapse: no vertex kept without a reason.
    straight = [[x / 1000.0, 0.0] for x in range(0, 101, 5)]
    assert len(_douglas_peucker(straight, 0.02, _chord_ok=lambda a, b:
                                _chord_stays_free(a, b, mask, to_px, res))) \
        == 2


def _peninsula_fixture(res_m, width_cells, height_m, length_m=0.066):
    """Straight wall with a rectangular occupied peninsula (analytic truth).

    Returns (wall, free_mask, to_px, tip). NOTE: 2 mm fixtures exceed the
    build_manifest envelope (eps/res = 10); they pin the bare primitive's
    eps bound (gain <= eps), not the supported sub-cell contract.
    """
    import cv2
    length_m = max(length_m, 30 * res_m)  # keep ~30 samples at any raster
    wall, x = [], 0.0
    while x < length_m:
        wall.append([x, 0.0])
        x += res_m
    hw = width_cells * res_m / 2
    cx = length_m / 2
    wall = [p for p in wall if not cx - hw < p[0] < cx + hw]
    wall += [[cx - hw, height_m], [cx + hw, height_m]]
    wall = sorted(wall)
    ncol, nrow = int(length_m / res_m) + 4, 30
    free = np.zeros((nrow, ncol), np.uint8)
    for u in range(ncol):
        for v in range(nrow):
            wx, wy = u * res_m, (nrow - 1 - v) * res_m
            occ = (cx - hw <= wx <= cx + hw and wy <= height_m)
            free[v, u] = 0 if (wy <= 0 or occ) else 255
    dil = cv2.dilate(free, np.ones((3, 3), np.uint8))

    def to_px(pt):
        return (pt[0] / res_m, (nrow - 1) - pt[1] / res_m)

    return wall, dil, to_px, [cx, height_m]


def _apex_gain_m(tip, simplified):
    """Distance from the true tip to the simplified polyline (metres)."""
    tip = np.array(tip, float)
    best = float('inf')
    for a, b in zip(simplified[:-1], simplified[1:]):
        a, b = np.array(a, float), np.array(b, float)
        seg = b - a
        t = min(1.0, max(0.0, float(np.dot(tip - a, seg))
                         / max(1e-18, float(np.dot(seg, seg)))))
        best = min(best, float(np.linalg.norm(tip - (a + t * seg))))
    return best


def test_rdp_gain_bounded_by_eps():
    """RDP-stage annexation gain never exceeds epsilon (sweep property).

    This pins the bare RDP primitive, not the wall chain: narrow
    sub-gate features ARE annexed (2-cell peninsula fully drops), but
    only up to their own height, which RDP requires to be <= eps.
    """
    from global_planner.annotation_core import _chord_stays_free, _douglas_peucker
    cases = [  # (res_m, width_cells, height_m, eps_m)
        (0.002, 2, 0.008, 0.02),
        (0.002, 2, 0.019, 0.02),
        (0.002, 1, 0.010, 0.02),
        (0.002, 7, 0.015, 0.02),
        (0.05, 2, 0.015, 0.02),
    ]
    for res_m, width_cells, height_m, eps_m in cases:
        wall, dil, to_px, tip = _peninsula_fixture(
            res_m, width_cells, height_m)
        gated = _douglas_peucker(
            wall, eps_m, _chord_ok=lambda a, b: _chord_stays_free(
                a, b, dil, to_px, res_m))
        assert len(gated) < len(wall)  # still decimates
        assert _apex_gain_m(tip, gated) <= eps_m * (1.0 + 1e-9)


def test_prefilter_mechanism_reinstates_above_bound_notch():
    """Gated-prefilter mechanism: above-bound notches survive the pass.

    Regression pin for the ungated-prefilter break: _simplify used to
    drop a 1-cell-wide x 1.2-cell-tall notch (0.0600 m = 3x eps at
    eps/res = 0.4) before RDP's deviation bound applied, and the
    annexing chord hit RDP's zero-deviation shortcut past the raster
    gate. This pins the mechanism (bound + gate), not the production
    floor value: the tip must survive the pre-filter so the chained
    RDP keeps it (gain ~0 here; production asserts floor + eps — see
    test_production_chain_gain_bounded_by_floor_plus_eps).
    """
    from global_planner.annotation_core import (
        _chord_stays_free, _douglas_peucker, _simplify)
    res_m, eps_m = 0.05, 0.02
    wall, dil, to_px, tip = _peninsula_fixture(res_m, 1, 0.06)
    gate = lambda a, b: _chord_stays_free(a, b, dil, to_px, res_m)
    spacing_m = max(2.0, 0.05 / res_m) * res_m
    pre = _simplify(wall, spacing_m, eps_m, gate)
    assert any(p[1] > 0.05 for p in pre)  # tip survives the pre-filter
    out = _douglas_peucker(pre, eps_m, _chord_ok=gate)
    assert _apex_gain_m(tip, out) <= eps_m * (1.0 + 1e-9)
    assert len(out) < len(wall)  # straight runs still decimate


def test_production_chain_gain_bounded_by_floor_plus_eps():
    """Production wall chain (floor prefilter + eps RDP) gains <= floor.

    Uses the exact chain build_manifest runs: prefilter bound 0.6
    cells, RDP bound eps, both gate-checked. A sub-floor spike
    (1 cell wide x 0.5 cell tall) is annexed up to its own height —
    that is the documented quantization floor, not a violation — while
    the above-floor 1.2-cell notch is kept (gain ~0).
    """
    from global_planner.annotation_core import (
        MAX_DP_EPS_PER_CELL, _chord_stays_free, _douglas_peucker,
        _simplify)
    res_m, eps_m = 0.05, 0.02
    floor_m = MAX_DP_EPS_PER_CELL * res_m
    gate_of = lambda dil, to_px: (
        lambda a, b: _chord_stays_free(a, b, dil, to_px, res_m))
    spacing_m = max(2.0, 0.05 / res_m) * res_m
    # Above-floor notch: kept end to end (gain ~0).
    wall, dil, to_px, tip = _peninsula_fixture(res_m, 1, 0.06)
    gate = gate_of(dil, to_px)
    pre = _simplify(wall, spacing_m, floor_m, gate)
    out = _douglas_peucker(pre, eps_m, _chord_ok=gate)
    assert _apex_gain_m(tip, out) <= eps_m * (1.0 + 1e-9)
    # Sub-floor spike: annexed, but bounded by the floor.
    wall, dil, to_px, tip = _peninsula_fixture(res_m, 1, 0.025)
    gate = gate_of(dil, to_px)
    pre = _simplify(wall, spacing_m, floor_m, gate)
    out = _douglas_peucker(pre, eps_m, _chord_ok=gate)
    assert _apex_gain_m(tip, out) <= floor_m * (1.0 + 1e-9)


def test_prefilter_floor_collapses_quantization_zigzag():
    """The envelope floor (0.6 cells) removes pixel staircase, not signal.

    A half-pixel diagonal zigzag is quantization noise: the floor-bound
    prefilter must collapse it instead of reinstating every jag (which
    is what exploded the checker's polygon budgets under an eps-bound
    prefilter). A 1.2-cell notch under the same bound must survive
    (pinned by test_full_chain_gain_bounded_by_eps).
    """
    from global_planner.annotation_core import _simplify
    res_m = 0.05
    floor_m = 0.6 * res_m
    zig = [[i * res_m, (i % 2) * res_m / 2] for i in range(41)]
    spacing_m = max(2.0, 0.05 / res_m) * res_m
    out = _simplify(zig, spacing_m, floor_m, chord_ok=lambda a, b: True)
    # The staircase is quantization noise: every dropped jag must lie
    # within the floor of the output polyline (an eps-bound prefilter
    # reinstated every jag and exploded the checker's polygon budgets).
    import numpy as np
    poly = np.asarray(out, float)
    worst = 0.0
    for p in np.asarray(zig, float):
        d = min(float(np.linalg.norm(
            p - (a + min(1.0, max(0.0, float(np.dot(p - a, b - a))
                                  / max(1e-18, float(np.dot(b - a, b - a)))))
                         * (b - a))))
                for a, b in zip(poly[:-1], poly[1:]))
        worst = max(worst, d)
    assert worst <= floor_m * (1.0 + 1e-9)
    assert len(out) < len(zig)


def test_envelope_rejects_coarse_eps(tmp_path):
    """eps/res above MAX_DP_EPS_PER_CELL fails closed before geometry."""
    track_map = TrackMap(MAPS / 'test/test.yaml')
    assert track_map.resolution == pytest.approx(0.05)
    outer, inner = extract_boundaries(track_map)
    with pytest.raises(AnnotationError, match='exceeds.*raster cells'):
        build_manifest(track_map, outer, inner,
                       _midline_seed(outer, inner),
                       approval='operator-approved', chain_dp_epsilon_m=0.05)


def test_envelope_accepts_boundary(tmp_path):
    """eps/res == 0.6 (baku's documented ratio) still builds strict PASS."""
    track_map = TrackMap(MAPS / 'test/test.yaml')
    outer, inner = extract_boundaries(track_map)
    payload, route, prepared, info = build_and_validate(
        track_map, outer, inner, _midline_seed(outer, inner),
        approval='operator-approved', chain_dp_epsilon_m=0.03)
    assert len(prepared.samples) > 100
    assert len(route.occurrences) == 4


def test_exported_walls_within_one_cell():
    """End-to-end contract on a supported map: no wall gains >= 1 cell.

    Samples every exported occurrence wall densely and measures depth
    inside occupied space via the distance transform of the UNDILATED
    reference mask. Single-pixel rounding on diagonal stair-steps reads
    up to sqrt(2) ~= 1.41 px without any annexation (measured: 2.2% of
    samples above 1.0 px, none above 1.42 on the test map); anything
    deeper is a contract violation.
    """
    import cv2
    from global_planner.annotation_core import _loop_reference_mask
    track_map = TrackMap(MAPS / 'test/test.yaml')
    outer, inner = extract_boundaries(track_map)
    payload, route, prepared, info = build_and_validate(
        track_map, outer, inner, _midline_seed(outer, inner),
        approval='operator-approved')
    ref = _loop_reference_mask(track_map, outer, inner)
    dt_occ = cv2.distanceTransform((ref == 0).astype(np.uint8),
                                   cv2.DIST_L2, 3)
    worst = 0.0
    for occ in payload['occurrences']:
        for chain in (occ['left'], occ['right']):
            pts = np.asarray([[track_map.world_to_pixel(p)[0],
                               track_map.world_to_pixel(p)[1]]
                              for p in chain], float)
            segs = np.linalg.norm(np.diff(pts, axis=0), axis=1)
            total = segs.sum()
            steps = max(2, int(total / 0.5))
            frac = np.linspace(0.0, 1.0, steps)
            cum = np.concatenate([[0.0], np.cumsum(segs)])
            for f in frac:
                d = f * total
                j = min(int(np.searchsorted(cum, d, side='right')) - 1,
                        len(pts) - 2)
                t = 0.0 if cum[j + 1] <= cum[j] else (
                    (d - cum[j]) / (cum[j + 1] - cum[j]))
                u, v = pts[j] + t * (pts[j + 1] - pts[j])
                ui, vi = int(round(u)), int(round(v))
                if 0 <= vi < dt_occ.shape[0] and 0 <= ui < dt_occ.shape[1]:
                    worst = max(worst, float(dt_occ[vi, ui]))
    assert worst <= 1.5, f'wall gains {worst:.2f} px of occupied space'


def test_endcaps_exact_and_shared():
    """Occurrence portals share exact endpoints (repin is identity)."""
    track_map = TrackMap(MAPS / 'test/test.yaml')
    outer, inner = extract_boundaries(track_map)
    payload, _, _, _ = build_and_validate(
        track_map, outer, inner, suggest_route(outer, inner),
        approval='operator-approved')
    occurrences = payload['occurrences']
    assert len(occurrences) == 4
    assert max(len(o['left']) + len(o['right'])
               for o in occurrences) < 512
    for k, occ in enumerate(occurrences):
        nxt = occurrences[(k + 1) % len(occurrences)]
        gate = payload['transitions'][k]['gate']
        assert occ['left'][-1] == nxt['left'][0]
        assert occ['right'][-1] == nxt['right'][0]
        assert gate == [occ['right'][-1], occ['left'][-1]]


def test_node_headless_configuration(tmp_path):
    """The ROS adapter fails fast without dirs and bounds its seen-set."""
    from global_planner import annotation_node as node_mod
    assert node_mod.rclpy is None  # headless env: documents the ROS blocker
    with pytest.raises(AnnotationError, match='maps directory not found'):
        node_mod.AnnotationNode(maps_dir='/nonexistent-dir-xyz',
                                out_dir=str(tmp_path))
    node = node_mod.AnnotationNode(maps_dir=str(MAPS), out_dir=str(tmp_path))
    for i in range(node._SEEN_CAP + 100):
        node._remember(f'id-{i}')
    assert len(node._seen) <= node._SEEN_CAP


def test_server_open_confines_map_paths(backend, tmp_path):
    """Absolute paths, ``..`` escapes and symlink escapes are refused;
    nested relative map directories keep working."""
    import shutil
    server = backend
    for bad in ('/etc/hostname', '../maps/test', '..', '', 'test/../../x'):
        with pytest.raises(AnnotationError, match='escapes|nonempty|not found'):
            server.op_open({'map': bad})
    # Symlink escape: a maps-dir entry pointing outside must not open.
    linkdir = tmp_path / 'maps'
    linkdir.mkdir(parents=True)
    (linkdir / 'evil').symlink_to('/etc', target_is_directory=True)
    server.configure(str(linkdir), str(tmp_path / 'out2'))
    with pytest.raises(AnnotationError, match='escapes|not found'):
        server.op_open({'map': 'evil/hostname'})
    # Nested legitimate layout keeps working: nest/sub/sub.yaml.
    nest = linkdir / 'nest' / 'sub'
    nest.mkdir(parents=True)
    shutil.copy(MAPS / 'test' / 'test.png', nest / 'test.png')
    shutil.copy(MAPS / 'test' / 'test.yaml', nest / 'sub.yaml')
    res = server.op_open({'map': 'nest/sub'})
    assert res['status'] == 'PASS'
    assert server.STATE['map'].png_path.name == 'test.png'


def test_server_update_bounds_points(backend):
    """Oversized, non-finite and malformed point data is rejected early."""
    server = backend
    server.op_open({'map': 'test'})
    with pytest.raises(AnnotationError, match='limit 20000'):
        server.op_update({'field': 'route_px',
                          'value': [[0.0, 0.0]] * 20001})
    with pytest.raises(AnnotationError, match='limit 20000'):
        server.op_update({'field': 'boundary_strokes_px',
                          'value': [[[0.0, 0.0]] * 20001]})
    for bad_pt in ([float('nan'), 0.0], [0.0, float('inf')],
                   ['x', 0.0], [True, 0.0], [0.0, 0.0, 0.0], 'xy',
                   [1e7, 0.0]):
        with pytest.raises(AnnotationError, match='finite'):
            server.op_update({'field': 'route_px',
                              'value': [[0.0, 0.0], [1.0, 1.0], bad_pt]})
    with pytest.raises(AnnotationError, match='point lists'):
        server.op_update({'field': 'boundary_strokes_px',
                          'value': ['not-a-stroke']})
    # Tuples are accepted as pairs; the boundary case stays valid.
    ok = server.op_update({'field': 'route_px',
                           'value': [(0.0, 0.0), (1.0, 1.0), (2.0, 0.0)]})
    assert ok['status'] == 'PASS'


def test_http_malformed_and_oversized_bodies(backend):
    """Malformed JSON, non-object bodies and oversized posts get
    structured FAIL/413 replies instead of killing the connection."""
    import http.client
    import threading
    from http.server import HTTPServer
    from global_planner.annotation_server import Handler, MAX_BODY_BYTES
    server = backend
    httpd = HTTPServer(('127.0.0.1', 0), Handler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.handle_request)
    thread.start()
    try:
        conn = http.client.HTTPConnection('127.0.0.1', port, timeout=30)
        conn.request('POST', '/api/session/state', body=b'{not json',
                     headers={'Content-Type': 'application/json'})
        resp = conn.getresponse()
        assert resp.status == 400
        assert json.loads(resp.read())['status'] == 'FAIL'
    finally:
        thread.join(timeout=30)

    def one_post(body, path='/api/session/state'):
        httpd2_thread = threading.Thread(target=httpd.handle_request)
        httpd2_thread.start()
        try:
            conn = http.client.HTTPConnection('127.0.0.1', port, timeout=30)
            conn.request('POST', path, body=body,
                         headers={'Content-Type': 'application/json'})
            resp = conn.getresponse()
            return resp.status, resp.read()
        finally:
            httpd2_thread.join(timeout=30)

    status, raw = one_post(b'[1, 2, 3]')
    assert status == 400
    assert json.loads(raw)['status'] == 'FAIL'
    status, raw = one_post(b'x' * (MAX_BODY_BYTES + 1))
    assert status == 413
    assert json.loads(raw)['status'] == 'FAIL'
    httpd.server_close()


def _copy_same_stem_map(tmp_path, dirname, tag):
    """Copy the test map to <maps>/<dirname>/same/same.{png,yaml}.

    The PNG bytes differ per tag (PIL text chunk; pixels untouched, so
    extraction/strict behavior is unchanged) while the stem is
    identical, reproducing the same-stem collision deterministically.
    """
    import shutil
    from PIL import Image, PngImagePlugin
    d = tmp_path / 'maps' / dirname / 'same'
    d.mkdir(parents=True)
    img = Image.open(MAPS / 'test' / 'test.png')
    info = PngImagePlugin.PngInfo()
    info.add_text('same-stem-tag', tag)
    img.save(d / 'same.png', pnginfo=info)
    (d / 'same.yaml').write_text(
        (MAPS / 'test/test.yaml').read_text(encoding='utf-8')
        .replace('test.png', 'same.png'), encoding='utf-8')


def _open_save_cycle(server, name, route):
    server.op_open({'map': name})
    server.op_update({'field': 'route_px', 'value': route})
    return server.op_save({})


def test_same_stem_maps_do_not_collide(backend, tmp_path):
    """Two distinct maps sharing one PNG stem keep independent artifacts."""
    import os
    server = backend
    _copy_same_stem_map(tmp_path, 'c1', 'first')
    _copy_same_stem_map(tmp_path, 'c2', 'second')
    server.configure(str(tmp_path / 'maps'), str(tmp_path / 'out'))
    track1 = TrackMap(tmp_path / 'maps/c1/same/same.yaml')
    track2 = TrackMap(tmp_path / 'maps/c2/same/same.yaml')
    assert track1.sha256 != track2.sha256
    assert map_namespace(track1) != map_namespace(track2)
    route1 = _midline_seed(*extract_boundaries(track1))
    route2 = _midline_seed(*extract_boundaries(track2))
    # Independent drafts.
    _open_save_cycle(server, 'c1/same', route1)
    _open_save_cycle(server, 'c2/same', route2)
    drafts = sorted(os.listdir(str(tmp_path / 'out')))
    assert drafts == sorted([draft_name(track1), draft_name(track2)])
    assert 'same_annotation.json' not in drafts
    # Reload retrieves the correct draft for each map.
    assert server.op_open({'map': 'c1/same'})['message'] == \
        'reopened saved draft'
    assert server.STATE['session']['route_px'] == route1
    assert server.op_open({'map': 'c2/same'})['message'] == \
        'reopened saved draft'
    assert server.STATE['session']['route_px'] == route2
    # Independent exports: both files survive with distinct content.
    for name in ('c1/same', 'c2/same'):
        server.op_open({'map': name})
        prev = server.op_preview({})
        server.op_approve({'approval_digest': prev['candidate_digest']})
        server.op_export({})
    exports = sorted(os.listdir(str(tmp_path / 'out')))
    assert export_name(track1) in exports
    assert export_name(track2) in exports
    assert 'same_legal_route.json' not in exports
    assert 'legal_route.json' not in exports
    e1 = (tmp_path / 'out' / export_name(track1)).read_bytes()
    e2 = (tmp_path / 'out' / export_name(track2)).read_bytes()
    assert e1 != e2


def test_legacy_draft_migrates_without_loss(backend, tmp_path):
    """A bare-stem draft is validated, then adopted under the new name."""
    server = backend
    server.op_open({'map': 'test'})
    track_map = server.STATE['map']
    legacy = Path(server.STATE['out_dir']) / 'test_annotation.json'
    save_session(server.STATE['session'], legacy)
    before = legacy.read_bytes()
    # Simulate a restart: drop in-memory state, reopen from disk.
    server.STATE.update(map=None, session=None, extraction=None,
                        candidate_digest=None)
    msg = server.op_open({'map': 'test'})['message']
    assert msg.startswith('reopened legacy draft (adopted as ')
    # Adoption copies forward; the legacy file is never destroyed here.
    assert legacy.read_bytes() == before
    assert (Path(server.STATE['out_dir'])
            / draft_name(track_map)).exists()
    # The namespaced draft is preferred on the next open.
    server.STATE.update(map=None, session=None, extraction=None,
                        candidate_digest=None)
    assert server.op_open({'map': 'test'})['message'] == 'reopened saved draft'
    # Saves go to the new name; the legacy bytes are untouched.
    server.op_save({})
    assert legacy.read_bytes() == before


def test_legacy_mid_scheme_draft_adopted(backend, tmp_path):
    """The previous parent__stem__sha8 scheme resolves through the chain."""
    from global_planner.annotation_core import _legacy_draft_names
    server = backend
    server.op_open({'map': 'test'})
    track_map = server.STATE['map']
    mid = Path(server.STATE['out_dir']) / _legacy_draft_names(track_map)[0]
    assert mid.name != draft_name(track_map)
    save_session(server.STATE['session'], mid)
    before = mid.read_bytes()
    server.STATE.update(map=None, session=None, extraction=None,
                        candidate_digest=None)
    msg = server.op_open({'map': 'test'})['message']
    assert msg.startswith('reopened legacy draft (adopted as ')
    assert mid.read_bytes() == before
    assert (Path(server.STATE['out_dir'])
            / draft_name(track_map)).exists()


def _copy_twin_map(tmp_path, dirname, resolution):
    """Copy the test PNG bytes verbatim with a different YAML resolution."""
    import re
    import shutil
    d = tmp_path / 'maps' / dirname / 'twin'
    d.mkdir(parents=True)
    shutil.copy(MAPS / 'test/test.png', d / 'twin.png')
    yaml_text = (MAPS / 'test/test.yaml').read_text(encoding='utf-8')
    yaml_text = yaml_text.replace('test.png', 'twin.png')
    yaml_text = re.sub(r'resolution: .*', f'resolution: {resolution}',
                       yaml_text)
    (d / 'twin.yaml').write_text(yaml_text, encoding='utf-8')


def test_same_png_bytes_different_yaml_no_collision(backend, tmp_path):
    """Identical PNG bytes under different YAML readings stay independent.

    Same stem, same bytes, same parent name, different resolution: the
    drafts must not share a slot, and a legacy file written for one
    reading must fail closed (never rebound) for the other.
    """
    import os
    server = backend
    _copy_twin_map(tmp_path, 'r1', '0.05')
    _copy_twin_map(tmp_path, 'r2', '0.06')
    server.configure(str(tmp_path / 'maps'), str(tmp_path / 'out'))
    track1 = TrackMap(tmp_path / 'maps/r1/twin/twin.yaml')
    track2 = TrackMap(tmp_path / 'maps/r2/twin/twin.yaml')
    assert track1.sha256 == track2.sha256
    assert map_namespace(track1) != map_namespace(track2)
    route = [[100, 100], [200, 100], [200, 200]]
    _open_save_cycle(server, 'r1/twin', route)
    _open_save_cycle(server, 'r2/twin', [[300, 300], [400, 300], [400, 400]])
    drafts = sorted(os.listdir(str(tmp_path / 'out')))
    assert drafts == sorted([draft_name(track1), draft_name(track2)])
    assert server.op_open({'map': 'r1/twin'})['message'] == \
        'reopened saved draft'
    assert server.STATE['session']['route_px'] == route
    # A bare-stem legacy draft written for reading 1 must fail closed
    # for reading 2 (resolution differs) and be left untouched.
    legacy = Path(server.STATE['out_dir']) / 'twin_annotation.json'
    save_session(server.STATE['session'], legacy)
    before = legacy.read_bytes()
    # Drop reading 2's own draft so the legacy fallback is exercised.
    (Path(server.STATE['out_dir']) / draft_name(track2)).unlink()
    server.STATE.update(map=None, session=None, extraction=None,
                        candidate_digest=None)
    with pytest.raises(AnnotationError, match='resolution differs'):
        server.op_open({'map': 'r2/twin'})
    assert legacy.read_bytes() == before
    assert not (Path(server.STATE['out_dir'])
                / draft_name(track2)).exists()


def test_atomic_write_text_cleans_tmp_on_failure(tmp_path, monkeypatch):
    """A failed replace never leaves a partial file or a stray tmp file."""
    import os
    target = tmp_path / 'out.json'
    target.write_text('{"v": 1}', encoding='utf-8')
    def _boom(*args):
        raise OSError('simulated replace failure')
    monkeypatch.setattr(os, 'replace', _boom)
    with pytest.raises(OSError, match='simulated replace failure'):
        atomic_write_text(target, '{"v": 2}')
    assert target.read_text(encoding='utf-8') == '{"v": 1}'
    assert list(tmp_path.glob('out.json.tmp-*')) == []


