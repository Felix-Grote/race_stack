"""Public compile CLI trust boundaries and strict explicit input contracts."""
from dataclasses import FrozenInstanceError, asdict, replace
import gzip
import json
import math
import os
from pathlib import Path
import subprocess
import sys

import pytest

import global_planner.route_compile as compiler
from global_planner.cyclic_retime import (
    DynamicsModel, ModelRegion, RegionLimits, RetimePolicy, curve_digest)
from global_planner.iqp_route_adapter import OptimizationResult, SolverPolicy
from global_planner.route_artifact import PolicySet, ValidationContext
from global_planner.route_corridor import OrderedCurve
from global_planner.route_input import load_route
from global_planner.route_reference import Curve, NumericPolicy
from global_planner.route_validate import Footprint, GeometryValidationPolicy
from global_planner.route_validate_dynamics import DynamicsValidationPolicy


FIX = Path(__file__).parent / 'fixtures' / 'project_a'
BODY = Footprint(.1, .1, .12, .01)
DELETE = object()


def _model(route):
    """Build an explicit synthetic model covering every supplied occurrence."""
    limits = RegionLimits(.05, 4., 2., 3., 4., 2.5, .02,
                          'W3 explicit synthetic planar limits; no car calibration')
    return DynamicsModel(tuple(ModelRegion(o.id, o.surface_id, limits)
                               for o in route.occurrences),
                         'W3 supplied synthetic model; no physical evidence')


def _vehicle():
    """Return a complete vehicle document without physical defaults."""
    route = load_route(FIX / 's0_route.json')
    return {'schema_version': 1, 'model': asdict(_model(route)), 'footprint': asdict(BODY)}


def _policy():
    """Return a complete independently selected validation context."""
    context = ValidationContext()
    return {'schema_version': 1, 'contract_id': context.contract_id,
            'numeric': asdict(NumericPolicy()), 'solver': asdict(SolverPolicy()),
            'retime': asdict(RetimePolicy()), 'geometry': asdict(GeometryValidationPolicy()),
            'dynamics': asdict(DynamicsValidationPolicy()),
            'required_geometry_coverage': list(context.required_geometry_coverage),
            'required_dynamics_coverage': list(context.required_dynamics_coverage),
            'retime_spacing_m': .5}


def _write(path, payload):
    """Write one finite JSON input document to its explicit test path."""
    path.write_text(json.dumps(payload, allow_nan=False), encoding='utf-8')
    return path


def _change(payload, path, value):
    """Apply one targeted malformed-input mutation to a fresh document."""
    node = payload
    for name in path[:-1]:
        node = node[name]
    if value is DELETE:
        del node[path[-1]]
    else:
        node[path[-1]] = value


def _candidate():
    """Reconstruct archived coefficients for orchestration fault injection."""
    records = json.loads(gzip.decompress((FIX / 'w2_a04_candidates.json.gz').read_bytes()))
    record = records['candidates']['s0_route']
    route = load_route(FIX / 's0_route.json')
    return OrderedCurve(route, Curve(record['coefficients'], record['owners']), record['q'])


def _policies(**changes):
    """Construct supported policies with explicit test-specific changes."""
    values = dict(numeric=NumericPolicy(), solver=SolverPolicy(), retime=RetimePolicy(),
                  geometry=GeometryValidationPolicy(), dynamics=DynamicsValidationPolicy())
    values.update(changes)
    return PolicySet(**values)


def _solver_result(ordered, policy=None):
    """Wrap an existing authority without running another optimization."""
    return OptimizationResult('CANDIDATE', ordered, (), 'retained approved test authority',
                              policy or SolverPolicy())


def _assert_unpublished(result, output):
    """Require an unsuccessful receipt and absence of accepted references."""
    assert result.status != 'PASS'
    assert result.reason
    assert not result.H and not result.artifact_path
    assert not list(output.glob('*/reference.json'))


def _cli(*arguments, cwd):
    """Run a fresh command process and enforce its JSON receipt contract."""
    completed = subprocess.run(
        [sys.executable, '-m', 'global_planner.route_compile', *map(str, arguments)],
        cwd=cwd, env=dict(os.environ), capture_output=True, text=True, timeout=180)
    try:
        report = json.loads(completed.stdout)
    except ValueError:
        pytest.fail('CLI did not return one JSON report: ' + completed.stdout[:500] +
                    completed.stderr[:500])
    assert report['schema_version'] == 1
    assert type(report['status']) is str
    if completed.returncode:
        assert report['status'] != 'PASS' and report['reason']
        assert not report.get('artifact_path')
    return completed, report


@pytest.mark.parametrize('path,value', [
    (('extra',), 1), (('schema_version',), True), (('schema_version',), 2),
    (('model',), DELETE), (('model', 'provenance'), ''),
    (('model', 'provenance'), DELETE), (('model', 'unknown_model'), {}),
    (('model', 'regions', 0, 'limits', 'speed_max_mps'), True),
    (('model', 'regions', 0, 'limits', 'ay_mps2'), '4.0'),
    (('model', 'regions', 0, 'limits', 'provenance'), ''),
    (('model', 'regions', 0, 'limits', 'ax_neg_mps2'), DELETE),
    (('model', 'regions', 0, 'occurrence_id'), False),
    (('model', 'steering'), dict(wheelbase_m=.3, angle_max_rad=.7, rate_max_radps=False)),
    (('model', 'steering'), []),
    (('footprint', 'margin_m'), True), (('footprint', 'width_m'), 0.),
    (('footprint', 'front_m'), DELETE), (('footprint', 'surrogate_radius'), .2),
])
def test_vehicle_loader_requires_complete_typed_supported_input(tmp_path, path, value):
    """Reject malformed model and body fields before compilation."""
    payload = _vehicle()
    _change(payload, path, value)
    with pytest.raises(ValueError):
        compiler.load_vehicle_config(_write(tmp_path / 'vehicle.json', payload))


@pytest.mark.parametrize('path,value', [
    (('extra',), 1), (('schema_version',), True), (('contract_id',), 'unsupported.v99'),
    (('numeric',), DELETE), (('numeric', 'arc_abs'), True),
    (('numeric', 'quad_limit'), 2.5), (('solver', 'qp_cpu_seconds'), True),
    (('retime', 'require_steering'), 1), (('retime', 'max_knots'), DELETE),
    (('geometry', 'numeric_policy', 'station_abs'), True),
    (('geometry', 'require_physical_coverage'), 1),
    (('dynamics', 'metadata_abs'), '1e-7'), (('dynamics', 'require_steering'), None),
    (('required_geometry_coverage',), 'legal_planar_geometry'),
    (('required_dynamics_coverage',), [False]),
    (('required_dynamics_coverage',), DELETE),
    (('retime_spacing_m',), True), (('retime_spacing_m',), 0.),
])
def test_policy_loader_requires_explicit_typed_context(tmp_path, path, value):
    """Reject incomplete, mistyped or unsupported policy documents."""
    payload = _policy()
    _change(payload, path, value)
    with pytest.raises(ValueError):
        compiler.load_policy(_write(tmp_path / 'policy.json', payload))


@pytest.mark.parametrize('kind', ['vehicle', 'policy'])
@pytest.mark.parametrize('mutation', [
    'duplicate', 'nested_duplicate', 'nan', 'overflow', 'truncated', 'utf8'])
def test_input_json_parser_rejects_ambiguous_or_nonfinite_bytes(tmp_path, kind, mutation):
    """Reject duplicate keys, invalid encoding and nonfinite JSON inputs."""
    payload = _vehicle() if kind == 'vehicle' else _policy()
    raw = json.dumps(payload).encode('utf-8')
    if mutation == 'duplicate':
        raw = raw.replace(b'"schema_version": 1', b'"schema_version": 1,"schema_version": 1')
    elif mutation == 'nested_duplicate':
        needle = b'"drag_over_mass": 0.02' if kind == 'vehicle' else b'"quad_limit": 100'
        assert needle in raw
        raw = raw.replace(needle, needle + b',' + needle)
    elif mutation == 'nan':
        raw = raw.replace(b'"schema_version": 1', b'"schema_version": NaN')
    elif mutation == 'overflow':
        raw = raw.replace(b'"schema_version": 1', b'"schema_version": 1e999')
    elif mutation == 'truncated':
        raw = raw[:-1]
    else:
        raw = b'\xff' + raw
    path = tmp_path / (kind + '.json')
    path.write_bytes(raw)
    loader = compiler.load_vehicle_config if kind == 'vehicle' else compiler.load_policy
    with pytest.raises(ValueError):
        loader(path)


@pytest.mark.parametrize('loader', [compiler.load_vehicle_config, compiler.load_policy])
def test_explicit_config_read_is_bounded_before_json_reconstruction(tmp_path, monkeypatch, loader):
    """Enforce the byte budget before invoking the JSON decoder."""
    path = tmp_path / 'oversized.json'
    path.write_bytes(b' ' * (2 * 1024 ** 2 + 1))

    def forbidden(*args, **kwargs):
        """Detect premature JSON reconstruction of an oversized input."""
        raise AssertionError('oversized config reached JSON reconstruction')

    monkeypatch.setattr(json, 'loads', forbidden)
    with pytest.raises(ValueError):
        loader(path)


def test_explicit_loaders_retain_signed_zero_and_model_provenance(tmp_path):
    """Preserve exact numerical spelling and unrestricted model provenance."""
    payload = _vehicle()
    payload['footprint']['margin_m'] = -0.0
    payload['model']['regions'][0]['limits']['drag_over_mass'] = -0.0
    payload['model']['provenance'] = (
        'Synthetic W3 \u2014 supplied software model; no car calibration')
    model, body = compiler.load_vehicle_config(_write(tmp_path / 'vehicle.json', payload))
    assert math.copysign(1., body.margin_m) == -1.
    assert math.copysign(1., model.regions[0].limits.drag_over_mass) == -1.
    assert model.provenance == payload['model']['provenance']
    policies, context, spacing = compiler.load_policy(_write(tmp_path / 'policy.json', _policy()))
    assert policies.numeric == context.numeric_policy == NumericPolicy()
    assert policies.geometry == context.geometry_policy
    assert policies.dynamics == context.dynamics_policy
    assert type(context.required_geometry_coverage) is tuple
    assert type(context.required_dynamics_coverage) is tuple
    assert spacing == .5


def test_numerical_failure_exposes_no_reference(tmp_path, monkeypatch):
    """Keep a numerical resource failure outside the accepted product API."""
    route = load_route(FIX / 's0_route.json')
    failure = OptimizationResult('RESOURCE_LIMIT', None, (),
                                 'injected point budget', SolverPolicy())
    monkeypatch.setattr(compiler, 'optimize', lambda *a, **k: failure)
    result = compiler.compile_reference(
        route, _model(route), BODY, _policies(), output_dir=tmp_path)
    _assert_unpublished(result, tmp_path)
    assert result.status == 'RESOURCE_LIMIT'
    with pytest.raises(FrozenInstanceError):
        result.status = 'PASS'


def test_model_coverage_is_checked_before_starting_the_solver(tmp_path, monkeypatch):
    """Reject missing occurrence coverage before spending solver resources."""
    route = load_route(FIX / 's0_route.json')
    model = _model(route)
    missing = replace(model, regions=model.regions[:-1])
    calls = []

    def optimizer(*args, **kwargs):
        """Record an unintended solver call for the incomplete model."""
        calls.append(True)
        return OptimizationResult('RESOURCE_LIMIT', None, (),
                                  'optimizer must not see incomplete model', SolverPolicy())

    monkeypatch.setattr(compiler, 'optimize', optimizer)
    result = compiler.compile_reference(route, missing, BODY, _policies(), output_dir=tmp_path)
    _assert_unpublished(result, tmp_path)
    assert calls == []


def test_geometry_uncertainty_cannot_start_retiming_or_publish(tmp_path, monkeypatch):
    """Require independent geometry acceptance before downstream work."""
    ordered = _candidate()
    monkeypatch.setattr(compiler, 'optimize', lambda *a, **k: _solver_result(ordered))

    def forbidden(*args, **kwargs):
        """Detect retiming before the mandatory geometry acceptance."""
        raise AssertionError('retimer called before required geometry PASS')

    monkeypatch.setattr(compiler, 'retime', forbidden)
    policies = _policies(geometry=replace(GeometryValidationPolicy(), max_intervals=0))
    result = compiler.compile_reference(
        ordered.route, _model(ordered.route), BODY, policies, output_dir=tmp_path)
    _assert_unpublished(result, tmp_path)
    assert result.geometry.status == 'INCONCLUSIVE'


def test_curve_approval_is_captured_before_retimer_can_change_lineage(tmp_path, monkeypatch):
    """Retain the original curve approval across a coordinated q mutation."""
    ordered = _candidate()
    expected = curve_digest(ordered)
    expectations = []
    original_geometry = compiler.validate_geometry
    original_dynamics = compiler.validate_dynamics
    original_retime = compiler.retime
    monkeypatch.setattr(compiler, 'optimize', lambda *a, **k: _solver_result(ordered))

    def geometry(*args, **kwargs):
        """Record the independently supplied geometry approval identity."""
        expectations.append(('geometry', kwargs.get('expected_curve_digest')))
        return original_geometry(*args, **kwargs)

    def malicious_retime(authority, *args, **kwargs):
        """Regenerate a profile after hostile mutation of inherited progress."""
        q = list(authority.q)
        q[3] += .01 * (q[4] - q[3])
        # Deliberate hostile intermediate mutation despite the producer's frozen
        # record. Recomputed self-hashes/profile must not replace trusted A04 C.
        object.__setattr__(authority, 'q', tuple(q))
        assert curve_digest(authority) != expected
        return original_retime(authority, *args, **kwargs)

    def dynamics(*args, **kwargs):
        """Record the independent dynamics expectation before replay."""
        expectations.append(('dynamics', kwargs.get('expected_curve_digest')))
        return original_dynamics(*args, **kwargs)

    monkeypatch.setattr(compiler, 'validate_geometry', geometry)
    monkeypatch.setattr(compiler, 'retime', malicious_retime)
    monkeypatch.setattr(compiler, 'validate_dynamics', dynamics)
    result = compiler.compile_reference(
        ordered.route, _model(ordered.route), BODY, _policies(), output_dir=tmp_path)
    _assert_unpublished(result, tmp_path)
    assert expectations == [('geometry', expected), ('dynamics', expected)]
    assert result.geometry.status == 'PASS' and result.dynamics.status == 'FAIL'


def test_payload_builder_cannot_reduce_approved_body_margin(tmp_path, monkeypatch):
    """Reject a permissive body substitution before artifact publication."""
    ordered = _candidate()
    original_builder = compiler.build_payload
    calls = []
    monkeypatch.setattr(compiler, 'optimize', lambda *a, **k: _solver_result(ordered))

    def malicious_builder(*args, **kwargs):
        """Substitute a smaller body margin in an otherwise valid payload."""
        payload = original_builder(*args, **kwargs)
        # The unchanged curve remains feasible for this more permissive body.
        # Neither an internal hash nor replay under this substituted body can
        # authorize changing the caller's independently approved physical input.
        payload['footprint']['margin_m'] = 0.
        return payload

    def forbidden_publisher(*args, **kwargs):
        """Detect publication of a changed independently approved body."""
        calls.append(True)
        raise AssertionError('changed producer body reached publication')

    monkeypatch.setattr(compiler, 'build_payload', malicious_builder)
    monkeypatch.setattr(compiler, 'publish_reference', forbidden_publisher)
    result = compiler.compile_reference(
        ordered.route, _model(ordered.route), BODY, _policies(), output_dir=tmp_path)
    _assert_unpublished(result, tmp_path)
    assert calls == []


@pytest.fixture(scope='module')
def fresh_cli(tmp_path_factory):
    """Compile a fresh accepted reference through the public CLI."""
    directory = tmp_path_factory.mktemp('fresh-compile-cli')
    vehicle = _write(directory / 'vehicle.json', _vehicle())
    policy = _write(directory / 'policy.json', _policy())
    report_path = directory / 'compile.json'
    process, report = _cli(
        'compile', '--manifest', FIX / 's0_route.json', '--vehicle-config', vehicle,
        '--policy', policy, '--output', directory / 'references', '--report', report_path,
        cwd=directory)
    assert process.returncode == 0, report
    assert report['status'] == 'PASS'
    assert report['geometry']['status'] == report['dynamics']['status'] == 'PASS'
    assert report['geometry']['curve_digest'] == report['dynamics']['curve_digest']
    assert len(report['H']) == 64 and int(report['H'], 16) >= 0
    artifact = Path(report['artifact_path'])
    assert artifact.is_file() and artifact.name == 'reference.json'
    assert artifact.parent.name == report['H']
    assert artifact.parent.parent == directory / 'references'
    assert json.loads(report_path.read_text()) == report
    return directory, policy, artifact, report


def test_fresh_cli_compile_validate_query_are_separate_processes(fresh_cli):
    """Replay persisted authority and query metric progress in new processes."""
    directory, policy, artifact, receipt = fresh_cli
    process, checked = _cli(
        'validate', '--artifact', artifact, '--expected-h', receipt['H'], '--policy', policy,
        '--report', directory / 'validated.json', cwd=directory)
    assert process.returncode == 0 and checked['status'] == 'PASS'
    assert checked['H'] == receipt['H']
    process, queried = _cli(
        'query', '--artifact', artifact, '--expected-h', receipt['H'], '--policy', policy,
        '--s-m', .25, '--occurrence-id', 'o0', cwd=directory)
    assert process.returncode == 0 and queried['status'] == 'PASS'
    sample = queried['sample']
    assert sample['s'] == .25 and sample['occurrence_id'] == 'o0'
    assert sample['surface_id'] == 'ground' and sample['speed_mps'] > 0
    assert sample['time_s'] > 0 and len(sample['xy']) == 2
    assert all(math.isfinite(sample[k]) for k in
               ('heading', 'curvature', 'speed_mps', 'acceleration_mps2', 'time_s'))
    assert not (directory / '.ros').exists()


@pytest.mark.parametrize('command', ['validate', 'query', 'export'])
def test_cli_cannot_authorize_artifact_using_its_own_H(fresh_cli, command):
    """Require the caller's external expected identity for every load command."""
    directory, policy, artifact, receipt = fresh_cli
    wrong = ('0' if receipt['H'][0] != '0' else '1') + receipt['H'][1:]
    arguments = [command, '--artifact', artifact, '--expected-h', wrong, '--policy', policy]
    if command == 'query':
        arguments += ['--s-m', '0']
    elif command == 'export':
        arguments += ['--step-m', '.1', '--output', directory / 'forbidden-export',
                      '--report', directory / 'wrong-H-export.json']
    else:
        arguments += ['--report', directory / 'wrong-H-validate.json']
    process, report = _cli(*arguments, cwd=directory)
    assert process.returncode != 0 and report['status'] != 'PASS'
    assert not (directory / 'forbidden-export').exists()


def test_cli_rejects_a_changed_independently_selected_validation_policy(fresh_cli):
    """Reject a reference loaded under a different validation policy."""
    directory, _, artifact, receipt = fresh_cli
    changed = _policy()
    changed['geometry']['max_curvature'] = .9
    policy = _write(directory / 'changed-policy.json', changed)
    process, report = _cli(
        'validate', '--artifact', artifact, '--expected-h', receipt['H'], '--policy', policy,
        '--report', directory / 'changed-policy-report.json', cwd=directory)
    assert process.returncode != 0 and report['status'] != 'PASS'


def test_cli_rejects_wrong_supplied_occurrence_at_known_metric_progress(fresh_cli):
    """Honor the caller's supplied occurrence when querying metric progress."""
    directory, policy, artifact, receipt = fresh_cli
    process, report = _cli(
        'query', '--artifact', artifact, '--expected-h', receipt['H'], '--policy', policy,
        '--s-m', '.25', '--occurrence-id', 'o1', cwd=directory)
    assert process.returncode != 0 and report['status'] != 'PASS'


def test_cli_corrupted_persisted_bytes_cannot_expose_a_reference(fresh_cli):
    """Reject truncated persisted bytes despite the original trusted identity."""
    directory, policy, artifact, receipt = fresh_cli
    corrupted = directory / 'corrupt-reference.json'
    corrupted.write_bytes(artifact.read_bytes()[:-1])
    process, report = _cli(
        'validate', '--artifact', corrupted, '--expected-h', receipt['H'], '--policy', policy,
        '--report', directory / 'corrupt-report.json', cwd=directory)
    assert process.returncode != 0 and report['status'] != 'PASS'


def test_report_output_cannot_overwrite_the_immutable_artifact(fresh_cli):
    """Keep a receipt path from replacing accepted reference bytes."""
    directory, policy, artifact, receipt = fresh_cli
    original = artifact.read_bytes()
    process, report = _cli(
        'validate', '--artifact', artifact, '--expected-h', receipt['H'], '--policy', policy,
        '--report', artifact, cwd=directory)
    assert process.returncode != 0 and report['status'] != 'PASS'
    assert artifact.read_bytes() == original


def test_cli_malformed_model_has_machine_readable_failure_and_no_reference(tmp_path):
    """Return an explicit JSON failure for missing model provenance."""
    vehicle = _vehicle()
    vehicle['model']['provenance'] = ''
    process, report = _cli(
        'compile', '--manifest', FIX / 's0_route.json', '--vehicle-config',
        _write(tmp_path / 'bad-model.json', vehicle), '--policy',
        _write(tmp_path / 'policy.json', _policy()), '--output', tmp_path / 'routes',
        '--report', tmp_path / 'failure.json', cwd=tmp_path)
    assert process.returncode != 0 and report['status'] == 'FAIL'
    assert json.loads((tmp_path / 'failure.json').read_text()) == report
    assert not list((tmp_path / 'routes').glob('*/reference.json'))


@pytest.mark.parametrize('arguments', [
    ('compile',),
    ('query', '--artifact', 'absent.json', '--expected-h', '0' * 64,
     '--policy', 'absent-policy.json', '--s-m', 'not-a-number'),
])
def test_cli_argument_failures_have_the_same_machine_readable_contract(tmp_path, arguments):
    """Report missing arguments and invalid numeric literals as JSON failures."""
    process, report = _cli(*arguments, cwd=tmp_path)
    assert process.returncode != 0 and report['status'] == 'FAIL'


def test_pure_compile_module_does_not_import_ros_or_legacy_planner(tmp_path):
    """Keep pure compiler imports independent of ROS and legacy planner code."""
    code = (
        'import json,sys; import global_planner.route_compile; '
        'print(json.dumps([x for x in sys.modules if x == "rclpy" or '
        'x in ("global_planner.global_planner_node", "global_planner.global_planner_utils", '
        '"global_planner.readwrite_global_waypoints")]))')
    process = subprocess.run([sys.executable, '-c', code], cwd=tmp_path,
                             capture_output=True, text=True, timeout=30)
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout) == []
