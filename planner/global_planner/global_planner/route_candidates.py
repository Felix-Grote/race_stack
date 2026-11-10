"""Deterministic bounded candidate selection over Project A route contracts.

Given one strictly validated route, enumerate a small deterministic set of
route variants by simplifying occurrence wall chains with bounded,
gate-checked settings, then select offline through the unchanged pipeline:
strict validation, corridor preparation, the pinned optimizer and the
independent checkers.

Candidates differ only in wall-chain simplification within the shared
``epsilon_m / resolution_m <= 0.6`` envelope; chords are deviation-checked
and eps-gated so occupied space is never gained beyond epsilon, and
endcaps stay bit-exact. Seeds are never modified; the seed digest is
pinned across variants. ``ENUMERATED`` (strict-valid variant) is not
``PREPARED`` (corridor preparation passed); selection receipts carry the
compile outcome status, ``PASS`` only after independent acceptance, so a
strict-valid variant is never reported as an optimizer PASS. The offline
selection entry point performs no browser drawing, scheduling or
persistence beyond the caller-supplied output directory. Identical
simplification inputs hit an in-memory cache instead of being recomputed.
"""

from dataclasses import dataclass, field
import math
import time

try:
    import resource as _resource
except ImportError:  # pragma: no cover - non-POSIX fallback
    _resource = None

from ._route_geometry import EPS, inside, signed_area_twice
from .route_corridor import prepare_route
from .route_compile import compile_reference
from .route_input import Route, validate_route

MAX_CANDIDATES = 6
MAX_EPSILON_PER_RESOLUTION = 0.6
DEFAULT_WALL_EPSILONS_M = (0.0, 0.01, 0.02)
_CACHE_MAX_ENTRIES = 256

_wall_cache = {}
_cache_hits = 0


class CandidateError(ValueError):
    """Invalid candidate policy or an unusable simplified variant."""


def _cpu_seconds():
    """Process CPU seconds, or wall fallback when resource is unavailable."""
    if _resource is not None:
        own = _resource.getrusage(_resource.RUSAGE_SELF)
        child = _resource.getrusage(_resource.RUSAGE_CHILDREN)
        return own.ru_utime + own.ru_stime + child.ru_utime + child.ru_stime
    return time.process_time()


def _check_number(value, name, minimum=0.0, strict=True):
    """Validate a plain numeric policy input without accepting booleans."""
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or (value <= minimum if strict else value < minimum)):
        raise CandidateError('invalid ' + name)
    return float(value)


def _perpendicular_distance(point, start, end):
    """Absolute distance of a point from the chord through start/end."""
    base = math.hypot(end[0] - start[0], end[1] - start[1])
    if base <= EPS:
        return math.hypot(point[0] - start[0], point[1] - start[1])
    area = abs((end[0] - start[0]) * (start[1] - point[1])
               - (start[0] - point[0]) * (end[1] - start[1]))
    return area / base


def simplify_open_chain(points, epsilon_m):
    """Deterministic Douglas-Peucker on an open chain, endpoints pinned.

    Iterative (no recursion depth dependence); ties resolve by index order,
    so identical input always yields identical output.
    """
    chain = [(float(x[0]), float(x[1])) for x in points]
    if len(chain) < 3 or epsilon_m <= 0.0:
        return chain
    keep = [False] * len(chain)
    keep[0] = keep[-1] = True
    stack = [(0, len(chain) - 1)]
    while stack:
        first, last = stack.pop()
        start, end = chain[first], chain[last]
        peak, peak_at = 0.0, -1
        for i in range(first + 1, last):
            distance = _perpendicular_distance(chain[i], start, end)
            if distance > peak:
                peak, peak_at = distance, i
        if peak_at >= 0 and peak > epsilon_m:
            keep[peak_at] = True
            stack.append((first, peak_at))
            stack.append((peak_at, last))
    return [point for point, kept in zip(chain, keep) if kept]


def _chord_deviation(chain, simplified, epsilon_m):
    """Worst distance of dropped originals from their simplified chord."""
    worst, j = 0.0, 0
    for k in range(len(simplified) - 1):
        start, end = simplified[k], simplified[k + 1]
        while j < len(chain) and chain[j] != start:
            j += 1
        i = j
        while i < len(chain) and chain[i] != end:
            worst = max(worst, _perpendicular_distance(chain[i], start, end))
            i += 1
        j = i
    if worst > epsilon_m * (1.0 + 1e-9):
        raise CandidateError(
            'simplified chord exceeds deviation bound: %.6g > %.6g'
            % (worst, epsilon_m))
    return worst


def _point_segment_distance(point, start, end):
    """Shortest distance of a point from the segment through start/end."""
    vx, vy = end[0] - start[0], end[1] - start[1]
    length_squared = vx * vx + vy * vy
    if length_squared <= EPS * EPS:
        return math.hypot(point[0] - start[0], point[1] - start[1])
    position = (((point[0] - start[0]) * vx + (point[1] - start[1]) * vy)
                / length_squared)
    position = max(0.0, min(1.0, position))
    closest = (start[0] + position * vx, start[1] + position * vy)
    return math.hypot(point[0] - closest[0], point[1] - closest[1])


def _distance_to_polygon(point, polygon):
    """Shortest distance of a point from any polygon edge."""
    edges = zip(polygon, polygon[1:] + polygon[:1])
    return min(_point_segment_distance(point, a, b) for a, b in edges)


def _seed_loop_area_sign(payload):
    """Winding sign of the concatenated seed loop for direction checks."""
    loop = []
    for occurrence in payload['occurrences']:
        loop.extend(tuple(x) for x in occurrence['seed'][:-1])
    twice = 0.0
    origin = loop[0]
    for a, b in zip(loop, loop[1:] + loop[:1]):
        twice += ((a[0] - origin[0]) * (b[1] - origin[1])
                  - (a[1] - origin[1]) * (b[0] - origin[0]))
    if abs(twice) <= EPS:
        raise CandidateError('degenerate seed loop winding')
    return 1 if twice > 0 else -1


def simplify_route_walls(route, epsilon_m, resolution_m):
    """Return a strictly validated route with simplified wall chains.

    Seeds, caps, portals, support and initialization are untouched. Raises
    CandidateError (a meaningful early rejection, never a partial route)
    when the envelope is violated, a chord leaves the deviation bound or
    the original ribbon, or the simplified payload fails strict validation.
    Identical inputs reuse the cache.
    """
    if type(route) is not Route:
        raise CandidateError('explicit validated Route required')
    epsilon = _check_number(epsilon_m, 'wall epsilon', minimum=0.0, strict=False)
    resolution = _check_number(resolution_m, 'raster resolution')
    if epsilon > 0.0 and epsilon / resolution > (
            MAX_EPSILON_PER_RESOLUTION * (1.0 + 1e-9)):
        raise CandidateError(
            'wall epsilon %.6g m exceeds %.1f raster cells at %.6g m/px; '
            'reduce epsilon_m (supported envelope: epsilon/resolution <= 0.6)'
            % (epsilon, MAX_EPSILON_PER_RESOLUTION, resolution))
    global _cache_hits
    key = (route.digest, repr(epsilon), repr(resolution))
    if key in _wall_cache:
        _cache_hits += 1
        return _wall_cache[key]
    payload = route.payload
    before_sign = _seed_loop_area_sign(payload)
    if epsilon == 0.0:
        simplified = validate_route(payload)
        if simplified.digest != route.digest:
            raise CandidateError('verbatim revalidation changed route identity')
        _store_cache(key, simplified)
        return simplified
    for occurrence in payload['occurrences']:
        polygon = (tuple(tuple(x) for x in occurrence['right'])
                   + tuple(tuple(x) for x in occurrence['left'][::-1]))
        for side in ('left', 'right'):
            original = [tuple(x) for x in occurrence[side]]
            reduced = simplify_open_chain(original, epsilon)
            if len(reduced) < 2:
                raise CandidateError(
                    'simplification emptied %s wall of %s'
                    % (side, occurrence['id']))
            if reduced[0] != original[0] or reduced[-1] != original[-1]:
                raise CandidateError('simplification moved an endcap')
            if any(math.hypot(a[0] - b[0], a[1] - b[1]) <= EPS
                   for a, b in zip(reduced, reduced[1:])):
                raise CandidateError('simplification collapsed consecutive wall points')
            _chord_deviation(original, reduced, epsilon)
            for a, b in zip(reduced, reduced[1:]):
                midpoint = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
                if (not inside(midpoint, polygon)
                        and _distance_to_polygon(midpoint, polygon)
                        > epsilon * (1.0 + 1e-9)):
                    raise CandidateError(
                        'simplified %s chord of %s leaves the original ribbon '
                        'beyond epsilon (eps gate)' % (side, occurrence['id']))
            occurrence[side] = [list(x) for x in reduced]
    if _seed_loop_area_sign(payload) != before_sign:
        raise CandidateError('simplification reversed seed winding')
    for occurrence in payload['occurrences']:
        polygon = (tuple(tuple(x) for x in occurrence['right'])
                   + tuple(tuple(x) for x in occurrence['left'][::-1]))
        if signed_area_twice(polygon) <= EPS:
            raise CandidateError(
                'simplified ribbon of %s lost orientation' % occurrence['id'])
    try:
        simplified = validate_route(payload)
    except ValueError as exc:
        raise CandidateError('simplified route rejected by strict validation: '
                             + str(exc)) from exc
    _store_cache(key, simplified)
    return simplified


def _store_cache(key, value):
    """Bounded FIFO cache for identical simplification inputs."""
    while len(_wall_cache) >= _CACHE_MAX_ENTRIES:
        _wall_cache.pop(next(iter(_wall_cache)))
    _wall_cache[key] = value


def cache_info():
    """Return the current simplification cache size and hit count."""
    return {'entries': len(_wall_cache), 'hits': _cache_hits}


def cache_clear():
    """Empty the simplification cache and reset the hit counter."""
    global _cache_hits
    _wall_cache.clear()
    _cache_hits = 0


def _seed_digest(route):
    """Short digest of concatenated seed chains (operator intent pin)."""
    import hashlib
    import json

    seeds = [occurrence['seed'] for occurrence in route.payload['occurrences']]
    return hashlib.sha256(json.dumps(
        seeds, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class CandidateSpec:
    """One enumerated variant: simplified route or a recorded rejection."""

    index: int
    epsilon_m: float
    route: object = None
    digest: str = ''
    seed_digest: str = ''
    wall_vertices: int = 0
    rejected: bool = False
    reason: str = ''

    @property
    def stage(self):
        """Never report a strict-valid variant as an optimizer PASS."""
        return 'REJECTED' if self.rejected else 'ENUMERATED'


def enumerate_candidates(route, *, resolution_m,
                         epsilons=DEFAULT_WALL_EPSILONS_M):
    """Enumerate bounded deterministic wall-simplification variants.

    Invalid policies raise CandidateError; per-variant simplification
    failures become REJECTED specs (early rejection before any corridor or
    optimizer work) in deterministic input order.
    """
    if type(route) is not Route:
        raise CandidateError('explicit validated Route required')
    resolution = _check_number(resolution_m, 'raster resolution')
    values = tuple(epsilons)
    if not values or len(values) > MAX_CANDIDATES:
        raise CandidateError(
            'expected 1..%d deterministic epsilon settings' % MAX_CANDIDATES)
    for value in values:
        _check_number(value, 'wall epsilon', minimum=0.0, strict=False)
    if len({repr(v) for v in values}) != len(values):
        raise CandidateError('duplicate epsilon settings are not candidates')
    for value in values:
        if value > 0.0 and float(value) / resolution > (
                MAX_EPSILON_PER_RESOLUTION * (1.0 + 1e-9)):
            raise CandidateError(
                'wall epsilon %.6g m exceeds %.1f raster cells at %.6g m/px; '
                'no candidate is produced outside the supported envelope'
                % (float(value), MAX_EPSILON_PER_RESOLUTION, resolution))
    seed_pin = _seed_digest(route)
    specs = []
    for index, value in enumerate(values):
        epsilon = float(value)
        try:
            simplified = simplify_route_walls(route, epsilon, resolution)
            if _seed_digest(simplified) != seed_pin:
                raise CandidateError('simplification altered seed intent')
            vertices = sum(len(o['left']) + len(o['right'])
                           for o in simplified.payload['occurrences'])
            specs.append(CandidateSpec(index, epsilon, simplified,
                                       simplified.digest, seed_pin, vertices))
        except CandidateError as exc:
            specs.append(CandidateSpec(index, epsilon, None, '', seed_pin, 0,
                                       True, str(exc)))
    return tuple(specs)


@dataclass(frozen=True)
class CandidateReceipt:
    """Measured outcome of one candidate through one offline pipeline stage."""

    index: int
    epsilon_m: float
    digest: str
    stage: str
    status: str
    reason: str
    wall_seconds: float
    cpu_seconds: float
    geometry_status: object = None
    dynamics_status: object = None
    artifact_H: object = None


@dataclass(frozen=True)
class PreparedCandidates:
    """Offline corridor-preparation outcome for every enumerated variant."""

    specs: tuple
    receipts: tuple
    wall_seconds: float
    cpu_seconds: float


def prepare_candidates(route, *, resolution_m,
                       epsilons=DEFAULT_WALL_EPSILONS_M,
                       corridor_spacing_m=0.25):
    """Run enumeration plus corridor preparation, without any optimizer.

    Rejected variants keep a REJECTED receipt and never reach preparation.
    Strict-valid variants are reported as ENUMERATED/PREPARED, never PASS.
    """
    spacing = _check_number(corridor_spacing_m, 'corridor spacing')
    start, start_cpu = time.monotonic(), _cpu_seconds()
    specs = enumerate_candidates(route, resolution_m=resolution_m,
                                 epsilons=epsilons)
    receipts = []
    for spec in specs:
        began, began_cpu = time.monotonic(), _cpu_seconds()
        if spec.rejected:
            receipts.append(CandidateReceipt(
                spec.index, spec.epsilon_m, '', 'REJECTED', 'REJECTED',
                spec.reason, 0.0, 0.0))
            continue
        try:
            prepared = prepare_route(spec.route, spacing=spacing)
            receipts.append(CandidateReceipt(
                spec.index, spec.epsilon_m, spec.digest, 'PREPARED', 'PREPARED',
                'strict-valid and corridor-prepared; no optimizer verdict '
                '(%d samples)' % len(prepared.samples),
                time.monotonic() - began, _cpu_seconds() - began_cpu))
        except ValueError as exc:
            receipts.append(CandidateReceipt(
                spec.index, spec.epsilon_m, spec.digest, 'REJECTED',
                getattr(exc, 'status', 'REJECTED'), str(exc),
                time.monotonic() - began, _cpu_seconds() - began_cpu))
    return PreparedCandidates(specs, tuple(receipts),
                              time.monotonic() - start,
                              _cpu_seconds() - start_cpu)


@dataclass(frozen=True)
class SelectionResult:
    """Offline selection outcome; PASS only after independent acceptance."""

    status: str
    selected: object = None
    receipts: tuple = ()
    wall_seconds: float = 0.0
    cpu_seconds: float = 0.0
    reason: str = ''


def select_candidate(route, *, model, footprint, policies, output_dir,
                     resolution_m, retime_spacing_m, validation_context=None,
                     epsilons=DEFAULT_WALL_EPSILONS_M,
                     provenance=None):
    """Compile enumerated variants offline and return the first PASS.

    Each valid variant compiles through the unchanged
    :func:`route_compile.compile_reference` (optimizer, independent
    geometry/dynamics checkers, persisted-byte replay) into its own
    ``candidate-{index}`` subdirectory. Rejected variants are recorded and
    skipped. The overall status is PASS only when a variant's independent
    validation passes; strict-valid or numerically converged variants alone
    yield NO_PASS with per-candidate reasons. No scheduling, database or
    browser involvement.
    """
    from pathlib import Path

    start, start_cpu = time.monotonic(), _cpu_seconds()
    specs = enumerate_candidates(route, resolution_m=resolution_m,
                                 epsilons=epsilons)
    own_provenance = dict(provenance or {})
    if any(type(k) is not str or type(v) is not str
           for k, v in own_provenance.items()):
        raise CandidateError('explicit informational provenance must be strings')
    receipts, selected = [], None
    for spec in specs:
        began, began_cpu = time.monotonic(), _cpu_seconds()
        if spec.rejected:
            receipts.append(CandidateReceipt(
                spec.index, spec.epsilon_m, '', 'REJECTED', 'REJECTED',
                spec.reason, 0.0, 0.0))
            continue
        try:
            candidate_provenance = dict(own_provenance)
            candidate_provenance['candidate_index'] = repr(spec.index)
            candidate_provenance['wall_epsilon_m'] = repr(spec.epsilon_m)
            result = compile_reference(
                spec.route, model, footprint, policies,
                output_dir=str(Path(output_dir) / ('candidate-%d' % spec.index)),
                retime_spacing_m=retime_spacing_m,
                validation_context=validation_context,
                provenance=candidate_provenance)
            receipt = CandidateReceipt(
                spec.index, spec.epsilon_m, spec.digest,
                'PASS' if result.status == 'PASS' else result.status,
                result.status, result.reason,
                time.monotonic() - began, _cpu_seconds() - began_cpu,
                None if result.geometry is None else result.geometry.status,
                None if result.dynamics is None else result.dynamics.status,
                result.H)
        except (ValueError, OSError, RuntimeError) as exc:
            receipt = CandidateReceipt(
                spec.index, spec.epsilon_m, spec.digest, 'REJECTED',
                getattr(exc, 'status', 'FAIL'), str(exc),
                time.monotonic() - began, _cpu_seconds() - began_cpu)
        receipts.append(receipt)
        if receipt.status == 'PASS' and selected is None:
            selected = receipt
    total_wall, total_cpu = time.monotonic() - start, _cpu_seconds() - start_cpu
    if selected is not None:
        return SelectionResult('PASS', selected, tuple(receipts),
                               total_wall, total_cpu)
    return SelectionResult(
        'NO_PASS', None, tuple(receipts), total_wall, total_cpu,
        'no enumerated variant reached independent validation PASS; '
        'strict-valid variants are not optimizer passes')
