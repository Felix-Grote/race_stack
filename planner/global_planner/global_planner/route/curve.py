"""
A closed curve made of cubic pieces, queried by distance s along it.

continuity:     position, tangent and curvature match at every join,
                including the seam where the last piece meets the first.
owners:         each piece records the section it belongs to.
"""
from bisect import bisect_right
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import accumulate
import math

import numpy as np
from numpy.typing import ArrayLike
from scipy.interpolate import CubicSpline

from .cubic import Coefficients, CubicSegment
from .errors import GeometryError
from .geometry import EPS, XY
from .tolerances import NumericPolicy


@dataclass(frozen=True)
class CurvePoint:
    """
    One point of a curve.

    s:                      distance along the curve, in metres.
    segment, t:             the piece and the position inside it.
    xy, tangent:            position and unit direction.
    curvature:              signed curvature, positive turning left.
    section_uid:            the section the piece belongs to.
    """

    s: float
    segment: int
    t: float
    xy: XY
    tangent: XY
    curvature: float
    section_uid: str


@dataclass(frozen=True)
class Sample(CurvePoint):
    """A curve point with its left normal and heading in radians."""

    left_normal: XY
    heading: float


@dataclass(frozen=True, init=False)
class Curve:
    """
    Closed cubic curve with cumulative piece lengths.

    segments:       the cubic pieces, in order.
    cumulative:     distance s at the start of each piece, plus the lap length.
    owners:         uid of the section each piece belongs to.
    policy:         tolerances for the whole lap.
    """

    segments: tuple[CubicSegment, ...]
    cumulative: tuple[float, ...]
    owners: tuple[str, ...]
    policy: NumericPolicy

    def __init__(self, coefficients: Sequence[ArrayLike], owners: Sequence[str],
                 policy: NumericPolicy = NumericPolicy()) -> None:
        coefficients = tuple(coefficients)
        if len(coefficients) < 2:
            raise GeometryError('a closed curve needs at least 2 pieces')

        segments = tuple(CubicSegment(c, policy) for c in coefficients)
        for i, a in enumerate(segments):
            b = segments[(i + 1) % len(segments)]
            ta, ka = a.frame(1.)
            tb, kb = b.frame(0.)
            if (math.dist(a.evaluate(1.), b.evaluate(0.)) > policy.join_abs or
                    math.dist(ta, tb) > policy.join_abs or abs(ka - kb) > policy.join_abs):
                raise GeometryError('pieces do not join in position, tangent and curvature')

        owners = tuple(owners)
        if len(owners) != len(segments) or any(type(x) is not str for x in owners):
            raise GeometryError('one owner section uid per piece required')

        cumulative = (0.,) + tuple(accumulate(s.length for s in segments))
        if np.finfo(float).eps * cumulative[-1] > policy.station_abs / 16:
            raise GeometryError('lap too long to resolve distances to station_abs')

        object.__setattr__(self, 'segments', segments)
        object.__setattr__(self, 'cumulative', cumulative)
        object.__setattr__(self, 'owners', owners)
        object.__setattr__(self, 'policy', policy)

    @classmethod
    def interpolate(cls, points: ArrayLike, owners: Sequence[str], q: ArrayLike | None = None,
                    policy: NumericPolicy = NumericPolicy()) -> 'Curve':
        """
        Fit a periodic cubic spline through the points, in order, without smoothing.

        owners:     owner section uid of the piece starting at each point.
        q:          spline parameter at each point plus one closing value;
                    the cumulative chord length by default.
        """
        p = np.asarray(points, dtype=float)
        if p.ndim != 2 or p.shape[1] != 2 or len(p) < 3 or not np.isfinite(p).all():
            raise GeometryError('need 3 or more finite XY points, without repeating the first')

        closed = np.vstack((p, p[0]))
        lengths = np.linalg.norm(np.diff(closed, axis=0), axis=1)
        if min(lengths) <= EPS:
            raise GeometryError('two consecutive points coincide')

        if q is None:
            q = np.r_[0., np.cumsum(lengths)]

        q = np.asarray(q, dtype=float)
        if q.shape != (len(p) + 1,) or not np.isfinite(q).all() or min(np.diff(q)) <= 0:
            raise GeometryError('q must increase, one value per point plus the closing one')

        cs = CubicSpline(q, closed, bc_type='periodic')
        h = np.diff(q)
        coeff = [[[cs.c[3 - k, i, j] * h[i] ** k for k in range(4)]
                  for j in range(2)] for i in range(len(p))]

        return cls(coeff, owners, policy)

    @property
    def coefficients(self) -> tuple[Coefficients, ...]:
        """Return the polynomial coefficients of every piece."""
        return tuple(s.coefficients for s in self.segments)

    @property
    def length(self) -> float:
        """Return the total lap length in metres."""
        return self.cumulative[-1]

    def station(self, segment: int, t: float) -> float:
        """Return the distance s of (segment, t); the end of the last piece gives length."""
        if type(segment) is not int or not 0 <= segment < len(self.segments):
            raise GeometryError('no such piece')

        if not math.isfinite(t) or not 0 <= t <= 1:
            raise GeometryError('t must lie in [0, 1]')

        # Piece endpoints use the stored cumulative distance, so a join has one s.
        if t == 0:
            return self.cumulative[segment]

        if t == 1:
            return self.cumulative[segment + 1]

        return self.cumulative[segment] + self.segments[segment].arc(t)

    def separation(self, s0: float, s1: float) -> float:
        """Return the distance between stations s0 and s1, the short way round."""
        d = abs(s0 - s1) % self.length

        return min(d, self.length - d)

    def wrap(self, s: float) -> float:
        """Wrap s into [0, length), rejecting values too large to resolve."""
        if not math.isfinite(s) or abs(s) * np.finfo(float).eps > self.policy.station_abs / 16:
            raise GeometryError('s is not finite or too large to resolve')

        # A tiny negative remainder can round up to length. Keep it on the
        # preceding side, at the largest representable value below length.
        wrapped = s % self.length
        return math.nextafter(self.length, 0.) if wrapped == self.length else wrapped

    def locate(self, s: float) -> tuple[int, float]:
        """Return (segment, t) at distance s; a join belongs to the piece after it."""
        s = self.wrap(s)
        i = min(bisect_right(self.cumulative, s) - 1, len(self.segments) - 1)
        # s - cumulative[i] can overshoot the piece length by rounding; clamp it.
        local = min(s - self.cumulative[i], self.segments[i].length)

        return i, self.segments[i].parameter(local)

    def sample(self, s: float, section_uid: str | None = None) -> Sample:
        """Return the Sample at s; a given section_uid must match the owner."""
        wrapped = self.wrap(s)
        i, t = self.locate(s)
        owner = self.owners[i]
        if section_uid is not None and section_uid != owner:
            raise GeometryError('s lies on a piece of another section')

        tangent, k = self.segments[i].frame(t)
        return Sample(wrapped, i, t, self.segments[i].evaluate(t), tangent, k, owner,
                      left_normal=(-tangent[1], tangent[0]),
                      heading=math.atan2(tangent[1], tangent[0]))

    def window(self, s0: float, s1: float, step: float) -> tuple[Sample, ...]:
        """Sample from s0 to s1 (unwrapped) every step, including both ends."""
        if not all(math.isfinite(v) for v in (s0, s1, step)) or step <= 0 or s1 < s0:
            raise GeometryError('window needs finite s0 <= s1 and a positive step')

        count = math.ceil((s1 - s0) / step)
        return tuple(self.sample(s0 + min(i * step, s1 - s0)) for i in range(count + 1))
