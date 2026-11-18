"""
The two walls of the kept road, and what may and may not be cut off them.

loops:      the kept free space must be one ring, clear of the image edge: one outer
            boundary and one hole. Anything else (a gap to the outside, a split, an island) is
            refused, never guessed at: the operator closes it with a stroke or picks a region.
find_track: the largest free region that is such a ring, the region kept unless the operator
            picks another; keep_track keeps the one picked while it is still a ring.
            The loops run through the centres of the boundary's free pixels.
legal:      the road may cover only the squares of kept free cells. Touching an occupied
            square is fine; covering any of its area is not.
thinning:   a traced wall has a point per pixel. Points are dropped while the wall stays
            within a distance of the traced one, and a shortcut is only taken when the ear it
            cuts off covers no occupied area at all, however far inside the road it strays.
            The final polygons are still checked against the legal squares (checks.py).
"""
from collections.abc import Callable, Sequence
import math

import cv2
import numpy as np
import shapely
from shapely.geometry import Polygon

from .track_map import AnnotationError, kept_mask, TrackMap

# Area in m2 below which a polygon covers nothing: numeric zero for exact area sums. Any real
# overlap with an occupied square is far larger.
AREA_EPS_M2 = 1e-9

# The farthest a thinned wall may stray from the traced one, in pixels, before the
# shortcut checks: a traced wall steps by up to half a pixel.
MAX_THINNING_PX = 0.6

ChordOk = Callable[[list[np.ndarray], int, int], bool]


def loops(kept: np.ndarray, region_picked: bool) -> tuple[np.ndarray, np.ndarray]:
    """Return the outer and inner loops of the kept free space, in file pixels, or refuse."""
    if kept[0, :].any() or kept[-1, :].any() or kept[:, 0].any() or kept[:, -1].any():
        raise AnnotationError('the free space reaches the edge of the map: draw a stroke to '
                              'close the outer wall')

    contours, hierarchy = cv2.findContours(kept, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    if hierarchy is None:
        raise AnnotationError('the map has no free space')

    parents = hierarchy[0][:, 3]
    outer = [i for i, p in enumerate(parents) if p == -1]
    if len(outer) != 1:
        if not region_picked:
            raise AnnotationError(f'the free space is in {len(outer)} pieces and none is a '
                                  f'closed track: draw walls to close it')

        raise AnnotationError(f'the free space is in {len(outer)} pieces')

    holes = [i for i, p in enumerate(parents) if p == outer[0]]
    if len(holes) != 1:
        raise AnnotationError(f'the track must enclose exactly one infield, not {len(holes)}: '
                              f'draw a stroke to close any open wall, or remove stray marks')

    return (contours[outer[0]].reshape(-1, 2).astype(float),
            contours[holes[0]].reshape(-1, 2).astype(float))


def is_track(kept: np.ndarray, region_picked: bool = True) -> bool:
    """Return whether loops takes the kept cells as a track."""
    try:
        loops(kept, region_picked)
        return True
    except AnnotationError:
        return False


def keep_track(free: np.ndarray, region_px: list | None) -> list | None:
    """Return the region to keep: the one given while it is still a track, else find_track's."""
    if region_px is not None:
        try:
            if is_track(kept_mask(free, region_px)):
                return region_px
        except AnnotationError:
            # The picked pixel is under a wall now.
            pass

    return find_track(free)


def find_track(free: np.ndarray) -> list[int] | None:
    """Return a pixel of the largest free region loops takes as a track, or None if none is."""
    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        (free > 0).astype(np.uint8), connectivity=8)
    height, width = free.shape
    for i in sorted(range(1, count), key=lambda k: -stats[k, cv2.CC_STAT_AREA]):
        u, v, w, h = (int(stats[i, k]) for k in (cv2.CC_STAT_LEFT, cv2.CC_STAT_TOP,
                                                 cv2.CC_STAT_WIDTH, cv2.CC_STAT_HEIGHT))
        # A track is clear of the image edge and has room for an infield.
        if u == 0 or v == 0 or u + w == width or v + h == height or min(w, h) < 3:
            continue

        region = labels[v:v + h, u:u + w] == i
        if not is_track(np.pad(region, 1).astype(np.uint8) * 255):
            continue

        dv, du = np.argwhere(region)[0]
        return [u + int(du), v + int(dv)]

    return None


def _boxes(track_map: TrackMap, us: np.ndarray, vs: np.ndarray) -> np.ndarray:
    """Return the cell squares of pixels (us, vs) as shapely boxes."""
    res = track_map.resolution
    cx = track_map.origin[0] + us * res
    cy = track_map.origin[1] + (track_map.height - 1 - vs) * res

    return shapely.box(cx - res / 2, cy - res / 2, cx + res / 2, cy + res / 2)


def occupied_area(poly, track_map: TrackMap, occupied: np.ndarray) -> float:
    """Return the area of poly over occupied cell squares, exactly, in m2."""
    minx, miny, maxx, maxy = poly.bounds
    ua, va = track_map.world_to_pixel((minx, maxy))
    ub, vb = track_map.world_to_pixel((maxx, miny))
    u0 = max(0, int(math.floor(min(ua, ub))) - 1)
    u1 = min(track_map.width - 1, int(math.ceil(max(ua, ub))) + 1)
    v0 = max(0, int(math.floor(min(va, vb))) - 1)
    v1 = min(track_map.height - 1, int(math.ceil(max(va, vb))) + 1)
    vs, us = np.nonzero(occupied[v0:v1 + 1, u0:u1 + 1])
    if not len(vs):
        return 0.

    return max(0., float(shapely.area(shapely.intersection(_boxes(track_map, us + u0, vs + v0),
                                                           poly)).sum()))


def legal_union(track_map: TrackMap, kept: np.ndarray):
    """Return the union of the kept cell squares, built from one box per run of free cells."""
    res = track_map.resolution
    rects = []
    for v, row in enumerate(kept > 0):
        if not row.any():
            continue

        edges = np.flatnonzero(np.diff(np.concatenate(([0], row.view(np.int8), [0]))))
        y = track_map.origin[1] + (track_map.height - 1 - v) * res
        rects += [(track_map.origin[0] + (u0 - .5) * res, y - res / 2,
                   track_map.origin[0] + (u1 - .5) * res, y + res / 2)
                  for u0, u1 in zip(edges[0::2], edges[1::2])]

    if not rects:
        return Polygon()

    r = np.array(rects)

    return shapely.union_all(shapely.box(r[:, 0], r[:, 1], r[:, 2], r[:, 3]))


def ear_ok(track_map: TrackMap, occupied: np.ndarray) -> ChordOk:
    """Return the check that the ear chord a-b cuts off pts covers no occupied area."""
    def ok(pts: list[np.ndarray], a: int, b: int) -> bool:
        ring = [(float(p[0]), float(p[1])) for p in pts[a:b + 1]]
        if len(ring) < 3:
            return True

        # A ring that crosses itself is split into its lobes, so none cancels another.
        ear = Polygon(ring)
        if not ear.is_valid:
            ear = shapely.make_valid(ear)

        return occupied_area(ear, track_map, occupied) <= AREA_EPS_M2

    return ok


def _refine(pts: list[np.ndarray], kept: list[bool], eps: float,
            chord_ok: ChordOk | None) -> list[tuple[float, float]]:
    """
    Keep more of pts until every chord between kept points is close enough and allowed.

    A chord is close enough when no dropped point lies farther than eps from it, and allowed
    when chord_ok says so. Otherwise the farthest point between its ends is kept too, and both
    halves are looked at again.
    """
    stack = [(a, b) for a, b in zip([i for i, k in enumerate(kept) if k][:-1],
                                    [i for i, k in enumerate(kept) if k][1:])]
    while stack:
        a, b = stack.pop()
        if b - a < 2:
            continue

        seg = pts[b] - pts[a]
        denom = float(np.dot(seg, seg))
        dist, idx = 0., -1
        for i in range(a + 1, b):
            t = 0. if denom < 1e-18 else float(np.dot(pts[i] - pts[a], seg) / denom)
            d = float(np.linalg.norm(pts[i] - (pts[a] + min(1., max(0., t)) * seg)))
            if d > dist:
                dist, idx = d, i

        if dist > eps or (chord_ok is not None and not chord_ok(pts, a, b)):
            idx = idx if idx >= 0 else (a + b) // 2
            kept[idx] = True
            stack += [(a, idx), (idx, b)]

    return [tuple(pts[i]) for i, k in enumerate(kept) if k]


def thin(points: Sequence, spacing: float, eps: float = 0.,
         chord_ok: ChordOk | None = None) -> list[tuple[float, float]]:
    """
    Drop points closer than spacing to the last one kept; both ends stay.

    With eps and chord_ok, every shortcut over dropped points is then checked as in _refine,
    so no feature smaller than spacing is lost unnoticed.
    """
    pts = [np.array(p, float) for p in points]
    if len(pts) < 2:
        return [tuple(p) for p in pts]

    keep = [0]
    for i in range(1, len(pts)):
        if float(np.linalg.norm(pts[i] - pts[keep[-1]])) >= spacing:
            keep.append(i)

    if keep[-1] != len(pts) - 1:
        keep.append(len(pts) - 1)

    if not (eps > 0 and chord_ok is not None):
        return [tuple(pts[i]) for i in keep]

    kept = [False] * len(pts)
    for i in keep:
        kept[i] = True

    return _refine(pts, kept, eps, chord_ok)


def douglas_peucker(points: Sequence, eps: float,
                    chord_ok: ChordOk | None = None) -> list[tuple[float, float]]:
    """Return the fewest points, ends included, whose polyline stays within eps and allowed."""
    pts = [np.array(p, float) for p in points]
    if len(pts) < 3 or eps <= 0:
        return [tuple(p) for p in pts]

    kept = [False] * len(pts)
    kept[0] = kept[-1] = True

    return _refine(pts, kept, eps, chord_ok)
