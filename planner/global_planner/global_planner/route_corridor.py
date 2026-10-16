"""Occurrence-owned original-border intervals and inherited ordered preparation."""
from bisect import bisect_right
from dataclasses import dataclass
import math

import numpy as np

from ._route_geometry import (EPS, cross, distance, dot, inside, line_intervals,
                              on_segment, segments_touch, sub)
from .route_reference import Curve, NumericPolicy


class CorridorError(ValueError):
    """Illegal/ambiguous ownership or unsupported local chart."""


def _layout(route):
    ends = [0.]
    for i, o in enumerate(route.occurrences):
        if route.portals[i - 1].after + route.portals[i].before >= o.length - EPS:
            raise CorridorError('overlapping portal progress support')
        ends.append(ends[-1] + o.length)
    return tuple(ends)


@dataclass(frozen=True)
class OrderedCurve:
    """Curve plus unwrapped original seed-metric lineage at every cubic knot."""

    route: object
    curve: Curve
    q: tuple

    def __post_init__(self):
        q = tuple(float(x) for x in self.q)
        ends = _layout(self.route)
        if (len(q) != len(self.curve.segments) + 1 or not all(math.isfinite(x) for x in q)
                or q[0] != 0 or abs(q[-1] - ends[-1]) > EPS
                or any(b <= a for a, b in zip(q, q[1:]))):
            raise CorridorError('nonmonotone/invalid inherited progress')
        # An occurrence boundary must remain a knot, not hidden inside a new cubic.
        if any(not any(abs(x - y) <= EPS for x in q) for y in ends):
            raise CorridorError('resampling lost an occurrence anchor')
        for i, owner in enumerate(self.curve.owners):
            j = min(bisect_right(ends, (q[i] + q[i + 1]) / 2) - 1,
                    len(self.route.occurrences) - 1)
            o = self.route.occurrences[j]
            if owner != (o.id, o.surface_id):
                raise CorridorError('illegal declared occurrence/surface change')
        object.__setattr__(self, 'q', q)

    @property
    def period(self):
        """Total original polyline seed metric, distinct from current curve L."""
        return self.q[-1]

    def progress(self, segment, t):
        """Inherit q by original segment/t, never recover it by XY matching."""
        if not 0 <= segment < len(self.q) - 1 or not 0 <= t <= 1:
            raise CorridorError('invalid lineage anchor')
        return (1 - t) * self.q[segment] + t * self.q[segment + 1]

    def station_at_q(self, q):
        """Transport a seed/cap/gate anchor through the monotone lineage map."""
        if not math.isfinite(q) or not 0 <= q <= self.period:
            raise CorridorError('anchor q outside selected lap')
        if q == self.period:
            return self.curve.length
        i = min(bisect_right(self.q, q) - 1, len(self.q) - 2)
        t = (q - self.q[i]) / (self.q[i + 1] - self.q[i])
        return self.curve.station(i, t)


def seed_curve(route, policy=NumericPolicy()):
    """Interpolate one selected full lap, preserving every original seed anchor."""
    ends = _layout(route)
    points, q, owners = [], [], []
    for i, o in enumerate(route.occurrences):
        local = 0.
        for a, b in zip(o.seed, o.seed[1:]):
            points.append(a)
            q.append(ends[i] + local)
            owners.append((o.id, o.surface_id))
            local += distance(a, b)
    q.append(ends[-1])
    return OrderedCurve(route, Curve.interpolate(points, q, owners, policy), tuple(q))


@dataclass(frozen=True)
class OrderedSample:
    """Metric sample and inherited source segment/t/q plus explicit owner/cap."""

    s: float
    segment: int
    t: float
    q: float
    xy: tuple
    tangent: tuple
    curvature: float
    occurrence_id: str
    surface_id: str
    cap_mps: float


def _sample(ordered, s):
    v = ordered.curve.sample(s)
    q = ordered.progress(v.segment, v.t)
    ends = _layout(ordered.route)
    i = min(bisect_right(ends, q) - 1, len(ordered.route.occurrences) - 1)
    o = ordered.route.occurrences[i]
    local = q - ends[i]
    cap = o.caps[max(0, bisect_right([x[0] for x in o.caps], local + EPS) - 1)][1]
    return OrderedSample(v.s, v.segment, v.t, q, v.xy, v.tangent, v.curvature,
                         o.id, o.surface_id, cap)


def resample_ordered(ordered, spacing):
    """Equal metric samples plus exact inherited occurrence/cap/portal anchors."""
    if not math.isfinite(spacing) or spacing <= 0:
        raise CorridorError('invalid metric spacing')
    count = math.ceil(ordered.curve.length / spacing)
    if count > ordered.curve.policy.max_samples:
        raise CorridorError('resampling budget exhausted')
    ends = _layout(ordered.route)
    anchors = {0.}
    for i, o in enumerate(ordered.route.occurrences):
        anchors.add(ends[i])
        anchors.update(ends[i] + c[0] for c in o.caps)
        anchors.add(ends[i + 1] - ordered.route.portals[i].before)
        anchors.add((ends[i + 1] + ordered.route.portals[i].after) % ordered.period)
    # Preserve anchors exactly; discard a uniform station numerically indistinguishable
    # from an anchor rather than losing semantic events during a tolerance merge.
    anchored = sorted(ordered.station_at_q(q) for q in anchors)
    stations = anchored + [ordered.curve.length * i / count for i in range(count)
                           if all(abs(ordered.curve.length * i / count - s) >
                                  ordered.curve.policy.station_abs for s in anchored)]
    stations.sort()
    if len(stations) > ordered.curve.policy.max_samples:
        raise CorridorError('resampling anchor budget exhausted')
    result = tuple(_sample(ordered, s) for s in stations)
    if any(a.q >= b.q for a, b in zip(result, result[1:])):
        raise CorridorError('resampling reversed progress')
    return result


def refit_ordered(ordered, samples, xy):
    """Refit shifted ordered knots with inherited q, for a later bounded adapter."""
    samples, xy = tuple(samples), tuple(xy)
    if len(samples) != len(xy) or not samples:
        raise CorridorError('shifted knot/lineage size mismatch')
    for v in samples:
        if abs(ordered.progress(v.segment, v.t) - v.q) > EPS:
            raise CorridorError('corrupt inherited source segment/t/q')
    q = tuple(v.q for v in samples) + (ordered.period,)
    owners = tuple((v.occurrence_id, v.surface_id) for v in samples)
    return OrderedCurve(ordered.route,
                        Curve.interpolate(xy, q, owners, ordered.curve.policy), q)


def _merge(intervals):
    result = []
    for a, b in sorted(intervals):
        if result and a <= result[-1][1]:
            result[-1] = (result[-1][0], max(b, result[-1][1]))
        else:
            result.append((a, b))
    return result


def _component(intervals):
    found = [(a, b) for a, b in intervals if a < -EPS and b > EPS]
    if len(found) != 1:
        raise CorridorError('reference outside/ambiguous connected legal interval')
    return found[0]


def _on_chain(p, chain):
    return any(on_segment(p, a, b) for a, b in zip(chain, chain[1:]))


def _normal_geometry(occurrences, xy, tangent, support=None, caps=()):
    if abs(math.hypot(*tangent) - 1) > 1e-8:
        raise CorridorError('invalid tangent chart')
    n = (-tangent[1], tangent[0])
    try:
        intervals = _merge([v for o in occurrences for v in
                            line_intervals(xy, n, o.polygon, caps)])
        if support is not None:
            mask = line_intervals(xy, n, support)
            intervals = _merge([(max(a, c), min(b, d)) for a, b in intervals
                                for c, d in mask if max(a, c) < min(b, d)])
        lo, hi = _component(intervals)
    except ValueError as exc:
        raise CorridorError(str(exc)) from exc
    # Outside portal support, endcaps are ownership limits, never invented walls.
    if support is None:
        left = (xy[0] + hi * n[0], xy[1] + hi * n[1])
        right = (xy[0] + lo * n[0], xy[1] + lo * n[1])
        if not any(_on_chain(left, o.left) for o in occurrences) or not any(
                _on_chain(right, o.right) for o in occurrences):
            raise CorridorError('normal exits end cap or inconsistent directed sides')
    return lo + EPS, hi - EPS  # strictly inward numerical allowance; never inflate


@dataclass(frozen=True)
class Corridor:
    """Signed left-positive interval plus TUM right/left width view."""

    lower: float
    upper: float
    occurrence_id: str
    surface_id: str
    portal_id: str
    support_occurrences: tuple
    q: float

    @property
    def right(self):
        """TUM positive right width; optimizer alpha equals minus left offset."""
        return -self.lower

    @property
    def left(self):
        """Positive left width."""
        return self.upper


def normal_interval(ordered, sample, chart_min=.05):
    """Intersect only declared original ownership or explicit adjacent support."""
    if not math.isfinite(chart_min) or not 0 < chart_min < 1:
        raise CorridorError('invalid local chart threshold')
    expected = _sample(ordered, sample.s)
    if sample != expected:
        raise CorridorError('stale/corrupt sample or illegal ownership change')
    ends = _layout(ordered.route)
    i = min(bisect_right(ends, sample.q) - 1, len(ends) - 2)
    o = ordered.route.occurrences[i]
    owners, support, caps, pid = (o,), None, (), ''
    active = []
    for j, portal in enumerate(ordered.route.portals):
        delta = (sample.q - ends[j + 1] + ordered.period / 2) % ordered.period
        delta -= ordered.period / 2
        if -portal.before - EPS <= delta <= portal.after + EPS:
            if inside(sample.xy, portal.support, False):
                active.append((j, portal))
    if len(active) > 1:
        raise CorridorError('ambiguous portal support')
    if active:
        j, portal = active[0]
        owners = (ordered.route.occurrences[j],
                  ordered.route.occurrences[(j + 1) % len(ordered.route.occurrences)])
        support, caps, pid = portal.support, (portal.gate,), portal.id
    lo, hi = _normal_geometry(owners, sample.xy, sample.tangent, support, caps)
    chart_jacobian = min(1 - sample.curvature * lo, 1 - sample.curvature * hi)
    if lo >= 0 or hi <= 0 or chart_jacobian < chart_min:
        raise CorridorError('folded/degenerate local chart; no width inflation/clamping')
    return Corridor(lo, hi, o.id, o.surface_id, pid, tuple(x.id for x in owners), sample.q)


def _gate_parameters(segment, gate):
    a, b = gate
    g = sub(b, a)
    c = np.asarray(segment.coefficients)
    f = g[0] * c[1] - g[1] * c[0]
    f[0] -= cross(g, a)
    uncertainty = EPS * math.hypot(*g) + 128 * np.finfo(float).eps * sum(abs(f))
    if max(abs(f)) <= uncertainty:
        raise CorridorError('curve collinear/uncertain with gate')
    roots = list(np.polynomial.polynomial.polyroots(f))
    # A double root may be returned as a complex pair. Independently inspect
    # stationary values near the line, then let bracket/segment/direction checks
    # reject an actual or numerically uncertain tangent contact.
    for root in np.polynomial.polynomial.polyroots(np.polynomial.polynomial.polyder(f)):
        if abs(root.imag) < 1e-7 and -EPS <= root.real <= 1 + EPS:
            if abs(np.polynomial.polynomial.polyval(root.real, f)) <= uncertainty:
                roots.append(complex(root.real, 0))
    result = []
    for root in roots:
        if 1e-10 < abs(root.imag) < 1e-7 and -.001 < root.real < 1.001:
            raise CorridorError('uncertain/tangent gate root')
        if abs(root.imag) <= 1e-10 and -EPS <= root.real <= 1 + EPS:
            result.append(max(0., min(1., float(root.real))))
    return tuple(result)


def portal_crossings(ordered):
    """Require a unique directed polynomial/gate intersection in each q bracket."""
    ends = _layout(ordered.route)
    result = []
    for j, portal in enumerate(ordered.route.portals):
        a, b = portal.gate
        g = sub(b, a)
        hits = []
        for i, seg in enumerate(ordered.curve.segments):
            # Only inherited adjacent brackets; unrelated projected decks are excluded.
            center = (ordered.q[i] + ordered.q[i + 1]) / 2
            width = (ordered.q[i + 1] - ordered.q[i]) / 2
            delta = (center - ends[j + 1] + ordered.period / 2) % ordered.period
            delta -= ordered.period / 2
            if delta + width < -portal.before - EPS or delta - width > portal.after + EPS:
                continue
            for t in _gate_parameters(seg, portal.gate):
                q = ordered.progress(i, t)
                delta_q = (q - ends[j + 1] + ordered.period / 2) % ordered.period
                delta_q -= ordered.period / 2
                if not -portal.before - EPS <= delta_q <= portal.after + EPS:
                    continue
                xy, d = seg.evaluate(t), seg.evaluate(t, 1)
                u = dot(sub(xy, a), g) / dot(g, g)
                if -EPS <= u <= EPS or 1 - EPS <= u <= 1 + EPS:
                    raise CorridorError('ambiguous gate endpoint intersection')
                if not 0 < u < 1:
                    continue
                if abs(cross(g, sub(xy, a))) > EPS * math.hypot(*g):
                    raise CorridorError('gate root residual')
                if cross(g, d) >= -EPS or not inside(xy, portal.support, False):
                    raise CorridorError('reverse/tangent/unsupported portal passage')
                s = ordered.curve.station(i, t) % ordered.curve.length
                if not any(min(abs(s - x[0]), ordered.curve.length - abs(s - x[0])) <
                           ordered.curve.policy.station_abs for x in hits):
                    hits.append((s, i, t, q))
        if len(hits) != 1:
            raise CorridorError('missing/ambiguous directed portal intersection: ' + portal.id)
        result.append((portal.id,) + hits[0])
    # The closing gate may be just before/after s=0: compare unwrapped q brackets.
    unwrapped = []
    for j, hit in enumerate(result):
        q = hit[-1]
        while q < ends[j + 1] - ordered.route.portals[j].before - EPS:
            q += ordered.period
        unwrapped.append(q)
    if any(a >= b for a, b in zip(unwrapped, unwrapped[1:])):
        raise CorridorError('wrong gate ordering')
    return tuple(result)


@dataclass(frozen=True)
class PreparedRoute:
    """Ephemeral geometric input; never an accepted optimized trajectory."""

    ordered: OrderedCurve
    samples: tuple
    corridors: tuple
    gates: tuple

    @property
    def reftrack(self):
        """Ordered TUM [x,y,right,left] rows without hidden preparation."""
        return tuple(v.xy + (c.right, c.left) for v, c in zip(self.samples, self.corridors))

    @property
    def normals_right(self):
        """TUM right-positive alpha normals."""
        return tuple((v.tangent[1], -v.tangent[0]) for v in self.samples)


def prepare_route(route, spacing=.25, policy=NumericPolicy(), ordered=None,
                  chart_pair_budget=1000000):
    """Recompute all widths from original geometry, rejecting unsupported charts."""
    if type(chart_pair_budget) is not int or chart_pair_budget < 1:
        raise CorridorError('invalid chart pair budget')
    if ordered is None:
        ordered = seed_curve(route, policy)
    if ordered.route.digest != route.digest:
        raise CorridorError('original route identity mismatch')
    gates = portal_crossings(ordered)
    samples = resample_ordered(ordered, spacing)
    corridors = tuple(normal_interval(ordered, v) for v in samples)
    # Within a single occurrence, nonadjacent normal intervals must not overlap.
    pairs = 0
    for i, (v, c) in enumerate(zip(samples, corridors)):
        n = (-v.tangent[1], v.tangent[0])
        a = (v.xy[0] + c.lower * n[0], v.xy[1] + c.lower * n[1])
        b = (v.xy[0] + c.upper * n[0], v.xy[1] + c.upper * n[1])
        for w, d in zip(samples[i + 2:], corridors[i + 2:]):
            if w.occurrence_id != v.occurrence_id:
                continue
            pairs += 1
            if pairs > chart_pair_budget:
                raise CorridorError('chart intersection pair budget exhausted')
            m = (-w.tangent[1], w.tangent[0])
            e = (w.xy[0] + d.lower * m[0], w.xy[1] + d.lower * m[1])
            f = (w.xy[0] + d.upper * m[0], w.xy[1] + d.upper * m[1])
            if segments_touch(a, b, e, f):
                raise CorridorError('ambiguous intersecting charts within occurrence')
    return PreparedRoute(ordered, samples, corridors, gates)
