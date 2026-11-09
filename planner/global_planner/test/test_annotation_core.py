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
    AnnotationError, TrackMap, build_and_validate, check_session_map,
    extract_boundaries, geometry_digest, load_session, new_session,
    patched_free_mask, require_approved, ridge_seed, save_session)
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
        os.path.join(server.STATE['out_dir'], 'legal_route.json'))
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
        os.path.join(server.STATE['out_dir'], 'legal_route.json'))


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
    assert (out / 'legal_route.json').exists()
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
    assert not (out / 'legal_route.json').exists()
    # Preview is read-only: prints the candidate digest, writes nothing.
    assert tool.main(['preview', '--map', str(track_map.yaml_path),
                      '--session', str(session_path),
                      '--out', str(out)]) == 0
    assert not (out / 'legal_route.json').exists()
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
    assert (out / 'legal_route.json').exists()
    payload = _json.loads((out / 'legal_route.json').read_text())
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
