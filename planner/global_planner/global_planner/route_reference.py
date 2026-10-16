"""Periodic cubic geometry and bounded metric queries without ROS or TUM."""
from bisect import bisect_right
from dataclasses import dataclass
import math

import numpy as np
from scipy.integrate import quad
from scipy.interpolate import CubicSpline
from scipy.optimize import brentq


class GeometryError(ValueError):
    """Unsupported geometry, numerical uncertainty or exhausted budget."""


@dataclass(frozen=True)
class NumericPolicy:
    """Software tolerances in metres/radians; never physical clearance margins."""

    arc_abs: float = 1e-10  # total-lap QUADPACK estimated error budget
    station_abs: float = 1e-8
    join_abs: float = 1e-8  # XY, unit tangent and curvature join tolerances
    min_speed: float = 1e-7  # |dr/dt| for each normalized coefficient segment
    quad_limit: int = 100
    regularity_depth: int = 24
    regularity_budget: int = 10000
    max_samples: int = 100000

    def __post_init__(self):
        for x in (self.arc_abs, self.station_abs, self.join_abs, self.min_speed):
            if not math.isfinite(x) or x <= 0:
                raise GeometryError('invalid numerical tolerance')
        if self.arc_abs * 8 > self.station_abs:
            raise GeometryError('station budget must exceed accumulated quadrature error')
        for x in (self.quad_limit, self.regularity_depth, self.regularity_budget,
                  self.max_samples):
            if type(x) is not int or x <= 0:
                raise GeometryError('invalid numerical resource budget')


def _coefficients(coeff):
    a = np.asarray(coeff, dtype=float)
    if a.shape != (2, 4) or not np.isfinite(a).all() or np.max(np.abs(a)) > 1e8:
        raise GeometryError('expected finite 2x4 ascending cubic coefficients within 1e8')
    return tuple(tuple(float(x) for x in row) for row in a)


def _eval(coeff, t, order=0):
    if not math.isfinite(t) or not 0 <= t <= 1 or order not in (0, 1, 2, 3):
        raise GeometryError('invalid coefficient parameter/derivative')
    a = np.asarray(coeff)
    if order == 0:
        v = a[:, 0] + t * (a[:, 1] + t * (a[:, 2] + t * a[:, 3]))
    elif order == 1:
        v = a[:, 1] + t * (2 * a[:, 2] + t * 3 * a[:, 3])
    elif order == 2:
        v = 2 * a[:, 2] + t * 6 * a[:, 3]
    else:
        v = 6 * a[:, 3]
    return tuple(float(x) for x in v)


def _regularity(coeff, policy):
    """Conservative quadratic derivative Bezier boxes; fail if unresolved."""
    a = np.asarray(coeff)
    controls = np.stack((a[:, 1], a[:, 1] + a[:, 2],
                         a[:, 1] + 2 * a[:, 2] + 3 * a[:, 3]))
    rounding = 128 * np.finfo(float).eps * max(1., np.max(np.abs(a)))
    upper = float(np.max(np.linalg.norm(controls, axis=1)) + rounding)
    stack = [(controls, 0)]
    count = 0
    while stack:
        c, depth = stack.pop()
        count += 1
        lo, hi = c.min(axis=0) - rounding, c.max(axis=0) + rounding
        nearest = np.maximum(0., np.maximum(lo, -hi))
        if np.linalg.norm(nearest) > policy.min_speed:
            continue
        if (depth >= policy.regularity_depth or count >= policy.regularity_budget or
                min(np.linalg.norm(c[0]), np.linalg.norm(c[-1])) <= policy.min_speed + rounding):
            raise GeometryError('zero/uncertain derivative or regularity budget exhausted')
        ab, bc = (c[0] + c[1]) / 2, (c[1] + c[2]) / 2
        mid = (ab + bc) / 2
        stack.extend(((np.stack((c[0], ab, mid)), depth + 1),
                      (np.stack((mid, bc, c[2])), depth + 1)))
    return upper


@dataclass(frozen=True, init=False)
class CubicSegment:
    """One regular normalized cubic, also useful for nonperiodic analytic probes."""

    coefficients: tuple
    policy: NumericPolicy
    length: float
    arc_error: float
    speed_upper: float

    def __init__(self, coefficients, policy=NumericPolicy()):
        coeff = _coefficients(coefficients)
        object.__setattr__(self, 'coefficients', coeff)
        object.__setattr__(self, 'policy', policy)
        object.__setattr__(self, 'speed_upper', _regularity(coeff, policy))
        length, error = self._integrate(1.)
        if length <= policy.min_speed:
            raise GeometryError('degenerate arc')
        object.__setattr__(self, 'length', length)
        object.__setattr__(self, 'arc_error', error)

    def evaluate(self, t, derivative=0):
        """Evaluate the exact stored polynomial or its parameter derivative."""
        return _eval(self.coefficients, t, derivative)

    def _integrate(self, t):
        result = quad(lambda u: math.hypot(*self.evaluate(u, 1)), 0., t,
                      epsabs=self.policy.arc_abs, epsrel=5e-14,
                      limit=self.policy.quad_limit, full_output=1)
        value, error = result[:2]
        if len(result) != 3 or not math.isfinite(value) or error > self.policy.arc_abs:
            raise GeometryError('arc integration uncertainty/budget exhausted')
        return value, error

    def arc(self, t):
        """Physical distance from segment start to t, never a chord fraction."""
        if not math.isfinite(t) or not 0 <= t <= 1:
            raise GeometryError('arc parameter outside [0,1]')
        if t == 0:
            return 0.
        if t == 1:
            return self.length
        return self._integrate(t)[0]

    def parameter(self, s):
        """Bracketed inversion, with a checked residual in physical metres."""
        if not math.isfinite(s) or not 0 <= s <= self.length:
            raise GeometryError('segment station outside arc')
        if s == 0:
            return 0.
        if s == self.length:
            return 1.
        xtol = self.policy.station_abs / (16 * self.speed_upper)
        try:
            t = brentq(lambda u: self.arc(u) - s, 0., 1., xtol=xtol,
                       rtol=4 * np.finfo(float).eps, maxiter=100)
        except (RuntimeError, ValueError) as exc:
            raise GeometryError('arc inversion failed') from exc
        if abs(self.arc(t) - s) + 2 * self.policy.arc_abs > self.policy.station_abs:
            raise GeometryError('metric inversion residual exceeds budget')
        return float(t)


@dataclass(frozen=True)
class Sample:
    """Immutable right-hand geometric view at supplied metric progress."""

    s: float
    segment: int
    t: float
    xy: tuple
    tangent: tuple
    left_normal: tuple
    heading: float
    curvature: float
    occurrence_id: str = ''
    surface_id: str = ''


def _frame(segment, t):
    d, dd = segment.evaluate(t, 1), segment.evaluate(t, 2)
    speed = math.hypot(*d)
    tangent = (d[0] / speed, d[1] / speed)
    k = (d[0] * dd[1] - d[1] * dd[0]) / speed ** 3
    return tangent, k


@dataclass(frozen=True, init=False)
class Curve:
    """One immutable periodic coefficient authority with derived metric lengths."""

    segments: tuple
    cumulative: tuple
    owners: tuple
    policy: NumericPolicy

    def __init__(self, coefficients, owners=None, policy=NumericPolicy()):
        coefficients = tuple(coefficients)
        if len(coefficients) < 2 or len(coefficients) > policy.max_samples:
            raise GeometryError('unsupported segment count')
        # Allocate the *whole lap* integration budget, not the same budget per edge.
        seg_policy = NumericPolicy(arc_abs=policy.arc_abs / len(coefficients),
                                   station_abs=policy.station_abs, join_abs=policy.join_abs,
                                   min_speed=policy.min_speed, quad_limit=policy.quad_limit,
                                   regularity_depth=policy.regularity_depth,
                                   regularity_budget=policy.regularity_budget,
                                   max_samples=policy.max_samples)
        segments = tuple(CubicSegment(c, seg_policy) for c in coefficients)
        for i, a in enumerate(segments):
            b = segments[(i + 1) % len(segments)]
            ta, ka = _frame(a, 1.)
            tb, kb = _frame(b, 0.)
            if (math.dist(a.evaluate(1.), b.evaluate(0.)) > policy.join_abs or
                    math.dist(ta, tb) > policy.join_abs or abs(ka - kb) > policy.join_abs):
                raise GeometryError('nonperiodic/discontinuous position, tangent or curvature')
        if owners is None:
            owners = (('', ''),) * len(segments)
        owners = tuple(tuple(x) for x in owners)
        bad_owner = any(len(x) != 2 or any(type(s) is not str for s in x) for x in owners)
        if len(owners) != len(segments) or bad_owner:
            raise GeometryError('invalid declared segment owners')
        cumulative = [0.]
        correction = 0.
        for segment in segments:
            y = segment.length - correction
            total = cumulative[-1] + y
            correction = (total - cumulative[-1]) - y
            cumulative.append(total)
        if np.finfo(float).eps * cumulative[-1] > policy.station_abs / 16:
            raise GeometryError('lap exceeds floating point station resolution')
        object.__setattr__(self, 'segments', segments)
        object.__setattr__(self, 'cumulative', tuple(cumulative))
        object.__setattr__(self, 'owners', owners)
        object.__setattr__(self, 'policy', policy)

    @classmethod
    def interpolate(cls, points, q=None, owners=None, policy=NumericPolicy()):
        """Periodic interpolation of ordered unique knots; no smoothing/XY remap."""
        p = np.asarray(points, dtype=float)
        if (p.ndim != 2 or p.shape[1] != 2 or len(p) < 3 or
                not np.isfinite(p).all()):
            raise GeometryError('expected >=3 finite ordered XY knots without terminal duplicate')
        closed = np.vstack((p, p[0]))
        lengths = np.linalg.norm(np.diff(closed, axis=0), axis=1)
        if min(lengths) <= 1e-9:
            raise GeometryError('zero-length consecutive interpolation edge')
        if q is None:
            q = np.r_[0., np.cumsum(lengths)]
        q = np.asarray(q, dtype=float)
        if q.shape != (len(p) + 1,) or not np.isfinite(q).all() or min(np.diff(q)) <= 0:
            raise GeometryError('nonmonotone knot parameter')
        cs = CubicSpline(q, closed, bc_type='periodic')
        h = np.diff(q)
        coeff = [[[cs.c[3 - k, i, j] * h[i] ** k for k in range(4)]
                  for j in range(2)] for i in range(len(p))]
        return cls(coeff, owners, policy)

    @property
    def coefficients(self):
        """Return the actual polynomial coefficients, never refitted samples."""
        return tuple(s.coefficients for s in self.segments)

    @property
    def length(self):
        """Total integrated lap length."""
        return self.cumulative[-1]

    def station(self, segment, t):
        """Unwrapped anchor station; terminal (last,1) equals L."""
        if type(segment) is not int or not 0 <= segment < len(self.segments):
            raise GeometryError('invalid segment')
        return self.cumulative[segment] + self.segments[segment].arc(t)

    def wrap(self, s):
        """Wrap finite supplied progress, rejecting unresolvable huge lap counts."""
        if not math.isfinite(s) or abs(s) * np.finfo(float).eps > self.policy.station_abs / 16:
            raise GeometryError('nonfinite/unresolvable metric progress')
        return s % self.length

    def locate(self, s):
        """Return segment/t with a half-open right-hand convention at knots/seam."""
        s = self.wrap(s)
        i = min(bisect_right(self.cumulative, s) - 1, len(self.segments) - 1)
        return i, self.segments[i].parameter(s - self.cumulative[i])

    def sample(self, s, occurrence_id=None):
        """Stateless query; optional supplied occurrence must match declared owner."""
        wrapped = self.wrap(s)
        i, t = self.locate(s)
        owner, surface = self.owners[i]
        if occurrence_id is not None and occurrence_id != owner:
            raise GeometryError('supplied occurrence disagrees with ordered progress')
        tangent, k = _frame(self.segments[i], t)
        return Sample(wrapped, i, t, self.segments[i].evaluate(t), tangent,
                      (-tangent[1], tangent[0]), math.atan2(tangent[1], tangent[0]), k,
                      owner, surface)

    def window(self, s0, s1, step):
        """Sample an increasing unwrapped metric interval, including its endpoints."""
        if (not all(math.isfinite(v) for v in (s0, s1, step)) or step <= 0 or s1 < s0):
            raise GeometryError('invalid metric window')
        count = math.ceil((s1 - s0) / step)
        if count + 1 > self.policy.max_samples:
            raise GeometryError('window sample budget exhausted')
        return tuple(self.sample(s0 + min(i * step, s1 - s0)) for i in range(count + 1))
