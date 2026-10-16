"""
Strict immutable offline references and stateless true-metric queries.

Only an externally expected artifact identity and an independently selected
validation context authorize loading. Both proofs are regenerated on the exact
saved coefficients; embedded reports are bounded historical snapshots.
This module supports pinned Linux/Humble, planar software
certificates only; it establishes no physical vehicle or 3D clearance evidence.
"""
from bisect import bisect_right
import ctypes
from dataclasses import asdict, dataclass, field, fields, is_dataclass
import fcntl
from fractions import Fraction
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import secrets
import stat

from .cyclic_retime import (
    DynamicsModel, ModelRegion, RegionLimits, RetimePolicy, SpeedKnot,
    SpeedProfile, SteeringLimits, curve_digest, model_digest)
from .iqp_route_adapter import SolverPolicy
from .route_corridor import OrderedCurve, _layout
from .route_input import validate_route
from .route_reference import Curve, GeometryError, NumericPolicy
from .route_validate import (
    Footprint, GateCertificate, GeometryValidationPolicy, IntervalCertificate,
    ValidationReport, _portal_delta, validate_geometry)
from .route_validate_dynamics import (
    DynamicEdgeCertificate, DynamicsValidationPolicy, DynamicsValidationReport,
    validate_dynamics)

SCHEMA_VERSION = 1
CONTRACT_ID = 'forzaeth.offline-reference.v1'
MAX_ARTIFACT_BYTES = 64 * 1024 ** 2
MAX_JSON_DEPTH = 32
MAX_JSON_NODES = 2000000
MAX_JSON_STRING_BYTES = 65536
_GEOMETRY_COVERAGE = ValidationReport('PASS', '').coverage
_DYNAMICS_COVERAGE = DynamicsValidationReport('PASS', '').coverage
_CONVENTIONS = {
    'frame': 'approved_route.frame_id', 'units': 'metres_seconds_radians',
    'heading': 'positive_X_counterclockwise', 'curvature': 'left_positive',
    'progress': 'true_metric_arclength', 'speed': 'affine_squared_speed_in_metric_arc',
    'acceleration': 'right_hand_cyclic_edge', 'seam': 'half_open_right_hand',
    'domain': 'declared_planar_software_only',
}
_PINNED_VERSIONS = {'numpy': '1.26.4', 'scipy': '1.11.4', 'quadprog': '0.1.7',
                    'trajectory-planning-helpers': '0.79'}
_REFERENCE_SEAL = object()


class ArtifactError(ValueError):
    """A malformed, unsupported or independently unaccepted reference."""

    def __init__(self, reason, status='FAIL'):
        """Retain an explicit fail-closed outcome for command-line receipts."""
        super().__init__(str(reason))
        self.status = status
        self.reason = str(reason)


def _keys(value, names, label):
    if type(value) is not dict or set(value) != set(names):
        raise ArtifactError('invalid or unknown fields in ' + label)


def _sha(value, label):
    if (type(value) is not str or len(value) != 64 or
            any(c not in '0123456789abcdef' for c in value)):
        raise ArtifactError('expected lowercase SHA256 for ' + label)
    return value


def _tree(value):
    stack, nodes = [(value, 0)], 0
    while stack:
        item, depth = stack.pop()
        nodes += 1
        if nodes > MAX_JSON_NODES or depth > MAX_JSON_DEPTH:
            raise ArtifactError('JSON container/depth budget exhausted')
        if type(item) is dict:
            for key, child in item.items():
                if type(key) is not str:
                    raise ArtifactError('JSON object keys must be text')
                stack.extend(((key, depth + 1), (child, depth + 1)))
        elif type(item) in (list, tuple):
            if len(item) > MAX_JSON_NODES:
                raise ArtifactError('JSON array budget exhausted')
            stack.extend((child, depth + 1) for child in item)
        elif type(item) is str:
            if len(item) > MAX_JSON_STRING_BYTES or len(item.encode('utf-8')) > (
                    MAX_JSON_STRING_BYTES):
                raise ArtifactError('JSON text budget exhausted')
        elif type(item) is float:
            if not math.isfinite(item):
                raise ArtifactError('nonfinite JSON binary64 value')
        elif type(item) is int:
            if item.bit_length() > 1024:
                raise ArtifactError('JSON integer budget exhausted')
        elif item is not None and type(item) is not bool:
            raise ArtifactError('unsupported JSON value type')


def canonical_bytes(value):
    """Encode deterministic JSON without changing numeric types or signed zero."""
    _tree(value)
    try:
        data = json.dumps(value, sort_keys=True, separators=(',', ':'),
                          ensure_ascii=False, allow_nan=False).encode('utf-8')
    except (ValueError, TypeError, UnicodeError) as exc:
        raise ArtifactError('value cannot be represented as strict UTF-8 JSON') from exc
    if len(data) > MAX_ARTIFACT_BYTES:
        raise ArtifactError('full artifact exceeds 64 MiB encoded budget')
    return data


canonical_json = canonical_bytes


def artifact_identity(payload):
    """Hash the canonical payload alone, excluding envelope and run telemetry."""
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def _parse_json(raw):
    if not isinstance(raw, bytes) or len(raw) > MAX_ARTIFACT_BYTES:
        raise ArtifactError('encoded JSON byte budget exhausted')
    try:
        text = raw.decode('utf-8')
        # Bound nesting before Python's recursive JSON decoder is entered.
        depth, quoted, escaped, tokens, atom = 0, False, False, 0, False
        for character in text:
            if quoted:
                if escaped:
                    escaped = False
                elif character == '\\':
                    escaped = True
                elif character == '"':
                    quoted = False
            elif character == '"':
                quoted, atom = True, False
                tokens += 1
            elif character in '[{':
                depth += 1
                tokens += 1
                atom = False
                if depth > MAX_JSON_DEPTH:
                    raise ArtifactError('JSON depth budget exhausted')
            elif character in ']}':
                depth -= 1
                atom = False
            elif character in ',:' or character.isspace():
                atom = False
            elif not atom:
                tokens += 1
                atom = True
            if tokens > MAX_JSON_NODES:
                raise ArtifactError('JSON token budget exhausted before decoding')

        def pairs(items):
            result = {}
            for key, value in items:
                if key in result:
                    raise ArtifactError('duplicate JSON key')
                result[key] = value
            return result

        def integer(value):
            if len(value) > 310:
                raise ArtifactError('JSON integer budget exhausted')
            return int(value)

        def number(value):
            result = float(value)
            if not math.isfinite(result):
                raise ArtifactError('nonfinite/overflow JSON number')
            return result

        def invalid(_):
            raise ArtifactError('nonfinite JSON constant')

        value = json.loads(text, object_pairs_hook=pairs, parse_int=integer,
                           parse_float=number, parse_constant=invalid)
        _tree(value)
        if type(value) is not dict:
            raise ArtifactError('JSON document must be an object')
        return value
    except (UnicodeError, json.JSONDecodeError, RecursionError, OverflowError) as exc:
        raise ArtifactError('invalid bounded UTF-8 JSON') from exc


def _open_directory(path, create=False):
    """Open a directory by file descriptor without following any symlink."""
    path = Path(os.path.abspath(os.fspath(path)))
    descriptor = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for component in path.parts[1:]:
            try:
                child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                dir_fd=descriptor)
            except FileNotFoundError:
                if not create:
                    raise
                try:
                    os.mkdir(component, 0o755, dir_fd=descriptor)
                except FileExistsError:
                    pass
                child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        return descriptor
    except OSError as exc:
        os.close(descriptor)
        raise ArtifactError('directory absent, unsupported or contains symlink: ' +
                            str(exc)) from exc


def _read_fd(descriptor, max_bytes):
    info = os.fstat(descriptor)
    if not stat.S_ISREG(info.st_mode) or info.st_size > max_bytes:
        raise ArtifactError('expected a bounded regular JSON file')
    chunks, size = [], 0
    while True:
        chunk = os.read(descriptor, min(65536, max_bytes + 1 - size))
        if not chunk:
            break
        chunks.append(chunk)
        size += len(chunk)
        if size > max_bytes:
            raise ArtifactError('encoded JSON byte budget exhausted')
    return b''.join(chunks)


def read_json(path, *, max_bytes=MAX_ARTIFACT_BYTES):
    """Read a bounded strict JSON object, rejecting duplicates and symlinks."""
    if type(max_bytes) is not int or not 0 < max_bytes <= MAX_ARTIFACT_BYTES:
        raise ArtifactError('invalid independently selected JSON byte budget')
    path = Path(os.path.abspath(os.fspath(path)))
    parent = _open_directory(path.parent)
    try:
        descriptor = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                             dir_fd=parent)
        try:
            return _parse_json(_read_fd(descriptor, max_bytes))
        finally:
            os.close(descriptor)
    except OSError as exc:
        raise ArtifactError('cannot read strict JSON file: ' + str(exc)) from exc
    finally:
        os.close(parent)


@dataclass(frozen=True)
class PolicySet:
    """The complete declared producer and independent acceptance policies."""

    numeric: NumericPolicy
    solver: SolverPolicy
    retime: RetimePolicy
    geometry: GeometryValidationPolicy
    dynamics: DynamicsValidationPolicy


@dataclass(frozen=True)
class ValidationContext:
    """Independently selected supported kernel, proof policies and coverage."""

    numeric_policy: NumericPolicy = field(default_factory=NumericPolicy)
    geometry_policy: GeometryValidationPolicy = field(default_factory=GeometryValidationPolicy)
    dynamics_policy: DynamicsValidationPolicy = field(default_factory=DynamicsValidationPolicy)
    required_geometry_coverage: tuple = _GEOMETRY_COVERAGE
    required_dynamics_coverage: tuple = _DYNAMICS_COVERAGE
    contract_id: str = CONTRACT_ID

    def __post_init__(self):
        """Reject inconsistent or self-selected numerical proof contexts."""
        if (type(self.numeric_policy) is not NumericPolicy or
                type(self.geometry_policy) is not GeometryValidationPolicy or
                type(self.dynamics_policy) is not DynamicsValidationPolicy):
            raise ArtifactError('explicit independently supported policy records required')
        expected = canonical_bytes(asdict(self.numeric_policy))
        if any(canonical_bytes(asdict(policy.numeric_policy)) != expected
               for policy in (self.geometry_policy, self.dynamics_policy)):
            raise ArtifactError('independent numerical policies disagree')
        for name in ('required_geometry_coverage', 'required_dynamics_coverage'):
            value = tuple(getattr(self, name))
            if any(type(item) is not str or not item for item in value):
                raise ArtifactError('invalid independently required coverage')
            object.__setattr__(self, name, value)


_OVERRIDES = {
    (GeometryValidationPolicy, 'numeric_policy'): NumericPolicy,
    (DynamicsValidationPolicy, 'numeric_policy'): NumericPolicy,
    (ModelRegion, 'limits'): RegionLimits,
    (DynamicsModel, 'regions'): (ModelRegion,),
    (DynamicsModel, 'steering'): 'nullable_steering',
    (SpeedProfile, 'knots'): (SpeedKnot,),
    (ValidationReport, 'intervals'): (IntervalCertificate,),
    (ValidationReport, 'gates'): (GateCertificate,),
    (ValidationReport, 'offending_interval'): (),
    (ValidationReport, 'coverage'): (str,),
    (ValidationReport, 'assumptions'): (str,),
    (IntervalCertificate, 'exact_t0'): (int, int),
    (IntervalCertificate, 'exact_t1'): (int, int),
    (DynamicEdgeCertificate, 'support_occurrences'): (str,),
    (DynamicsValidationReport, 'edges'): (DynamicEdgeCertificate,),
    (DynamicsValidationReport, 'worst_residuals'): ((str, float),),
    (DynamicsValidationReport, 'coverage'): (str,),
    (DynamicsValidationReport, 'assumptions'): (str,),
}


def _decode_value(value, specification, label):
    if specification == 'nullable_steering':
        return None if value is None else decode_record(SteeringLimits, value, label)
    if isinstance(specification, type) and is_dataclass(specification):
        return decode_record(specification, value, label)
    if type(specification) is tuple:
        if type(value) not in (list, tuple):
            raise ArtifactError('expected array for ' + label)
        if len(specification) == 1:
            return tuple(_decode_value(item, specification[0], label) for item in value)
        if len(value) != len(specification):
            raise ArtifactError('wrong array dimensions in ' + label)
        return tuple(_decode_value(item, spec, label) for item, spec in zip(value, specification))
    if specification is float:
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ArtifactError('expected finite number for ' + label)
    elif specification in (int, str, bool):
        if type(value) is not specification:
            raise ArtifactError('wrong scalar type for ' + label)
    else:
        raise ArtifactError('unsupported typed field: ' + label)
    return value


def decode_record(cls, data, field='record'):
    """Decode all and only typed dataclass fields without numeric normalization."""
    if not isinstance(cls, type) or not is_dataclass(cls):
        raise ArtifactError('unsupported record type')
    expected = fields(cls)
    _keys(data, (item.name for item in expected), field)
    try:
        values = {item.name: _decode_value(data[item.name],
                                           _OVERRIDES.get((cls, item.name), item.type),
                                           field + '.' + item.name) for item in expected}
        record = cls(**values)
        # A constructor may coerce numeric types. Never silently change the
        # approved W2 JSON/digest spelling, including 1 versus 1.0 and -0.0.
        if canonical_bytes(asdict(record)) != canonical_bytes(data):
            raise ArtifactError('typed construction changes exact numeric authority: ' + field)
        return record
    except (TypeError, ValueError, OverflowError) as exc:
        if isinstance(exc, ArtifactError):
            raise
        raise ArtifactError('invalid typed ' + field + ': ' + str(exc)) from exc


def implementation_identity():
    """Snapshot installed kernel/checker source, numerical dependencies and pins."""
    modules = ('_route_geometry', 'route_input', 'route_reference', 'route_corridor',
               'iqp_route_adapter', 'route_validate', 'cyclic_retime',
               'route_validate_dynamics', 'route_artifact', 'route_compile', 'route_legacy_export')
    directory = Path(__file__).parent
    hashes = {name: hashlib.sha256((directory / (name + '.py')).read_bytes()).hexdigest()
              for name in modules}
    versions = {name: importlib.metadata.version(name) for name in _PINNED_VERSIONS}
    specification = importlib.util.find_spec('trajectory_planning_helpers')
    if specification is None or specification.origin is None:
        raise ArtifactError('missing supported numerical helper', 'UNSUPPORTED')
    helper_root = Path(specification.origin).parent
    helper_hashes = {name: hashlib.sha256((helper_root / name).read_bytes()).hexdigest()
                     for name in ('opt_min_curv.py', 'calc_splines.py')}
    return {'contract_id': CONTRACT_ID, 'accepted_w2_commit':
            'fe53365f86d660b4f6d4389925f9810cf33d41b3', 'optimizer_gitlink':
            'b1b38ecfefec7200d5bcb243f115af1d795b3766',
            'python': platform.python_version(), 'python_implementation':
            platform.python_implementation(), 'dependencies': versions,
            'module_sha256': hashes, 'helper_sha256': helper_hashes}


def _supported_context(context):
    if type(context) is not ValidationContext or context.contract_id != CONTRACT_ID:
        raise ArtifactError('unsupported independently selected validation contract',
                            'UNSUPPORTED')
    for policy in (context.numeric_policy, context.geometry_policy, context.dynamics_policy):
        decode_record(type(policy), asdict(policy))
    if (not set(context.required_geometry_coverage) <= set(_GEOMETRY_COVERAGE) or
            not set(context.required_dynamics_coverage) <= set(_DYNAMICS_COVERAGE)):
        raise ArtifactError('unsupported independently required coverage', 'UNSUPPORTED')
    identity = implementation_identity()
    if (identity['python'] != '3.10.12' or identity['python_implementation'] != 'CPython' or
            identity['dependencies'] != _PINNED_VERSIONS):
        raise ArtifactError('unsupported pinned Python/numerical runtime', 'UNSUPPORTED')
    from .iqp_route_adapter import _HASHES
    if identity['helper_sha256'] != _HASHES:
        raise ArtifactError('changed supported numerical helper implementation', 'UNSUPPORTED')
    return identity


def build_payload(ordered, profile, model, footprint, *, solver_policy, retime_policy,
                  geometry_policy, dynamics_policy, approved_curve_digest,
                  geometry_report, dynamics_report, provenance=None):
    """Capture a trusted producer handoff; publication still replays both proofs."""
    _sha(approved_curve_digest, 'trusted A04 curve approval')
    if (type(ordered) is not OrderedCurve or type(profile) is not SpeedProfile or
            type(model) is not DynamicsModel or type(footprint) is not Footprint):
        raise ArtifactError('unsupported explicit reference authority records')
    if (curve_digest(ordered) != approved_curve_digest or
            profile.curve_digest != approved_curve_digest or
            profile.model_digest != model_digest(model)):
        raise ArtifactError('trusted A04 approval or profile model binding changed')
    if any(report.status != 'PASS' or report.curve_digest != approved_curve_digest
           for report in (geometry_report, dynamics_report)):
        raise ArtifactError('both independently bound PASS reports are required')
    policies = PolicySet(ordered.curve.policy, solver_policy, retime_policy,
                         geometry_policy, dynamics_policy)
    payload = {
        'conventions': dict(_CONVENTIONS), 'approved_route': ordered.route.payload,
        'curve': {'coefficients': ordered.curve.coefficients,
                  'owners': ordered.curve.owners, 'q': ordered.q},
        'approved_curve_digest': approved_curve_digest, 'model': asdict(model),
        'footprint': asdict(footprint), 'speed_profile': asdict(profile),
        'policies': asdict(policies), 'implementation': implementation_identity(),
        'validation': {'geometry': asdict(geometry_report), 'dynamics': asdict(dynamics_report)},
        'provenance': {} if provenance is None else provenance,
    }
    return _parse_json(canonical_bytes(payload))


def _array(value, label, maximum, minimum=0):
    if type(value) is not list or not minimum <= len(value) <= maximum:
        raise ArtifactError('invalid or excessive array count in ' + label)
    return value


def _route_preflight(payload, context):
    if type(payload) is not dict or len(canonical_bytes(payload)) > min(
            context.geometry_policy.max_route_bytes, context.dynamics_policy.max_route_bytes):
        raise ArtifactError('approved route encoded byte budget exhausted')
    occurrences = _array(payload.get('occurrences'), 'occurrences',
                         context.dynamics_policy.max_model_regions, 1)
    portals = _array(payload.get('transitions'), 'transitions', len(occurrences), 1)
    polygons = []
    for occurrence in occurrences:
        if type(occurrence) is not dict:
            raise ArtifactError('invalid occurrence record')
        left = _array(occurrence.get('left'), 'left boundary', MAX_JSON_NODES, 2)
        right = _array(occurrence.get('right'), 'right boundary', MAX_JSON_NODES, 2)
        _array(occurrence.get('seed'), 'seed', context.numeric_policy.max_samples, 2)
        _array(occurrence.get('caps'), 'caps', context.dynamics_policy.max_knots, 1)
        polygons.append(len(left) + len(right))
    originals = tuple(polygons)
    for portal in portals:
        if type(portal) is not dict:
            raise ArtifactError('invalid portal record')
        polygons.append(len(_array(portal.get('support'), 'portal support', MAX_JSON_NODES, 3)))
    initialization = payload.get('initialization')
    if type(initialization) is not dict:
        raise ArtifactError('invalid initialization')
    polygons.append(len(_array(initialization.get('zone'), 'initialization zone',
                               MAX_JSON_NODES, 3)))
    unions = [n + originals[(i + 1) % len(originals)] - 2 for i, n in enumerate(originals)]
    if (max(polygons + unions) > min(context.geometry_policy.max_polygon_vertices,
                                     context.dynamics_policy.max_polygon_vertices) or
            sum(n * n for n in polygons + list(originals) + unions) > min(
                context.geometry_policy.max_polygon_work,
                context.dynamics_policy.max_polygon_work)):
        raise ArtifactError('independent original polygon preprocessing budget exhausted')


@dataclass(frozen=True)
class ReferenceSample:
    """One wrapped metric state with owner, right-hand dynamics and portal support."""

    H: str
    s: float
    segment: int
    t: float
    xy: tuple
    tangent: tuple
    left_normal: tuple
    heading: float
    curvature: float
    occurrence_id: str
    surface_id: str
    speed_mps: float
    acceleration_mps2: float
    time_s: float
    portal_support: tuple


@dataclass(frozen=True, init=False)
class Reference:
    """An immutable product exposing fresh proofs and the H-bound producer main time."""

    H: str
    path: object
    ordered: OrderedCurve
    profile: SpeedProfile
    model: DynamicsModel
    footprint: Footprint
    policies: PolicySet
    geometry_report: ValidationReport
    dynamics_report: DynamicsValidationReport
    _payload_bytes: bytes
    _main_lap_time_s: float
    _stations: tuple
    _edge_lengths: tuple
    _start_arcs: tuple
    _times: tuple
    _portal_windows: tuple
    _seal: object

    def __init__(self):
        """Require construction through trusted publication or checked loading."""
        raise ArtifactError('Reference must be independently loaded or published')

    @property
    def length(self):
        """Return the integrated length of the actual stored coefficients."""
        return self.ordered.curve.length

    @property
    def lap_time_s(self):
        """Return the immutable producer-selected main lap time certified by both enclosures."""
        return self._main_lap_time_s

    @property
    def payload(self):
        """Return detached saved authority and historical producer reports."""
        return _parse_json(self._payload_bytes)

    def locate(self, s_m):
        """Locate supplied finite metric progress with right-hand seam ownership."""
        _progress(s_m)
        return self.ordered.curve.locate(s_m)

    def sample(self, s_m, occurrence_id=None):
        """Query true arc, affine squared speed, cyclic acceleration and model time."""
        _progress(s_m)
        geometric = self.ordered.curve.sample(s_m, occurrence_id)
        index = bisect_right(self._stations, geometric.s) - 1
        knot = self.profile.knots[index]
        following = self.profile.knots[(index + 1) % len(self.profile.knots)]
        distance = self._edge_lengths[index]
        if geometric.s == self._stations[index]:
            local = 0.
        else:
            if geometric.segment != knot.segment:
                raise ArtifactError('metric profile/coefficient ownership disagreement')
            local = (self.ordered.curve.segments[knot.segment].arc(geometric.t) -
                     self._start_arcs[index])
            allowance = self.policies.numeric.station_abs
            if local < -allowance or local > distance + allowance:
                raise ArtifactError('metric query exceeds local arc inversion allowance')
            local = min(distance, max(0., local))
        squared = knot.u + (following.u - knot.u) * (local / distance)
        speed = math.sqrt(squared)
        acceleration = (following.u - knot.u) / (2 * distance)
        elapsed = self._times[index] + 2 * local / (math.sqrt(knot.u) + speed)
        support = tuple(portal for portal, low, high in self._portal_windows
                        if (low <= geometric.s <= high if low <= high else
                            geometric.s >= low or geometric.s <= high))
        return ReferenceSample(self.H, geometric.s, geometric.segment, geometric.t,
                               geometric.xy, geometric.tangent, geometric.left_normal,
                               geometric.heading, geometric.curvature, geometric.occurrence_id,
                               geometric.surface_id, speed, acceleration, elapsed, support)

    def window(self, s0_m, s1_m, step_m):
        """Sample an increasing unwrapped metric interval, including both endpoints."""
        for value in (s0_m, s1_m, step_m):
            _progress(value)
        if step_m <= 0 or s1_m < s0_m:
            raise GeometryError('invalid metric window')
        count = math.ceil((s1_m - s0_m) / step_m)
        if count + 1 > self.policies.numeric.max_samples:
            raise GeometryError('window sample budget exhausted')
        return tuple(self.sample(s0_m + min(i * step_m, s1_m - s0_m))
                     for i in range(count + 1))


def _progress(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise GeometryError('finite numeric metric progress required')


def _reference(H, path, ordered, profile, model, footprint, policies, geometry, dynamics, payload):
    reference = object.__new__(Reference)
    stations, distances, starts, times = [], [], [], [0.]
    edge_times = []
    for i, knot in enumerate(profile.knots):
        following = profile.knots[(i + 1) % len(profile.knots)]
        segment = ordered.curve.segments[knot.segment]
        end = following.t if following.segment == knot.segment and i + 1 < len(
            profile.knots) else 1.
        start_arc = segment.arc(knot.t)
        distance = segment.arc(end) - start_arc
        stations.append(ordered.curve.station(knot.segment, knot.t))
        starts.append(start_arc)
        distances.append(distance)
        edge_times.append(2 * distance / (math.sqrt(knot.u) + math.sqrt(following.u)))
        times.append(math.fsum(edge_times))
    ends, windows = _layout(ordered.route), []
    for i, portal in enumerate(ordered.route.portals):
        # Transport declared q anchors once; never substitute them for true s.
        low_q = float((Fraction(ends[i + 1]) - Fraction(portal.before)) %
                      Fraction(ordered.period))
        high_q = float((Fraction(ends[i + 1]) + Fraction(portal.after)) %
                       Fraction(ordered.period))
        windows.append((portal.id, ordered.station_at_q(low_q), ordered.station_at_q(high_q)))
    values = dict(H=H, path=path, ordered=ordered, profile=profile, model=model,
                  footprint=footprint, policies=policies, geometry_report=geometry,
                  dynamics_report=dynamics, _payload_bytes=canonical_bytes(payload),
                  _main_lap_time_s=payload['validation']['dynamics']['lap_time_s'],
                  _stations=tuple(stations), _edge_lengths=tuple(distances),
                  _start_arcs=tuple(starts), _times=tuple(times),
                  _portal_windows=tuple(windows), _seal=_REFERENCE_SEAL)
    for name, value in values.items():
        object.__setattr__(reference, name, value)
    return reference


def _history_fields(stored, replay, names, label):
    """Compare categorical authority without comparing historical numeric bounds."""
    if canonical_bytes(tuple(getattr(stored, name) for name in names)) != canonical_bytes(
            tuple(getattr(replay, name) for name in names)):
        raise ArtifactError(label + ' stored historical authority differs from replay')


def _history_fraction(pair):
    if pair[1] <= 0:
        raise ArtifactError('geometry stored historical rational denominator must be positive')
    value = Fraction(*pair)
    if pair != (value.numerator, value.denominator):
        raise ArtifactError('geometry stored historical rational endpoint is not canonical')
    return value


def _historical_geometry(stored, replay, ordered, footprint, policy):
    """Check snapshot structure and domains; the fresh proof alone certifies geometry."""
    _history_fields(stored, replay, (
        'status', 'reason', 'curve_digest', 'route_sha256', 'coefficients_sha256',
        'coverage', 'assumptions', 'offending_interval'), 'geometry')
    if len(stored.gates) != len(replay.gates):
        raise ArtifactError('geometry stored historical gate coverage differs from replay')
    for gate, actual in zip(stored.gates, replay.gates):
        _history_fields(gate, actual, ('portal_id', 'segment', 't0', 't1', 'q_lower', 'q_upper'),
                        'geometry gate')
        if gate.signed_direction_upper >= -1e-9:
            raise ArtifactError('geometry stored historical gate direction is inconsistent')
    q = tuple(Fraction(value) for value in ordered.q)
    ends = tuple(Fraction(value) for value in _layout(ordered.route))
    portals = {portal.id: (i, portal) for i, portal in enumerate(ordered.route.portals)}
    partitions = [[] for _ in ordered.curve.segments]
    for leaf in stored.intervals:
        if not 0 <= leaf.segment < len(partitions):
            raise ArtifactError('geometry stored historical segment is out of range')
        low, high = _history_fraction(leaf.exact_t0), _history_fraction(leaf.exact_t1)
        if (not 0 <= low < high <= 1 or
                canonical_bytes((leaf.t0, leaf.t1)) != canonical_bytes((float(low), float(high)))):
            raise ArtifactError('geometry stored historical interval endpoints are inconsistent')
        if leaf.occurrence_id != ordered.curve.owners[leaf.segment][0]:
            raise ArtifactError('geometry stored historical occurrence owner is inconsistent')
        if leaf.portal_id:
            if leaf.portal_id not in portals:
                raise ArtifactError('geometry stored historical portal is unknown')
            index, portal = portals[leaf.portal_id]
            qlow = q[leaf.segment] + low * (q[leaf.segment + 1] - q[leaf.segment])
            qhigh = q[leaf.segment] + high * (q[leaf.segment + 1] - q[leaf.segment])
            dlo = _portal_delta(qlow, ends[index + 1], ends[-1])
            dhi = _portal_delta(qhigh, ends[index + 1], ends[-1])
            if (leaf.occurrence_id not in (portal.source, portal.target) or
                    not -Fraction(portal.before) <= dlo <= dhi <= Fraction(portal.after)):
                raise ArtifactError('geometry stored historical portal support is inconsistent')
        if (leaf.method not in ('enclosing_disc_sweep', 'rectangle_curvature_sweep') or
                not 0 <= leaf.curvature_upper <= policy.max_curvature or
                leaf.speed_lower <= policy.numeric_policy.min_speed or
                min(leaf.displacement_upper_m, leaf.clearance_lower_m, leaf.numeric_error_m) < 0 or
                canonical_bytes(leaf.required_margin_m) != canonical_bytes(footprint.margin_m)):
            raise ArtifactError('geometry stored historical bound domain or method '
                                'is inconsistent')
        # Do not re-certify rounded historical clearance or require the replay's
        # adaptive partition/method: either can legitimately differ across hosts.
        partitions[leaf.segment].append((low, high))
    for partition in partitions:
        previous = Fraction(0)
        for low, high in sorted(partition):
            if low != previous:
                raise ArtifactError('geometry stored historical intervals overlap or have a gap')
            previous = high
        if previous != 1:
            raise ArtifactError('geometry stored historical intervals do not cover the segment')


def _history_overlap(low, high, current_low, current_high, label, positive=False):
    if (low > high or (positive and low <= 0) or
            high < current_low or current_high < low):
        raise ArtifactError('dynamics stored historical ' + label + ' enclosure is inconsistent')


def _history_residual(value, limit):
    # A06 renders an accepted exact residual by rounding outward twice. This
    # permits that display conversion only; fresh acceptance keeps its policy.
    return value <= math.nextafter(math.nextafter(limit, math.inf), math.inf)


def _historical_dynamics(stored, replay, profile, policy):
    """Check historical coherence without treating old quantitative bounds as authority."""
    _history_fields(stored, replay, (
        'status', 'reason', 'curve_digest', 'model_digest', 'coverage', 'assumptions',
        'offending_edge'), 'dynamics')
    if (len(stored.edges) != len(profile.knots) or len(stored.edges) != len(replay.edges) or
            tuple(name for name, _ in stored.worst_residuals) != tuple(
                name for name, _ in replay.worst_residuals)):
        raise ArtifactError('dynamics stored historical edge or residual coverage is inconsistent')
    work = 0
    for index, (edge, actual) in enumerate(zip(stored.edges, replay.edges)):
        _history_fields(edge, actual, ('edge', 'segment', 't0', 't1', 'closing', 'cap_mps',
                                       'support_occurrences'), 'dynamics edge')
        _history_overlap(edge.distance_lower_m, edge.distance_upper_m,
                         actual.distance_lower_m, actual.distance_upper_m, 'distance', True)
        _history_overlap(edge.time_lower_s, edge.time_upper_s,
                         actual.time_lower_s, actual.time_upper_s, 'edge time', True)
        _history_overlap(edge.acceleration_lower_mps2, edge.acceleration_upper_mps2,
                         actual.acceleration_lower_mps2, actual.acceleration_upper_mps2,
                         'acceleration')
        du = Fraction(profile.knots[(index + 1) % len(profile.knots)].u) - Fraction(
            profile.knots[index].u)
        accelerations = (du / (2 * Fraction(edge.distance_lower_m)),
                         du / (2 * Fraction(edge.distance_upper_m)))
        if (not edge.distance_lower_m <= edge.distance_m <= edge.distance_upper_m or
                Fraction(edge.acceleration_lower_mps2) > min(accelerations) or
                Fraction(edge.acceleration_upper_mps2) < max(accelerations) or
                min(edge.curvature_upper, edge.curvature_rate_upper) < 0 or
                edge.bound_intervals <= 0 or
                not _history_residual(edge.normalized_residual_upper, policy.residual_abs) or
                not _history_residual(edge.steering_angle_residual_rad, policy.angle_abs_rad)):
            raise ArtifactError('dynamics stored historical numeric domain is inconsistent')
        work += edge.bound_intervals
    if work > policy.max_intervals:
        raise ArtifactError('dynamics stored historical refinement budget is inconsistent')
    for name, value in stored.worst_residuals:
        limit = policy.angle_abs_rad if name == 'steering_angle_rad' else policy.residual_abs
        if not _history_residual(value, limit):
            raise ArtifactError('dynamics stored historical residual exceeds its declared policy')
    _history_overlap(stored.lap_time_lower_s, stored.lap_time_upper_s,
                     replay.lap_time_lower_s, replay.lap_time_upper_s, 'lap time', True)
    if not replay.lap_time_lower_s <= stored.lap_time_s <= replay.lap_time_upper_s:
        raise ArtifactError('dynamics stored historical main lap time lies outside '
                            'replay enclosure')
    if (not stored.lap_time_lower_s <= stored.lap_time_s <= stored.lap_time_upper_s or
            stored.lap_time_error_s < max(stored.lap_time_s - stored.lap_time_lower_s,
                                          stored.lap_time_upper_s - stored.lap_time_s, 0.)):
        raise ArtifactError('dynamics stored historical lap-time summary is inconsistent')


def _decode_reference(raw, expected_H, context, path, expected_curve_digest=None):
    _sha(expected_H, 'externally trusted artifact H')
    implementation = _supported_context(context)
    envelope = _parse_json(raw)
    _keys(envelope, ('schema_version', 'H', 'payload'), 'reference envelope')
    if type(envelope['schema_version']) is not int or envelope['schema_version'] != SCHEMA_VERSION:
        raise ArtifactError('unsupported reference schema version', 'UNSUPPORTED')
    _sha(envelope['H'], 'embedded H')
    payload = envelope['payload']
    if envelope['H'] != expected_H or artifact_identity(payload) != expected_H:
        raise ArtifactError('externally trusted artifact H mismatch')
    _keys(payload, ('conventions', 'approved_route', 'curve', 'approved_curve_digest', 'model',
                    'footprint', 'speed_profile', 'policies', 'implementation', 'validation',
                    'provenance'), 'reference payload')
    if canonical_bytes(payload['conventions']) != canonical_bytes(_CONVENTIONS):
        raise ArtifactError('unsupported reference conventions', 'UNSUPPORTED')
    if canonical_bytes(payload['implementation']) != canonical_bytes(implementation):
        raise ArtifactError('unsupported or changed kernel/checker/dependency identity',
                            'UNSUPPORTED')
    policies = decode_record(PolicySet, payload['policies'], 'policies')
    for actual, expected in ((policies.numeric, context.numeric_policy),
                             (policies.geometry, context.geometry_policy),
                             (policies.dynamics, context.dynamics_policy)):
        if canonical_bytes(asdict(actual)) != canonical_bytes(asdict(expected)):
            raise ArtifactError('artifact differs from independent acceptance policy',
                                'UNSUPPORTED')
    provenance = payload['provenance']
    if (type(provenance) is not dict or any(type(key) is not str or type(value) is not str
                                            for key, value in provenance.items()) or
            len(canonical_bytes(provenance)) > 256 * 1024):
        raise ArtifactError('expected bounded informational string provenance')
    approval = _sha(payload['approved_curve_digest'], 'trusted embedded A04 approval')
    if expected_curve_digest is not None:
        _sha(expected_curve_digest, 'independently retained producer A04 approval')
        if approval != expected_curve_digest:
            raise ArtifactError('staged payload differs from independently retained A04 approval')
        approval = expected_curve_digest
    _route_preflight(payload['approved_route'], context)
    route = validate_route(payload['approved_route'])
    if canonical_bytes(route.payload) != canonical_bytes(payload['approved_route']):
        raise ArtifactError('approved route is not its exact A01 canonical authority')
    curve_data = payload['curve']
    _keys(curve_data, ('coefficients', 'owners', 'q'), 'curve')
    coefficients = _array(curve_data['coefficients'], 'coefficients', min(
        context.geometry_policy.max_segments, context.dynamics_policy.max_segments), 2)
    count = len(coefficients)
    owners = _array(curve_data['owners'], 'owners', count, count)
    q = _array(curve_data['q'], 'q', count + 1, count + 1)
    for coefficient in coefficients:
        _array(coefficient, 'coefficient axes', 2, 2)
        for row in coefficient:
            _array(row, 'coefficient powers', 4, 4)
            if any(type(value) is not float for value in row):
                raise ArtifactError('actual W2 coefficients must retain binary64 float types')
    if any(type(value) is not float for value in q):
        raise ArtifactError('actual W2 q must retain binary64 float types')
    for owner in owners:
        _array(owner, 'owner', 2, 2)
        if any(type(value) is not str for value in owner):
            raise ArtifactError('invalid occurrence/surface owner')
    model_data = payload['model']
    if type(model_data) is not dict:
        raise ArtifactError('invalid model')
    _array(model_data.get('regions'), 'model regions',
           context.dynamics_policy.max_model_regions, 1)
    model = decode_record(DynamicsModel, model_data, 'model')
    footprint = decode_record(Footprint, payload['footprint'], 'footprint')
    profile_data = payload['speed_profile']
    if type(profile_data) is not dict:
        raise ArtifactError('invalid profile')
    _array(profile_data.get('knots'), 'profile knots', context.dynamics_policy.max_knots, 2)
    profile = decode_record(SpeedProfile, profile_data, 'speed_profile')
    validation = payload['validation']
    _keys(validation, ('geometry', 'dynamics'), 'validation')
    if type(validation['geometry']) is not dict or type(validation['dynamics']) is not dict:
        raise ArtifactError('invalid stored validation records')
    _array(validation['geometry'].get('intervals'), 'geometry intervals',
           context.geometry_policy.max_intervals)
    _array(validation['geometry'].get('gates'), 'geometry gates', len(route.portals))
    _array(validation['dynamics'].get('edges'), 'dynamics edges',
           context.dynamics_policy.max_knots)
    stored_geometry = decode_record(ValidationReport, validation['geometry'], 'geometry report')
    stored_dynamics = decode_record(DynamicsValidationReport, validation['dynamics'],
                                    'dynamics report')
    ordered = OrderedCurve(route, Curve(coefficients, owners, context.numeric_policy), q)
    geometry = validate_geometry(ordered, route, footprint, context.geometry_policy,
                                 expected_curve_digest=approval)
    dynamics = validate_dynamics(ordered, profile, model, context.dynamics_policy,
                                 expected_curve_digest=approval)
    for name, report, required in (
            ('geometry', geometry, context.required_geometry_coverage),
            ('dynamics', dynamics, context.required_dynamics_coverage)):
        if report.status != 'PASS' or report.curve_digest != approval:
            raise ArtifactError(name + ' replay ' + report.status + ': ' + report.reason,
                                report.status)
        if not set(required) <= set(report.coverage):
            raise ArtifactError(name + ' lacks independently required coverage', 'UNSUPPORTED')
    _historical_geometry(stored_geometry, geometry, ordered, footprint, context.geometry_policy)
    _historical_dynamics(stored_dynamics, dynamics, profile, context.dynamics_policy)
    return _reference(expected_H, path, ordered, profile, model, footprint,
                      policies, geometry, dynamics, payload)


def _load_bytes(raw, expected_H, context, path, expected_curve_digest=None):
    try:
        return _decode_reference(raw, expected_H, context, path, expected_curve_digest)
    except ArtifactError:
        raise
    except (ValueError, TypeError, OverflowError, KeyError, IndexError) as exc:
        raise ArtifactError('malformed reconstructed reference authority: ' + str(exc)) from exc


def load_reference(path, *, expected_H, validation_context):
    """Reload exact saved bytes under an external H and replay both independent checks."""
    _sha(expected_H, 'externally trusted artifact H')
    path = Path(os.path.abspath(os.fspath(path)))
    if path.name != 'reference.json':
        path = path / 'reference.json'
    if any(part.startswith(('.tmp-', '.lock-')) for part in path.parts):
        raise ArtifactError('private staging and lock paths cannot be accepted references')
    parent = _open_directory(path.parent)
    try:
        if sorted(os.listdir(parent)) != ['reference.json']:
            raise ArtifactError('immutable reference directory has unknown or incomplete files')
        descriptor = os.open('reference.json', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                             dir_fd=parent)
        try:
            raw = _read_fd(descriptor, MAX_ARTIFACT_BYTES)
        finally:
            os.close(descriptor)
        return _load_bytes(raw, expected_H, validation_context, path)
    except (OSError, GeometryError) as exc:
        raise ArtifactError('cannot reconstruct accepted reference: ' + str(exc)) from exc
    finally:
        os.close(parent)


def _rename_noreplace(source_name, target_name, parent_fd):
    """Atomically rename one Linux directory without replacing any existing target."""
    libc = ctypes.CDLL(None, use_errno=True)
    rename = getattr(libc, 'renameat2', None)
    if rename is None:
        raise ArtifactError('Linux renameat2 no-replace support required', 'UNSUPPORTED')
    rename.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
    rename.restype = ctypes.c_int
    if rename(parent_fd, os.fsencode(source_name), parent_fd, os.fsencode(target_name), 1) != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))


def _write_all(descriptor, data):
    view = memoryview(data)
    while view:
        written = os.write(descriptor, view)
        if written <= 0:
            raise ArtifactError('incomplete staged artifact write')
        view = view[written:]


def publish_reference(payload, output_dir, *, expected_H, expected_curve_digest,
                      validation_context=ValidationContext()):
    """
    Replay staged bytes and durably publish a new immutable digest directory.

    The trusted producer freezes expected_H after comparing all original input
    authorities and retains expected_curve_digest directly from the A04 return.
    Both expectations remain separate from the mutable payload.

    A post-rename parent-fsync failure can leave a complete valid directory with
    uncertain power-loss durability and no receipt. All earlier failures leave
    the accepted directory absent. Existing targets are never replaced, including
    targets created by uncooperative writers between inspection and rename.
    """
    _sha(expected_H, 'independently frozen producer artifact H')
    _sha(expected_curve_digest, 'independently retained producer A04 approval')
    _supported_context(validation_context)
    H = artifact_identity(payload)
    if H != expected_H:
        raise ArtifactError('payload differs from independently frozen producer artifact H')
    data = canonical_bytes({'schema_version': SCHEMA_VERSION, 'H': H, 'payload': payload})
    output = Path(os.path.abspath(os.fspath(output_dir)))
    parent = _open_directory(output, create=True)
    lock = stage = None
    stage_name, published = None, False
    try:
        lock = os.open('.lock-' + H, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK,
                       0o600, dir_fd=parent)
        info = os.fstat(lock)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ArtifactError('publication lock must be a private regular file')
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            os.stat(H, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise ArtifactError('immutable artifact target already exists')
        stage_name = '.tmp-' + H + '-' + secrets.token_hex(12)
        os.mkdir(stage_name, 0o700, dir_fd=parent)
        stage = os.open(stage_name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
        descriptor = os.open('reference.json', os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             0o600, dir_fd=stage)
        try:
            _write_all(descriptor, data)
            os.fchmod(descriptor, 0o444)
            os.fsync(descriptor)
            os.lseek(descriptor, 0, os.SEEK_SET)
            saved = _read_fd(descriptor, MAX_ARTIFACT_BYTES)
        finally:
            os.close(descriptor)
        path = output / H / 'reference.json'
        reference = _load_bytes(saved, expected_H, validation_context, path, expected_curve_digest)
        if sorted(os.listdir(stage)) != ['reference.json']:
            raise ArtifactError('staged reference contains unknown content')
        os.fchmod(stage, 0o555)
        os.fsync(stage)
        _rename_noreplace(stage_name, H, parent)
        published = True
        os.fsync(parent)
        return reference
    except OSError as exc:
        raise ArtifactError('atomic reference publication failed: ' + str(exc)) from exc
    finally:
        if stage is not None:
            if not published:
                os.fchmod(stage, 0o700)
                try:
                    os.unlink('reference.json', dir_fd=stage)
                except FileNotFoundError:
                    pass
            os.close(stage)
        if stage_name is not None and not published:
            try:
                os.rmdir(stage_name, dir_fd=parent)
            except FileNotFoundError:
                pass
        if lock is not None:
            os.close(lock)
        os.close(parent)
