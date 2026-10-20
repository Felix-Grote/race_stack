"""
Explicit offline compilation and independently checked reference commands.

No command discovers a map, vehicle configuration, checkout, or running ROS node.
The compiler captures the trusted A04 authority before any downstream operation.
"""
from dataclasses import asdict, dataclass
import argparse
import hashlib
import json
import math
import numbers
import os
from pathlib import Path
import resource
import tempfile
import time

from .cyclic_retime import DynamicsModel, curve_digest, model_digest, retime
from .iqp_route_adapter import optimize
from .route_artifact import (CONTRACT_ID, PolicySet, ValidationContext, artifact_identity,
                             build_payload, canonical_bytes, decode_record, load_reference,
                             publish_reference, read_json)
from .route_input import Route, validate_route
from .route_validate import Footprint, validate_geometry
from .route_validate_dynamics import validate_dynamics

MAX_CONFIG_BYTES = 2 * 1024 ** 2


@dataclass(frozen=True)
class CompileResult:
    """A receipt; only PASS carries a usable immutable artifact identity/path."""

    status: str
    reason: str
    H: object = None
    artifact_path: object = None
    geometry: object = None
    dynamics: object = None
    run_report: object = None


def _keys(value, names, where):
    if type(value) is not dict or set(value) != set(names.split()):
        raise ValueError(where + ': missing/unknown fields')


def _coverage(value, where):
    if (type(value) is not list or len(value) > 64 or
            any(type(x) is not str or not x or len(x) > 128 for x in value) or
            len(value) != len(set(value))):
        raise ValueError(where + ': expected bounded unique coverage names')
    return tuple(value)


def load_vehicle_config(path):
    """Parse a bounded explicit model/body document, with no physical defaults."""
    return _vehicle_document(read_json(path, max_bytes=MAX_CONFIG_BYTES))


def _vehicle_document(value):
    _keys(value, 'schema_version model footprint', 'vehicle config')
    if type(value['schema_version']) is not int or value['schema_version'] != 1:
        raise ValueError('unsupported vehicle config schema')
    return (decode_record(DynamicsModel, value['model'], 'model'),
            decode_record(Footprint, value['footprint'], 'footprint'))


def load_policy(path):
    """Load the caller's independent numerical and validation context."""
    return _policy_document(read_json(path, max_bytes=MAX_CONFIG_BYTES))


def _policy_document(value):
    _keys(value, 'schema_version contract_id numeric solver retime geometry dynamics '
          'required_geometry_coverage required_dynamics_coverage retime_spacing_m', 'policy')
    if type(value['schema_version']) is not int or value['schema_version'] != 1:
        raise ValueError('unsupported policy schema')
    if type(value['contract_id']) is not str or value['contract_id'] != CONTRACT_ID:
        raise ValueError('unsupported independently selected reference contract')
    policy_names = ('numeric', 'solver', 'retime', 'geometry', 'dynamics')
    policies = decode_record(PolicySet, {k: value[k] for k in policy_names}, 'policies')
    context = ValidationContext(
        numeric_policy=policies.numeric, geometry_policy=policies.geometry,
        dynamics_policy=policies.dynamics,
        required_geometry_coverage=_coverage(value['required_geometry_coverage'], 'geometry'),
        required_dynamics_coverage=_coverage(value['required_dynamics_coverage'], 'dynamics'),
        contract_id=value['contract_id'])
    spacing = value['retime_spacing_m']
    if type(spacing) not in (int, float) or not math.isfinite(spacing) or spacing <= 0:
        raise ValueError('invalid explicit retiming spacing')
    return policies, context, spacing


def _context(policies):
    return ValidationContext(numeric_policy=policies.numeric,
                             geometry_policy=policies.geometry,
                             dynamics_policy=policies.dynamics)


def _cpu():
    own = resource.getrusage(resource.RUSAGE_SELF)
    child = resource.getrusage(resource.RUSAGE_CHILDREN)
    return own.ru_utime + own.ru_stime + child.ru_utime + child.ru_stime


def _telemetry(value):
    # Numerical observations contain NumPy scalars. Project this separate run
    # view to native JSON scalars; immutable authorities use the exact codec.
    if type(value) in (str, bool, int, float, type(None)):
        return value
    if type(value) is dict:
        return {key: _telemetry(item) for key, item in value.items()}
    if type(value) in (list, tuple):
        return tuple(_telemetry(item) for item in value)
    if isinstance(value, numbers.Integral):
        return int(value)
    if isinstance(value, numbers.Real):
        return float(value)
    raise ValueError('unsupported separate run telemetry value')


def compile_reference(route, model, footprint, policies, *, output_dir,
                      retime_spacing_m=.5, validation_context=None, provenance=None):
    """
    Compile one approved route and publish only after persisted-byte replay.

    The approved curve expectation is captured immediately after the trusted
    optimizer returns. Every subsequent checker receives that same value.
    """
    if (type(route) is not Route or type(model) is not DynamicsModel or
            type(footprint) is not Footprint or type(policies) is not PolicySet):
        raise ValueError('explicit validated route/model/footprint/PolicySet required')
    approved = validate_route(route.payload)
    if approved != route:
        raise ValueError('route records differ from their original validated payload')
    expected_regions = {(o.id, o.surface_id) for o in approved.occurrences}
    if {(r.occurrence_id, r.surface_id) for r in model.regions} != expected_regions:
        return CompileResult('UNSUPPORTED', 'model coverage must exactly match route occurrences')
    if ((policies.retime.require_steering or policies.dynamics.require_steering) and
            model.steering is None):
        return CompileResult('UNSUPPORTED', 'independently required steering model unavailable')
    context = _context(policies) if validation_context is None else validation_context
    if type(context) is not ValidationContext:
        raise ValueError('independent ValidationContext required')
    if (canonical_bytes(asdict(context.numeric_policy)) !=
            canonical_bytes(asdict(policies.numeric)) or
            canonical_bytes(asdict(context.geometry_policy)) !=
            canonical_bytes(asdict(policies.geometry)) or
            canonical_bytes(asdict(context.dynamics_policy)) !=
            canonical_bytes(asdict(policies.dynamics))):
        raise ValueError('compile policy differs from independent acceptance context')
    if (type(retime_spacing_m) not in (int, float) or
            not math.isfinite(retime_spacing_m) or retime_spacing_m <= 0):
        raise ValueError('invalid retiming metric spacing')
    own_provenance = dict(provenance or {})
    own_provenance['retime_spacing_m'] = repr(retime_spacing_m)
    if any(type(key) is not str or type(value) is not str
           for key, value in own_provenance.items()):
        raise ValueError('explicit informational provenance must contain strings')
    # Freeze caller-controlled inputs before invoking downstream producers.
    expected_fields = {key: canonical_bytes(value) for key, value in {
        'approved_route': approved.payload, 'model': asdict(model),
        'footprint': asdict(footprint), 'policies': asdict(policies),
        'provenance': own_provenance}.items()}
    start, start_cpu = time.monotonic(), _cpu()
    run = {'scope': 'synthetic or explicitly supplied offline planar model only', 'phases': {}}
    geometric = dynamic = None

    def observed(name, call):
        began, cpu = time.monotonic(), _cpu()
        result = call()
        run['phases'][name] = {'wall_seconds': time.monotonic() - began,
                               'cpu_seconds': _cpu() - cpu}
        return result

    def receipt(status, reason, reference=None):
        run['wall_seconds'] = time.monotonic() - start
        run['cpu_seconds'] = _cpu() - start_cpu
        run['parent_peak_rss_bytes'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        return CompileResult(status, reason, None if reference is None else reference.H,
                             None if reference is None else str(reference.path),
                             geometric, dynamic, _telemetry(run))

    try:
        began, began_cpu = time.monotonic(), _cpu()
        numerical = optimize(approved, policy=policies.solver, numeric_policy=policies.numeric)
        # This must precede retiming, metadata production, serialization, or any
        # other downstream call. A profile/selfhash never supplies approval.
        expected = (curve_digest(numerical.ordered) if numerical.status == 'CANDIDATE' and
                    numerical.ordered is not None else None)
        run['phases']['optimization'] = {'wall_seconds': time.monotonic() - began,
                                         'cpu_seconds': _cpu() - began_cpu}
        if numerical.status != 'CANDIDATE' or numerical.ordered is None:
            return receipt('FAIL' if numerical.status == 'CANDIDATE' else numerical.status,
                           numerical.reason)
        ordered = numerical.ordered
        expected_fields['approved_curve_digest'] = canonical_bytes(expected)
        expected_fields['curve'] = canonical_bytes({
            'coefficients': ordered.curve.coefficients, 'owners': ordered.curve.owners,
            'q': ordered.q})
        run['approved_curve_digest'] = expected
        run['solver_iteration_count'] = len(numerical.traces)
        run['solver_iterations'] = [asdict(trace) for trace in numerical.traces]
        geometric = observed('geometry', lambda: validate_geometry(
            ordered, approved, footprint, policies.geometry, expected_curve_digest=expected))
        if geometric.status != 'PASS':
            return receipt(geometric.status, geometric.reason)
        if not set(context.required_geometry_coverage).issubset(geometric.coverage):
            return receipt('UNSUPPORTED', 'required independent geometry coverage unavailable')
        approved_geometry_bytes = canonical_bytes(asdict(geometric))
        timed = observed('retiming', lambda: retime(
            ordered, model, spacing_m=retime_spacing_m, policy=policies.retime))
        run['retimer'] = {k: getattr(timed, k) for k in
                          ('status', 'message', 'objective', 'iterations', 'edge_count',
                           'max_lp_residual')}
        for name in ('objective', 'max_lp_residual'):
            if run['retimer'][name] is not None:
                run['retimer'][name] = float(run['retimer'][name])
        if timed.status != 'CANDIDATE' or timed.profile is None:
            return receipt(timed.status, timed.message)
        expected_fields['speed_profile'] = canonical_bytes(asdict(timed.profile))
        dynamic = observed('dynamics', lambda: validate_dynamics(
            ordered, timed.profile, model, policies.dynamics, metadata=timed.metadata,
            expected_curve_digest=expected))
        if dynamic.status != 'PASS':
            return receipt(dynamic.status, dynamic.reason)
        if not set(context.required_dynamics_coverage).issubset(dynamic.coverage):
            return receipt('UNSUPPORTED', 'required independent dynamics coverage unavailable')
        if geometric.curve_digest != expected or dynamic.curve_digest != expected:
            return receipt('FAIL', 'independent reports disagree with trusted final authority')
        approved_dynamics_bytes = canonical_bytes(asdict(dynamic))
        payload = build_payload(
            ordered, timed.profile, model, footprint, solver_policy=policies.solver,
            retime_policy=policies.retime, geometry_policy=policies.geometry,
            dynamics_policy=policies.dynamics, approved_curve_digest=expected,
            geometry_report=geometric, dynamics_report=dynamic, provenance=own_provenance)
        if type(payload) is not dict or type(payload.get('validation')) is not dict:
            return receipt('FAIL', 'serialized reference has invalid authority shape')
        for key, frozen in expected_fields.items():
            if canonical_bytes(payload.get(key)) != frozen:
                return receipt('FAIL',
                               'serialized authority differs from controlled input: ' + key)
        if (canonical_bytes(payload.get('validation', {}).get('geometry')) !=
                approved_geometry_bytes or
                canonical_bytes(payload.get('validation', {}).get('dynamics')) !=
                approved_dynamics_bytes):
            return receipt('FAIL', 'serialized proof differs from independently retained report')
        expected_H = artifact_identity(payload)
        reference = observed('persisted_revalidation_and_publication', lambda: publish_reference(
            payload, output_dir, expected_H=expected_H, expected_curve_digest=expected,
            validation_context=context))
        return receipt('PASS', '', reference)
    except (ValueError, OSError, RuntimeError) as exc:
        return receipt(getattr(exc, 'status', 'FAIL'), str(exc))


def _write_report(path, value):
    """Atomically create a separate receipt without replacing any existing path."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    encoded = canonical_bytes(value)
    descriptor, temporary = tempfile.mkstemp(prefix='.receipt-', dir=target.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, target, follow_symlinks=False)
        parent = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(parent)
        finally:
            os.close(parent)
    finally:
        os.unlink(temporary)


def _provenance(args, route, model, policies, inputs):
    result = {'route_digest': route.digest, 'model_digest': model_digest(model),
              'policy_digest': hashlib.sha256(canonical_bytes(asdict(policies))).hexdigest()}
    for key, document in inputs.items():
        # Hash the actual bounded input snapshots used in this compilation.
        result[key + '_canonical_sha256'] = hashlib.sha256(
            canonical_bytes(document)).hexdigest()
    if args.build_manifest:
        build = read_json(args.build_manifest, max_bytes=MAX_CONFIG_BYTES)
        source = build.get('source_commit')
        if (build.get('schema_version') != 1 or type(build.get('schema_version')) is not int or
                type(source) is not str or len(source) != 40 or
                any(c not in '0123456789abcdef' for c in source) or
                type(build.get('gitlinks')) is not dict):
            raise ValueError('invalid explicit build provenance manifest')
        result['build_manifest_sha256'] = hashlib.sha256(canonical_bytes(build)).hexdigest()
        result['source_commit'] = source
        result['gitlinks'] = canonical_bytes(build['gitlinks']).decode('utf-8')
    return result


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        """Report argument errors through the command's JSON error contract."""
        raise ValueError('arguments: ' + message)


def _parser():
    parser = _ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    compiler = sub.add_parser('compile', help='compile and publish one explicit legal route')
    compiler.add_argument('--manifest', required=True)
    compiler.add_argument('--vehicle-config', required=True)
    compiler.add_argument('--output', required=True)
    compiler.add_argument('--build-manifest')
    for command in ('validate', 'query', 'export'):
        child = sub.add_parser(command)
        child.add_argument('--artifact', required=True)
        child.add_argument('--expected-h', required=True)
        if command == 'query':
            child.add_argument('--s-m', required=True, type=float)
            child.add_argument('--occurrence-id')
        if command == 'export':
            child.add_argument('--step-m', required=True, type=float)
            child.add_argument('--output', required=True)
    for child in sub.choices.values():
        child.add_argument('--policy', required=True)
        if child is not sub.choices['query']:
            child.add_argument('--report', required=True)
    return parser


def main(argv=None):
    """Run a single explicit installed command and emit machine-readable JSON."""
    args = result = None
    try:
        args = _parser().parse_args(argv)
        policy_document = read_json(args.policy, max_bytes=MAX_CONFIG_BYTES)
        policies, context, spacing = _policy_document(policy_document)
        if args.command == 'compile':
            route_document = read_json(args.manifest, max_bytes=MAX_CONFIG_BYTES)
            vehicle_document = read_json(args.vehicle_config, max_bytes=MAX_CONFIG_BYTES)
            route = validate_route(route_document)
            model, body = _vehicle_document(vehicle_document)
            receipt = compile_reference(
                route, model, body, policies, output_dir=args.output,
                retime_spacing_m=spacing, validation_context=context,
                provenance=_provenance(args, route, model, policies, {
                    'manifest_input': route_document, 'vehicle_input': vehicle_document,
                    'policy_input': policy_document}))
            result = {'schema_version': 1, **asdict(receipt)}
        else:
            reference = load_reference(args.artifact, expected_H=args.expected_h,
                                       validation_context=context)
            result = {'schema_version': 1, 'status': 'PASS', 'reason': '', 'H': reference.H}
            if args.command == 'validate':
                result.update(artifact_path=str(reference.path),
                              geometry=asdict(reference.geometry_report),
                              dynamics=asdict(reference.dynamics_report))
            elif args.command == 'query':
                result['sample'] = asdict(reference.sample(args.s_m, args.occurrence_id))
            else:
                from .route_legacy_export import export_waypoints
                result.update(asdict(export_waypoints(
                    reference, step_m=args.step_m, output_dir=args.output)))
        if hasattr(args, 'report'):
            _write_report(args.report, result)
    except (ValueError, OSError, RuntimeError) as exc:
        result = {'schema_version': 1, 'status': getattr(exc, 'status', 'FAIL'),
                  'reason': str(exc)}
        if hasattr(args, 'report'):
            try:
                _write_report(args.report, result)
            except (ValueError, OSError, RuntimeError):
                # stdout is still an explicit failed receipt; no immutable
                # artifact or pre-existing report is ever overwritten.
                pass
    print(json.dumps(result, sort_keys=True, separators=(',', ':'), allow_nan=False))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
