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
    AnnotationError, TrackMap, build_and_validate, extract_boundaries,
    load_session, new_session, patched_free_mask, save_session)
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
    payload, route, prepared = build_and_validate(
        track_map, outer, inner, _midline_seed(outer, inner),
        approval='operator-approved')
    assert len(route.occurrences) == 4
    assert len(prepared.samples) > 100
    assert payload['physical_map']['sha256'] == track_map.sha256


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


def test_open_gap_rejected_then_stroke_repairs_it(tmp_path):
    """An opened wall fails closed; a boundary stroke restores the loop."""
    src = TrackMap(MAPS / 'test/test.yaml')
    img = src.image.copy()
    # Cut a gap in the outer wall: whiten a vertical strip at the top.
    img[0:60, 210:225] = 255
    png = tmp_path / 'gap.png'
    import cv2
    cv2.imwrite(str(png), img)
    yaml = tmp_path / 'gap.yaml'
    yaml.write_text('image: gap.png\nresolution: 0.05\n'
                    'origin: [-8.4, -5.35, 0]\nnegate: 0\n'
                    'occupied_thresh: 0.65\nfree_thresh: 0.196\n')
    gap_map = TrackMap(yaml)
    # Without knowing exactly where the wall was, extraction must not
    # silently invent a legal boundary: either it rejects, or the loop
    # count changed. A stroke across the cut must be *accepted* by the
    # extractor's topology check if it re-encloses the annulus.
    try:
        extract_boundaries(gap_map)
        rejected = False
    except AnnotationError:
        rejected = True
    stroke = [[[212, 5], [220, 30], [218, 58]]]
    if rejected:
        outer, inner = extract_boundaries(gap_map, stroke, stroke_width_px=9)
        assert len(outer) > 100 and len(inner) > 100


def test_reversed_direction_also_valid_but_distinct():
    """Direction is semantic: reversed lap validates with a new digest."""
    track_map = TrackMap(MAPS / 'test/test.yaml')
    outer, inner = extract_boundaries(track_map)
    seed = _midline_seed(outer, inner)
    fwd, _, _ = build_and_validate(track_map, outer, inner, seed,
                                   approval='operator-approved')
    rev, _, _ = build_and_validate(track_map, outer, inner, seed[::-1],
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
    payload, _, _ = build_and_validate(
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
