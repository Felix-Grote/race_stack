"""
Lap progress q: where along the route each point of a curve belongs.

q:          measured along the sections' centrelines, section after
            section, so it stays fixed while the curve itself moves.
section i:  covers q from route.section_bounds[i] to route.section_bounds[i + 1].
"""
from bisect import bisect_right
from dataclasses import dataclass
import math

from .curve import Curve
from .errors import LapError
from .geometry import distance, EPS
from .tolerances import NumericPolicy
from .track import Route


@dataclass(frozen=True)
class LapCurve:
    """
    A curve plus the lap progress q at each of its knots.

    route:      the route the curve belongs to.
    curve:      the closed cubic curve.
    q:          progress at the start of each piece, plus the full lap at the end.

    Every section start is a knot, and every piece lies in the section that owns it.
    """

    route: Route
    curve: Curve
    q: tuple[float, ...]

    def __post_init__(self) -> None:
        q = tuple(float(x) for x in self.q)
        bounds = self.route.section_bounds
        if (len(q) != len(self.curve.segments) + 1 or not all(math.isfinite(x) for x in q)
                or q[0] != 0 or abs(q[-1] - bounds[-1]) > EPS
                or any(b <= a for a, b in zip(q, q[1:]))):
            raise LapError('q must start at 0, increase, and end at the lap length')

        # A section boundary must remain a knot, not hidden inside a new cubic.
        if any(not any(abs(x - y) <= EPS for x in q) for y in bounds):
            raise LapError('a section start is not a knot of the curve')

        object.__setattr__(self, 'q', q)
        for i, owner in enumerate(self.curve.owners):
            if owner != self.route.sections[self.section_index((q[i] + q[i + 1]) / 2)].uid:
                raise LapError('piece owned by the wrong section')

    @property
    def period(self) -> float:
        """Return the lap length in q, which differs from the curve length."""
        return self.q[-1]

    def section_index(self, q: float) -> int:
        """Return the index of the section that owns lap progress q."""
        return min(bisect_right(self.route.section_bounds, q) - 1, len(self.route.sections) - 1)

    def progress(self, segment: int, t: float) -> float:
        """Return q at (segment, t), interpolated between the knots, never from XY."""
        if not 0 <= segment < len(self.q) - 1 or not 0 <= t <= 1:
            raise LapError('no such piece, or t outside [0, 1]')

        return (1 - t) * self.q[segment] + t * self.q[segment + 1]

    def parameter_at_progress(self, q: float) -> tuple[int, float]:
        """Return (segment, t) at lap progress q."""
        if not math.isfinite(q) or not 0 <= q <= self.period:
            raise LapError('q outside the lap')

        if q == self.period:
            return len(self.q) - 2, 1.

        i = min(bisect_right(self.q, q) - 1, len(self.q) - 2)
        t = (q - self.q[i]) / (self.q[i + 1] - self.q[i])
        return i, t

    def station_at_progress(self, q: float) -> float:
        """Return the curve distance s at lap progress q."""
        i, t = self.parameter_at_progress(q)
        return self.curve.station(i, t)

    def wrapped_offset(self, q: float, anchor: float) -> float:
        """Return q - anchor wrapped around the lap into [-period/2, period/2)."""
        return (q - anchor + self.period / 2) % self.period - self.period / 2


def centre_curve(route: Route, policy: NumericPolicy = NumericPolicy()) -> LapCurve:
    """Fit a closed curve through every centreline point of every section, in lap order."""
    bounds = route.section_bounds
    points, q, owners = [], [], []
    for i, section in enumerate(route.sections):
        local = 0.
        for a, b in zip(section.centreline, section.centreline[1:]):
            points.append(a)
            q.append(bounds[i] + local)
            owners.append(section.uid)
            local += distance(a, b)

    q.append(bounds[-1])

    return LapCurve(route, Curve.interpolate(points, owners, q, policy), tuple(q))
