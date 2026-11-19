"""Where a lap curve crosses each portal gate: exactly once, forwards, in lap order."""
from dataclasses import dataclass
import math

import numpy as np
from numpy.polynomial.polynomial import polyder, polyroots, polyval

from .cubic import CubicSegment
from .errors import LapError
from .geometry import cross, dot, EPS, sub
from .lap import LapCurve
from .track import Portal


@dataclass(frozen=True)
class Crossing:
    """
    Where a lap curve crosses one portal's gate.

    portal_uid:     the portal.
    s:              distance along the curve.
    segment, t:     the piece and the position inside it.
    q:              lap progress.
    """

    portal_uid: str
    s: float
    segment: int
    t: float
    q: float


def _gate_parameters(segment: CubicSegment, portal: Portal) -> tuple[float, ...]:
    """Return the t in [0, 1] where the cubic piece meets the line of the portal's gate."""
    a, b = portal.gate
    g = sub(b, a)
    c = np.asarray(segment.coefficients)
    f = g[0] * c[1] - g[1] * c[0]
    f[0] -= cross(g, a)

    uncertainty = EPS * math.hypot(*g) + 128 * np.finfo(float).eps * sum(abs(f))
    if max(abs(f)) <= uncertainty:
        raise LapError(f'portal {portal.uid}: a piece of the line runs along the gate')

    roots = list(polyroots(f))

    """
    A double root may be returned as a complex pair. Independently inspect
    stationary values near the line, then let bracket/segment/direction checks
    reject an actual or numerically uncertain tangent contact.
    """
    for root in polyroots(polyder(f)):
        if abs(root.imag) < 1e-7 and -EPS <= root.real <= 1 + EPS:
            if abs(polyval(root.real, f)) <= uncertainty:
                roots.append(complex(root.real, 0))

    result = []
    for root in roots:
        if 1e-10 < abs(root.imag) < 1e-7 and -.001 < root.real < 1.001:
            raise LapError(f'portal {portal.uid}: the line may touch the gate without crossing')

        if abs(root.imag) <= 1e-10 and -EPS <= root.real <= 1 + EPS:
            result.append(max(0., min(1., float(root.real))))

    return tuple(result)


def portal_crossings(lap: LapCurve) -> tuple[Crossing, ...]:
    """
    Return each portal's single crossing, in lap order.

    owners:     only pieces of the two sections the portal joins count, so a bridge
                passing over the gate is ignored.
    raises:     on a missing, repeated, backwards or tangent crossing, or if
                the crossings are out of lap order.
    """
    bounds = lap.route.section_bounds
    result = []
    for portal in lap.route.portals:
        a, b = portal.gate
        g = sub(b, a)
        hits = []
        for i, seg in enumerate(lap.curve.segments):
            if not portal.joins(lap.curve.owners[i]):
                continue

            for t in _gate_parameters(seg, portal):
                q = lap.progress(i, t)
                xy, d = seg.evaluate(t), seg.evaluate(t, 1)
                u = dot(sub(xy, a), g) / dot(g, g)
                if -EPS <= u <= EPS or 1 - EPS <= u <= 1 + EPS:
                    raise LapError(f'portal {portal.uid}: the line crosses at a gate end')

                if not 0 < u < 1:
                    continue

                if abs(cross(g, sub(xy, a))) > EPS * math.hypot(*g):
                    raise LapError(f'portal {portal.uid}: crossing point not on the gate')

                if cross(g, d) >= -EPS:
                    raise LapError(f'portal {portal.uid}: the line crosses backwards or grazes')

                s = lap.curve.wrap(lap.curve.station(i, t))
                if not any(lap.curve.separation(s, x.s) < lap.curve.policy.station_abs
                           for x in hits):
                    hits.append(Crossing(portal.uid, s, i, t, q))

        if len(hits) != 1:
            raise LapError(f'portal {portal.uid}: crossed {len(hits)} times, expected once')

        result.append(hits[0])

    # The closing gate may be just before/after q=0: compare q relative to each gate.
    unwrapped = [bounds[j + 1] + lap.wrapped_offset(hit.q, bounds[j + 1])
                 for j, hit in enumerate(result)]

    if any(a >= b for a, b in zip(unwrapped, unwrapped[1:])):
        raise LapError('gates are crossed out of lap order')

    return tuple(result)
