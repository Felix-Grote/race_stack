"""Independent continuous acceptance of the declared planar cyclic speed model.

This module never consumes LP rows, solver residuals, success flags or retimer
constraint helpers. Binary64 model/profile values denote exact reals. Fraction
arithmetic checks both distance extremes and endpoint squared speeds; A05's
independently bounded polynomial kernel encloses interior curvature and rate.
"""
from bisect import bisect_right
from dataclasses import asdict, dataclass
from fractions import Fraction
import hashlib
import json
import math
import time

from .cyclic_retime import (DynamicsModel, ModelRegion, ProfileMetadata, RegionLimits,
                            SpeedKnot, SpeedProfile, SteeringLimits)
from .route_input import validate_route
from .route_reference import Curve, GeometryError, NumericPolicy
from .route_validate import BoundUncertain, _sqrt, interval_bounds


@dataclass(frozen=True)
class DynamicsValidationPolicy:
    """Software accuracy/resources, separate from supplied physical budgets."""

    numeric_policy: NumericPolicy = NumericPolicy()
    residual_abs: float = 1e-8  # normalized motor/diamond/squared-speed/rate residual
    angle_abs_rad: float = 1e-10
    metadata_abs: float = 1e-7
    metadata_rel: float = 1e-8
    moving_speed_mps: float = 1e-6
    max_knots: int = 10000
    max_segments: int = 2048
    max_intervals: int = 100000
    max_depth: int = 20
    max_route_bytes: int = 2 * 1024 ** 2
    max_polygon_vertices: int = 512
    max_polygon_work: int = 2000000
    max_model_regions: int = 2048
    max_text_bytes: int = 65536
    wall_seconds: float = 120.
    require_steering: bool = False

    def __post_init__(self):
        if type(self.numeric_policy) is not NumericPolicy:
            raise ValueError('independent NumericPolicy required')
        for key in ('residual_abs', 'angle_abs_rad', 'metadata_abs', 'metadata_rel',
                    'moving_speed_mps', 'wall_seconds'):
            value = getattr(self, key)
            if (isinstance(value, bool) or not isinstance(value, (int, float)) or
                    not math.isfinite(value) or value <= 0):
                raise ValueError('invalid independent dynamics policy: ' + key)
        for key in ('max_knots', 'max_segments', 'max_intervals', 'max_depth',
                    'max_route_bytes', 'max_polygon_vertices', 'max_polygon_work',
                    'max_model_regions', 'max_text_bytes'):
            if type(getattr(self, key)) is not int or getattr(self, key) < 0:
                raise ValueError('invalid independent dynamics resource: ' + key)
        if type(self.require_steering) is not bool:
            raise ValueError('invalid required steering policy')


@dataclass(frozen=True)
class DynamicEdgeCertificate:
    edge: int
    segment: int
    t0: float
    t1: float
    closing: bool
    distance_m: float
    distance_lower_m: float
    distance_upper_m: float
    acceleration_lower_mps2: float
    acceleration_upper_mps2: float
    curvature_upper: float
    curvature_rate_upper: float
    cap_mps: float
    support_occurrences: tuple
    normalized_residual_upper: float
    steering_angle_residual_rad: float
    bound_intervals: int
    time_lower_s: float
    time_upper_s: float


@dataclass(frozen=True)
class DynamicsValidationReport:
    status: str
    reason: str
    edges: tuple = ()
    worst_residuals: tuple = ()
    offending_edge: int = -1
    curve_digest: str = ''
    model_digest: str = ''
    lap_time_s: float = 0.
    lap_time_lower_s: float = 0.
    lap_time_upper_s: float = 0.
    lap_time_error_s: float = 0.
    coverage: tuple = ('declared_planar_diamond', 'motor_and_drag', 'cyclic_closure',
                       'original_static_caps', 'supplied_surface_limits')
    assumptions: tuple = ('exact binary64 source/model/profile values',
                          'A05 exact-rational polynomial enclosures',
                          'W1 bounded local arc integration',
                          'IEEE754 sqrt and atan within four ulps',
                          'normalized residual tolerance is software accuracy only',
                          'no tire/contact/3D/physical vehicle certification')


class _Stop(Exception):
    def __init__(self, status, reason, edge=-1):
        self.status, self.reason, self.edge = status, reason, edge


def _f(value):
    if (isinstance(value, bool) or not isinstance(value, (int, float, Fraction)) or
            isinstance(value, float) and not math.isfinite(value)):
        raise _Stop('FAIL', 'nonfinite/non-numeric independent input')
    return Fraction(value)


def _up(value):
    try:
        converted = float(value)
    except OverflowError as exc:
        raise _Stop('INCONCLUSIVE', 'unrepresentable independent numerical bound') from exc
    if not math.isfinite(converted):
        raise _Stop('INCONCLUSIVE', 'unrepresentable independent numerical bound')
    result = math.nextafter(math.nextafter(converted, math.inf), math.inf)
    if not math.isfinite(result):
        raise _Stop('INCONCLUSIVE', 'unrepresentable independent numerical bound')
    return result


def _down(value):
    try:
        converted = float(value)
    except OverflowError as exc:
        raise _Stop('INCONCLUSIVE', 'unrepresentable independent numerical bound') from exc
    if not math.isfinite(converted):
        raise _Stop('INCONCLUSIVE', 'unrepresentable independent numerical bound')
    result = math.nextafter(math.nextafter(converted, -math.inf), -math.inf)
    if not math.isfinite(result):
        raise _Stop('INCONCLUSIVE', 'unrepresentable independent numerical bound')
    return result


def _digest(value):
    encoded = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(encoded.encode('utf-8')).hexdigest()


def _binary_number(value):
    return (not isinstance(value, bool) and isinstance(value, (int, float)) and
            math.isfinite(value))


def _angle(value):
    # A positive rational too large for binary64 has atan below pi/2. Using
    # pi/2 is a safe upper limit; no overflowing bound becomes a false FAIL.
    try:
        return math.atan(float(value))
    except OverflowError:
        return math.pi / 2


def _identities(ordered, model):
    curve = _digest({'coefficients': ordered.curve.coefficients,
                     'owners': ordered.curve.owners, 'q': ordered.q,
                     'route_digest': ordered.route.digest,
                     'numeric_policy': asdict(ordered.curve.policy)})
    return curve, _digest(asdict(model))


def _model_regions(model, route, policy):
    if type(model) is not DynamicsModel:
        raise _Stop('UNSUPPORTED', 'explicit supported planar DynamicsModel required')
    if type(model.provenance) is not str or not model.provenance.strip():
        raise _Stop('UNSUPPORTED', 'missing explicit model provenance')
    if len(model.regions) != len(route.occurrences):
        raise _Stop('UNSUPPORTED', 'model must cover every original occurrence/surface')
    regions = {}
    for region in model.regions:
        if type(region) is not ModelRegion or type(region.limits) is not RegionLimits:
            raise _Stop('UNSUPPORTED', 'unsupported model region or missing declared limits')
        key = region.occurrence_id, region.surface_id
        if key in regions:
            raise _Stop('UNSUPPORTED', 'duplicate original occurrence/surface model')
        limits = region.limits
        for name in ('speed_min_mps', 'speed_max_mps', 'ax_pos_mps2', 'ax_neg_mps2',
                     'ay_mps2', 'motor_mps2', 'drag_over_mass'):
            if not _binary_number(getattr(limits, name)):
                raise _Stop('UNSUPPORTED', 'non-binary64 supplied model limit')
            value = _f(getattr(limits, name))
            nonnegative = name in ('speed_min_mps', 'drag_over_mass')
            if value < 0 or (not nonnegative and value == 0):
                raise _Stop('UNSUPPORTED', 'nonpositive or unsupported supplied model limit')
        if limits.speed_min_mps >= limits.speed_max_mps:
            raise _Stop('UNSUPPORTED', 'empty supplied moving speed range')
        if type(limits.provenance) is not str or not limits.provenance.strip():
            raise _Stop('UNSUPPORTED', 'missing supplied region provenance')
        regions[key] = limits
    if set(regions) != {(o.id, o.surface_id) for o in route.occurrences}:
        raise _Stop('UNSUPPORTED', 'wrong original occurrence/surface model coverage')
    steering = model.steering
    if policy.require_steering and steering is None:
        raise _Stop('UNSUPPORTED', 'required supplied steering model is absent')
    if steering is not None:
        if type(steering) is not SteeringLimits:
            raise _Stop('UNSUPPORTED', 'unsupported supplied steering model')
        if any(not _binary_number(getattr(steering, x)) or
               _f(getattr(steering, x)) <= 0 for x in
               ('wheelbase_m', 'angle_max_rad', 'rate_max_radps')):
            raise _Stop('UNSUPPORTED', 'invalid supplied steering limits')
        if steering.angle_max_rad >= math.pi / 2:
            raise _Stop('UNSUPPORTED', 'unsupported steering angle range')
    return regions


def _authority(ordered, policy):
    if (type(ordered.route.encoded) is not bytes or
            len(ordered.route.encoded) > policy.max_route_bytes or
            len(ordered.curve.segments) > policy.max_segments):
        raise _Stop('INCONCLUSIVE', 'independent dynamics input budget exhausted')
    count = len(ordered.curve.segments)
    coefficients = ordered.curve.coefficients
    if (len(coefficients) != count or len(ordered.curve.owners) != count or
            len(ordered.q) != count + 1):
        raise _Stop('FAIL', 'inconsistent independent coefficient/owner/q shape')
    for coefficient in coefficients:
        if len(coefficient) != 2 or any(len(row) != 4 for row in coefficient):
            raise _Stop('FAIL', 'invalid actual coefficient tensor')
        for row in coefficient:
            for value in row:
                if not _binary_number(value) or abs(_f(value)) > 1e8:
                    raise _Stop('FAIL', 'actual coefficient exceeds supported magnitude')
    payload = ordered.route.payload
    if (len(payload['occurrences']) > policy.max_segments or
            len(payload['transitions']) > policy.max_segments):
        raise _Stop('INCONCLUSIVE', 'independent route record budget exhausted')
    sizes = [len(o['left']) + len(o['right']) for o in payload['occurrences']]
    sizes += [len(p['support']) for p in payload['transitions']]
    sizes.append(len(payload['initialization']['zone']))
    if (any(size > policy.max_polygon_vertices for size in sizes) or
            sum(size * size for size in sizes) > policy.max_polygon_work or
            sum(len(o['seed']) for o in payload['occurrences']) > policy.max_segments * 2):
        raise _Stop('INCONCLUSIVE', 'independent original geometry budget exhausted')
    route = validate_route(payload)
    if route != ordered.route:
        raise _Stop('FAIL', 'forged original route authority')
    if ordered.curve.policy != policy.numeric_policy:
        raise _Stop('FAIL', 'independently expected numerical policy mismatch')
    curve = Curve(coefficients, ordered.curve.owners, policy.numeric_policy)
    if curve != ordered.curve:
        raise _Stop('FAIL', 'stale or corrupt canonical metric metadata')
    ends = [0.]
    for index, occurrence in enumerate(route.occurrences):
        if route.portals[index - 1].after + route.portals[index].before >= \
                occurrence.length - 1e-9:
            raise _Stop('FAIL', 'overlapping original portal progress supports')
        ends.append(ends[-1] + occurrence.length)
    ends = tuple(_f(x) for x in ends)
    if any(not _binary_number(value) for value in ordered.q):
        raise _Stop('FAIL', 'inherited q must use finite binary64 values')
    q = tuple(_f(x) for x in ordered.q)
    if (q[0] != 0 or q[-1] != ends[-1] or any(a >= b for a, b in zip(q, q[1:])) or
            any(x not in q for x in ends)):
        raise _Stop('FAIL', 'invalid exact inherited q or missing occurrence anchors')
    for index, owner in enumerate(curve.owners):
        occurrence = min(bisect_right(ends, q[index]) - 1, len(route.occurrences) - 1)
        original = route.occurrences[occurrence]
        if (q[index + 1] > ends[occurrence + 1] or
                owner != (original.id, original.surface_id)):
            raise _Stop('FAIL', 'wrong inherited occurrence/surface ownership')
    return route, curve, q, ends


def _cap(occurrence, start, end, low, high):
    positions = tuple(start + _f(local) for local, _ in occurrence.caps)
    if positions[-1] >= end or any(a >= b for a, b in zip(positions, positions[1:])):
        raise _Stop('INCONCLUSIVE', 'unresolvable original static cap ordering')
    values = [value for index, (_, value) in enumerate(occurrence.caps)
              if positions[index] <= high and
              (positions[index + 1] if index + 1 < len(positions) else end) >= low]
    if not values:
        raise _Stop('FAIL', 'missing original static speed cap coverage')
    return min(values)


def _budgets(route, ends, regions, low, high):
    """Closed rational q overlaps retain events rounded across a stored knot."""
    selected, caps = {}, []
    for index, occurrence in enumerate(route.occurrences):
        left, right = max(low, ends[index]), min(high, ends[index + 1])
        if left <= right:
            selected[index] = regions[(occurrence.id, occurrence.surface_id)]
            caps.append(_cap(occurrence, ends[index], ends[index + 1], left, right))
    period = ends[-1]
    for index, portal in enumerate(route.portals):
        before, after = _f(portal.before), _f(portal.after)
        start, finish = ends[index + 1] - before, ends[index + 1] + after
        if not any(start + shift <= high and finish + shift >= low
                   for shift in (-period, Fraction(0), period)):
            continue
        target = (index + 1) % len(route.occurrences)
        for owner, left, right in ((index, ends[index + 1] - before, ends[index + 1]),
                                   (target, ends[target], ends[target] + after)):
            occurrence = route.occurrences[owner]
            selected[owner] = regions[(occurrence.id, occurrence.surface_id)]
            caps.append(_cap(occurrence, ends[owner], ends[owner + 1], left, right))
    return min(caps), tuple((route.occurrences[i].id, value)
                            for i, value in sorted(selected.items()))


def _profile_knots(profile, curve, policy):
    if type(profile) is not SpeedProfile:
        raise _Stop('FAIL', 'canonical immutable SpeedProfile required')
    if not _binary_number(profile.lap_time_s) or profile.lap_time_s <= 0:
        raise _Stop('FAIL', 'nonpositive/nonfinite profile lap-time metadata')
    knots = profile.knots
    if not knots or len(knots) > policy.max_knots:
        raise _Stop('INCONCLUSIVE', 'independent speed knot budget exhausted')
    anchors = []
    for knot in knots:
        if (type(knot) is not SpeedKnot or type(knot.segment) is not int or
                not 0 <= knot.segment < len(curve.segments) or
                not _binary_number(knot.t) or not _binary_number(knot.u) or
                not 0 <= _f(knot.t) < 1 or _f(knot.u) <= 0):
            raise _Stop('FAIL', 'invalid canonical half-open speed knot')
        anchors.append((knot.segment, _f(knot.t)))
    if anchors[0] != (0, 0) or any(a >= b for a, b in zip(anchors, anchors[1:])):
        raise _Stop('FAIL', 'speed anchors must start at seam and increase uniquely')
    if any((index, Fraction(0)) not in anchors for index in range(len(curve.segments))):
        raise _Stop('FAIL', 'speed profile lost a coefficient boundary anchor')
    return tuple(knots)


def _input_limits(profile, model, metadata, policy):
    if type(profile) is not SpeedProfile:
        raise _Stop('FAIL', 'canonical immutable SpeedProfile required')
    if len(profile.knots) > policy.max_knots:
        raise _Stop('INCONCLUSIVE', 'independent speed knot budget exhausted')
    if type(model) is not DynamicsModel:
        raise _Stop('UNSUPPORTED', 'explicit supported planar DynamicsModel required')
    if len(model.regions) > policy.max_model_regions:
        raise _Stop('INCONCLUSIVE', 'independent model region budget exhausted')
    texts = [model.provenance]
    for region in model.regions:
        if type(region) is not ModelRegion or type(region.limits) is not RegionLimits:
            raise _Stop('UNSUPPORTED', 'unsupported supplied model region')
        texts.extend((region.occurrence_id, region.surface_id, region.limits.provenance))
    if any(type(value) is not str for value in texts):
        raise _Stop('UNSUPPORTED', 'missing supplied model identity/provenance')
    if (sum(len(value) for value in texts) > policy.max_text_bytes or
            sum(len(value.encode('utf-8')) for value in texts) > policy.max_text_bytes):
        raise _Stop('INCONCLUSIVE', 'independent provenance byte budget exhausted')
    for value in (profile.curve_digest, profile.model_digest):
        if type(value) is not str or len(value) != 64:
            raise _Stop('FAIL', 'malformed profile provenance digest')
    if metadata is not None:
        if type(metadata) is not ProfileMetadata:
            raise _Stop('FAIL', 'unsupported exported metadata record')
        if any(len(getattr(metadata, name)) > policy.max_knots for name in
               ('stations_m', 'velocity_mps', 'acceleration_mps2',
                'curvature_per_m', 'time_s')):
            raise _Stop('INCONCLUSIVE', 'independent exported metadata budget exhausted')


def _arc(segment, low, high):
    first, last = segment.arc(float(low)), segment.arc(float(high))
    nominal = last - first
    error = 2 * _f(segment.policy.arc_abs)
    error += 32 * _f(math.ulp(1.)) * (abs(_f(first)) + abs(_f(last)))
    # Interior witness parameters are exact dyadics and need not fit in 53 bits.
    # Their conversion error is transported through the conservative speed bound.
    error += _f(segment.speed_upper) * (abs(_f(float(low)) - low) +
                                        abs(_f(float(high)) - high))
    lower, upper = _down(_f(nominal) - error), _up(_f(nominal) + error)
    if not 0 < lower <= nominal <= upper:
        raise _Stop('INCONCLUSIVE', 'metric edge uncertainty exceeds positive arc')
    return nominal, lower, upper


def _polynomial(coefficient, parameter, order=0):
    result = []
    for row in coefficient:
        values = tuple(_f(x) for x in row)
        for _ in range(order):
            values = tuple(i * values[i] for i in range(1, len(values)))
        value = Fraction(0)
        for number in reversed(values):
            value = value * parameter + number
        result.append(value)
    return tuple(result)


def _point_curvature(coefficient, parameter):
    d = _polynomial(coefficient, parameter, 1)
    dd = _polynomial(coefficient, parameter, 2)
    third = _polynomial(coefficient, parameter, 3)
    g = d[0] ** 2 + d[1] ** 2
    if g <= 0:
        raise _Stop('FAIL', 'demonstrated zero derivative in final coefficients')
    cross = d[0] * dd[1] - d[1] * dd[0]
    cross_prime = d[0] * third[1] - d[1] * third[0]
    g_prime = 2 * (d[0] * dd[0] + d[1] * dd[1])
    rate = (2 * cross_prime * g - 3 * cross * g_prime) / (2 * g ** 3)
    return cross ** 2 / g ** 3, rate ** 2, cross, g


def _residuals(accelerations, speeds, curvature, rate, cap, supports, steering, policy):
    """Direct exact model evaluation at every sufficient corner, never LP rows."""
    result = {'static_speed': max(u / _f(cap) ** 2 - 1 for u in speeds),
              'moving_speed': max((_f(policy.moving_speed_mps) ** 2 - u) /
                                  _f(policy.moving_speed_mps) ** 2 for u in speeds)}
    for _, limits in supports:
        result['model_speed'] = max(result.get('model_speed', -math.inf),
                                    max(u / _f(limits.speed_max_mps) ** 2 - 1
                                        for u in speeds))
        result['minimum_speed'] = max(result.get('minimum_speed', -math.inf),
                                      max((_f(limits.speed_min_mps) ** 2 - u) /
                                          max(Fraction(1), _f(limits.speed_min_mps) ** 2)
                                          for u in speeds))
        for acceleration in accelerations:
            for u in speeds:
                drive = acceleration + _f(limits.drag_over_mass) * u
                values = {'motor': drive / _f(limits.motor_mps2) - 1,
                          'diamond_positive': drive / _f(limits.ax_pos_mps2) +
                          curvature * u / _f(limits.ay_mps2) - 1,
                          'diamond_negative': -drive / _f(limits.ax_neg_mps2) +
                          curvature * u / _f(limits.ay_mps2) - 1,
                          'lateral': curvature * u / _f(limits.ay_mps2) - 1}
                for key, value in values.items():
                    result[key] = max(result.get(key, -math.inf), value)
    if steering is not None:
        result['steering_rate'] = max((_f(steering.wheelbase_m) * rate) ** 2 * u /
                                      _f(steering.rate_max_radps) ** 2 - 1 for u in speeds)
        angle = _angle(_f(steering.wheelbase_m) * curvature)
        result['steering_angle_rad'] = angle + 8 * math.ulp(1.) - steering.angle_max_rad
    return result


def _violates(values, policy):
    return any(value > (policy.angle_abs_rad if key == 'steering_angle_rad' else
                        policy.residual_abs) for key, value in values.items())


def _witness(coefficient, parameter, segment, low, high, ui, uj, distances,
             accelerations, cap, supports, steering, policy):
    if ui == uj:
        speeds = (ui,)
    elif parameter == low:
        speeds = (ui,)
    elif parameter == high:
        speeds = (uj,)
    else:
        _, local_low, local_high = _arc(segment, low, parameter)
        ratios = (max(Fraction(0), _f(local_low) / _f(distances[2])),
                  min(Fraction(1), _f(local_high) / _f(distances[1])))
        speeds = tuple(ui + (uj - ui) * ratio for ratio in ratios)
    squared, rate_squared, _, _ = _point_curvature(coefficient, parameter)
    curvature_lower = _f(_sqrt(squared, False))
    # A demonstrated witness uses the minimum over all arc-error possibilities.
    for _, limits in supports:
        possibilities = []
        for acceleration in accelerations:
            for u in speeds:
                drive = acceleration + _f(limits.drag_over_mass) * u
                possibilities.append((drive / _f(limits.motor_mps2) - 1,
                                      drive / _f(limits.ax_pos_mps2) +
                                      curvature_lower * u / _f(limits.ay_mps2) - 1,
                                      -drive / _f(limits.ax_neg_mps2) +
                                      curvature_lower * u / _f(limits.ay_mps2) - 1,
                                      curvature_lower * u / _f(limits.ay_mps2) - 1))
        if any(min(row[column] for row in possibilities) > policy.residual_abs
               for column in range(4)):
            return True
    if steering is not None:
        angle = _angle(_f(steering.wheelbase_m) * curvature_lower)
        if angle - 8 * math.ulp(1.) > steering.angle_max_rad + policy.angle_abs_rad:
            return True
        denominator = (1 + _f(steering.wheelbase_m) ** 2 * squared) ** 2
        rate = _f(steering.wheelbase_m) ** 2 * rate_squared * min(speeds) / denominator
        if rate / _f(steering.rate_max_radps) ** 2 - 1 > policy.residual_abs:
            return True
    return False


def _edge_bounds(coefficient, segment, low, high, ui, uj, distances, accelerations,
                 cap, supports, steering, policy, counter, check, edge):
    leaves = [(low, high, 0, None)]
    while True:
        check()
        updated = []
        for left, right, depth, bound in leaves:
            check()
            if bound is None:
                counter[0] += 1
                if counter[0] > policy.max_intervals:
                    raise _Stop('INCONCLUSIVE', 'dynamics interval budget exhausted', edge)
                try:
                    bound = interval_bounds(coefficient, left, right)
                except BoundUncertain:
                    if depth >= policy.max_depth:
                        raise _Stop('INCONCLUSIVE', 'unresolved derivative bound budget', edge)
                    mid = (left + right) / 2
                    updated.extend(((left, mid, depth + 1, None),
                                    (mid, right, depth + 1, None)))
                    continue
            updated.append((left, right, depth, bound))
        leaves = updated
        if any(bound is None for _, _, _, bound in leaves):
            continue
        curvature = max(bound.curvature_upper for _, _, _, bound in leaves)
        rate = max(bound.curvature_rate_upper for _, _, _, bound in leaves)
        residuals = _residuals(accelerations, (ui, uj), _f(curvature), _f(rate), cap,
                               supports, steering, policy)
        if not _violates(residuals, policy):
            return curvature, rate, residuals, len(leaves)
        # Caps/range violations are exact at a canonical endpoint.
        if any(value > policy.residual_abs for key, value in residuals.items()
               if key in ('static_speed', 'moving_speed', 'model_speed', 'minimum_speed')):
            raise _Stop('FAIL', 'demonstrated original static/model speed violation', edge)
        for left, right, _, _ in leaves:
            check()
            for parameter in (left, (left + right) / 2, right):
                check()
                if _witness(coefficient, parameter, segment, low, high, ui, uj, distances,
                            accelerations, cap, supports, steering, policy):
                    raise _Stop('FAIL', 'demonstrated continuous dynamic constraint violation',
                                edge)
        metric = 'curvature_rate_upper' if residuals.get('steering_rate', -1) > \
            policy.residual_abs else 'curvature_upper'
        index = max(range(len(leaves)), key=lambda j: getattr(leaves[j][3], metric))
        left, right, depth, _ = leaves.pop(index)
        if depth >= policy.max_depth:
            raise _Stop('INCONCLUSIVE', 'unresolved continuous dynamics depth budget', edge)
        mid = (left + right) / 2
        leaves.extend(((left, mid, depth + 1, None), (mid, right, depth + 1, None)))


def _close(observed, expected, policy):
    if not _binary_number(observed):
        return False
    value = float(_f(observed))
    return abs(value - expected) <= policy.metadata_abs + policy.metadata_rel * abs(expected)


def validate_dynamics(ordered, profile, model, policy=DynamicsValidationPolicy(), metadata=None):
    """Reconstruct and certify the complete supported cyclic planar profile.

    The phase-boundary deadline is cooperative; numeric kernel/size/depth budgets
    also bound work. Reported time enclosures propagate every local arc allowance,
    rather than equating nominal metadata consistency with true-time accuracy.
    """
    certificates, worst = [], {}
    identity, model_identity = '', ''
    nominal_time = lower_time = upper_time = 0.
    began = time.monotonic()

    def check():
        if time.monotonic() - began >= policy.wall_seconds:
            raise _Stop('INCONCLUSIVE', 'independent dynamics wall budget exhausted')

    def report(status, reason, edge=-1):
        error = max(nominal_time - lower_time, upper_time - nominal_time, 0.)
        return DynamicsValidationReport(
            status, reason, tuple(certificates), tuple(sorted(worst.items())), edge,
            identity, model_identity, nominal_time, lower_time, upper_time, error)

    try:
        if type(policy) is not DynamicsValidationPolicy:
            raise _Stop('FAIL', 'invalid independent dynamics policy')
        check()
        _input_limits(profile, model, metadata, policy)
        route, curve, q, ends = _authority(ordered, policy)
        regions = _model_regions(model, route, policy)
        identity, model_identity = _identities(ordered, model)
        knots = _profile_knots(profile, curve, policy)
        if profile.curve_digest != identity or profile.model_digest != model_identity:
            raise _Stop('FAIL', 'profile curve/model provenance digest mismatch')
        stations = []
        for knot in knots:
            check()
            stations.append(curve.station(knot.segment, knot.t))
        stations = tuple(stations)
        velocity = tuple(math.sqrt(float(_f(k.u))) for k in knots)
        accelerations, times, curvatures = [], [0.], []
        nominal_edges, time_lowers, time_uppers = [], [], []
        counter = [0]
        for index, knot in enumerate(knots):
            check()
            next_knot = knots[(index + 1) % len(knots)]
            if next_knot.segment == knot.segment and index + 1 < len(knots):
                end_parameter = _f(next_knot.t)
            elif (next_knot.segment == (knot.segment + 1) % len(curve.segments) and
                  next_knot.t == 0):
                end_parameter = Fraction(1)
            else:
                raise _Stop('FAIL', 'profile edge skipped a coefficient boundary', index)
            start_parameter = _f(knot.t)
            segment = curve.segments[knot.segment]
            distances = _arc(segment, start_parameter, end_parameter)
            ui, uj = _f(knot.u), _f(next_knot.u)
            du = uj - ui
            acceleration = tuple(du / (2 * _f(distance)) for distance in distances[1:])
            acceleration = min(acceleration), max(acceleration)
            low = q[knot.segment] + start_parameter * (q[knot.segment + 1] - q[knot.segment])
            high = q[knot.segment] + end_parameter * (q[knot.segment + 1] - q[knot.segment])
            cap, supports = _budgets(route, ends, regions, low, high)
            curvature, rate, residuals, interval_count = _edge_bounds(
                segment.coefficients, segment, start_parameter, end_parameter, ui, uj,
                distances, acceleration, cap, supports, model.steering, policy, counter,
                check, index)
            for name, value in residuals.items():
                worst[name] = max(worst.get(name, -math.inf), _up(value))
            denominator = velocity[index] + velocity[(index + 1) % len(knots)]
            if denominator <= 0:
                raise _Stop('FAIL', 'nontraversable zero-motion cyclic edge', index)
            edge_time = 2 * distances[0] / denominator
            denominator_low = _f(_sqrt(ui, False)) + _f(_sqrt(uj, False))
            denominator_high = _f(_sqrt(ui)) + _f(_sqrt(uj))
            if denominator_low <= 0:
                raise _Stop('INCONCLUSIVE', 'unresolved positive traversal time', index)
            time_low = _down(2 * _f(distances[1]) / denominator_high)
            time_high = _up(2 * _f(distances[2]) / denominator_low)
            nominal_edges.append(edge_time)
            time_lowers.append(_f(time_low))
            time_uppers.append(_f(time_high))
            accelerations.append(float(du / (2 * _f(distances[0]))))
            times.append(math.fsum(nominal_edges))
            squared, _, cross, g = _point_curvature(segment.coefficients, start_parameter)
            curvatures.append(math.copysign(_sqrt(squared), float(cross)))
            normalized = max((value for key, value in residuals.items()
                              if key != 'steering_angle_rad'), default=Fraction(-1))
            certificates.append(DynamicEdgeCertificate(
                index, knot.segment, knot.t, float(end_parameter), index + 1 == len(knots),
                distances[0], distances[1], distances[2], _down(acceleration[0]),
                _up(acceleration[1]), curvature, rate, cap,
                tuple(owner for owner, _ in supports), _up(normalized),
                float(residuals.get('steering_angle_rad', -math.pi)), interval_count,
                time_low, time_high))
        nominal_time = math.fsum(nominal_edges)
        lower_time, upper_time = _down(sum(time_lowers)), _up(sum(time_uppers))
        if not _close(profile.lap_time_s, nominal_time, policy):
            raise _Stop('FAIL', 'stale/inconsistent profile lap-time metadata')
        if metadata is not None:
            if type(metadata) is not ProfileMetadata or metadata.curve_digest != identity:
                raise _Stop('FAIL', 'stale or unsupported exported metadata authority')
            expected = {'stations_m': stations, 'velocity_mps': velocity,
                        'acceleration_mps2': accelerations, 'curvature_per_m': curvatures,
                        'time_s': times[:-1]}
            for name, values in expected.items():
                observed = getattr(metadata, name)
                if len(observed) != len(values) or any(
                        not _close(a, b, policy) for a, b in zip(observed, values)):
                    raise _Stop('FAIL', 'stale/inconsistent exported ' + name)
            if not _close(metadata.lap_time_s, nominal_time, policy):
                raise _Stop('FAIL', 'stale/inconsistent exported lap time')
        check()
        return report('PASS', 'continuous cyclic planar dynamics and metadata certified')
    except _Stop as exc:
        return report(exc.status, exc.reason, exc.edge)
    except BoundUncertain as exc:
        return report('INCONCLUSIVE', 'unresolved independent polynomial bound: ' + str(exc))
    except GeometryError as exc:
        return report('INCONCLUSIVE', 'independent coefficient/arc reconstruction: ' + str(exc))
    except (AttributeError, TypeError, ValueError, IndexError, KeyError, OverflowError) as exc:
        return report('FAIL', 'malformed independent dynamics input: ' + str(exc))
