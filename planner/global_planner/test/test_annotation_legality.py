# Copyright 2026 ForzaETH
"""Adversarial legality tests: exact cell-square containment.

The contract under test (see LEGALITY.md): the union of emitted
section polygons lies within the closed squares of the selected
legal cells - zero annexed area, boundary contact allowed. The
oracle below measures that with its own run-length rectangle union
(not the production checker), so generator and checker cannot share
a blind spot. Cases split into checker-only false-acceptance
regressions (hand-mutated payloads), generator-reachable geometry
(real strokes on synthetic and real maps), and primitive semantics.
"""
import sys
import time
from pathlib import Path

import numpy as np
import pytest
import shapely
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

sys.path.insert(0, str(Path(__file__).parents[1]))

from global_planner.annotation_core import (  # noqa: E402
    AnnotationError, TrackMap, _annexation, _ear_annexed_m2,
    build_candidate, build_route, check_payload, effective_free_mask,
    extract_boundaries, new_session, patched_free_mask)

MAPS = Path(__file__).parents[3] / 'stack_master' / 'maps'
BAKU_CUTS = [[[316.0, 584.0], [284.0, 482.0]],
             [[201.0, 294.0], [319.0, 298.0]],
             [[362.0, 187.0], [309.0, 81.0]],
             [[100.0, 308.0], [190.0, 297.0]]]
BAKU_SEED = [179, 25]


def _legal_union(track_map, mask):
    """Oracle legal region: row run-length rectangles, unioned."""
    res = track_map.resolution
    rects = []
    for v in range(track_map.height):
        row = mask[v] > 0
        if not row.any():
            continue
        edges = np.flatnonzero(np.diff(
            np.concatenate(([0], row.view(np.int8), [0]))))
        y_c = track_map.origin[1] + (track_map.height - 1 - v) * res
        for u0, u1 in zip(edges[0::2], edges[1::2]):
            rects.append(box(track_map.origin[0] + (u0 - 0.5) * res,
                             y_c - res / 2,
                             track_map.origin[0] + (u1 - 0.5) * res,
                             y_c + res / 2))
    return unary_union(rects)


def _oracle(track_map, payload, legal):
    """(illegal area, road area) of the payload against legal squares."""
    union = unary_union(
        [Polygon(list(s['right']) + list(reversed(s['left'])))
         for s in payload['sections']])
    return union.difference(_legal_union(track_map, legal)).area, union


def _midline(outer, inner, count=120):
    step = max(1, len(outer) // count)
    return [((p + inner[int(np.argmin(
        np.linalg.norm(inner - p, axis=1)))]) / 2).tolist()
        for p in outer[::step]]


def _candidate(track_map, strokes=(), seed=None, width=5, guide='midline',
               **session_kw):
    session = new_session(track_map)
    session['boundary_strokes_px'] = [list(map(list, s)) for s in strokes]
    session['stroke_width_px'] = width
    session['retained_region_px'] = seed
    session.update(session_kw)
    outer, inner = extract_boundaries(track_map, strokes, width, seed)
    if guide == 'suggest':
        from global_planner.annotation_core import suggest_route
        session['route_px'] = suggest_route(outer, inner)
    else:
        session['route_px'] = _midline(outer, inner)
    payload, route, receipt, _ = build_candidate(track_map, session)
    legal = effective_free_mask(track_map, strokes, width, seed)
    return payload, route, receipt, legal


def _write_map(tmp_path, image, name='syn.png', resolution=0.05):
    import cv2
    cv2.imwrite(str(tmp_path / name), image)
    yaml = tmp_path / (Path(name).stem + '.yaml')
    yaml.write_text(
        f'image: {name}\nresolution: {resolution}\n'
        'origin: [0.0, 0.0, 0]\nnegate: 0\n'
        'occupied_thresh: 0.65\nfree_thresh: 0.196\n')
    return TrackMap(yaml)


def _annulus(tmp_path, size=400, resolution=0.05, name='annulus.png'):
    """Binary square annulus: white ring, black infield and surround.

    400 px at the default guide spacing gives the joint placement
    enough seed samples to quarter the lap (small maps legitimately
    fail that upstream of any legality question).
    """
    import cv2
    img = np.zeros((size, size), np.uint8)
    lo, hi = round(0.1 * size), round(0.9 * size)
    ilo, ihi = round(0.35 * size), round(0.65 * size)
    cv2.rectangle(img, (lo, lo), (hi, hi), 255, -1)
    cv2.rectangle(img, (ilo, ilo), (ihi, ihi), 0, -1)
    return _write_map(tmp_path, img, name=name, resolution=resolution)


def _diamond_ring(tmp_path, size=480, resolution=0.05):
    """Diamond annulus: every wall is a 45-degree raster staircase."""
    import cv2
    img = np.zeros((size, size), np.uint8)
    c = size // 2
    o_off, i_off = round(0.06 * size), round(0.27 * size)
    outer = np.array([[c, o_off], [size - o_off, c],
                      [c, size - o_off], [o_off, c]])
    inner = np.array([[c, i_off], [size - i_off, c],
                      [c, size - i_off], [i_off, c]])
    cv2.fillPoly(img, [outer], 255)
    cv2.fillPoly(img, [inner], 0)
    return _write_map(tmp_path, img, name='diamond.png',
                      resolution=resolution)


# ----------------------------------------------------------------------
# Independent oracle on real maps and real corner cuts
# ----------------------------------------------------------------------

@pytest.mark.parametrize('name', ['test/test', 'baku/baku',
                                  'spa/spa', 'zuri/zuri'])
def test_real_maps_annex_exactly_zero(name):
    track_map = TrackMap(MAPS / f'{name}.yaml')
    payload, _, receipt, legal = _candidate(track_map)
    illegal, _ = _oracle(track_map, payload, legal)
    assert illegal <= 1e-9  # exact zero, up to GEOS overlay residue
    assert receipt['stages']['vector_legal']['annexed_m2'] == 0.0


@pytest.mark.parametrize('cuts', [BAKU_CUTS[:1], BAKU_CUTS])
def test_baku_cuts_excluded_pockets_stay_excluded(cuts):
    """Cut pockets are preserved exactly: zero overlap, not ~zero."""
    track_map = TrackMap(MAPS / 'baku/baku.yaml')
    payload, _, _, legal = _candidate(track_map, cuts, BAKU_SEED)
    illegal, road = _oracle(track_map, payload, legal)
    assert illegal <= 1e-9  # exact zero, up to GEOS overlay residue
    patched = patched_free_mask(track_map, cuts, 5)
    pocket = ((patched > 0) & (legal == 0)).astype(np.uint8) * 255
    assert (pocket > 0).sum() > 500 * len(cuts)
    assert road.intersection(_legal_union(track_map, pocket)).area <= 1e-9


def test_diagonal_staircase_ring_exact(tmp_path):
    """45-degree walls: the dominant real-map annexation source under
    the old gate must now be exactly zero without losing the track."""
    track_map = _diamond_ring(tmp_path)
    payload, _, _, legal = _candidate(track_map, guide='suggest')
    illegal, road = _oracle(track_map, payload, legal)
    assert illegal <= 1e-9  # exact zero, up to GEOS overlay residue
    legal_area = (legal > 0).sum() * track_map.resolution ** 2
    assert road.area > 0.85 * legal_area


@pytest.mark.parametrize('width', [1, 3, 13])
def test_corner_cut_gap_widths_preserved(tmp_path, width):
    """Excluded corner pockets behind 1/3/13-px occupied bands (the
    stroke itself) are never bridged by exported geometry."""
    track_map = _annulus(tmp_path)
    cut = [[[40.0, 120.0], [120.0, 40.0]]]
    try:
        payload, _, _, legal = _candidate(
            track_map, cut, seed=[200, 340], width=width, guide='suggest')
    except AnnotationError:
        # A 1-px diagonal stroke leaves a checkerboard of pinholes
        # along its staircase; extraction fails closed on topology.
        # That is acceptable: it must never silently build instead.
        assert width == 1
        return
    illegal, road = _oracle(track_map, payload, legal)
    assert illegal <= 1e-9  # exact zero, up to GEOS overlay residue
    patched = patched_free_mask(track_map, cut, width)
    pocket = ((patched > 0) & (legal == 0)).astype(np.uint8) * 255
    if width > 1:
        # A 1-px diagonal stroke leaks under 8-connectivity (free cells
        # touch at stroke corners), so no pocket forms at width 1;
        # wider bands separate it and it must stay excluded exactly.
        assert (pocket > 0).any()
    if (pocket > 0).any():
        assert road.intersection(
            _legal_union(track_map, pocket)).area <= 1e-9


def test_tooth_on_wall_survives(tmp_path):
    """A short stroke tooth protruding from the inner wall into the
    road: the wall must detour around it, not simplify through it."""
    track_map = _annulus(tmp_path)
    # Inner wall of the bottom arm is v=260; tooth reaches down to 290.
    tooth = [[[200.0, 262.0], [200.0, 290.0]]]
    payload, _, _, legal = _candidate(track_map, tooth, width=3,
                                      guide='suggest')
    illegal, _ = _oracle(track_map, payload, legal)
    assert illegal <= 1e-9  # exact zero, up to GEOS overlay residue
    tip = np.array(track_map.pixel_to_world((200, 290)))
    walls = [np.array(s[side]) for s in payload['sections']
             for side in ('left', 'right')]
    nearest = min(float(np.linalg.norm(w - tip, axis=1).min())
                  for w in walls)
    assert nearest < 3 * track_map.resolution  # wall hugs the tooth


def test_island_inside_road_fails_closed(tmp_path):
    """An occupied island fully inside the road makes the free region
    non-annular; extraction rejects instead of routing around it."""
    track_map = _annulus(tmp_path)
    with pytest.raises(AnnotationError):
        _candidate(track_map, [[[200.0, 310.0], [200.0, 312.0]]],
                   width=5)


def test_pinch_slit_never_annexes(tmp_path):
    """A stroke pinching the road to a slit: either the route builds
    with zero annexation or it fails closed - never a legal-looking
    payload over occupied space."""
    track_map = _annulus(tmp_path)
    pinch = [[[200.0, 262.0], [200.0, 352.0]]]
    try:
        payload, _, _, legal = _candidate(track_map, pinch, width=3,
                                          guide='suggest')
    except AnnotationError:
        return
    illegal, _ = _oracle(track_map, payload, legal)
    assert illegal <= 1e-9  # exact zero, up to GEOS overlay residue


@pytest.mark.parametrize('eps', [0.0, 0.02, 0.03])
def test_thinnings_all_exact(eps):
    """Every supported thinning is exact, including eps=0 (the ear-
    gated pre-filter alone must already guarantee containment)."""
    track_map = TrackMap(MAPS / 'baku/baku.yaml')
    payload, _, _, legal = _candidate(
        track_map, chain_dp_epsilon_m=eps)
    illegal, _ = _oracle(track_map, payload, legal)
    assert illegal <= 1e-9  # exact zero, up to GEOS overlay residue


@pytest.mark.parametrize('resolution', [0.02, 0.1])
def test_other_resolutions_exact(tmp_path, resolution):
    track_map = _annulus(tmp_path, resolution=resolution,
                         name=f'ann{int(resolution * 1000)}.png')
    strokes = [[[40.0, 120.0], [120.0, 40.0]]]
    legal = effective_free_mask(track_map, strokes, 5, [200, 340])
    outer, inner = extract_boundaries(track_map, strokes, 5, [200, 340])
    from global_planner.annotation_core import suggest_route
    payload, _ = build_route(
        track_map, outer, inner, suggest_route(outer, inner),
        legal_mask=legal, spacing_m=0.15,
        chain_dp_epsilon_m=0.5 * resolution)
    check_payload(payload, track_map, legal)
    illegal, _ = _oracle(track_map, payload, legal)
    assert illegal <= 1e-9  # exact zero, up to GEOS overlay residue



def _shift_outward(section, wall, mid, dist_m, half=2):
    """Move wall points around index mid away from the section centroid."""
    poly = Polygon(list(section['right']) + list(reversed(section['left'])))
    c = np.array([poly.centroid.x, poly.centroid.y])
    for i in range(max(1, mid - half), min(len(wall) - 1, mid + half + 1)):
        p = np.array(wall[i], float)
        d = p - c
        n = float(np.linalg.norm(d))
        if n > 0:
            wall[i] = (p + d / n * dist_m).tolist()

# ----------------------------------------------------------------------
# Checker false-acceptance regressions (hand-mutated payloads)
# ----------------------------------------------------------------------

def _baku_payload():
    track_map = TrackMap(MAPS / 'baku/baku.yaml')
    payload, _, _, legal = _candidate(track_map)
    return track_map, payload, legal


def test_checker_rejects_one_cell_island_coverage(tmp_path):
    """A payload covering a 1-cell occupied island must fail, however
    small: shift a wall run outward across one occupied cell."""
    track_map = _annulus(tmp_path)
    payload, _, _, legal = _candidate(track_map, guide='suggest')
    wall = payload['sections'][0]['left']
    mid = len(wall) // 2
    _shift_outward(payload['sections'][0], wall, mid,
                   1.2 * track_map.resolution)
    with pytest.raises(AnnotationError, match='VECTOR_LEGAL'):
        check_payload(payload, track_map, legal)


@pytest.mark.parametrize('shift_m', [0.005, 0.01, 0.049])
def test_checker_rejects_small_wall_shifts(shift_m):
    """Doc 22: +0.01..0.049 m wall shifts passed the old full pipeline.
    Any positive annexation now fails, at any depth."""
    track_map, payload, legal = _baku_payload()
    wall = payload['sections'][1]['left']
    mid = len(wall) // 2
    _shift_outward(payload['sections'][1], wall, mid, shift_m, half=3)
    with pytest.raises(AnnotationError, match='VECTOR_LEGAL'):
        check_payload(payload, track_map, legal)


def test_checker_rejects_restored_excluded_pocket():
    """Rebuilding the uncut walls over a cut session's legal mask
    (pocket restored) is exactly the silent-erosion failure mode."""
    track_map = TrackMap(MAPS / 'baku/baku.yaml')
    payload, _, _, _ = _candidate(track_map)
    cut_legal = effective_free_mask(track_map, BAKU_CUTS, 5, BAKU_SEED)
    with pytest.raises(AnnotationError, match='VECTOR_LEGAL'):
        check_payload(payload, track_map, cut_legal)


# ----------------------------------------------------------------------
# Primitive semantics: boundary contact, spikes, collinear ears
# ----------------------------------------------------------------------

def _one_island_map(tmp_path):
    """20x20 all-free map with one occupied cell at (10, 10)."""
    img = np.full((20, 20), 255, np.uint8)
    img[10, 10] = 0
    return _write_map(tmp_path, img, name='island.png')


def test_annexation_primitive_semantics(tmp_path):
    track_map = _one_island_map(tmp_path)
    legal = effective_free_mask(track_map, [], 5)
    occupied = legal == 0
    res = track_map.resolution
    cx, cy = track_map.pixel_to_world((10, 10))  # the occupied cell

    def annexed(poly):
        area, _ = _annexation(poly, track_map, occupied)
        return area

    # Exactly the neighbouring free square: edge contact only.
    free_sq = box(cx + res / 2, cy - res / 2, cx + 3 * res / 2, cy + res / 2)
    assert annexed(free_sq) == 0.0
    # Exactly the occupied square.
    occ_sq = box(cx - res / 2, cy - res / 2, cx + res / 2, cy + res / 2)
    assert annexed(occ_sq) == pytest.approx(res ** 2)
    # A spike 0.99 cells into the occupied square.
    spike = box(cx + res / 2 - 0.99 * res, cy - res / 4,
                cx + res / 2, cy + res / 4)
    assert annexed(spike) == pytest.approx(0.99 * res * res / 2)
    # A hair past the boundary is already positive.
    hair = box(cx + res / 2 - 1e-6, cy - res / 4,
               cx + res / 2, cy + res / 4)
    assert 0.0 < annexed(hair) < 1e-6


def test_ear_primitive_diagonal_and_collinear(tmp_path):
    """Diagonal staircase ears annex >0 (chord must be rejected);
    exactly collinear subchains have zero ear area."""
    track_map = _diamond_ring(tmp_path)
    legal = effective_free_mask(track_map, [], 5)
    occupied = legal == 0
    outer, inner = extract_boundaries(track_map)
    # Some long diagonal window must annex staircase corners (the
    # chord the gate exists to reject); adjacent points never annex.
    found = False
    for chain in (outer, inner):
        pts = [np.array(track_map.pixel_to_world(p)) for p in chain]
        assert _ear_annexed_m2(pts, 10, 11, track_map, occupied) == 0.0
        for start in range(0, len(pts) - 40, 20):
            if _ear_annexed_m2(pts, start, start + 40,
                               track_map, occupied) > 0.0:
                found = True
    assert found
    line = [np.array([float(k), 0.0]) for k in range(6)]
    assert _ear_annexed_m2(line, 0, 5, track_map, occupied) == 0.0


def test_baku_build_stays_fast_enough_for_preview():
    """Performance guard: full candidate (build + exact checks) on
    the largest real map stays in interactive-preview territory."""
    track_map = TrackMap(MAPS / 'baku/baku.yaml')
    start = time.time()
    _candidate(track_map)
    assert time.time() - start < 6.0
