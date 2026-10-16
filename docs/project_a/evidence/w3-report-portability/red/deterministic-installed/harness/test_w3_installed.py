"""Exercise the actual installed CLI, persisted bytes and generated ROS messages."""
import copy
from dataclasses import asdict, replace
import hashlib
import importlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import re
import socket
import struct
import subprocess

import pytest


_GITLINKS = {
    'base_system/f110_simulator/f1tenth_gym': 'f8f8c9d4781d44a2959bae013f276410cb4e9da0',
    'base_system/f110_simulator/f1tenth_gym_ros': '163020c0b631a5bdd9ddc59e6132337cec04cc27',
    'base_system/f1tenth_system': '5d6490fc6426deb1254198020133a85c0614f183',
    'base_system/f1tenth_system/ackermann_mux': 'ed4eac7284d13cae66628688e6fd32e585a96a62',
    'base_system/f1tenth_system/teleop_tools': '09938461991ec2260ddab6db8ac962f46d205669',
    'planner/global_planner/global_planner/global_racetrajectory_optimization':
        'b1b38ecfefec7200d5bcb243f115af1d795b3766',
    'sensors/vesc': '2fd19be756544693752d3e5b36c128e6157e4bd3',
}
_GROUPS = (
    'map_info_str', 'est_lap_time', 'centerline_markers', 'centerline_waypoints',
    'global_traj_markers_iqp', 'global_traj_wpnts_iqp', 'global_traj_markers_sp',
    'global_traj_wpnts_sp', 'trackbounds_markers',
)


def _hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(value):
    # Independent implementation of the published identity encoding.
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode()


def _inputs():
    from ament_index_python.packages import get_package_prefix, get_package_share_directory
    share = Path(get_package_share_directory('global_planner')) / 'project_a'
    assert str(share.resolve()).startswith('/work/install/')
    manifest = json.loads((share / 'build_identity.json').read_text())
    assert manifest['schema_version'] == 1
    assert re.fullmatch('[0-9a-f]{40}', manifest['source_commit'])
    assert manifest['gitlinks'] == _GITLINKS
    expected = os.environ.get('PROJECT_A_EXPECTED_COMMIT')
    if expected:
        assert manifest['source_commit'] == expected
    if os.environ.get('PROJECT_A_EXPECTED_CLEAN') == '1':
        assert manifest['source_dirty'] is False
    resources = ('fixtures/s0_route.json', 'models/synthetic_model.json',
                 'policies/synthetic_policy.json')
    for name in resources:
        path = share / name
        assert path.is_file() and not path.is_symlink()
        assert _hash(path) == manifest['installed_resource_hashes'][name]
    executable = Path(get_package_prefix('global_planner')) / 'lib/global_planner/compile_route'
    assert executable.is_file() and not executable.is_symlink()
    return share, manifest, executable


def _invoke(product, label, arguments, *, success=True, query=False):
    report = product['output'] / (label + '.json')
    command = [str(product['executable']), *map(str, arguments)]
    if not query:
        command.extend(('--report', str(report)))
    completed = subprocess.run(command, cwd=product['output'], capture_output=True,
                               text=True, timeout=240, check=False)
    stdout = product['output'] / (label + '.stdout.txt')
    stderr = product['output'] / (label + '.stderr.txt')
    stdout.write_text(completed.stdout)
    stderr.write_text(completed.stderr)
    value = json.loads(completed.stdout if query else report.read_text())
    product['commands'].append({'command': command, 'returncode': completed.returncode,
                                'status': value.get('status'), 'reason': value.get('reason'),
                                'report': None if query else str(report),
                                'stdout': str(stdout), 'stderr': str(stderr)})
    assert value['schema_version'] == 1
    if success:
        assert completed.returncode == 0, (value, completed.stderr)
        assert value['status'] == 'PASS', value
    else:
        assert completed.returncode != 0, value
        assert value['status'] != 'PASS', value
        assert not value.get('artifact_path'), value
    return value


@pytest.fixture(scope='module')
def product():
    """Capture the trusted compile receipt before adversarial mutations begin."""
    share, manifest, executable = _inputs()
    output = Path(os.environ.get('PROJECT_A_RUNTIME_OUTPUT', '/work')) / 'w3-installed'
    output.mkdir()
    state = {'share': share, 'manifest': manifest, 'executable': executable,
             'output': output, 'commands': []}
    receipt = _invoke(state, 'compile', (
        'compile', '--manifest', share / 'fixtures/s0_route.json',
        '--vehicle-config', share / 'models/synthetic_model.json',
        '--policy', share / 'policies/synthetic_policy.json',
        '--build-manifest', share / 'build_identity.json', '--output', output / 'references'))
    trusted_h = receipt['H']
    assert re.fullmatch('[0-9a-f]{64}', trusted_h)
    artifact = Path(receipt['artifact_path'])
    assert artifact.is_file() and artifact.name == 'reference.json'
    assert artifact.parent.name == trusted_h
    state.update(H=trusted_h, artifact=artifact, receipt=receipt)
    yield state
    evidence = {
        'scope': 'Installed synthetic offline software; independent W3 review remains required',
        'source_free': os.environ.get('PROJECT_A_SOURCE_FREE') == '1',
        'source_commit': manifest['source_commit'], 'source_dirty': manifest['source_dirty'],
        'gitlinks': manifest['gitlinks'], 'resources': manifest['installed_resource_hashes'],
        'trusted_identity_source': 'Controlled compile receipt retained before mutation tests',
        'H': trusted_h, 'artifact_path': str(artifact), 'artifact_sha256': _hash(artifact),
        'commands': state['commands'],
    }
    (output.parent / 'w3-installed.json').write_text(json.dumps(evidence, indent=2) + '\n')
    assert not Path('/work/.ros').exists()
    assert not (output.parent / '.ros').exists()


def test_installed_w3_origins_resources_and_isolation():
    """Verify non-symlink installed code, pinned inputs and actual runtime isolation."""
    _share, manifest, _executable = _inputs()
    identities = {}
    for name in ('route_input', 'route_reference', 'route_corridor', 'iqp_route_adapter',
                 'route_validate', 'route_validate_dynamics', 'cyclic_retime',
                 'route_artifact', 'route_compile', 'route_legacy_export'):
        module = importlib.import_module('global_planner.' + name)
        path = Path(module.__file__)
        assert not path.is_symlink()
        assert str(path.resolve()).startswith('/work/install/')
        source_key = 'planner/global_planner/global_planner/' + path.name
        assert _hash(path) == manifest['source_hashes'][source_key]
        identities[module.__name__] = {'path': str(path.resolve()), 'sha256': _hash(path)}
    entries = {entry.name: entry.value for entry in
               importlib.metadata.distribution('global_planner').entry_points}
    assert entries == {
        'global_planner': 'global_planner.global_planner_node:main',
        'mapping_node': 'global_planner.mapping_node:main',
        'global_trajectory_publisher': 'global_planner.global_trajectory_publisher:main',
        'compile_route': 'global_planner.route_compile:main',
    }
    for name in ('Wpnt.msg', 'WpntArray.msg'):
        from ament_index_python.packages import get_package_share_directory
        message = Path(get_package_share_directory('f110_msgs')) / 'msg' / name
        assert _hash(message) == manifest['source_hashes'][
            'utilities/libraries/f110_msgs/msg/' + name]
    if os.environ.get('PROJECT_A_SOURCE_FREE') == '1':
        forbidden_paths = ('/src', '/workspace', '/work/src', '/work/build', '/work/optimizer')
        for forbidden in forbidden_paths:
            assert not Path(forbidden).exists(), forbidden
        assert os.getuid() != 0
        security = dict(line.split(':', 1) for line in
                        Path('/proc/self/status').read_text().splitlines() if ':' in line)
        assert int(security['CapEff'].strip(), 16) == 0
        assert security['NoNewPrivs'].strip() == '1'
        assert socket.if_nameindex() == [(1, 'lo')]
        readonly_paths = ('/', '/work', '/work/install', '/work/python', '/runtime-harness')
        for path in readonly_paths:
            assert os.statvfs(path).f_flag & os.ST_RDONLY, path
        assert not any('/src' in item or '/build' in item for item in __import__('sys').path)
        assert not Path('/work/.ros').exists()
        Path('/results/runtime-identity.json').write_text(json.dumps({
            'source_commit': manifest['source_commit'], 'source_dirty': manifest['source_dirty'],
            'uid': os.getuid(), 'cap_eff': security['CapEff'].strip(),
            'no_new_privileges': security['NoNewPrivs'].strip(),
            'interfaces': socket.if_nameindex(), 'verified_readonly_paths': readonly_paths,
            'verified_absent_paths': forbidden_paths, 'modules': identities,
            'console_script': str(_executable),
            'installed_resource_hashes': manifest['installed_resource_hashes'],
        }, indent=2) + '\n')
        Path('/results/build-identity.json').write_bytes(
            (_share / 'build_identity.json').read_bytes())


def test_installed_w3_persist_revalidate_query_export_cdr(product):
    """Use separate processes and verify all nine existing ROS message groups."""
    common = ('--artifact', product['artifact'], '--expected-h', product['H'],
              '--policy', product['share'] / 'policies/synthetic_policy.json')
    validated = _invoke(product, 'validate', ('validate', *common))
    for kind in ('geometry', 'dynamics'):
        assert validated[kind]['status'] == 'PASS'
        assert validated[kind]['curve_digest'] == product['receipt'][kind]['curve_digest']
    samples = {}
    for label, station in (('seam', 0.), ('metric', .5), ('negative', -.125)):
        queried = _invoke(product, 'query-' + label,
                          ('query', *common, '--s-m', station), query=True)
        assert queried['H'] == product['H']
        sample = queried['sample']
        assert math.isfinite(sample['time_s']) and sample['speed_mps'] > 0
        heading = math.atan2(sample['tangent'][1], sample['tangent'][0])
        error = sample['heading'] - heading
        assert abs(math.atan2(math.sin(error), math.cos(error))) < 1e-12
        samples[label] = sample
    assert abs(samples['metric']['s'] - .5) < 1e-8
    exported = _invoke(product, 'export', (
        'export', *common, '--step-m', .5, '--output', product['output'] / 'legacy'))
    from global_planner.readwrite_global_waypoints import read_global_waypoints
    from rclpy.serialization import deserialize_message, serialize_message
    from rosidl_runtime_py.convert import message_to_ordereddict
    raw = json.loads(Path(exported['output_path']).read_text())
    assert tuple(raw) == _GROUPS
    loaded = read_global_waypoints(str(Path(exported['output_path']).parent))
    assert len(loaded) == 9
    for name, original in zip(_GROUPS, loaded):
        assert message_to_ordereddict(original) == raw[name]
        restored = deserialize_message(serialize_message(original), type(original))
        assert message_to_ordereddict(restored) == raw[name]
    points = loaded[5].wpnts
    assert len(points) == exported['waypoint_count']
    assert [p.id for p in points] == list(range(len(points)))
    assert points[0].s_m == 0. and points[-1].s_m == exported['length_m']
    assert all(0 < b.s_m - a.s_m <= .5 + 1e-8 for a, b in zip(points, points[1:]))
    assert all(p.d_m == 0 and p.d_left > 0 and p.d_right > 0 for p in points)
    for field in points[0].get_fields_and_field_types():
        if field not in ('id', 's_m'):
            assert getattr(points[0], field) == getattr(points[-1], field)
    for label, point in (('seam', points[0]),
                         ('metric', next(p for p in points if p.s_m == .5))):
        sample = samples[label]
        assert (point.x_m, point.y_m) == tuple(sample['xy'])
        assert point.psi_rad == sample['heading']
        assert point.kappa_radpm == sample['curvature']
        assert point.vx_mps == sample['speed_mps']
        assert point.ax_mps2 == sample['acceleration_mps2']
    assert abs(samples['negative']['s'] - (exported['length_m'] - .125)) < 1e-8
    rounded = struct.unpack('<f', struct.pack('<f', exported['lap_time_s']))[0]
    assert loaded[1].data == exported['legacy_lap_time_float32_s'] == rounded
    assert not loaded[3].wpnts and not loaded[7].wpnts
    assert not loaded[2].markers and not loaded[6].markers
    assert set(exported['unavailable_groups']) == set(_GROUPS[2:4] + _GROUPS[6:8])


def test_installed_w3_corruption_and_context_fail_closed(product):
    """Challenge independent H, curve approval and policy trust in new processes."""
    policy = product['share'] / 'policies/synthetic_policy.json'

    def reject(label, artifact, reason, expected=None, selected_policy=None):
        rejected = _invoke(product, label, (
            'validate', '--artifact', artifact, '--expected-h', expected or product['H'],
            '--policy', selected_policy or policy), success=False)
        assert reason in rejected['reason'], rejected
        assert 'Not a directory' not in rejected['reason'], rejected
        return rejected

    def mutation_file(label, data):
        directory = product['output'] / label
        directory.mkdir()
        path = directory / 'reference.json'
        path.write_bytes(data)
        assert list(directory.iterdir()) == [path]
        return path

    def changed_policy(payload):
        payload['policies']['numeric']['arc_abs'] = 2e-10
        for kind in ('geometry', 'dynamics'):
            payload['policies'][kind]['numeric_policy']['arc_abs'] = 2e-10

    def changed_approval(payload):
        payload['approved_curve_digest'] = '0' * 64
        payload['speed_profile']['curve_digest'] = '0' * 64
        for kind in ('geometry', 'dynamics'):
            payload['validation'][kind]['curve_digest'] = '0' * 64

    wrong = ('1' if product['H'][0] == '0' else '0') + product['H'][1:]
    reject('wrong-expected-h', product['artifact'], 'H mismatch', wrong)
    envelope = json.loads(product['artifact'].read_text())
    mutations = {
        'approval': changed_approval,
        'model': lambda p: p['model']['regions'][0]['limits'].update(speed_max_mps=3.25),
        'policy': changed_policy,
        'coefficient': lambda p: p['curve']['coefficients'][0][0].__setitem__(0, 1.25),
        'implementation': lambda p: p['implementation'].update(contract_id='unsupported.v99'),
    }
    for label, mutate in mutations.items():
        changed = copy.deepcopy(envelope)
        mutate(changed['payload'])
        changed['H'] = hashlib.sha256(_canonical(changed['payload'])).hexdigest()
        assert changed['H'] != product['H']
        path = mutation_file('mutated-' + label, _canonical(changed))
        reject('reject-' + label + '-old-h', path, 'H mismatch')
        new_h_reason = {
            'approval': 'geometry replay FAIL',
            'model': 'dynamics replay FAIL',
            'policy': 'independent acceptance policy',
            'implementation': 'changed kernel/checker/dependency identity',
        }
        if label in new_h_reason:
            reject('reject-' + label + '-new-h', path, new_h_reason[label], changed['H'])
    partial = product['output'] / '.tmp-interrupted'
    partial.mkdir()
    partial_file = partial / 'reference.json'
    partial_file.write_bytes(product['artifact'].read_bytes()[:200])
    reject('incomplete-stage', partial_file, 'private staging')
    truncated = mutation_file('truncated', product['artifact'].read_bytes()[:200])
    reject('truncated-content', truncated, 'invalid bounded UTF-8 JSON')
    corrupt = mutation_file('corrupt', product['artifact'].read_bytes() + b'\x00')
    reject('corrupt-bytes', corrupt, 'invalid bounded UTF-8 JSON')
    unsupported = json.loads(policy.read_text())
    unsupported['required_geometry_coverage'] = ['three_dimensional_clearance']
    unsupported_file = product['output'] / 'unsupported-policy.json'
    unsupported_file.write_bytes(_canonical(unsupported))
    reject('unsupported-coverage', product['artifact'],
           'unsupported independently required coverage', selected_policy=unsupported_file)
    wrong_owner = _invoke(product, 'wrong-supplied-occurrence', (
        'query', '--artifact', product['artifact'], '--expected-h', product['H'],
        '--policy', policy, '--s-m', .5, '--occurrence-id', 'unapproved-occurrence'),
        success=False, query=True)
    assert 'supplied occurrence' in wrong_owner['reason'], wrong_owner
    # All mutations used independent copies; the accepted original stays intact.
    assert _hash(product['artifact']) == hashlib.sha256(_canonical(envelope)).hexdigest()


def test_installed_w3_replays_numeric_proofs_without_rewriting_authority(product, monkeypatch):
    """Replay both real checks despite conservative report drift and reject false contracts."""
    from global_planner import route_artifact as artifact
    from global_planner.route_compile import load_policy

    assert str(Path(artifact.__file__).resolve()).startswith('/work/install/')
    original_bytes = product['artifact'].read_bytes()
    envelope = json.loads(original_bytes)
    payload = envelope['payload']
    approved = product['receipt']['geometry']['curve_digest']
    assert approved == payload['approved_curve_digest']
    _, context, _ = load_policy(product['share'] / 'policies/synthetic_policy.json')
    context = replace(context, required_geometry_coverage=('legal_planar_geometry',),
                      required_dynamics_coverage=('declared_planar_diamond',))
    real_geometry, real_dynamics = artifact.validate_geometry, artifact.validate_dynamics
    calls = {'geometry': 0, 'dynamics': 0}
    fresh, changes = {}, {}

    def geometry(*arguments, **keywords):
        assert keywords['expected_curve_digest'] == approved
        report = real_geometry(*arguments, **keywords)
        assert report.status == 'PASS' and report.curve_digest == approved
        calls['geometry'] += 1
        previous = payload['validation']['geometry']['intervals'][0]['curvature_upper']
        upper = math.nextafter(max(report.intervals[0].curvature_upper, previous), math.inf)
        assert upper < context.geometry_policy.max_curvature
        changed = replace(report.intervals[0], curvature_upper=upper)
        changes['geometry'] = {'historical': previous,
                               'independent_replay': report.intervals[0].curvature_upper,
                               'conservative_replay': upper}
        fresh['geometry'] = replace(report, intervals=(changed, *report.intervals[1:]))
        return fresh['geometry']

    def dynamics(*arguments, **keywords):
        assert keywords['expected_curve_digest'] == approved
        report = real_dynamics(*arguments, **keywords)
        assert report.status == 'PASS' and report.curve_digest == approved
        calls['dynamics'] += 1
        previous = payload['validation']['dynamics']['lap_time_upper_s']
        upper = math.nextafter(max(report.lap_time_upper_s, previous), math.inf)
        error = max(report.lap_time_error_s, upper - report.lap_time_s)
        changes['dynamics'] = {'historical': previous,
                               'independent_replay': report.lap_time_upper_s,
                               'conservative_replay': upper}
        fresh['dynamics'] = replace(report, lap_time_upper_s=upper, lap_time_error_s=error)
        return fresh['dynamics']

    # The producer was the compile CLI subprocess; this installed pytest process is a consumer.
    monkeypatch.setattr(artifact, 'validate_geometry', geometry)
    monkeypatch.setattr(artifact, 'validate_dynamics', dynamics)
    reference = artifact.load_reference(product['artifact'], expected_H=product['H'],
                                        validation_context=context)
    assert calls == {'geometry': 1, 'dynamics': 1}
    assert reference.H == product['H'] and artifact.curve_digest(reference.ordered) == approved
    for key, actual in (('coefficients', reference.ordered.curve.coefficients),
                        ('owners', reference.ordered.curve.owners), ('q', reference.ordered.q)):
        assert _canonical(actual) == _canonical(payload['curve'][key])
    for key, actual in (('speed_profile', reference.profile), ('model', reference.model),
                        ('footprint', reference.footprint), ('policies', reference.policies)):
        assert _canonical(asdict(actual)) == _canonical(payload[key])
    assert _canonical(reference.payload) == _canonical(payload)
    for kind, report in (('geometry', reference.geometry_report),
                         ('dynamics', reference.dynamics_report)):
        assert report == fresh[kind]
        assert _canonical(asdict(report)) != _canonical(payload['validation'][kind])
    assert reference.sample(.5).H == product['H']
    positive_calls = dict(calls)
    positive_changes = copy.deepcopy(changes)

    # A new test H cannot make fabricated stored categorical metadata an accepted certificate.
    forged = copy.deepcopy(envelope)
    forged['payload']['validation']['geometry']['reason'] = 'fabricated historical rationale'
    forged['H'] = hashlib.sha256(_canonical(forged['payload'])).hexdigest()
    directory = product['output'] / 'stored-proof-contract'
    directory.mkdir()
    forged_path = directory / 'reference.json'
    forged_path.write_bytes(_canonical(forged))
    with pytest.raises(artifact.ArtifactError, match='stored historical') as stored_error:
        artifact.load_reference(forged_path, expected_H=forged['H'], validation_context=context)
    assert str(stored_error.value).startswith('geometry stored historical')

    # A real PASS with missing independently required coverage still cannot authorize a handle.
    def missing_coverage(*arguments, **keywords):
        report = dynamics(*arguments, **keywords)
        return replace(report, coverage=tuple(value for value in report.coverage
                                              if value != 'declared_planar_diamond'))

    monkeypatch.setattr(artifact, 'validate_dynamics', missing_coverage)
    with pytest.raises(artifact.ArtifactError,
                       match='independently required coverage') as coverage_error:
        artifact.load_reference(product['artifact'], expected_H=product['H'],
                                validation_context=context)
    assert coverage_error.value.status == 'UNSUPPORTED'
    assert product['artifact'].read_bytes() == original_bytes
    (product['output'] / 'numeric-replay-variation.json').write_text(json.dumps({
        'status': 'PASS', 'H': product['H'], 'curve_digest': approved,
        'unchanged_artifact_sha256': hashlib.sha256(original_bytes).hexdigest(),
        'positive_real_validator_calls': positive_calls, 'numeric_changes': positive_changes,
        'stored_contract_rejection': str(stored_error.value),
        'missing_fresh_required_coverage': str(coverage_error.value),
        'scope': 'Deterministic conservative report-variation injection after both real checks',
    }, indent=2) + '\n')
