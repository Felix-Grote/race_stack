"""
One planar cubic piece r(t), t in [0, 1]: evaluation and arc length.

coefficients:   2x4 array, one row per axis, ascending powers of t.
arc length:     adaptive Gauss-Kronrod quadrature (scipy quad) of |r'(t)|.
inverse:        bracketed root finding (scipy brentq) on the arc length.
"""
from dataclasses import dataclass
import math

import numpy as np
from numpy.polynomial import Polynomial
from numpy.typing import ArrayLike
from scipy.integrate import quad
from scipy.optimize import brentq

from .errors import GeometryError
from .geometry import XY
from .tolerances import NumericPolicy

Coefficients = tuple[tuple[float, float, float, float], tuple[float, float, float, float]]


def _coefficients(coeff: ArrayLike) -> Coefficients:
    a = np.asarray(coeff, dtype=float)
    if a.shape != (2, 4) or not np.isfinite(a).all() or np.max(np.abs(a)) > 1e8:
        raise GeometryError('expected finite 2x4 ascending cubic coefficients within 1e8')

    return tuple(tuple(float(x) for x in row) for row in a)


def _speed_range(coeff: Coefficients) -> tuple[float, float]:
    """Return min and max of |r'(t)| on [0, 1]; extremes sit at roots of d|r'|^2/dt."""
    dx, dy = (Polynomial(row).deriv() for row in coeff)
    squared = dx * dx + dy * dy
    t = [0., 1.] + [r.real for r in squared.deriv().roots()
                    if abs(r.imag) < 1e-12 and 0 < r.real < 1]
    values = squared(np.array(t))

    return math.sqrt(max(float(values.min()), 0.)), math.sqrt(float(values.max()))


@dataclass(frozen=True, init=False)
class CubicSegment:
    """
    One regular cubic piece with its arc length.

    coefficients:   2x4 ascending coefficients, as tuples.
    policy:         tolerances used for this piece.
    length:         arc length from t=0 to t=1, in metres.
    speed_upper:    largest |r'| over the piece.
    """

    coefficients: Coefficients
    policy: NumericPolicy
    length: float
    speed_upper: float

    def __init__(self, coefficients: ArrayLike, policy: NumericPolicy = NumericPolicy()) -> None:
        coeff = _coefficients(coefficients)
        speed_lower, speed_upper = _speed_range(coeff)
        if speed_lower <= policy.min_speed:
            raise GeometryError('zero or near-zero derivative on cubic piece')

        object.__setattr__(self, 'coefficients', coeff)
        object.__setattr__(self, 'policy', policy)
        object.__setattr__(self, 'speed_upper', speed_upper)
        object.__setattr__(self, 'length', self._integrate(1.))

    def evaluate(self, t: float, derivative: int = 0) -> XY:
        """Evaluate r(t), r'(t) or r''(t) for derivative 0, 1 or 2."""
        if not math.isfinite(t) or not 0 <= t <= 1 or derivative not in (0, 1, 2):
            raise GeometryError('t must lie in [0, 1] and derivative be 0, 1 or 2')

        a = self.coefficients
        if derivative == 0:
            return tuple(r[0] + t * (r[1] + t * (r[2] + t * r[3])) for r in a)

        if derivative == 1:
            return tuple(r[1] + t * (2 * r[2] + t * 3 * r[3]) for r in a)

        return tuple(2 * r[2] + t * 6 * r[3] for r in a)

    def frame(self, t: float) -> tuple[XY, float]:
        """Return the unit tangent and signed curvature at t."""
        d, dd = self.evaluate(t, 1), self.evaluate(t, 2)
        speed = math.hypot(*d)
        tangent = (d[0] / speed, d[1] / speed)
        k = (d[0] * dd[1] - d[1] * dd[0]) / speed ** 3

        return tangent, k

    def _integrate(self, t: float) -> float:
        (_, x1, x2, x3), (_, y1, y2, y3) = self.coefficients

        def speed(u: float) -> float:
            return math.hypot(x1 + u * (2 * x2 + u * 3 * x3), y1 + u * (2 * y2 + u * 3 * y3))

        tolerance = self.policy.station_abs / 16
        value, error = quad(speed, 0., t, epsabs=tolerance, epsrel=0., limit=100)
        if not math.isfinite(value) or error > tolerance:
            raise GeometryError('arc length integration did not converge')

        return value

    def arc(self, t: float) -> float:
        """Return the distance in metres along the piece from t=0 to t."""
        if not math.isfinite(t) or not 0 <= t <= 1:
            raise GeometryError('t must lie in [0, 1]')

        if t == 0:
            return 0.

        if t == 1:
            return self.length

        return self._integrate(t)

    def parameter(self, s: float) -> float:
        """Return the t at distance s along the piece, with a checked residual."""
        if not math.isfinite(s) or not 0 <= s <= self.length:
            raise GeometryError('s must lie within the piece')

        if s == 0:
            return 0.

        if s == self.length:
            return 1.

        xtol = self.policy.station_abs / (16 * self.speed_upper)
        try:
            t = brentq(lambda u: self.arc(u) - s, 0., 1., xtol=xtol, maxiter=100)
        except (RuntimeError, ValueError) as exc:
            raise GeometryError('arc inversion failed') from exc

        if abs(self.arc(t) - s) > self.policy.station_abs:
            raise GeometryError('arc length inversion not accurate enough')

        return float(t)
