"""Independent fail-closed continuous planar validation of exact cubics.

Binary64 inputs denote exact real numbers. Polynomial algebra, Bernstein boxes,
polygon orientation, intersections and squared distances use Fraction arithmetic;
only square roots and reporting convert to binary64, rounded outwards by two ulps.
The elementary-operation model is IEEE-754 binary64 with sqrt/hypot error <=1 ulp.
No sampling density, optimizer width, solver flag or approximate polynomial root
can authorize PASS. Physical contact, 3D clearance and tracking are not covered.
"""
from bisect import bisect_right
from dataclasses import asdict, dataclass
from fractions import Fraction
import math

from .route_input import RouteError, validate_route
from .route_reference import Curve, GeometryError, NumericPolicy


class BoundUncertain(ValueError):
    """An interval cannot be enclosed under this supported numerical model."""


def validate_dynamics(ordered, profile, model, policy=None, metadata=None, *,
                      expected_curve_digest=None):
    """Independently check cyclic dynamics; import lazily to keep geometry pure."""
    from .route_validate_dynamics import DynamicsValidationPolicy, validate_dynamics as check
    if policy is None:
        policy = DynamicsValidationPolicy()
    return check(ordered, profile, model, policy=policy, metadata=metadata,
                 expected_curve_digest=expected_curve_digest)


def _f(x):
    if isinstance(x, bool) or not isinstance(x, (int, float, Fraction)):
        raise BoundUncertain('non-numeric or boolean bound input')
    if isinstance(x, float) and not math.isfinite(x):
        raise BoundUncertain('nonfinite bound input')
    return Fraction(x)


def _up(x):
    try:
        value = float(x)
    except OverflowError as exc:
        raise BoundUncertain('bound exceeds finite binary64 range') from exc
    if not math.isfinite(value):
        raise BoundUncertain('bound exceeds finite binary64 range')
    result = math.nextafter(math.nextafter(value, math.inf), math.inf)
    if not math.isfinite(result):
        raise BoundUncertain('outward bound exceeds finite binary64 range')
    return result


def _sqrt(x, upper=True):
    if x < 0:
        raise BoundUncertain('negative squared bound')
    if x == 0:
        return 0.
    x = Fraction(x)
    # Scale *before* conversion: subnormal squared curvature/speed can lose a
    # large relative fraction even when its square root is an ordinary float.
    exponent = (x.numerator.bit_length() - x.denominator.bit_length()) // 2
    factor = Fraction(2 ** (2 * exponent)) if exponent >= 0 else Fraction(1, 2 ** (-2 * exponent))
    value = math.sqrt(float(x / factor))
    direction = math.inf if upper else 0.
    value = math.nextafter(math.nextafter(value, direction), direction)
    try:
        result = math.ldexp(value, exponent)
    except OverflowError as exc:
        raise BoundUncertain('square-root bound exceeds finite binary64 range') from exc
    result = math.nextafter(result, direction)
    if not math.isfinite(result):
        raise BoundUncertain('square-root bound exceeds finite binary64 range')
    return result


def _polyval(p, t):
    value = Fraction(0)
    for v in reversed(p):
        value = value * t + v
    return value


def _derivative(p):
    return tuple(i * p[i] for i in range(1, len(p))) or (Fraction(0),)


def _add(p, q, scale=1):
    return tuple((p[i] if i < len(p) else 0) +
                 scale * (q[i] if i < len(q) else 0)
                 for i in range(max(len(p), len(q))))


def _multiply(p, q):
    out = [Fraction(0)] * (len(p) + len(q) - 1)
    for i, a in enumerate(p):
        for j, b in enumerate(q):
            out[i + j] += a * b
    return tuple(out)


def _bernstein(p, lo, hi):
    """Exact power-to-Bernstein conversion after t=lo+(hi-lo)*u."""
    n, h = len(p) - 1, hi - lo
    power = tuple(sum((p[j] * math.comb(j, k) * lo ** (j - k) * h ** k
                       for j in range(k, n + 1)), Fraction(0))
                  for k in range(n + 1))
    return tuple(sum((power[k] * Fraction(math.comb(i, k), math.comb(n, k))
                      for k in range(i + 1)), Fraction(0)) for i in range(n + 1))


def _coefficient_records(coefficients):
    try:
        if len(coefficients) != 2 or any(len(row) != 4 for row in coefficients):
            raise BoundUncertain('expected exact 2x4 ascending cubic coefficients')
        rows = tuple(tuple(_f(x) for x in row) for row in coefficients)
    except TypeError as exc:
        raise BoundUncertain('malformed coefficient array') from exc
    if any(abs(x) > 1e8 for row in rows for x in row):
        raise BoundUncertain('coefficient magnitude exceeds supported model')
    return rows


@dataclass(frozen=True)
class IntervalBounds:
    """Conservative whole-interval quantities, never sampled extrema."""

    speed_lower: float
    speed_upper: float
    curvature_upper: float
    curvature_rate_upper: float
    numeric_error: float


def interval_bounds(coefficients, t0=0., t1=1.):
    """Exact Bernstein enclosures of speed, |kappa| and |d kappa/ds|.

    The derivative box may contain zero even for a regular curve. Callers must
    subdivide or return INCONCLUSIVE, rather than infer a nonzero lower bound.
    With d=r', c=cross(d,d') and g=d.d, kappa=c/g**(3/2) and
    d(kappa)/ds=(2*c'*g-3*c*g')/(2*g**3). These polynomials are formed exactly;
    sqrt/ratio outputs are outward conversions of rational bounds.
    """
    a = _coefficient_records(coefficients)
    lo, hi = _f(t0), _f(t1)
    if not 0 <= lo < hi <= 1:
        raise BoundUncertain('invalid parameter interval')
    d = tuple(_derivative(row) for row in a)
    controls = tuple(_bernstein(row, lo, hi) for row in d)
    nearest = [max(Fraction(0), min(row), -max(row)) for row in controls]
    gmin = sum((v * v for v in nearest), Fraction(0))
    if gmin <= 0:
        raise BoundUncertain('derivative Bernstein box contains zero')
    gmax = max(sum((controls[j][i] ** 2 for j in range(2)), Fraction(0))
               for i in range(3))
    c = _add(_multiply(d[0], _derivative(d[1])),
             _multiply(d[1], _derivative(d[0])), -1)
    g = _add(_multiply(d[0], d[0]), _multiply(d[1], d[1]))
    cmax = max(abs(v) for v in _bernstein(c, lo, hi))
    rate = _add(tuple(2 * v for v in _multiply(_derivative(c), g)),
                tuple(3 * v for v in _multiply(c, _derivative(g))), -1)
    rmax = max(abs(v) for v in _bernstein(rate, lo, hi))
    return IntervalBounds(_sqrt(gmin, False), _sqrt(gmax),
                          _sqrt(cmax ** 2 / gmin ** 3),
                          _up(rmax / (2 * gmin ** 3)) if rmax else 0., 0.)


def _point(p):
    return tuple(_f(x) for x in p)


def _sub(a, b):
    return a[0] - b[0], a[1] - b[1]


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1]


def _cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def _edges(poly):
    return zip(poly, poly[1:] + poly[:1])


def _on(p, a, b):
    if any(p[j] < min(a[j], b[j]) or p[j] > max(a[j], b[j]) for j in range(2)):
        return False
    return (_cross(_sub(p, a), _sub(b, a)) == 0 and
            _dot(_sub(p, a), _sub(p, b)) <= 0)


def _touch(a, b, c, d):
    if any(max(a[j], b[j]) < min(c[j], d[j]) or max(c[j], d[j]) < min(a[j], b[j])
           for j in range(2)):
        return False
    oa, ob = _cross(_sub(b, a), _sub(c, a)), _cross(_sub(b, a), _sub(d, a))
    oc, od = _cross(_sub(d, c), _sub(a, c)), _cross(_sub(d, c), _sub(b, c))
    return ((oa * ob < 0 and oc * od < 0) or
            (oa == 0 and _on(c, a, b)) or (ob == 0 and _on(d, a, b)) or
            (oc == 0 and _on(a, c, d)) or (od == 0 and _on(b, c, d)))


def _inside(p, poly):
    """Exact strict ray parity. Boundary points are not legal interior."""
    hit = False
    for a, b in _edges(poly):
        if _on(p, a, b):
            return False
        if (a[1] > p[1]) != (b[1] > p[1]):
            x = a[0] + (p[1] - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            if x > p[0]:
                hit = not hit
    return hit


def _simple(poly):
    es = tuple(_edges(poly))
    if len(poly) < 3 or any(a == b for a, b in es):
        return False
    if sum((_cross(a, b) for a, b in es), Fraction(0)) == 0:
        return False
    for i, (a, b) in enumerate(es):
        c = es[(i + 1) % len(es)][1]
        if _cross(_sub(b, a), _sub(c, b)) == 0 and _dot(_sub(b, a), _sub(c, b)) <= 0:
            return False
        for j in range(i + 2, len(es)):
            if not (i == 0 and j == len(es) - 1) and _touch(a, b, *es[j]):
                return False
    return True


def _point_segment_distance2(p, a, b):
    d, v = _sub(b, a), _sub(p, a)
    den = _dot(d, d)
    if not den:
        return _dot(v, v)
    t = max(Fraction(0), min(Fraction(1), _dot(v, d) / den))
    r = v[0] - t * d[0], v[1] - t * d[1]
    return _dot(r, r)


def _point_clearance2(point, poly):
    if not _inside(point, poly):
        return None
    best = None
    for a, b in _edges(poly):
        lower = sum((max(Fraction(0), min(a[j], b[j]) - point[j],
                         point[j] - max(a[j], b[j])) ** 2 for j in range(2)), Fraction(0))
        if best is None or lower < best:
            distance = _point_segment_distance2(point, a, b)
            best = distance if best is None else min(best, distance)
    return best


def _rectangle_clearance2(rectangle, poly):
    """Full edge/interior check against a simple polygon, not four-corner proof.

    A hole cannot be silently filled: supported polygons are independently
    required simple with one ring. Any supplied holes/schema extension rejects.
    Boundary vertices in the body catch enclosed complement components as well.
    """
    if any(not _inside(p, poly) for p in rectangle):
        return None
    if any(_touch(a, b, c, d) for a, b in _edges(rectangle) for c, d in _edges(poly)):
        return None
    if any(_inside(p, rectangle) for p in poly):
        return None
    best = None
    for a, b in _edges(rectangle):
        for c, d in _edges(poly):
            # Exact box separation is a lower bound on segment separation.
            # It prunes rational projections, without changing acceptance.
            lower = sum((max(Fraction(0), min(a[j], b[j]) - max(c[j], d[j]),
                             min(c[j], d[j]) - max(a[j], b[j])) ** 2
                         for j in range(2)), Fraction(0))
            if best is None or lower < best:
                value = min(_point_segment_distance2(a, c, d),
                            _point_segment_distance2(b, c, d),
                            _point_segment_distance2(c, a, b),
                            _point_segment_distance2(d, a, b))
                best = value if best is None else min(best, value)
    return best


@dataclass(frozen=True)
class Footprint:
    """Reference-aligned rectangle and an explicit isotropic geometric margin."""

    front_m: float
    rear_m: float
    width_m: float
    margin_m: float

    def __post_init__(self):
        for name in ('front_m', 'rear_m', 'width_m', 'margin_m'):
            x = getattr(self, name)
            if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x):
                raise ValueError('invalid footprint/margin')
            if x < 0 or (name != 'margin_m' and x == 0):
                raise ValueError('invalid footprint/margin')

    @property
    def radius(self):
        return _sqrt(max(_f(self.front_m) ** 2, _f(self.rear_m) ** 2) +
                     (_f(self.width_m) / 2) ** 2)


@dataclass(frozen=True)
class GeometryValidationPolicy:
    """Independent expected kernel and finite continuous-certificate resources."""

    numeric_policy: NumericPolicy = NumericPolicy()
    max_curvature: float = 1.
    max_depth: int = 24
    max_intervals: int = 50000
    max_gate_depth: int = 52
    max_gate_boxes: int = 20000
    max_segments: int = 2048
    max_route_bytes: int = 2 * 1024 ** 2
    max_polygon_vertices: int = 512
    max_polygon_work: int = 2000000
    require_physical_coverage: bool = False

    def __post_init__(self):
        if type(self.numeric_policy) is not NumericPolicy:
            raise ValueError('unsupported expected numerical kernel')
        if (isinstance(self.max_curvature, bool) or
                not isinstance(self.max_curvature, (int, float))
                or not math.isfinite(self.max_curvature) or self.max_curvature <= 0):
            raise ValueError('invalid independent curvature limit')
        for name in ('max_depth', 'max_intervals', 'max_gate_depth', 'max_gate_boxes',
                     'max_segments', 'max_route_bytes', 'max_polygon_vertices',
                     'max_polygon_work'):
            if type(getattr(self, name)) is not int or getattr(self, name) < 0:
                raise ValueError('invalid validation resource budget')
        if type(self.require_physical_coverage) is not bool:
            raise ValueError('invalid physical coverage policy')


@dataclass(frozen=True)
class IntervalCertificate:
    segment: int
    t0: float
    t1: float
    exact_t0: tuple
    exact_t1: tuple
    occurrence_id: str
    portal_id: str
    curvature_upper: float
    speed_lower: float
    displacement_upper_m: float
    clearance_lower_m: float
    required_margin_m: float
    numeric_error_m: float
    method: str


@dataclass(frozen=True)
class GateCertificate:
    portal_id: str
    segment: int
    t0: float
    t1: float
    q_lower: float
    q_upper: float
    signed_direction_upper: float


@dataclass(frozen=True)
class ValidationReport:
    status: str
    reason: str
    intervals: tuple = ()
    gates: tuple = ()
    offending_interval: tuple = ()
    route_sha256: str = ''
    coefficients_sha256: str = ''
    coverage: tuple = ('legal_planar_geometry', 'reference_aligned_rectangle',
                       'declared_geometric_margin')
    assumptions: tuple = ('exact binary64 coefficient/input values',
                          'exact rational polynomial/polygon predicates',
                          'IEEE754 sqrt/hypot within one ulp',
                          'atan2 absolute error <=4 binary64 eps radians',
                          'join tolerance is a numerical software allowance',
                          'no physical obstacle/contact/3D/tracking certificate')
    curve_digest: str = ''


class _Stop(Exception):
    def __init__(self, status, reason, interval=()):
        self.status, self.reason, self.interval = status, reason, interval


def _position(coeff, t, derivative=0):
    return tuple(_polyval(_derivative(row) if derivative else row, t) for row in coeff)


def _rectangle(coeff, t, footprint, bounds):
    p, d = _position(coeff, t), _position(coeff, t, 1)
    length = math.hypot(float(d[0]), float(d[1]))
    tangent = float(d[0]) / length, float(d[1]) / length
    normal = -tangent[1], tangent[0]
    rect = tuple(tuple(p[j] + _f(x) * _f(tangent[j]) + _f(y) * _f(normal[j])
                       for j in range(2))
                 for x, y in ((footprint.front_m, footprint.width_m / 2),
                              (-footprint.rear_m, footprint.width_m / 2),
                              (-footprint.rear_m, -footprint.width_m / 2),
                              (footprint.front_m, -footprint.width_m / 2)))
    # Exact polynomial evaluation removes global-coordinate cancellation. The
    # remaining float tangent normalization/rectangle products have <=32 eps
    # relative error; 512 eps includes norm conversion and a conditioning factor.
    error = _up(512 * math.ulp(1.) * (1 + footprint.radius) *
                max(1., bounds.speed_upper / bounds.speed_lower))
    return rect, error


def _union_polygon(source, target):
    if source.right[-1] != target.right[0] or source.left[-1] != target.left[0]:
        raise _Stop('INCONCLUSIVE', 'unsupported nonexact shared endcap; no gap bridging')
    chain = (source.right + target.right[1:] + target.left[::-1] +
             source.left[::-1][1:])
    poly = tuple(_point(p) for p in chain)
    if not _simple(poly):
        raise _Stop('INCONCLUSIVE', 'unsupported non-simple adjacent union or hole')
    return poly


def _portal_delta(q, end, period):
    if end == period:
        return q if q < period / 2 else q - period
    return q - end


def _root_intervals(polynomial, projection, gate_norm2, policy, counter):
    """Bernstein sign variation isolates every finite-gate root, no np.roots.

    Descartes' variation bound after the [a,b] Bernstein transform counts roots
    in the open interval. Zero endpoints are collected separately and deduped
    exactly; unresolved multiple/tangent roots exhaust fail-closed resources.
    """
    found = set()
    stack = [(Fraction(0), Fraction(1), 0)]
    while stack:
        lo, hi, depth = stack.pop()
        counter[0] += 1
        if counter[0] > policy.max_gate_boxes:
            raise _Stop('INCONCLUSIVE', 'gate root isolation budget exhausted')
        projection_box = _bernstein(projection, lo, hi)
        if max(projection_box) < 0 or min(projection_box) > gate_norm2:
            continue
        controls = _bernstein(polynomial, lo, hi)
        if min(controls) > 0 or max(controls) < 0:
            continue
        if not any(controls):
            raise _Stop('INCONCLUSIVE', 'collinear/uncertain finite gate passage')
        if controls[0] == 0:
            found.add((lo, lo))
        if controls[-1] == 0:
            found.add((hi, hi))
        signs = [1 if x > 0 else -1 for x in controls if x]
        variation = sum(a != b for a, b in zip(signs, signs[1:]))
        if not variation:
            continue
        if variation == 1 and hi - lo <= Fraction(1, 2 ** 42):
            found.add((lo, hi))
            continue
        if depth >= policy.max_gate_depth:
            raise _Stop('INCONCLUSIVE', 'uncertain/tangent gate root or depth exhausted')
        mid = (lo + hi) / 2
        stack.extend(((lo, mid, depth + 1), (mid, hi, depth + 1)))
    return tuple(sorted(found))


def _validate_gates(curve, q, route, ends, policy):
    reports, counter = [], [0]
    for j, portal in enumerate(route.portals):
        a, b = (_point(p) for p in portal.gate)
        g = _sub(b, a)
        norm2, hits = _dot(g, g), []
        for i, segment in enumerate(curve.segments):
            if curve.owners[i][0] not in (portal.source, portal.target):
                continue  # A different deck's projected intersection is irrelevant.
            coeff = _coefficient_records(segment.coefficients)
            f = tuple(g[0] * coeff[1][k] - g[1] * coeff[0][k] for k in range(4))
            f = (f[0] - _cross(g, a),) + f[1:]
            projection = tuple(g[0] * coeff[0][k] + g[1] * coeff[1][k]
                               for k in range(4))
            projection = (projection[0] - _dot(g, a),) + projection[1:]
            for lo, hi in _root_intervals(f, projection, norm2, policy, counter):
                box = _bernstein(projection, lo, hi)
                if max(box) < 0 or min(box) > norm2:
                    continue
                if min(box) <= 0 or max(box) >= norm2:
                    raise _Stop('INCONCLUSIVE', 'gate endpoint contact/uncertainty',
                                (i, float(lo), float(hi)))
                derivative_box = _bernstein(_derivative(f), lo, hi)
                direction = max(derivative_box)
                if direction >= 0:
                    if min(derivative_box) >= 0:
                        raise _Stop('FAIL', 'reverse/tangent directed gate passage',
                                    (i, float(lo), float(hi)))
                    raise _Stop('INCONCLUSIVE', 'uncertain directed gate derivative',
                                (i, float(lo), float(hi)))
                direction_upper = -_sqrt(direction ** 2 / norm2, False)
                if direction_upper >= -1e-9:
                    raise _Stop('INCONCLUSIVE', 'numerically uncertain gate direction')
                qlo, qhi = q[i] + lo * (q[i + 1] - q[i]), q[i] + hi * (q[i + 1] - q[i])
                dlo = _portal_delta(qlo, ends[j + 1], ends[-1])
                dhi = _portal_delta(qhi, ends[j + 1], ends[-1])
                if dlo < -_f(portal.before) or dhi > _f(portal.after):
                    raise _Stop('FAIL', 'extra/out-of-bracket applicable-owner gate passage',
                                (i, float(lo), float(hi)))
                midpoint = (lo + hi) / 2
                xy = _position(coeff, midpoint)
                clearance = _point_clearance2(xy, tuple(_point(p) for p in portal.support))
                # Speed bound on a point root is taken on its containing cubic.
                speed = segment.speed_upper
                displacement = _f(speed) * (hi - lo) / 2 + _f(policy.numeric_policy.join_abs)
                if clearance is None or clearance <= displacement ** 2:
                    raise _Stop('INCONCLUSIVE', 'gate root not proved inside portal support')
                hits.append((i, lo, hi, qlo, qhi, direction_upper))
        # Exact shared knot roots belong to both coefficient domains. Only exact
        # endpoints of consecutive segments may coalesce; nearby roots do not.
        unique = []
        for hit in hits:
            i, lo, hi = hit[:3]
            duplicate = any((lo == hi == 0 and old[1] == old[2] == 1 and
                             (old[0] + 1) % len(curve.segments) == i) or
                            (lo == hi == 1 and old[1] == old[2] == 0 and
                             (i + 1) % len(curve.segments) == old[0]) for old in unique)
            if not duplicate:
                unique.append(hit)
        if len(unique) != 1:
            raise _Stop('FAIL',
                        'missing or multiple independent directed gate passages: ' + portal.id)
        i, lo, hi, qlo, qhi, direction = unique[0]
        reports.append(GateCertificate(portal.id, i, float(lo), float(hi),
                                       float(qlo), float(qhi), direction))
    # Route brackets are disjoint and selected cyclic order is independently
    # checked against the actual isolated roots, with closing q unwrapped.
    order = []
    for gate in reports:
        low, high = gate.q_lower, gate.q_upper
        if gate.portal_id == route.portals[-1].id and high < float(ends[-1] / 2):
            low, high = low + float(ends[-1]), high + float(ends[-1])
        order.append((low, high))
    if any(a[1] >= b[0] for a, b in zip(order, order[1:])):
        raise _Stop('FAIL', 'incorrect independent directed gate sequence')
    return tuple(reports)


def validate_geometry(candidate, approved_route, footprint, policy=GeometryValidationPolicy(), *,
                      expected_curve_digest=None):
    """Validate actual coefficients against separately supplied original authority.

    PASS means planar legal geometry and the supplied reference-aligned body plus
    margin only. Missing required physical coverage, unsupported holes/union
    topology and exhausted bounds give INCONCLUSIVE, never an accepted artifact.
    The caller must retain expected_curve_digest at a trusted handoff before
    receiving mutable intermediates; hashing the received candidate is not an
    independent authority and cannot prove historical q inheritance.
    """
    import hashlib
    import json

    certificates, gates, digest, coefficient_digest, identity = [], (), '', '', ''
    try:
        if type(footprint) is not Footprint or type(policy) is not GeometryValidationPolicy:
            raise _Stop('FAIL', 'invalid independent footprint or validation policy')
        if expected_curve_digest is None:
            raise _Stop('INCONCLUSIVE', 'missing independently retained complete curve authority')
        if (type(expected_curve_digest) is not str or len(expected_curve_digest) != 64 or
                any(c not in '0123456789abcdef' for c in expected_curve_digest)):
            raise _Stop('FAIL', 'malformed independently retained complete curve digest')
        if (not isinstance(approved_route.encoded, bytes) or
                len(approved_route.encoded) > policy.max_route_bytes or
                len(candidate.curve.segments) > policy.max_segments):
            raise _Stop('INCONCLUSIVE', 'independent preprocessing input budget exhausted')
        payload = approved_route.payload
        originals = [len(o['left']) + len(o['right']) for o in payload['occurrences']]
        vertex_counts = originals + [len(p['support']) for p in payload['transitions']]
        vertex_counts += [len(payload['initialization']['zone'])]
        unions_count = [n + originals[(j + 1) % len(originals)] - 2
                        for j, n in enumerate(originals)]
        if (any(n > policy.max_polygon_vertices for n in vertex_counts) or
                any(n > policy.max_polygon_vertices for n in unions_count) or
                sum(n * n for n in vertex_counts + originals + unions_count) >
                policy.max_polygon_work):
            raise _Stop('INCONCLUSIVE', 'independent polygon preprocessing budget exhausted')
        try:
            route = validate_route(payload)
        except (AttributeError, RouteError, ValueError, TypeError) as exc:
            raise _Stop('FAIL',
                        'invalid/unsupported approved legal geometry: ' + str(exc)) from exc
        digest = route.digest
        if approved_route != route or candidate.route != route:
            raise _Stop('FAIL', 'forged/stale original legal-route authority')
        if candidate.curve.policy != policy.numeric_policy:
            raise _Stop('FAIL',
                        'candidate numerical policy differs from independently expected policy')
        coefficients = candidate.curve.coefficients
        count = len(candidate.curve.segments)
        if (len(coefficients) != count or len(candidate.curve.owners) != count or
                len(candidate.q) != count + 1):
            raise _Stop('FAIL', 'inconsistent coefficient/owner/q resource shape')
        try:
            for coefficient in coefficients:
                _coefficient_records(coefficient)
        except BoundUncertain as exc:
            raise _Stop('FAIL', 'invalid actual coefficient shape/value: ' + str(exc)) from exc
        coefficient_digest = hashlib.sha256(json.dumps(coefficients, separators=(',', ':'),
                                                       allow_nan=False).encode()).hexdigest()
        # Rebuild all derived length/regularity/join metadata from exact authority.
        curve = Curve(coefficients, candidate.curve.owners, policy.numeric_policy)
        if candidate.curve != curve:
            raise _Stop('FAIL', 'corrupt/stale canonical curve metadata')
        ends_float = [0.]
        for occurrence in route.occurrences:
            ends_float.append(ends_float[-1] + occurrence.length)
        if any(route.portals[j - 1].after + route.portals[j].before >= occurrence.length - 1e-9
               for j, occurrence in enumerate(route.occurrences)):
            raise _Stop('FAIL', 'overlapping portal progress brackets are unsupported')
        ends = tuple(_f(x) for x in ends_float)
        q = tuple(_f(x) for x in candidate.q)
        if (len(q) != len(curve.segments) + 1 or q[0] != 0 or q[-1] != ends[-1] or
                any(a >= b for a, b in zip(q, q[1:])) or any(x not in q for x in ends)):
            raise _Stop('FAIL', 'invalid exact q lineage or lost occurrence anchor')
        for i, owner in enumerate(curve.owners):
            j = min(bisect_right(ends, q[i]) - 1, len(route.occurrences) - 1)
            expected = route.occurrences[j]
            if q[i + 1] > ends[j + 1] or owner != (expected.id, expected.surface_id):
                raise _Stop('FAIL', 'incorrect occurrence/surface owner or interval crossing')
        # The caller retains this authority before intermediate mutation. Rehash
        # every actual field independently; a self-consistent candidate/profile
        # digest cannot establish historical q inheritance or approve a new curve.
        authority = {'coefficients': curve.coefficients, 'owners': curve.owners,
                     'q': candidate.q, 'route_digest': route.digest,
                     'numeric_policy': asdict(candidate.curve.policy)}
        identity = hashlib.sha256(json.dumps(
            authority, sort_keys=True, separators=(',', ':'), allow_nan=False
        ).encode('utf-8')).hexdigest()
        if identity != expected_curve_digest:
            raise _Stop('FAIL', 'complete curve differs from independently retained authority')
        if policy.require_physical_coverage:
            raise _Stop('INCONCLUSIVE',
                        'unsupported required physical obstacle/contact/3D coverage')
        polygons = tuple(tuple(_point(p) for p in o.polygon) for o in route.occurrences)
        if any(not _simple(p) for p in polygons):
            raise _Stop('FAIL', 'invalid independent original simple ribbon topology')
        unions = tuple(_union_polygon(route.occurrences[j],
                                      route.occurrences[(j + 1) % len(route.occurrences)])
                       for j in range(len(route.occurrences)))
        supports = tuple(tuple(_point(p) for p in p.support) for p in route.portals)
        if any(not _simple(p) for p in supports):
            raise _Stop('FAIL', 'invalid independent portal support topology')
        gates = _validate_gates(curve, q, route, ends, policy)
        init = route.payload['initialization']
        init_lo, init_hi = (_f(x) for x in init['seed_interval_m'])
        init_zone = tuple(_point(p) for p in init['zone'])
        if not _simple(init_zone):
            raise _Stop('FAIL', 'invalid independent initialization zone topology')
        heading_lo, heading_hi = init['heading_interval_rad']
        anchors = {init_lo, init_hi}
        for j, portal in enumerate(route.portals):
            anchors.add(ends[j + 1] - _f(portal.before))
            anchors.add((ends[j + 1] if j + 1 < len(route.occurrences) else 0) + _f(portal.after))
        stack = []
        for i in range(len(curve.segments)):
            interior = sorted((v - q[i]) / (q[i + 1] - q[i])
                              for v in anchors if q[i] < v < q[i + 1])
            cuts = [Fraction(0)] + interior + [Fraction(1)]
            stack.extend((i, a, b, 0) for a, b in zip(cuts, cuts[1:]))
        visited = 0
        while stack:
            i, lo, hi, depth = stack.pop()
            visited += 1
            if visited > policy.max_intervals:
                raise _Stop('INCONCLUSIVE', 'continuous interval budget exhausted',
                            (i, float(lo), float(hi)))
            coeff = _coefficient_records(curve.segments[i].coefficients)
            midpoint = (lo + hi) / 2
            qlo, qhi = q[i] + lo * (q[i + 1] - q[i]), q[i] + hi * (q[i + 1] - q[i])
            owner_index = min(bisect_right(ends, (qlo + qhi) / 2) - 1, len(polygons) - 1)
            xy = _position(coeff, midpoint)
            try:
                bounds = interval_bounds(coeff, lo, hi)
            except BoundUncertain:
                bounds = None
            accepted, need_split = False, bounds is None
            if bounds is not None:
                if bounds.speed_lower <= policy.numeric_policy.min_speed:
                    need_split = True
                d = _position(coeff, midpoint, 1)
                dd = tuple(_polyval(_derivative(_derivative(row)), midpoint) for row in coeff)
                if _cross(d, dd) ** 2 > _f(policy.max_curvature) ** 2 * _dot(d, d) ** 3:
                    raise _Stop('FAIL', 'actual interior curvature exceeds independent limit',
                                (i, float(lo), float(hi)))
                if bounds.curvature_upper > policy.max_curvature:
                    need_split = True
                domains = [(polygons[owner_index], '', ())]
                for j, portal in enumerate(route.portals):
                    if curve.owners[i][0] not in (portal.source, portal.target):
                        continue
                    dlo = _portal_delta(qlo, ends[j + 1], ends[-1])
                    dhi = _portal_delta(qhi, ends[j + 1], ends[-1])
                    if -_f(portal.before) <= dlo <= dhi <= _f(portal.after):
                        domains.append((unions[j], portal.id, (supports[j],)))
                path_radius = _up(_f(bounds.speed_upper) * (hi - lo) / 2)
                join_error = policy.numeric_policy.join_abs
                rectangle, rect_error = _rectangle(coeff, midpoint, footprint, bounds)
                legal_midpoint = False
                for poly, portal_id, masks in domains:
                    domain = (poly,) + masks
                    point_clearances = tuple(_point_clearance2(xy, p) for p in domain)
                    if all(v is not None for v in point_clearances):
                        clearance2 = min(point_clearances)
                        radius = (_f(footprint.radius) + _f(footprint.margin_m) +
                                  _f(path_radius) + _f(join_error))
                        if clearance2 > radius ** 2 and not need_split:
                            clearance = math.nextafter(
                                _sqrt(clearance2, False) - footprint.radius, -math.inf)
                            method, numeric_error = 'enclosing_disc_sweep', join_error
                            displacement = path_radius
                            accepted = True
                    if not accepted:
                        rect_clearances = tuple(_rectangle_clearance2(rectangle, p)
                                                for p in domain)
                        if all(v is not None for v in rect_clearances):
                            legal_midpoint = True
                            clearance2 = min(rect_clearances)
                            displacement = _up(_f(path_radius) *
                                               (1 + _f(footprint.radius) *
                                                _f(bounds.curvature_upper)))
                            numeric_error = _up(rect_error + join_error)
                            required = (_f(displacement) + _f(numeric_error) +
                                        _f(footprint.margin_m))
                            if clearance2 > required ** 2 and not need_split:
                                clearance = _sqrt(clearance2, False)
                                method, accepted = 'rectangle_curvature_sweep', True
                    if accepted:
                        if init_lo <= qlo < qhi <= init_hi:
                            init_clearance = _point_clearance2(xy, init_zone)
                            init_radius = _f(path_radius) + _f(join_error)
                            angle = math.atan2(float(d[1]), float(d[0]))
                            # Exact derivative evaluation leaves <=32eps vector
                            # normalization error. 512eps*condition also bounds
                            # its angular effect; atan2 adds <=4eps radians.
                            angle_error = _up(516 * math.ulp(1.) *
                                              max(1., bounds.speed_upper / bounds.speed_lower))
                            angle_radius = _up(_f(bounds.curvature_upper) *
                                               _f(path_radius) + _f(angle_error))
                            all_heading = heading_lo == -math.pi and heading_hi == math.pi
                            heading_ok = all_heading or (
                                heading_lo < angle - angle_radius and
                                angle + angle_radius < heading_hi)
                            if init_clearance is None:
                                distance2 = min(_point_segment_distance2(xy, a, b)
                                                for a, b in _edges(init_zone))
                                if distance2 > _f(join_error) ** 2:
                                    raise _Stop(
                                        'FAIL', 'demonstrated initialization zone inapplicability',
                                        (i, float(lo), float(hi)))
                            if not all_heading and (
                                    angle + angle_error < heading_lo or
                                    angle - angle_error > heading_hi):
                                raise _Stop(
                                    'FAIL', 'demonstrated initialization heading inapplicability',
                                    (i, float(lo), float(hi)))
                            if (init_clearance is None or
                                    init_clearance <= init_radius ** 2 or not heading_ok):
                                accepted = False
                                break
                        certificate = IntervalCertificate(
                            i, float(lo), float(hi),
                            (lo.numerator, lo.denominator), (hi.numerator, hi.denominator),
                            curve.owners[i][0], portal_id, bounds.curvature_upper,
                            bounds.speed_lower, displacement, clearance, footprint.margin_m,
                            numeric_error, method)
                        certificates.append(certificate)
                        break
                if not accepted and not legal_midpoint:
                    # Exact midpoint rectangle test demonstrates a violation when
                    # a body vertex is outside every permitted domain farther
                    # than normalization/join error. Near contacts stay uncertain.
                    for point in (xy,) + rectangle:
                        outside_all = True
                        for poly, _, masks in domains:
                            if all(_inside(point, p) for p in (poly,) + masks):
                                outside_all = False
                                break
                        if outside_all:
                            distances = [min(_point_segment_distance2(point, a, b)
                                             for a, b in _edges(p))
                                         for poly, _, masks in domains for p in (poly,) + masks]
                            error = join_error if point is xy else rect_error + join_error
                            if min(distances) > _f(error) ** 2:
                                raise _Stop('FAIL', 'demonstrated actual rectangle midpoint exit',
                                            (i, float(lo), float(hi)))
                    if len(domains) == 1:
                        # A simple ribbon boundary vertex strictly inside the
                        # body proves a complement wedge is covered, even when
                        # all four body corners and its reference remain legal.
                        for point in domains[0][0]:
                            clearance2 = _point_clearance2(point, rectangle)
                            if (clearance2 is not None and
                                    clearance2 > _f(rect_error + join_error) ** 2):
                                raise _Stop(
                                    'FAIL',
                                    'demonstrated rectangle interior covers legal boundary',
                                    (i, float(lo), float(hi)))
            if not accepted:
                if depth >= policy.max_depth:
                    raise _Stop('INCONCLUSIVE',
                                'continuous bound/clearance/initialization depth exhausted',
                                (i, float(lo), float(hi)))
                stack.extend(((i, lo, midpoint, depth + 1), (i, midpoint, hi, depth + 1)))
        return ValidationReport('PASS', 'continuous planar geometry and swept footprint certified',
                                tuple(certificates), gates, (), digest, coefficient_digest,
                                curve_digest=identity)
    except _Stop as exc:
        return ValidationReport(exc.status, exc.reason, tuple(certificates), gates,
                                exc.interval, digest, coefficient_digest, curve_digest=identity)
    except GeometryError as exc:
        status = 'INCONCLUSIVE' if 'budget' in str(exc) or 'uncertain' in str(exc) else 'FAIL'
        return ValidationReport(status, 'independent coefficient reconstruction: ' + str(exc),
                                tuple(certificates), gates, (), digest, coefficient_digest,
                                curve_digest=identity)
    except BoundUncertain as exc:
        return ValidationReport('INCONCLUSIVE', 'unsupported numerical bound: ' + str(exc),
                                tuple(certificates), gates, (), digest, coefficient_digest,
                                curve_digest=identity)
    except (AttributeError, TypeError, ValueError, IndexError, KeyError, OverflowError) as exc:
        return ValidationReport('FAIL', 'malformed candidate/authority: ' + str(exc),
                                tuple(certificates), gates, (), digest, coefficient_digest,
                                curve_digest=identity)
