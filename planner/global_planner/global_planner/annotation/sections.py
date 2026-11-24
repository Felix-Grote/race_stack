"""
The route manifest built from the walls and the guide; checks.py checks it.

guide:      it must stay on the kept cells all the way round, never crossing a wall;
            where it does not is marked for the page.
joints:     the guide is resampled, at least _MIN_SEED_POINTS times round the lap, smoothed
            and pulled into the middle half of the road. Which loop is the left wall follows
            from the way the guide turns: the infield is on the left of a counterclockwise
            lap. The guide is cut into n_sections near even fractions of the lap, each cut on
            the straightest guide point nearby where the nearest point of the left wall lies
            to its left and that of the right wall to its right: gates on straights keep the
            portal charts unfolded. A cut's gate joins those two points.
walls:      each wall is walked one way round for the whole lap, the way that passes the
            gates in order in exactly one turn; a guide whose gates allow neither is refused.
            Each section's walls are the stretches between its gates, thinned (walls.py) so
            the route package's centreline stays fast. Both sections at a gate share its two
            end points exactly.
start:      the operator draws the start line: two clicks, one on each side of the road.
            The line through them, run on to the walls, is the first gate; the lap begins
            where a line crosses it, and nothing else is asked of the line there. A start
            set as one click, as older drafts hold, gets the gate that fits nearest after it.
"""
import math

import numpy as np

from .guide import off_road, resample, signed_area, starting_at
from .track_map import AnnotationError, TrackMap
from .walls import douglas_peucker, ear_ok, MAX_THINNING_PX, thin

# How far apart the thinned walls may stray from the traced ones, in metres; capped at
# MAX_THINNING_PX on fine maps.
WALL_EPS_M = 0.02

# The fewest points the resampled guide has round a lap: enough for well separated cuts on a
# short track. Longer laps keep the given spacing.
_MIN_SEED_POINTS = 64


def _gap(a: int, b: int, n: int) -> int:
    """Return how many steps apart indices a and b are around a loop of n."""
    return min((a - b) % n, (b - a) % n)


def _arc(chain: np.ndarray, start: int, end: int, step: int) -> list[np.ndarray]:
    """Return a closed chain's points from start to end, both included, stepping by step."""
    out, i = [], start
    while True:
        out.append(chain[i])
        if i == end:
            return out

        i = (i + step) % len(chain)


def _seed(track_map: TrackMap, outer: np.ndarray, inner: np.ndarray, guide_px,
          spacing_m: float, smoothing_passes: int) -> list[np.ndarray]:
    """Return the guide in metres, resampled, smoothed and pulled into the middle of the road."""
    closed = np.vstack((np.asarray(guide_px, float), np.asarray(guide_px[:1], float)))
    perimeter_px = float(np.sum(np.linalg.norm(np.diff(closed, axis=0), axis=1)))
    spacing_px = min(spacing_m / track_map.resolution, perimeter_px / _MIN_SEED_POINTS)
    arr = np.array(resample(guide_px, spacing_px), float)
    kernel = np.array([1., 2., 3., 2., 1.])
    kernel /= kernel.sum()
    for _ in range(smoothing_passes):
        arr = np.stack([sum(kernel[k] * np.roll(arr[:, c], k - 2) for k in range(5))
                        for c in range(2)], axis=1)

    seed = []
    for p in (np.array(track_map.pixel_to_world(q)) for q in arr):
        lo = outer[int(np.argmin(np.linalg.norm(outer - p, axis=1)))]
        li = inner[int(np.argmin(np.linalg.norm(inner - p, axis=1)))]
        mid, half = (lo + li) / 2., (lo - li) / 2.
        denom = float(np.dot(half, half))
        alpha = 0. if denom < 1e-12 else float(np.clip(np.dot(p - mid, half) / denom, -.5, .5))
        seed.append(mid + alpha * half)

    return seed


def _sides(seed: list[np.ndarray], left: np.ndarray,
           right: np.ndarray) -> tuple[list[int], list[int], list[bool]]:
    """
    Return, for every seed point, the nearest point of each wall and whether a gate fits there.

    A gate fits where the nearest left-wall point lies left of the direction of travel and
    the nearest right-wall point right of it.
    """
    def nearest(chain: np.ndarray, p: np.ndarray) -> int:
        return int(np.argmin(np.linalg.norm(chain - p, axis=1)))

    lj, rj, fits = [], [], []
    for i, p in enumerate(seed):
        tangent = seed[(i + 1) % len(seed)] - seed[i - 1]
        norm = np.linalg.norm(tangent)
        lj.append(nearest(left, p))
        rj.append(nearest(right, p))
        if norm < 1e-12:
            fits.append(False)
            continue

        normal = np.array([-tangent[1], tangent[0]]) / norm
        fits.append(float(np.dot(left[lj[-1]] - p, normal)) > 0
                    and float(np.dot(right[rj[-1]] - p, normal)) < 0)

    return lj, rj, fits


def _drawn_gate(ends: np.ndarray, left: np.ndarray, right: np.ndarray, seed: list[np.ndarray],
                reach_m: float) -> tuple[int, int]:
    """
    Return the left- and right-wall points the drawn start line meets, run on to the walls.

    ends:       the two points the operator clicked, in metres, in either order.
    reach_m:    how near the line a wall point must lie to count as met: a cell of the map.

    Of the places where the line meets a wall, the nearest to its middle counts: the line
    run on would cross the rest of the track too.
    """
    middle, along = ends.mean(axis=0), ends[1] - ends[0]
    along = along / np.linalg.norm(along)
    met = []
    for wall in (left, right):
        offset = wall - middle
        near = np.flatnonzero(np.abs(offset @ np.array([-along[1], along[0]])) <= reach_m)
        if not near.size:
            raise AnnotationError('the start line misses a wall: draw it across the road, '
                                  'from one wall to the other')

        met.append(int(near[np.argmin(np.abs(offset[near] @ along))]))

    # As for every gate: the left wall to the left of the way the guide runs, the right one
    # to its right. Seen from the line's own middle: in a bend the guide's first point can
    # lie off to one side of it, with both walls on the same side of the point.
    tangent = seed[1] - seed[-1]
    normal = np.array([-tangent[1], tangent[0]])
    if not (np.dot(left[met[0]] - middle, normal) > 0 > np.dot(right[met[1]] - middle, normal)):
        raise AnnotationError('the start line does not cross the road: draw it from one wall '
                              'to the other, across the guide')

    return met[0], met[1]


def _direction(idxs: list[int], n: int, side: str) -> int:
    """Return the step, 1 or -1, that walks a closed wall of n points through idxs in one turn."""
    for step in (1, -1):
        gaps = [((b - a) * step) % n for a, b in zip(idxs, idxs[1:] + idxs[:1])]
        if all(gaps) and sum(gaps) == n:
            return step

    raise AnnotationError(f'the gates do not follow each other along the {side} wall: redraw the '
                          f'guide')


def _cuts(seed: list[np.ndarray], n_sections: int, fits: list[bool]) -> list[int]:
    """
    Return where to cut the seed: near even fractions, on its straightest points that fit.

    The first cut is the start line, so it is not moved to a straighter place: it is made at
    the seed's first point, where the operator drew it, or, for a start set as one click, at
    the first point after it where a gate fits.
    """
    n = len(seed)
    turn = []
    for i, p in enumerate(seed):
        a, b = seed[i] - seed[i - 1], seed[(i + 1) % n] - p
        turn.append(abs(math.atan2(a[0] * b[1] - a[1] * b[0], float(np.dot(a, b)))))

    # Cuts must stay well apart: neighbouring windows overlap.
    min_sep = max(8, n // 8)
    cuts = []
    for k in range(n_sections):
        target = int(round(k * n / n_sections))
        window = [j % n for j in range(target - n // 8, target + n // 8)]
        window = [j for j in window if fits[j] and all(_gap(j, c, n) >= min_sep for c in cuts)]
        if k == 0:
            ahead = [j for j in range(n // 8) if fits[j]]
            if not ahead:
                raise AnnotationError('no start line fits across the road there: set the start '
                                      'on a straighter part of the track')

            cuts.append(ahead[0])
            continue

        if not window:
            raise AnnotationError('cannot cut the guide into well separated sections: redraw '
                                  'it more evenly, between the walls')

        # Rounded so near-straight points, equal up to float noise, tie the same way on
        # every machine.
        cuts.append(min(window, key=lambda j: round(turn[j], 6)))

    cuts.sort()
    if len(set(cuts)) != n_sections or any(_gap(a, b, n) < min_sep
                                           for a, b in zip(cuts, cuts[1:] + cuts[:1])):
        raise AnnotationError('cannot cut the guide into well separated sections: redraw it '
                              'more evenly')

    return cuts


def build(track_map: TrackMap, outer_px: np.ndarray, inner_px: np.ndarray, guide_px,
          start_px, kept: np.ndarray, name: str, surface: str, max_speed_mps: float,
          n_sections: int = 4, spacing_m: float = 0.75, smoothing_passes: int = 4) -> dict:
    """Return the route manifest for the walls and the guide; checks.check checks it."""
    try:
        max_speed_mps = float(max_speed_mps)
    except (TypeError, ValueError) as exc:
        raise AnnotationError('the speed limit must be a number') from exc

    # The guide is not exported, but a guide through a wall cuts the lap where no car drives.
    off = off_road(kept, guide_px)
    if len(off):
        raise AnnotationError('the guide crosses a wall or leaves the road (marked red): redraw '
                              'it there, or press Suggest', at_px=off)

    # One click, or the two ends of a drawn start line: either way the lap starts at its middle.
    start = np.asarray(start_px, float).reshape(-1, 2)
    middle_px = [float(v) for v in start.mean(axis=0)]
    if len(off_road(kept, [middle_px])):
        raise AnnotationError('the start is off the road (marked red): set it again',
                              at_px=[middle_px])

    guide_px = starting_at(guide_px, middle_px)

    outer = np.array([track_map.pixel_to_world(p) for p in outer_px])
    inner = np.array([track_map.pixel_to_world(p) for p in inner_px])
    seed = _seed(track_map, outer, inner, guide_px, spacing_m, smoothing_passes)
    left, right = (inner, outer) if signed_area(seed) > 0 else (outer, inner)
    lj, rj, fits = _sides(seed, left, right)
    if len(start) == 2:
        ends = np.array([track_map.pixel_to_world(p) for p in start])
        lj[0], rj[0] = _drawn_gate(ends, left, right, seed, track_map.resolution)
        fits[0] = True

    cuts = _cuts(seed, n_sections, fits)
    left_step = _direction([lj[c] for c in cuts], len(left), 'left')
    right_step = _direction([rj[c] for c in cuts], len(right), 'right')

    chord_ok = ear_ok(track_map, kept == 0)
    spacing = max(2., .05 / track_map.resolution) * track_map.resolution
    floor_m = MAX_THINNING_PX * track_map.resolution
    eps_m = min(WALL_EPS_M, floor_m)

    def wall(chain: np.ndarray, j0: int, j1: int, step: int) -> list[tuple[float, float]]:
        pts = douglas_peucker(thin(_arc(chain, j0, j1, step), spacing, floor_m, chord_ok),
                              eps_m, chord_ok)
        pts[0], pts[-1] = tuple(chain[j0]), tuple(chain[j1])
        return pts

    sections = []
    for k, (a, b) in enumerate(zip(cuts, cuts[1:] + cuts[:1])):
        sections.append({'uid': f's{k}', 'surface': surface, 'max_speed_mps': max_speed_mps,
                         'left': [[float(x), float(y)]
                                  for x, y in wall(left, lj[a], lj[b], left_step)],
                         'right': [[float(x), float(y)]
                                   for x, y in wall(right, rj[a], rj[b], right_step)]})

    # The first section begins on the start line; the manifest holds no other start.
    return {'name': name, 'map': {'frame_id': 'map', 'sha256': track_map.sha256},
            'sections': sections}
