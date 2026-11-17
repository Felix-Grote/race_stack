# Copyright 2026 ForzaETH
"""Legality oracle tests: exported road annexes exactly zero.

The contract (see LEGALITY.md): the union of emitted section polygons
lies within the closed squares of the selected legal cells — zero
annexed area, boundary contact allowed. The oracle below measures
that with its own run-length rectangle union (not the production
checker), so generator and checker cannot share a blind spot.
"""
import sys
from pathlib import Path

import numpy as np
import pytest
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

sys.path.insert(0, str(Path(__file__).parents[1]))

from conftest import MAPS, midline_seed, write_map  # noqa: E402
from global_planner.annotation_core import (  # noqa: E402
    AnnotationError, TrackMap, build_candidate, build_route,
    check_payload, effective_free_mask, extract_boundaries, new_session,
    patched_free_mask, suggest_route)
from global_planner.route.manifest import validate_route  # noqa: E402

BAKU_CUTS = [[[316.0, 584.0], [284.0, 482.0]],
             [[201.0, 294.0], [319.0, 298.0]],
             [[362.0, 187.0], [309.0, 81.0]],
             [[100.0, 308.0], [190.0, 297.0]]]
BAKU_SEED = [179, 25]
GLC_SEED = [54, 383]


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
    """(illegal area, road union) of the payload against legal squares."""
    union = unary_union(
        [Polygon(list(s['right']) + list(reversed(s['left'])))
         for s in payload['sections']])
    return union.difference(_legal_union(track_map, legal)).area, union


def _candidate(track_map, strokes=(), seed=None, width=5, guide='midline',
               **session_kw):
    session = new_session(track_map)
    session['boundary_strokes_px'] = [list(map(list, s)) for s in strokes]
    session['stroke_width_px'] = width
    session['retained_region_px'] = seed
    session.update(session_kw)
    outer, inner = extract_boundaries(track_map, strokes, width, seed)
    if guide == 'suggest':
        guide_pts = suggest_route(outer, inner)
        session['route_px'] = guide_pts + [guide_pts[0]]  # completed lap
    else:
        session['route_px'] = midline_seed(outer, inner)
    payload, route, receipt, _ = build_candidate(track_map, session)
    legal = effective_free_mask(track_map, strokes, width, seed)
    return payload, route, receipt, legal


def _annulus(tmp_path, size=400, name='annulus.png'):
    """Binary square annulus large enough for joint placement."""
    import cv2
    img = np.zeros((size, size), np.uint8)
    lo, hi = round(0.1 * size), round(0.9 * size)
    ilo, ihi = round(0.35 * size), round(0.65 * size)
    cv2.rectangle(img, (lo, lo), (hi, hi), 255, -1)
    cv2.rectangle(img, (ilo, ilo), (ihi, ihi), 0, -1)
    return write_map(tmp_path, img, name=name)


def _diamond(tmp_path, size=480):
    """Diamond annulus: every wall is a 45-degree raster staircase."""
    import cv2
    img = np.zeros((size, size), np.uint8)
    c = size // 2
    o_off, i_off = round(0.06 * size), round(0.27 * size)
    cv2.fillPoly(img, [np.array([[c, o_off], [size - o_off, c],
                                 [c, size - o_off], [o_off, c]])], 255)
    cv2.fillPoly(img, [np.array([[c, i_off], [size - i_off, c],
                                 [c, size - i_off], [i_off, c]])], 0)
    return write_map(tmp_path, img, name='diamond.png')


@pytest.mark.parametrize('name,seed', [
    ('test/test', None), ('baku/baku', None), ('spa/spa', None),
    ('zuri/zuri', None), ('GLC_smile_small/GLC_smile_small', None),
    ('glc_ot_ez/glc_ot_ez', GLC_SEED),
    ('hangar_1905_v0/hangar_1905_v0', None)])
def test_real_maps_annex_exactly_zero(name, seed):
    """Every supported real map (binary and grayscale) exports legally."""
    track_map = TrackMap(MAPS / f'{name}.yaml')
    session_seed = seed
    payload, _, receipt, legal = _candidate(track_map, seed=session_seed)
    illegal, _ = _oracle(track_map, payload, legal)
    assert illegal <= 1e-9  # exact zero, up to GEOS overlay residue
    assert receipt['stages']['vector_legal']['annexed_m2'] == 0.0


@pytest.mark.parametrize('cuts', [BAKU_CUTS[:1], BAKU_CUTS])
def test_baku_cuts_excluded_pockets_stay_excluded(cuts):
    """Cut pockets are preserved exactly: zero overlap, not ~zero."""
    track_map = TrackMap(MAPS / 'baku/baku.yaml')
    payload, _, _, legal = _candidate(track_map, cuts, BAKU_SEED)
    illegal, road = _oracle(track_map, payload, legal)
    assert illegal <= 1e-9
    patched = patched_free_mask(track_map, cuts, 5)
    pocket = ((patched > 0) & (legal == 0)).astype(np.uint8) * 255
    assert (pocket > 0).sum() > 500 * len(cuts)
    assert road.intersection(_legal_union(track_map, pocket)).area <= 1e-9


def test_diagonal_staircase_ring_exact(tmp_path):
    """45-degree walls: exactly zero annexation without losing the track."""
    track_map = _diamond(tmp_path)
    payload, _, _, legal = _candidate(track_map, guide='suggest')
    illegal, road = _oracle(track_map, payload, legal)
    assert illegal <= 1e-9
    legal_area = (legal > 0).sum() * track_map.resolution ** 2
    assert road.area > 0.85 * legal_area


@pytest.mark.parametrize('width', [3, 13])
def test_corner_cut_gap_widths_preserved(tmp_path, width):
    """Excluded pockets behind occupied stroke bands are never bridged."""
    track_map = _annulus(tmp_path)
    cut = [[[40.0, 120.0], [120.0, 40.0]]]
    payload, _, _, legal = _candidate(
        track_map, cut, seed=[200, 340], width=width, guide='suggest')
    illegal, road = _oracle(track_map, payload, legal)
    assert illegal <= 1e-9
    patched = patched_free_mask(track_map, cut, width)
    pocket = ((patched > 0) & (legal == 0)).astype(np.uint8) * 255
    assert (pocket > 0).any()
    assert road.intersection(_legal_union(track_map, pocket)).area <= 1e-9


def test_tooth_on_wall_survives(tmp_path):
    """A stroke tooth protruding into the road: walls detour around it."""
    track_map = _annulus(tmp_path)
    tooth = [[[200.0, 262.0], [200.0, 290.0]]]
    payload, _, _, legal = _candidate(track_map, tooth, width=3,
                                      guide='suggest')
    illegal, _ = _oracle(track_map, payload, legal)
    assert illegal <= 1e-9
    tip = np.array(track_map.pixel_to_world((200, 290)))
    walls = [np.array(s[side]) for s in payload['sections']
             for side in ('left', 'right')]
    nearest = min(float(np.linalg.norm(w - tip, axis=1).min()) for w in walls)
    assert nearest < 3 * track_map.resolution  # wall hugs the tooth


def test_island_and_pinch_fail_closed(tmp_path):
    """Occupied island in the road rejects; a pinch never annexes."""
    track_map = _annulus(tmp_path)
    with pytest.raises(AnnotationError):
        _candidate(track_map, [[[200.0, 310.0], [200.0, 312.0]]], width=5)
    pinch = [[[200.0, 262.0], [200.0, 352.0]]]
    try:
        payload, _, _, legal = _candidate(track_map, pinch, width=3,
                                          guide='suggest')
    except AnnotationError:
        return  # failing closed is the other acceptable outcome
    illegal, _ = _oracle(track_map, payload, legal)
    assert illegal <= 1e-9


@pytest.mark.parametrize('eps', [0.0, 0.02, 0.03])
def test_thinnings_all_exact(eps):
    """Every supported thinning is exact, including eps=0."""
    track_map = TrackMap(MAPS / 'baku/baku.yaml')
    payload, _, _, legal = _candidate(track_map, chain_dp_epsilon_m=eps)
    illegal, _ = _oracle(track_map, payload, legal)
    assert illegal <= 1e-9


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


def test_checker_rejects_annexed_payloads(tmp_path):
    """Hand-mutated payloads covering occupied/excluded cells fail."""
    track_map = _annulus(tmp_path)
    payload, _, _, legal = _candidate(track_map, guide='suggest')
    wall = payload['sections'][0]['left']
    _shift_outward(payload['sections'][0], wall, len(wall) // 2,
                   1.2 * track_map.resolution)
    with pytest.raises(AnnotationError, match='VECTOR_LEGAL'):
        check_payload(payload, track_map, legal)
    # A 1 cm outward shift on a real map (the old silent-acceptance bug).
    baku = TrackMap(MAPS / 'baku/baku.yaml')
    payload, _, _, legal = _candidate(baku)
    wall = payload['sections'][1]['left']
    _shift_outward(payload['sections'][1], wall, len(wall) // 2, 0.01,
                   half=3)
    with pytest.raises(AnnotationError, match='VECTOR_LEGAL'):
        check_payload(payload, baku, legal)
    # Rebuilding uncut walls over a cut session's legal mask restores
    # the excluded pocket: exactly the silent-erosion failure mode.
    payload, _, _, _ = _candidate(baku)
    cut_legal = effective_free_mask(baku, BAKU_CUTS, 5, BAKU_SEED)
    with pytest.raises(AnnotationError, match='VECTOR_LEGAL'):
        check_payload(payload, baku, cut_legal)


def test_self_crossing_ear_measured_by_lobes(tmp_path):
    """A bowtie ear's signed area cancels; its lobes must not.

    Regression: measuring the ear as one signed polygon would report
    zero annexation for a self-crossing chord whose two lobes cover
    occupied cells. ``_ear_annexed_m2`` must measure both lobes.
    """
    from global_planner.annotation_core import _ear_annexed_m2, \
        _signed_area
    track_map = _annulus(tmp_path, size=200, name='ear.png')
    occupied = effective_free_mask(track_map, []) == 0
    # Bowtie over the occupied infield (world m, 200px * 0.05, origin 0):
    # lobes are the two triangles meeting at the centre.
    pts = [(3.0, 3.0), (7.0, 7.0), (7.0, 3.0), (3.0, 7.0)]
    assert _signed_area(pts + [pts[0]]) == pytest.approx(0.0, abs=1e-12)
    assert _ear_annexed_m2(pts, 0, 3, track_map, occupied) > 0.1
    # Same bowtie entirely inside free ring arm annexes nothing.
    free_pts = [(1.5, 7.5), (3.5, 8.5), (3.5, 7.5), (1.5, 8.5)]
    assert _ear_annexed_m2(free_pts, 0, 3, track_map, occupied) \
        == pytest.approx(0.0, abs=1e-9)


def test_generated_zone_contained_at_rotated_starts():
    """The generated start zone stays inside the section union wherever
    around the lap the guide starts."""
    track_map = TrackMap(MAPS / 'baku/baku.yaml')
    legal = effective_free_mask(track_map, [], 5)
    outer, inner = extract_boundaries(track_map)
    seed = midline_seed(outer, inner)
    closed = seed  # conftest returns the completed (closed) lap
    for k in range(8):
        shift = (len(closed) - 1) * k // 8
        rot = closed[shift:-1] + closed[:shift] + [closed[shift]]
        payload, _ = build_route(track_map, outer, inner, rot,
                                 legal_mask=legal)
        validate_route(payload)  # raises if the zone escapes
