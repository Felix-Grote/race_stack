"""Conservative offline cyclic squared-speed LP; output requires independent validation.

Inputs are explicitly supplied planar software budgets, never inferred tire/contact
performance. Binary64 source values denote exact reals; exact q intersections retain
all cap and portal restrictions even when the mesh's event parameter rounds.
"""
from dataclasses import asdict, dataclass
from fractions import Fraction
import hashlib
import io
import json
import math
from pathlib import Path
import time

import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix

from .route_corridor import OrderedCurve, _layout, resample_ordered
from .route_input import validate_route
from .route_reference import Curve, _frame
from .route_validate import BoundUncertain, interval_bounds


class DynamicsError(ValueError):
    """Invalid explicit model, profile or retiming policy."""


def _number(value, name, minimum=0., strict=True):
    if (isinstance(value, bool) or not isinstance(value, (int, float)) or
            not math.isfinite(value) or (value <= minimum if strict else value < minimum)):
        raise DynamicsError('invalid ' + name)
    return float(value)


def _text(value, name):
    if type(value) is not str or not value.strip():
        raise DynamicsError('missing ' + name)
    return value


@dataclass(frozen=True)
class SteeringLimits:
    wheelbase_m: float
    angle_max_rad: float
    rate_max_radps: float

    def __post_init__(self):
        for key in ('wheelbase_m', 'angle_max_rad', 'rate_max_radps'):
            object.__setattr__(self, key, _number(getattr(self, key), key))
        if self.angle_max_rad >= math.pi / 2:
            raise DynamicsError('steering angle must be below pi/2')


@dataclass(frozen=True)
class RegionLimits:
    speed_min_mps: float
    speed_max_mps: float
    ax_pos_mps2: float
    ax_neg_mps2: float
    ay_mps2: float
    motor_mps2: float
    drag_over_mass: float
    provenance: str

    def __post_init__(self):
        for key in ('speed_min_mps', 'drag_over_mass'):
            object.__setattr__(self, key, _number(getattr(self, key), key, strict=False))
        for key in ('speed_max_mps', 'ax_pos_mps2', 'ax_neg_mps2', 'ay_mps2',
                    'motor_mps2'):
            object.__setattr__(self, key, _number(getattr(self, key), key))
        if self.speed_min_mps >= self.speed_max_mps:
            raise DynamicsError('empty explicit speed range')
        _text(self.provenance, 'region provenance')


@dataclass(frozen=True)
class ModelRegion:
    occurrence_id: str
    surface_id: str
    limits: RegionLimits

    def __post_init__(self):
        _text(self.occurrence_id, 'occurrence identity')
        _text(self.surface_id, 'surface identity')
        if type(self.limits) is not RegionLimits:
            raise DynamicsError('explicit RegionLimits required')


@dataclass(frozen=True)
class DynamicsModel:
    regions: tuple
    provenance: str
    steering: object = None

    def __post_init__(self):
        regions = tuple(self.regions)
        if not regions or any(type(x) is not ModelRegion for x in regions):
            raise DynamicsError('explicit model regions required')
        keys = [(x.occurrence_id, x.surface_id) for x in regions]
        if len(keys) != len(set(keys)):
            raise DynamicsError('duplicate occurrence/surface model')
        if self.steering is not None and type(self.steering) is not SteeringLimits:
            raise DynamicsError('unsupported steering model')
        _text(self.provenance, 'model provenance')
        object.__setattr__(self, 'regions', regions)


@dataclass(frozen=True)
class SpeedKnot:
    segment: int
    t: float
    u: float


@dataclass(frozen=True)
class SpeedProfile:
    knots: tuple
    curve_digest: str
    model_digest: str
    lap_time_s: float

    def __post_init__(self):
        object.__setattr__(self, 'knots', tuple(self.knots))


@dataclass(frozen=True)
class ProfileMetadata:
    stations_m: tuple
    velocity_mps: tuple
    acceleration_mps2: tuple
    curvature_per_m: tuple
    time_s: tuple
    lap_time_s: float
    curve_digest: str


@dataclass(frozen=True)
class RetimePolicy:
    residual_abs: float = 1e-8
    moving_speed_mps: float = 1e-6
    max_knots: int = 10000
    max_lp_iterations: int = 100000
    time_limit_s: float = 10.
    bound_depth: int = 20
    require_steering: bool = False
    constraint_margin: float = 1e-9
    max_constraints: int = 1000000
    max_segments: int = 2048
    max_route_bytes: int = 2 * 1024 ** 2
    max_polygon_vertices: int = 512
    max_polygon_work: int = 2000000
    max_text_bytes: int = 65536

    def __post_init__(self):
        for key in ('residual_abs', 'moving_speed_mps', 'time_limit_s', 'constraint_margin'):
            _number(getattr(self, key), key)
        for key in ('max_knots', 'max_lp_iterations', 'bound_depth', 'max_constraints',
                    'max_segments', 'max_route_bytes', 'max_polygon_vertices', 'max_polygon_work',
                    'max_text_bytes'):
            if type(getattr(self, key)) is not int or getattr(self, key) <= 0:
                raise DynamicsError('invalid resource ' + key)
        if type(self.require_steering) is not bool or self.constraint_margin >= 1:
            raise DynamicsError('invalid required steering or LP margin')


@dataclass(frozen=True)
class RetimeResult:
    status: str
    profile: object
    message: str
    objective: object = None
    iterations: int = 0
    edge_count: int = 0
    max_lp_residual: object = None
    metadata: object = None


def _digest(value):
    data = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(data.encode('utf-8')).hexdigest()


def curve_digest(ordered):
    """Deterministic identity of coefficients, lineage, route and numerical policy."""
    return _digest({'coefficients': ordered.curve.coefficients, 'owners': ordered.curve.owners,
                    'q': ordered.q, 'route_digest': ordered.route.digest,
                    'numeric_policy': asdict(ordered.curve.policy)})


def model_digest(model):
    return _digest(asdict(model))


class _Abort(Exception):
    def __init__(self, status, reason):
        self.status, self.reason = status, reason


def _check_time(deadline):
    if time.monotonic() >= deadline:
        raise _Abort('INCONCLUSIVE', 'retiming time budget exhausted')


def _arc_interval(segment, t0, t1):
    a, b = segment.arc(t0), segment.arc(t1)
    ds = b - a
    # Every partial integral has the segment's complete declared error budget.
    error = 2 * segment.policy.arc_abs + 32 * np.finfo(float).eps * (abs(a) + abs(b))
    lo = math.nextafter(ds - error, -math.inf)
    hi = math.nextafter(ds + error, math.inf)
    if not 0 < lo <= ds <= hi or not math.isfinite(hi):
        raise _Abort('INCONCLUSIVE', 'metric edge uncertainty exceeds positive arc')
    return ds, lo, hi


def _cap_min(occurrence, start, lo, hi, end):
    caps = occurrence.caps
    selected = []
    for i, (local, cap) in enumerate(caps):
        a = start + Fraction(local)
        b = start + Fraction(caps[i + 1][0]) if i + 1 < len(caps) else end
        if a <= hi and b >= lo:
            selected.append(cap)
    if not selected:
        raise _Abort('REJECT', 'missing explicit static cap coverage')
    return min(selected)


def _edge_support(ordered, regions, segment, t0, t1):
    """Whole-edge closed exact-q overlaps; no rounded-event midpoint shortcut."""
    route = ordered.route
    ends = tuple(Fraction(x) for x in _layout(route))
    q0, q1 = Fraction(ordered.q[segment]), Fraction(ordered.q[segment + 1])
    lo = q0 + Fraction(t0) * (q1 - q0)
    hi = q0 + Fraction(t1) * (q1 - q0)
    owner = ordered.curve.owners[segment]
    index = next(i for i, o in enumerate(route.occurrences) if (o.id, o.surface_id) == owner)
    current = route.occurrences[index]
    limits = {index: regions[owner]}
    cap = _cap_min(current, ends[index], lo, hi, ends[index + 1])
    period = ends[-1]
    for i, portal in enumerate(route.portals):
        target = (i + 1) % len(route.occurrences)
        a, b = ends[i + 1] - Fraction(portal.before), ends[i + 1] + Fraction(portal.after)
        if any(a + shift <= hi and b + shift >= lo for shift in (-period, 0, period)):
            for j in (i, target):
                o = route.occurrences[j]
                limits[j] = regions[(o.id, o.surface_id)]
            previous, following = route.occurrences[i], route.occurrences[target]
            cap = min(cap, _cap_min(previous, ends[i], a, ends[i + 1], ends[i + 1]),
                      _cap_min(following, ends[target], ends[target],
                               ends[target] + Fraction(portal.after), ends[target + 1]))
    return cap, tuple(limits[j] for j in sorted(limits))


def _mesh(ordered, spacing_m, policy, deadline, steering):
    # Retain W1's canonical rounded semantic event anchors, not an extra near-ulp
    # rational event mesh. Exact source events still govern all edge constraints.
    anchors = set()
    for sample in resample_ordered(ordered, spacing_m):
        if sample.t == 1.:
            anchors.add(((sample.segment + 1) % len(ordered.curve.segments), 0.))
        else:
            anchors.add((sample.segment, sample.t))
    anchors.update((i, 0.) for i in range(len(ordered.curve.segments)))
    if len(anchors) > policy.max_knots:
        raise _Abort('INCONCLUSIVE', 'retiming knot budget exhausted')
    initial = sorted(anchors)
    leaves = []
    for k, (segment, t0) in enumerate(initial):
        following = initial[(k + 1) % len(initial)]
        t1 = following[1] if following[0] == segment else 1.
        stack = [(t0, t1, 0)]
        while stack:
            _check_time(deadline)
            a, b, depth = stack.pop()
            try:
                bound = interval_bounds(ordered.curve.segments[segment].coefficients, a, b)
                uncertain = bound.speed_lower <= ordered.curve.policy.min_speed
                steer = steering
                angle_uncertain = (steer is not None and
                                   math.atan(steer.wheelbase_m * bound.curvature_upper) >
                                   steer.angle_max_rad)
                uncertain = uncertain or angle_uncertain
            except BoundUncertain:
                uncertain = True
            if uncertain:
                mid = (a + b) / 2
                if depth >= policy.bound_depth or not a < mid < b:
                    raise _Abort('INCONCLUSIVE', 'curvature/steering bound budget exhausted')
                if len(anchors) >= policy.max_knots:
                    raise _Abort('INCONCLUSIVE', 'retiming knot budget exhausted')
                anchors.add((segment, mid))
                stack.extend(((mid, b, depth + 1), (a, mid, depth + 1)))
                continue
            ds, low, high = _arc_interval(ordered.curve.segments[segment], a, b)
            leaves.append((segment, a, b, ds, low, high, bound))
    return tuple(sorted(leaves, key=lambda x: (x[0], x[1])))


def retime(ordered, model, spacing_m=.5, policy=RetimePolicy()):
    """Maximize distance-weighted u under sufficient whole-lap constraints.

    CANDIDATE is a numerical result, never an independent acceptance verdict.
    The positive moving-speed floor is a declared traversal policy, not grip data.
    """
    if type(policy) is not RetimePolicy:
        return RetimeResult('UNSUPPORTED', None, 'explicit supported retiming policy required')
    deadline = time.monotonic() + policy.time_limit_s
    try:
        _number(spacing_m, 'metric spacing')
        floor_squared = policy.moving_speed_mps ** 2
        if not math.isfinite(floor_squared) or floor_squared <= 0:
            raise _Abort('UNSUPPORTED', 'moving-speed floor outside supported binary64 range')
        if type(model) is not DynamicsModel:
            raise _Abort('UNSUPPORTED', 'explicit supported planar model required')
        if policy.require_steering and model.steering is None:
            raise _Abort('UNSUPPORTED', 'required steering model absent')
        # Bound work before reconstruction and metric inversion. Cached L only
        # rejects early; reconstructed geometry below remains the authority.
        segment_count = len(ordered.curve.segments)
        if (segment_count > policy.max_segments or
                len(ordered.route.encoded) > policy.max_route_bytes):
            raise _Abort('INCONCLUSIVE', 'retiming encoded source-size budget exhausted')
        if (segment_count > policy.max_knots or len(ordered.q) != segment_count + 1 or
                len(ordered.route.occurrences) > policy.max_knots or
                len(model.regions) > policy.max_knots):
            raise _Abort('INCONCLUSIVE', 'retiming source-size budget exhausted')
        texts = [model.provenance]
        for region in model.regions:
            texts.extend((region.occurrence_id, region.surface_id, region.limits.provenance))
        # Character lengths reject huge strings before allocating encoded copies.
        if (sum(len(value) for value in texts) > policy.max_text_bytes or
                sum(len(value.encode('utf-8')) for value in texts) > policy.max_text_bytes):
            raise _Abort('INCONCLUSIVE', 'retiming model text budget exhausted')
        coefficients, owners = ordered.curve.coefficients, ordered.curve.owners
        if (len(coefficients) != segment_count or len(owners) != segment_count or
                any(len(c) != 2 or any(len(row) != 4 for row in c) for c in coefficients)):
            raise _Abort('REJECT', 'invalid coefficient/owner dimensions')
        if math.ceil(ordered.curve.length / spacing_m) > policy.max_knots:
            raise _Abort('INCONCLUSIVE', 'retiming uniform knot budget exhausted')
        _check_time(deadline)
        # Reconstruct the coefficient/route authorities; no cached station is trusted.
        payload = ordered.route.payload
        polygon_counts = [len(o['left']) + len(o['right']) for o in payload['occurrences']]
        polygon_counts += [len(p['support']) for p in payload['transitions']]
        polygon_counts.append(len(payload['initialization']['zone']))
        if (any(n > policy.max_polygon_vertices for n in polygon_counts) or
                sum(n * n for n in polygon_counts) > policy.max_polygon_work):
            raise _Abort('INCONCLUSIVE', 'retiming route-predicate work budget exhausted')
        semantic = sum(len(o['caps']) for o in payload['occurrences']) + 3 * len(model.regions)
        predicted = math.ceil(ordered.curve.length / spacing_m) + semantic + segment_count
        if predicted > policy.max_knots:
            raise _Abort('INCONCLUSIVE', 'retiming combined mesh budget exhausted')
        route = validate_route(payload)
        if route != ordered.route:
            raise _Abort('REJECT', 'route record differs from approved payload')
        curve = Curve(coefficients, owners, ordered.curve.policy)
        if curve != ordered.curve:
            raise _Abort('REJECT', 'stale curve metric metadata')
        ordered = OrderedCurve(route, curve, ordered.q)
        _check_time(deadline)
        if math.ceil(curve.length / spacing_m) > policy.max_knots:
            raise _Abort('INCONCLUSIVE', 'retiming uniform knot budget exhausted')
        regions = {(r.occurrence_id, r.surface_id): r.limits for r in model.regions}
        if set(regions) != {(o.id, o.surface_id) for o in route.occurrences}:
            raise _Abort('UNSUPPORTED', 'model does not cover exact occurrence/surface set')
        edges = _mesh(ordered, spacing_m, policy, deadline, model.steering)
        count = len(edges)
        lower = [floor_squared] * count
        upper = [math.inf] * count
        rows, cols, values, rhs = [], [], [], []
        weights = np.zeros(count)

        def constraint(i, j, ci, cj):
            if len(rhs) >= policy.max_constraints:
                raise _Abort('INCONCLUSIVE', 'LP constraint budget exhausted')
            if not math.isfinite(ci) or not math.isfinite(cj):
                raise _Abort('INCONCLUSIVE', 'nonfinite normalized constraint')
            row = len(rhs)
            rows.extend((row, row))
            cols.extend((i, j))
            values.extend((ci, cj))
            rhs.append(1 - policy.constraint_margin)

        for i, (segment, t0, t1, ds, low, high, bound) in enumerate(edges):
            _check_time(deadline)
            j = (i + 1) % count
            weights[i] += ds / 2
            weights[j] += ds / 2
            cap, supported = _edge_support(ordered, regions, segment, t0, t1)
            if model.steering is not None and bound.curvature_rate_upper > 0:
                steering = model.steering
                rate_factor = steering.wheelbase_m * bound.curvature_rate_upper
                if not math.isfinite(rate_factor) or rate_factor <= 0:
                    raise _Abort('INCONCLUSIVE', 'steering rate bound exceeds numerical range')
                cap = min(cap, steering.rate_max_radps / rate_factor)
            for limits in supported:
                minimum = max(policy.moving_speed_mps, limits.speed_min_mps) ** 2
                maximum = min(cap, limits.speed_max_mps) ** 2
                for node in (i, j):
                    lower[node] = max(lower[node], minimum)
                    upper[node] = min(upper[node], math.nextafter(maximum, 0.))
                for distance in (low, high):
                    acceleration = 1 / (2 * distance)
                    for endpoint in (i, j):
                        for sign, axis in ((1, limits.ax_pos_mps2),
                                           (-1, limits.ax_neg_mps2)):
                            extra = (sign * limits.drag_over_mass / axis +
                                     bound.curvature_upper / limits.ay_mps2)
                            ci, cj = -sign * acceleration / axis, sign * acceleration / axis
                            constraint(i, j, ci + (extra if endpoint == i else 0.),
                                       cj + (extra if endpoint == j else 0.))
                        motor = limits.motor_mps2
                        extra = limits.drag_over_mass / motor
                        constraint(i, j, -acceleration / motor +
                                   (extra if endpoint == i else 0.), acceleration / motor +
                                   (extra if endpoint == j else 0.))
        if any(a > b or not math.isfinite(b) for a, b in zip(lower, upper)):
            raise _Abort('REJECT', 'static/model/steering caps contradict moving speed range')
        matrix = coo_matrix((values, (rows, cols)), shape=(len(rhs), count)).tocsr()
        _check_time(deadline)
        solved = linprog(-weights, A_ub=matrix, b_ub=np.asarray(rhs),
                         bounds=list(zip(lower, upper)), method='highs',
                         options={'maxiter': policy.max_lp_iterations,
                                  'time_limit': max(1e-6, deadline - time.monotonic()),
                                  'primal_feasibility_tolerance': 1e-10,
                                  'dual_feasibility_tolerance': 1e-10})
        _check_time(deadline)
        if not solved.success:
            status = 'REJECT' if solved.status == 2 else 'INCONCLUSIVE'
            raise _Abort(status, 'cyclic LP failed: ' + str(solved.message))
        u = np.asarray(solved.x)
        if u.shape != (count,) or not np.isfinite(u).all():
            raise _Abort('INCONCLUSIVE', 'nonfinite or malformed cyclic LP result')
        residual = max(0., float(np.max(matrix @ u - np.asarray(rhs))),
                       max(a - v for a, v in zip(lower, u)),
                       max(v - b for v, b in zip(u, upper)))
        if residual > policy.residual_abs:
            raise _Abort('INCONCLUSIVE', 'LP residual exceeds declared allowance')
        knots = tuple(SpeedKnot(e[0], e[1], float(v)) for e, v in zip(edges, u))
        velocity = tuple(math.sqrt(float(v)) for v in u)
        acceleration, times = [], [0.]
        for i, edge in enumerate(edges):
            j = (i + 1) % count
            acceleration.append(float((u[j] - u[i]) / (2 * edge[3])))
            times.append(times[-1] + 2 * edge[3] / (velocity[i] + velocity[j]))
        identity = curve_digest(ordered)
        profile = SpeedProfile(knots, identity, model_digest(model), times[-1])
        metadata = ProfileMetadata(
            tuple(curve.station(k.segment, k.t) for k in knots), velocity,
            tuple(acceleration), tuple(_frame(curve.segments[k.segment], k.t)[1] for k in knots),
            tuple(times[:-1]), times[-1], identity)
        _check_time(deadline)
        return RetimeResult('CANDIDATE', profile, 'independent validation required',
                            float(weights @ u), int(solved.nit), count, residual, metadata)
    except _Abort as exc:
        return RetimeResult(exc.status, None, exc.reason)
    except (ValueError, TypeError, ArithmeticError, RuntimeError, AttributeError,
            KeyError, IndexError) as exc:
        return RetimeResult('INCONCLUSIVE', None, 'retiming computation failed: ' + str(exc))


def _table(path, columns):
    path = Path(path)
    limit = 8 * 1024 * 1024
    with path.open('rb') as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise DynamicsError('table resource size exceeded')
    table = np.loadtxt(io.BytesIO(data), delimiter=',', comments='#', ndmin=2)
    if (table.shape[1] != columns or len(table) < 2 or not np.isfinite(table).all() or
            np.any(np.diff(table[:, 0]) <= 0) or table[0, 0] < 0 or
            np.any(table[:, 1:] <= 0)):
        raise DynamicsError('unsupported finite ordered positive table')
    return table, hashlib.sha256(data).hexdigest()


def _table_minimum(table, column, low, high):
    if low < table[0, 0] or high > table[-1, 0]:
        raise DynamicsError('table does not cover full declared speed range; no extrapolation')

    def value(x):
        i = min(max(0, int(np.searchsorted(table[:, 0], x, side='right')) - 1), len(table) - 2)
        a, b = (Fraction(float(table[j, 0])) for j in (i, i + 1))
        y, z = (Fraction(float(table[j, column])) for j in (i, i + 1))
        return y + (Fraction(x) - a) * (z - y) / (b - a)
    candidates = [value(low), value(high)]
    candidates.extend(Fraction(float(row[column])) for row in table if low <= row[0] <= high)
    exact = min(candidates)
    result = float(exact)
    if Fraction(result) > exact:
        result = math.nextafter(result, 0.)
    return result


def limits_from_tables(ggv_path, motor_path, *, speed_min_mps, speed_max_mps,
                       braking_mps2, drag_over_mass, provenance):
    """Import explicit CSVs using conservative full-range piecewise-linear minima.

    GGV columns are speed, positive longitudinal axis, lateral axis. Motor columns
    are speed, motor acceleration. Braking and drag are separate supplied budgets.
    These files alone do not establish a combined tire or physical contact model.
    """
    low = _number(speed_min_mps, 'minimum table speed', strict=False)
    high = _number(speed_max_mps, 'maximum table speed')
    if low >= high:
        raise DynamicsError('empty table speed range')
    ggv, ggv_hash = _table(ggv_path, 3)
    motor, motor_hash = _table(motor_path, 2)
    source = json.dumps({'supplied_provenance': _text(provenance, 'table provenance'),
                         'ggv_sha256': ggv_hash, 'motor_sha256': motor_hash,
                         'speed_range_mps': [low, high],
                         'rule': 'piecewise_linear_full_range_minimum'}, sort_keys=True)
    return RegionLimits(low, high, _table_minimum(ggv, 1, low, high), braking_mps2,
                        _table_minimum(ggv, 2, low, high),
                        _table_minimum(motor, 1, low, high), drag_over_mass, source)
