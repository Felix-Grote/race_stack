"""
The guide: a closed loop the operator draws inside the track, in file pixels.

meaning:    it sets the direction of travel and roughly where the sections are cut; it is not
            exported. Each section's centreline comes from its walls (route/centreline.py).
on road:    it must stay on the kept cells all the way round, never crossing a wall.
start:      the operator sets where the car starts; the guide is run from its place nearest
            to it, so the lap, and its first cut, begin there.
suggest:    the midline, where the inner wall is as far as the outer one: the edge of the
            infield grown by the road cells nearer to it, so a closed loop on the road. It is
            smoothed where that keeps it on the road, and simplified with no shortcut off it.
"""
import math

import cv2
import numpy as np
from shapely.geometry import LinearRing, Point

from .track_map import AnnotationError
from .walls import douglas_peucker


def signed_area(points) -> float:
    """Return the area enclosed by a closed loop; positive when it runs counterclockwise."""
    pts = np.asarray(points, float)

    return 0.5 * float(np.sum(pts[:, 0] * np.roll(pts[:, 1], -1)
                              - np.roll(pts[:, 0], -1) * pts[:, 1]))


def resample(points, spacing: float) -> list[np.ndarray]:
    """Return a closed loop resampled at near-even spacing, at least 12 points."""
    pts = [np.array(p, float) for p in points]
    if len(pts) < 3:
        raise AnnotationError('the guide needs at least 3 points')

    if np.linalg.norm(pts[0] - pts[-1]) < 1e-9:
        pts = pts[:-1]

    seg = [float(np.linalg.norm(b - a)) for a, b in zip(pts, pts[1:] + pts[:1])]
    if min(seg) < 1e-9:
        raise AnnotationError('the guide has two points on top of each other')

    # Added one by one: sum() compensates rounding since Python 3.12, so it would place the
    # points differently on the car's Python than on a newer one.
    total = 0.
    for d in seg:
        total += d

    count = max(12, int(total / spacing))
    out, target, acc, i = [], 0., 0., 0
    while len(out) < count:
        while acc + seg[i] < target:
            acc += seg[i]
            i = (i + 1) % len(pts)

        out.append(pts[i] + (target - acc) / seg[i] * (pts[(i + 1) % len(pts)] - pts[i]))
        target += total / count

    return out


def starting_at(loop, point) -> list[list[float]]:
    """Return a closed loop, open end dropped, run from its nearest place to a point."""
    pts = [list(map(float, p)) for p in loop]
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts = pts[:-1]

    ring = LinearRing(pts)
    along = ring.project(Point(point))
    # Each vertex's distance along the loop: those past the start come first.
    ends = np.concatenate(([0.], np.cumsum(np.linalg.norm(np.diff(
        np.vstack((pts, pts[:1])), axis=0), axis=1))))[:-1]
    first = int(np.searchsorted(ends, along, side='right'))
    start = list(ring.interpolate(along).coords[0])
    rest = pts[first:] + pts[:first]
    if math.dist(start, rest[0]) < 1e-9:
        rest = rest[1:]

    return [start] + rest


def off_road(kept: np.ndarray, loop) -> np.ndarray:
    """Return the cells, in order round a closed loop, where it leaves the kept cells."""
    pts = np.asarray(loop, float).reshape(-1, 2)
    ends = np.roll(pts, -1, 0)
    # Four samples per pixel of length, so no cell a segment passes through is skipped.
    counts = np.maximum(1, np.ceil(np.linalg.norm(ends - pts, axis=1) * 4).astype(int))
    seg = np.repeat(np.arange(len(pts)), counts)
    frac = (np.arange(len(seg)) - np.repeat(np.cumsum(counts) - counts, counts)) \
        / np.repeat(counts, counts)
    uv = np.rint(pts[seg] + frac[:, None] * (ends[seg] - pts[seg])).astype(int)
    height, width = kept.shape
    inside = (uv[:, 0] >= 0) & (uv[:, 0] < width) & (uv[:, 1] >= 0) & (uv[:, 1] < height)
    bad = ~inside
    bad[inside] = kept[uv[inside, 1], uv[inside, 0]] == 0
    cells, first = np.unique(uv[bad], axis=0, return_index=True)

    return cells[np.argsort(first)]


def midline(kept: np.ndarray, inner: np.ndarray, smooth_px: int = 4,
            eps_px: float = 1.5) -> list[list[float]]:
    """Return the loop as far from the inner wall as from the outer one, on the road."""
    hole = np.zeros_like(kept)
    cv2.fillPoly(hole, [np.rint(inner).astype(np.int32).reshape(-1, 1, 2)], 255)
    hole = (hole > 0) & (kept == 0)
    outside = (kept == 0) & ~hole
    to_inner = cv2.distanceTransform(np.where(hole, 0, 255).astype(np.uint8), cv2.DIST_L2, 5)
    to_outer = cv2.distanceTransform(np.where(outside, 0, 255).astype(np.uint8), cv2.DIST_L2, 5)
    # The infield and the road nearer to it: its edge runs midway, on road cells.
    near = (hole | ((kept > 0) & (to_inner <= to_outer))).astype(np.uint8)
    contours, _ = cv2.findContours(near, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    loop = max(contours, key=cv2.contourArea).reshape(-1, 2).astype(float)
    # A moving average takes out the pixel steps, unless it would leave the road.
    window = np.ones(2 * smooth_px + 1) / (2 * smooth_px + 1)
    padded = np.vstack((loop[-smooth_px:], loop, loop[:smooth_px]))
    smooth = np.column_stack([np.convolve(padded[:, k], window, 'valid') for k in (0, 1)])
    if not len(off_road(kept, smooth)):
        loop = smooth

    def on_road(pts: list[np.ndarray], a: int, b: int) -> bool:
        return not len(off_road(kept, [pts[a], pts[b]]))

    closed = douglas_peucker(list(loop) + [loop[0]], eps_px, on_road)

    return [[float(u), float(v)] for u, v in closed[:-1]]
