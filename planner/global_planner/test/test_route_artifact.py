"""A07 exact binary64 authority, independent replay, metric and atomicity attacks."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, asdict, replace
from fractions import Fraction
import copy
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import subprocess
import sys

import pytest

import global_planner.route_artifact as artifact
import global_planner.route_validate as geometry_checker
from global_planner.cyclic_retime import (
    DynamicsModel, ModelRegion, RegionLimits, RetimePolicy, curve_digest,
    model_digest, retime)
from global_planner.iqp_route_adapter import SolverPolicy
from global_planner.route_artifact import (
    ArtifactError, Reference, ValidationContext, artifact_identity, build_payload,
    canonical_bytes, decode_record, load_reference, publish_reference, read_json)
from global_planner.route_corridor import OrderedCurve
from global_planner.route_input import load_route
from global_planner.route_reference import Curve, GeometryError, NumericPolicy
from global_planner.route_validate import Footprint, GeometryValidationPolicy, validate_geometry
from global_planner.route_validate_dynamics import DynamicsValidationPolicy, validate_dynamics

FIX = Path(__file__).parent / 'fixtures' / 'project_a'


def inputs(name='s0_route'):
    """Build independently certified archived synthetic test authority."""
    frozen = (FIX / 'w2_a04_candidates.json.gz').read_bytes()
    assert hashlib.sha256(frozen).hexdigest() == (
        '2a506953026b75fc5be4defb1b018577faa46cebdbdfcd767c0103e733b2279b')
    value = json.loads(gzip.decompress(frozen))['candidates'][name]
    route = load_route(FIX / (name + '.json'))
    ordered = OrderedCurve(route, Curve(value['coefficients'], value['owners']), value['q'])
    approved = curve_digest(ordered)  # Trusted test-fixture handoff before retiming/encoding.
    limits = RegionLimits(.05, 3., 2., 3., 4., 2.5, -0.0,
                          'Explicit synthetic test limits; signed-zero regression')
    model = DynamicsModel(tuple(ModelRegion(o.id, o.surface_id, limits)
                                for o in route.occurrences), 'Synthetic planar artifact test')
    footprint = Footprint(.1, .1, .12, .01)
    geometry_policy = GeometryValidationPolicy()
    dynamics_policy = DynamicsValidationPolicy()
    geometry = validate_geometry(ordered, route, footprint, geometry_policy,
                                 expected_curve_digest=approved)
    assert geometry.status == 'PASS', geometry
    timed = retime(ordered, model)
    assert timed.status == 'CANDIDATE', timed
    dynamics = validate_dynamics(ordered, timed.profile, model, dynamics_policy,
                                 metadata=timed.metadata, expected_curve_digest=approved)
    assert dynamics.status == 'PASS', dynamics
    payload = build_payload(
        ordered, timed.profile, model, footprint, solver_policy=SolverPolicy(),
        retime_policy=RetimePolicy(), geometry_policy=geometry_policy,
        dynamics_policy=dynamics_policy, approved_curve_digest=approved,
        geometry_report=geometry, dynamics_report=dynamics,
        provenance={'scope': 'Approved archived W2 synthetic coefficients; A07 replay tests'})
    return payload, ValidationContext(), ordered, model, timed


@pytest.fixture(scope='module')
def authority():
    """Return the shared independent authority and acceptance context."""
    return inputs()


@pytest.fixture(scope='module')
def published(authority, tmp_path_factory):
    """Publish an immutable reference under separately retained approvals."""
    payload, context, _, _, _ = authority
    return publish_reference(payload, tmp_path_factory.mktemp('accepted-reference'),
                             expected_H=artifact_identity(payload),
                             expected_curve_digest=curve_digest(authority[2]),
                             validation_context=context)


def write_reference(directory, payload, H=None):
    """Write an explicitly selected envelope for adversarial loading."""
    H = artifact_identity(payload) if H is None else H
    directory.mkdir()
    path = directory / 'reference.json'
    path.write_bytes(canonical_bytes({'schema_version': 1, 'H': H, 'payload': payload}))
    return path, H


def test_exact_roundtrip_preserves_w2_signed_zero_and_authority(authority, published, monkeypatch):
    """Verify exact roundtrip preserves w2 signed zero and authority."""
    payload, context, ordered, model, timed = authority
    calls = []
    geometry, dynamics = artifact.validate_geometry, artifact.validate_dynamics

    def replay_geometry(*args, **kwargs):
        """Record the independent geometry expectation before replay."""
        calls.append(('geometry', kwargs['expected_curve_digest']))
        return geometry(*args, **kwargs)

    def replay_dynamics(*args, **kwargs):
        """Record the independent dynamics expectation before replay."""
        calls.append(('dynamics', kwargs['expected_curve_digest']))
        return dynamics(*args, **kwargs)

    monkeypatch.setattr(artifact, 'validate_geometry', replay_geometry)
    monkeypatch.setattr(artifact, 'validate_dynamics', replay_dynamics)
    loaded = load_reference(published.path, expected_H=published.H, validation_context=context)
    assert calls == [('geometry', payload['approved_curve_digest']),
                     ('dynamics', payload['approved_curve_digest'])]
    assert canonical_bytes(loaded.ordered.curve.coefficients) == canonical_bytes(
        ordered.curve.coefficients)
    assert canonical_bytes(loaded.ordered.q) == canonical_bytes(ordered.q)
    assert canonical_bytes(asdict(loaded.profile)) == canonical_bytes(asdict(timed.profile))
    assert curve_digest(loaded.ordered) == payload['approved_curve_digest']
    assert model_digest(loaded.model) == model_digest(model)
    assert math.copysign(1., loaded.model.regions[0].limits.drag_over_mass) == -1.
    assert b'-0.0' in loaded.path.read_bytes()
    assert loaded.H == artifact_identity(payload)
    assert loaded.geometry_report.curve_digest == loaded.dynamics_report.curve_digest
    assert loaded.lap_time_s == loaded.dynamics_report.lap_time_s


def test_codec_preserves_numeric_spelling_bool_and_null():
    """Verify codec preserves numeric spelling bool and null."""
    encoded = canonical_bytes({'z': -0.0, 'i': 1, 'f': 1.0, 'b': False, 'n': None})
    assert encoded == b'{"b":false,"f":1.0,"i":1,"n":null,"z":-0.0}'
    assert canonical_bytes(-0.0) != canonical_bytes(0.0)
    assert canonical_bytes(1) != canonical_bytes(1.0)
    with pytest.raises(ArtifactError):
        decode_record(Footprint, {'front_m': True, 'rear_m': .1, 'width_m': .1, 'margin_m': 0.})
    numeric = asdict(NumericPolicy())
    numeric['max_samples'] = 1.0
    with pytest.raises(ArtifactError):
        decode_record(NumericPolicy, numeric)
    # Constructor normalization is explicitly rejected instead of changing model_digest.
    limits = asdict(RegionLimits(.05, 3., 2., 3., 4., 2.5, 0., 'synthetic'))
    limits['speed_max_mps'] = 3
    with pytest.raises(ArtifactError, match='changes exact numeric authority'):
        decode_record(RegionLimits, limits)


@pytest.mark.parametrize('raw', [
    b'{"a":1,"a":2}', b'{"a":{"x":1,"x":2}}', b'{"x":NaN}',
    b'{"x":Infinity}', b'{"x":1e999}', b'{"x":', b'[]', b'\xff',
    b'{"x":' + b'[' * 40 + b']' * 40 + b'}', b'{"x":"\\ud800"}',
    b'{"x":' + b'1' * 311 + b'}',
])
def test_strict_json_rejects_malformed_duplicate_overflow_and_depth(raw, tmp_path):
    """Verify strict json rejects malformed duplicate overflow and depth."""
    path = tmp_path / 'input.json'
    path.write_bytes(raw)
    with pytest.raises(ArtifactError):
        read_json(path)


def test_predecode_nodes_text_and_encoded_byte_limits(tmp_path, monkeypatch):
    """Verify predecode nodes text and encoded byte limits."""
    path = tmp_path / 'input.json'
    path.write_text('{"x":[' + ','.join('[]' for _ in range(100)) + ']}')
    monkeypatch.setattr(artifact, 'MAX_JSON_NODES', 50)
    with pytest.raises(ArtifactError, match='before decoding'):
        read_json(path)
    monkeypatch.setattr(artifact, 'MAX_JSON_NODES', 2000000)
    path.write_text(json.dumps({'x': 'a' * (artifact.MAX_JSON_STRING_BYTES + 1)}))
    with pytest.raises(ArtifactError, match='text budget'):
        read_json(path)
    with path.open('wb') as stream:
        stream.truncate(artifact.MAX_ARTIFACT_BYTES + 1)
    with pytest.raises(ArtifactError, match='bounded regular'):
        read_json(path)


def mutate(payload, kind):
    """Return one selected authority mutation without changing the original."""
    changed = copy.deepcopy(payload)
    if kind == 'coefficients':
        changed['curve']['coefficients'][0][0][0] += .01
    elif kind == 'q':
        changed['curve']['q'][1] += .0001
    elif kind == 'approval':
        changed['approved_curve_digest'] = '0' * 64
    elif kind == 'model':
        changed['model']['provenance'] += ' changed'
    elif kind == 'profile':
        changed['speed_profile']['knots'][0]['u'] *= 1.1
    elif kind == 'footprint':
        changed['footprint']['front_m'] += .01
    elif kind == 'policy':
        changed['policies']['geometry']['max_curvature'] *= 2
    elif kind == 'implementation':
        changed['implementation']['module_sha256']['route_validate'] = '0' * 64
    elif kind == 'proof':
        changed['validation']['geometry']['intervals'][0]['clearance_lower_m'] = -1.
    elif kind == 'unknown':
        changed['new_authority'] = True
    elif kind == 'owner':
        changed['curve']['owners'][0][1] = 'unrelated_surface'
    return changed


@pytest.mark.parametrize('kind', [
    'coefficients', 'q', 'approval', 'model', 'profile', 'footprint', 'policy',
    'implementation', 'proof', 'unknown', 'owner',
])
def test_old_external_H_rejects_every_authority_mutation(kind, authority, tmp_path):
    """Verify old external H rejects every authority mutation."""
    payload, context, _, _, _ = authority
    original = artifact_identity(payload)
    path, _ = write_reference(tmp_path / 'mutated', mutate(payload, kind))
    with pytest.raises(ArtifactError, match='H mismatch'):
        load_reference(path, expected_H=original, validation_context=context)


@pytest.mark.parametrize('kind', [
    'coefficients', 'q', 'approval', 'model', 'profile', 'footprint', 'policy',
    'implementation', 'proof', 'unknown', 'owner',
])
def test_self_rehash_and_stored_PASS_cannot_bypass_independent_replay(kind, authority, tmp_path):
    """Verify self rehash and stored PASS cannot bypass independent replay."""
    payload, context, _, _, _ = authority
    changed = mutate(payload, kind)
    if kind == 'footprint':
        # A new external H can authorize a different body that really fits.
        # This case must instead demonstrate an actual geometric violation.
        changed['footprint']['front_m'] = payload['footprint']['front_m'] + 10.
    path, H = write_reference(tmp_path / 'mutated', changed)
    with pytest.raises(ArtifactError) as result:
        load_reference(path, expected_H=H, validation_context=context)
    if kind == 'footprint':
        assert result.value.status == 'FAIL'
        assert result.value.reason.startswith('geometry replay FAIL:')


def test_wrong_missing_expected_H_and_unsupported_context(authority, published):
    """Verify wrong missing expected H and unsupported context."""
    _, context, _, _, _ = authority
    for expected in (None, '', 'A' * 64, '0' * 64):
        with pytest.raises(ArtifactError):
            load_reference(published.path, expected_H=expected, validation_context=context)
    with pytest.raises(TypeError):
        load_reference(published.path, validation_context=context)
    for unsupported in (replace(context, contract_id='unrecognized'),
                        replace(context, required_geometry_coverage=('3d_clearance',)),
                        replace(context, geometry_policy=replace(context.geometry_policy,
                                                                 max_curvature=2.))):
        with pytest.raises(ArtifactError):
            load_reference(published.path, expected_H=published.H, validation_context=unsupported)


def test_immutable_records_and_detached_payload(published):
    """Verify immutable records and detached payload."""
    with pytest.raises(FrozenInstanceError):
        published.H = '0' * 64
    with pytest.raises(FrozenInstanceError):
        published.model.provenance = 'changed'
    with pytest.raises(TypeError):
        published.ordered.curve.coefficients[0][0][0] = 1.
    with pytest.raises(ArtifactError):
        Reference()
    copy_payload = published.payload
    copy_payload['curve']['q'][1] += .1
    assert artifact_identity(published.payload) == published.H


def edge_distance(curve, knots, index):
    """Integrate one actual metric speed-profile edge."""
    knot, following = knots[index], knots[(index + 1) % len(knots)]
    end = following.t if following.segment == knot.segment and index + 1 < len(knots) else 1.
    segment = curve.segments[knot.segment]
    return segment.arc(end) - segment.arc(knot.t)


def test_true_metric_affine_u_all_right_hand_edges_and_closing_acceleration(published):
    """Verify true metric affine u all right hand edges and closing acceleration."""
    curve, knots = published.ordered.curve, published.profile.knots
    times = []
    for index, knot in enumerate(knots):
        following = knots[(index + 1) % len(knots)]
        station = curve.station(knot.segment, knot.t)
        distance = edge_distance(curve, knots, index)
        row = published.sample(station)
        assert row.speed_mps == math.sqrt(knot.u)
        assert row.acceleration_mps2 == pytest.approx((following.u - knot.u) / (2 * distance),
                                                      abs=1e-12)
        assert row.time_s == pytest.approx(math.fsum(times), abs=1e-12)
        for fraction in (.2, .7):
            interior = published.sample(station + fraction * distance)
            expected_u = knot.u + fraction * (following.u - knot.u)
            assert interior.speed_mps ** 2 == pytest.approx(expected_u, abs=2e-7)
            expected_time = math.fsum(times) + 2 * fraction * distance / (
                math.sqrt(knot.u) + math.sqrt(expected_u))
            assert interior.time_s == pytest.approx(expected_time, abs=2e-8)
            assert interior.acceleration_mps2 == row.acceleration_mps2
        times.append(2 * distance / (math.sqrt(knot.u) + math.sqrt(following.u)))
    assert math.fsum(times) == published.lap_time_s
    assert published.sample(published.length).time_s == 0.
    assert published.sample(published.length).acceleration_mps2 == (
        published.sample(0.).acceleration_mps2)


def test_metric_seam_negative_multiple_laps_owner_and_portal_queries(published):
    """Verify metric seam negative multiple laps owner and portal queries."""
    length = published.length
    for station in (-.3, -.0001, 0., .2, length - .1, length, 2 * length + .2):
        row = published.sample(station)
        baseline = published.sample(station % length)
        assert row.xy == pytest.approx(baseline.xy, abs=1e-8)
        assert row.speed_mps == pytest.approx(baseline.speed_mps, abs=1e-7)
        assert published.locate(station) == published.ordered.curve.locate(station)
    ends = [0.]
    for occurrence in published.ordered.route.occurrences:
        station = published.ordered.station_at_q(ends[-1])
        assert published.sample(station, occurrence.id).occurrence_id == occurrence.id
        with pytest.raises(GeometryError):
            published.sample(station, 'wrong_occurrence')
        ends.append(ends[-1] + occurrence.length)
    for i, portal in enumerate(published.ordered.route.portals):
        for q in ((ends[i + 1] - portal.before) % ends[-1],
                  ends[i + 1] % ends[-1], (ends[i + 1] + portal.after) % ends[-1]):
            assert portal.id in published.sample(
                published.ordered.station_at_q(q)).portal_support
    assert len(published.window(-.2, .3, .2)) == 4
    for bad in (True, math.inf, math.nan, '1'):
        with pytest.raises(GeometryError):
            published.sample(bad)
    with pytest.raises(GeometryError):
        published.window(0., length * 2, 1e-10)


@pytest.mark.parametrize('name,sign', [('s0_reverse_route', -1), ('s0_rotated_route', 1)])
def test_reversed_and_rotated_authority_remains_exact(name, sign, tmp_path):
    """Verify reversed and rotated authority remains exact."""
    payload, context, ordered, _, _ = inputs(name)
    reference = publish_reference(payload, tmp_path / name,
                                  expected_H=artifact_identity(payload),
                                  expected_curve_digest=curve_digest(ordered),
                                  validation_context=context)
    assert canonical_bytes(reference.ordered.curve.coefficients) == canonical_bytes(
        ordered.curve.coefficients)
    assert math.copysign(1., reference.sample(.3).curvature) == sign
    assert reference.sample(reference.length).xy == reference.sample(0.).xy


def test_existing_target_and_unknown_extra_files_are_never_replaced(
        authority, published, tmp_path):
    """Verify existing target and unknown extra files are never replaced."""
    payload, context, _, _, _ = authority
    original = published.path.read_bytes()
    with pytest.raises(ArtifactError, match='already exists'):
        publish_reference(payload, published.path.parent.parent,
                          expected_H=artifact_identity(payload),
                          expected_curve_digest=curve_digest(authority[2]),
                          validation_context=context)
    assert published.path.read_bytes() == original
    directory = tmp_path / 'extra'
    path, H = write_reference(directory, payload)
    (directory / 'unexpected').write_text('incomplete attachment')
    with pytest.raises(ArtifactError, match='unknown or incomplete'):
        load_reference(path, expected_H=H, validation_context=context)


@pytest.mark.parametrize('kind', ['parent', 'target', 'lock', 'reference'])
def test_symlinks_fail_closed_without_modifying_targets(kind, authority, published, tmp_path):
    """Verify symlinks fail closed without modifying targets."""
    payload, context, _, _, _ = authority
    H = artifact_identity(payload)
    victim = tmp_path / 'victim'
    victim.mkdir()
    (victim / 'sentinel').write_text('unchanged')
    output = tmp_path / 'output'
    if kind == 'parent':
        output.symlink_to(victim, target_is_directory=True)
    else:
        output.mkdir()
        if kind == 'target':
            (output / H).symlink_to(victim, target_is_directory=True)
        elif kind == 'lock':
            (output / ('.lock-' + H)).symlink_to(victim / 'sentinel')
        else:
            folder = output / H
            folder.mkdir()
            (folder / 'reference.json').symlink_to(published.path)
            with pytest.raises(ArtifactError):
                load_reference(folder, expected_H=H, validation_context=context)
            return
    with pytest.raises(ArtifactError):
        publish_reference(payload, output, expected_H=artifact_identity(payload),
                          expected_curve_digest=curve_digest(authority[2]),
                          validation_context=context)
    assert (victim / 'sentinel').read_text() == 'unchanged'
    assert sorted(p.name for p in victim.iterdir()) == ['sentinel']


@pytest.mark.parametrize('failure', [
    'write', 'corrupt', 'file_fsync', 'stage_fsync', 'parent_fsync'])
def test_publication_failure_is_absent_or_fully_valid(
        failure, authority, tmp_path, monkeypatch):
    """Verify publication failure is absent or fully valid."""
    payload, context, _, _, _ = authority
    H = artifact_identity(payload)
    output = tmp_path / 'output'
    original_write, original_fsync = artifact._write_all, os.fsync
    if failure == 'write':
        def partial(descriptor, data):
            """Inject an interrupted partial staged-file write."""
            os.write(descriptor, data[:100])
            raise OSError('injected interrupted write')
        monkeypatch.setattr(artifact, '_write_all', partial)
    elif failure == 'corrupt':
        monkeypatch.setattr(artifact, '_write_all',
                            lambda fd, data: original_write(fd, data[:-50]))
    else:
        counts = [0]
        target = {'file_fsync': 1, 'stage_fsync': 2, 'parent_fsync': 3}[failure]

        def fail_fsync(descriptor):
            """Inject failure at the selected durable-publication boundary."""
            counts[0] += 1
            if counts[0] == target:
                raise OSError('injected fsync failure')
            return original_fsync(descriptor)
        monkeypatch.setattr(artifact.os, 'fsync', fail_fsync)
    with pytest.raises(ArtifactError):
        publish_reference(payload, output, expected_H=artifact_identity(payload),
                          expected_curve_digest=curve_digest(authority[2]),
                          validation_context=context)
    monkeypatch.undo()
    if failure == 'parent_fsync':
        loaded = load_reference(output / H, expected_H=H, validation_context=context)
        assert loaded.H == H
    else:
        assert not (output / H).exists()
    assert not list(output.glob('.tmp-*'))


def test_failed_continuous_validation_publishes_nothing(authority, tmp_path):
    """Verify failed continuous validation publishes nothing."""
    payload, context, _, _, _ = authority
    invalid = mutate(payload, 'approval')
    with pytest.raises(ArtifactError, match='retained A04 approval'):
        publish_reference(invalid, tmp_path / 'output',
                          expected_H=artifact_identity(invalid),
                          expected_curve_digest=curve_digest(authority[2]),
                          validation_context=context)
    assert not (tmp_path / 'output' / artifact_identity(invalid)).exists()
    assert not list((tmp_path / 'output').glob('.tmp-*'))


def test_concurrent_writers_have_one_winner_and_no_replacement(authority, tmp_path):
    """Verify concurrent writers have one winner and no replacement."""
    payload, context, _, _, _ = authority
    output = tmp_path / 'output'

    def writer(_):
        """Attempt one concurrent publication and retain its outcome."""
        try:
            return publish_reference(
                payload, output, expected_H=artifact_identity(payload),
                expected_curve_digest=curve_digest(authority[2]),
                validation_context=context)
        except ArtifactError as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(writer, range(2)))
    assert sum(type(value) is Reference for value in results) == 1
    assert sum(isinstance(value, ArtifactError) for value in results) == 1
    winner = next(value for value in results if type(value) is Reference)
    assert load_reference(winner.path, expected_H=winner.H,
                          validation_context=context).H == winner.H
    assert not list(output.glob('.tmp-*'))


def test_uncooperative_target_race_does_not_replace_existing_directory(
        authority, tmp_path, monkeypatch):
    """Verify uncooperative target race does not replace existing directory."""
    payload, context, _, _, _ = authority
    output = tmp_path / 'output'
    original = artifact._rename_noreplace

    def race(source, target, parent):
        """Create a competing target immediately before atomic rename."""
        os.mkdir(target, dir_fd=parent)
        return original(source, target, parent)

    monkeypatch.setattr(artifact, '_rename_noreplace', race)
    with pytest.raises(ArtifactError):
        publish_reference(payload, output, expected_H=artifact_identity(payload),
                          expected_curve_digest=curve_digest(authority[2]),
                          validation_context=context)
    assert list((output / artifact_identity(payload)).iterdir()) == []
    assert not list(output.glob('.tmp-*'))


def test_abrupt_process_exit_leaves_only_unloadable_private_stage(authority, tmp_path):
    """Verify abrupt process exit leaves only unloadable private stage."""
    payload, context, _, _, _ = authority
    source = tmp_path / 'payload.json'
    source.write_bytes(canonical_bytes(payload))
    output = tmp_path / 'output'
    script = '''
import os, sys
import global_planner.route_artifact as a
def stop(fd,data):
    os.write(fd,data[:100])
    os._exit(42)
a._write_all=stop
a.publish_reference(a.read_json(sys.argv[1]),sys.argv[2],
                    expected_curve_digest=sys.argv[3],expected_H=sys.argv[4])
'''
    result = subprocess.run([sys.executable, '-c', script, str(source), str(output),
                             curve_digest(authority[2]), artifact_identity(payload)],
                            check=False)
    assert result.returncode == 42
    H = artifact_identity(payload)
    assert not (output / H).exists()
    stages = list(output.glob('.tmp-*'))
    assert len(stages) == 1
    with pytest.raises(ArtifactError, match='staging'):
        load_reference(stages[0], expected_H=H, validation_context=context)


def test_coordinated_payload_q_profile_and_reports_cannot_replace_original_producer_approval(
        authority, tmp_path):
    """Reject coordinated q/profile/proof replacement under the original producer approval."""
    payload, context, ordered, model, _ = authority
    retained = curve_digest(ordered)
    q = list(ordered.q)
    q[1] += .0001
    forged = OrderedCurve(ordered.route, ordered.curve, q)
    forged_approval = curve_digest(forged)
    assert forged_approval != retained
    footprint = decode_record(Footprint, payload['footprint'])
    geometry = validate_geometry(forged, forged.route, footprint, context.geometry_policy,
                                 expected_curve_digest=forged_approval)
    assert geometry.status == 'PASS', geometry
    timed = retime(forged, model)
    assert timed.status == 'CANDIDATE', timed
    dynamics = validate_dynamics(forged, timed.profile, model, context.dynamics_policy,
                                 expected_curve_digest=forged_approval)
    assert dynamics.status == 'PASS', dynamics
    coordinated = build_payload(
        forged, timed.profile, model, footprint, solver_policy=SolverPolicy(),
        retime_policy=RetimePolicy(), geometry_policy=context.geometry_policy,
        dynamics_policy=context.dynamics_policy, approved_curve_digest=forged_approval,
        geometry_report=geometry, dynamics_report=dynamics)
    with pytest.raises(ArtifactError, match='independently retained A04 approval'):
        publish_reference(coordinated, tmp_path / 'output',
                          expected_H=artifact_identity(coordinated),
                          expected_curve_digest=retained,
                          validation_context=context)
    assert not (tmp_path / 'output' / artifact_identity(coordinated)).exists()
    with pytest.raises(TypeError):
        publish_reference(coordinated, tmp_path / 'missing-expectation')


@pytest.mark.parametrize('kind', ['model', 'footprint', 'profile', 'policy', 'proof'])
def test_publisher_requires_independently_frozen_H_before_mutable_payload_handoff(
        kind, authority, tmp_path):
    """Verify publisher requires independently frozen H before mutable payload handoff."""
    payload, context, ordered, _, _ = authority
    retained_H = artifact_identity(payload)
    retained_curve = curve_digest(ordered)
    changed = mutate(payload, kind)
    assert artifact_identity(changed) != retained_H
    with pytest.raises(ArtifactError, match='independently frozen producer artifact H'):
        publish_reference(changed, tmp_path / 'output', expected_H=retained_H,
                          expected_curve_digest=retained_curve, validation_context=context)
    assert not (tmp_path / 'output').exists()


def test_historical_numeric_variation_does_not_reject_fresh_dual_pass(
        published, monkeypatch):
    """Accept unchanged authority after genuine checks produce different display bounds."""
    before = published.path.read_bytes()
    approval = curve_digest(published.ordered)
    actual_geometry = artifact.validate_geometry
    actual_dynamics = artifact.validate_dynamics
    reports = {}

    def replay_geometry(*args, **kwargs):
        """Run the real proof before varying one numeric report field outward."""
        assert kwargs['expected_curve_digest'] == approval
        report = actual_geometry(*args, **kwargs)
        assert report.status == 'PASS'
        first = report.intervals[0]
        varied = replace(first, displacement_upper_m=math.nextafter(
            first.displacement_upper_m, math.inf))
        reports['geometry'] = replace(report, intervals=(varied,) + report.intervals[1:])
        assert reports['geometry'] != report
        return reports['geometry']

    def replay_dynamics(*args, **kwargs):
        """Run the real proof before varying its outward lap-time display bound."""
        assert kwargs['expected_curve_digest'] == approval
        report = actual_dynamics(*args, **kwargs)
        assert report.status == 'PASS'
        upper = math.nextafter(report.lap_time_upper_s, math.inf)
        nominal = math.nextafter(report.lap_time_s, math.inf)
        assert report.lap_time_lower_s <= nominal <= upper
        reports['dynamics'] = replace(
            report, lap_time_s=nominal, lap_time_upper_s=upper,
            lap_time_error_s=max(nominal - report.lap_time_lower_s, upper - nominal))
        assert reports['dynamics'] != report
        return reports['dynamics']

    monkeypatch.setattr(artifact, 'validate_geometry', replay_geometry)
    monkeypatch.setattr(artifact, 'validate_dynamics', replay_dynamics)
    reference = load_reference(published.path, expected_H=published.H,
                               validation_context=ValidationContext())
    assert reference.geometry_report is reports['geometry']
    assert reference.dynamics_report is reports['dynamics']
    assert reference.path.read_bytes() == before
    assert reference.H == published.H
    assert curve_digest(reference.ordered) == approval
    for value, original in ((reference.ordered.curve.coefficients,
                             published.ordered.curve.coefficients),
                            (reference.ordered.q, published.ordered.q),
                            (reference.ordered.curve.owners, published.ordered.curve.owners),
                            (asdict(reference.profile), asdict(published.profile))):
        assert canonical_bytes(value) == canonical_bytes(original)
    assert reference.payload['validation'] == published.payload['validation']
    assert reference.lap_time_s == published.lap_time_s
    assert reference.lap_time_s != reference.dynamics_report.lap_time_s
    assert reference.sample(.3 * reference.length).time_s == published.sample(
        .3 * published.length).time_s


def test_historical_geometry_can_have_a_different_genuine_adaptive_partition(
        published, monkeypatch):
    """Accept unchanged bytes when conservative uncertainty refines a real geometry proof."""
    before = published.path.read_bytes()
    approval = curve_digest(published.ordered)
    original_report = published.geometry_report
    leaf = original_report.intervals[0]
    target = (published.ordered.curve.segments[leaf.segment].coefficients,
              Fraction(*leaf.exact_t0), Fraction(*leaf.exact_t1))
    actual_bounds = geometry_checker.interval_bounds
    actual_geometry = artifact.validate_geometry
    actual_dynamics = artifact.validate_dynamics
    reports, refined = {}, []

    def uncertain_once(coefficients, low, high):
        """Request one additional conservative subdivision after evaluating real bounds."""
        result = actual_bounds(coefficients, low, high)
        coefficient_tuple = tuple(tuple(float(value) for value in row) for row in coefficients)
        if not refined and (coefficient_tuple, low, high) == target:
            refined.append(True)
            raise geometry_checker.BoundUncertain('test-only conservative refinement')
        return result

    def replay_geometry(*args, **kwargs):
        """Produce a genuine independent PASS after one additional adaptive split."""
        assert kwargs['expected_curve_digest'] == approval
        with monkeypatch.context() as patch:
            patch.setattr(geometry_checker, 'interval_bounds', uncertain_once)
            report = actual_geometry(*args, **kwargs)
        assert refined and report.status == 'PASS'
        assert len(report.intervals) > len(original_report.intervals)
        reports['geometry'] = report
        return report

    def replay_dynamics(*args, **kwargs):
        """Retain the separate real cyclic dynamics acceptance call."""
        assert kwargs['expected_curve_digest'] == approval
        reports['dynamics'] = actual_dynamics(*args, **kwargs)
        assert reports['dynamics'].status == 'PASS'
        return reports['dynamics']

    monkeypatch.setattr(artifact, 'validate_geometry', replay_geometry)
    monkeypatch.setattr(artifact, 'validate_dynamics', replay_dynamics)
    reference = load_reference(published.path, expected_H=published.H,
                               validation_context=ValidationContext())
    assert reference.geometry_report is reports['geometry']
    assert reference.dynamics_report is reports['dynamics']
    assert reference.path.read_bytes() == before
    assert reference.H == published.H
    assert curve_digest(reference.ordered) == approval


@pytest.mark.parametrize('case', [
    'geometry_reason', 'geometry_curve', 'geometry_coefficients', 'geometry_coverage',
    'geometry_assumptions', 'geometry_gap', 'geometry_overlap', 'geometry_owner',
    'geometry_portal', 'geometry_method', 'geometry_bound', 'geometry_rational', 'geometry_gate',
    'dynamics_status', 'dynamics_model', 'dynamics_curve', 'dynamics_support', 'dynamics_cap',
    'dynamics_distance', 'dynamics_time', 'dynamics_acceleration', 'dynamics_work',
    'dynamics_residual', 'dynamics_lap', 'dynamics_error', 'dynamics_residual_names',
])
def test_historical_snapshots_fail_closed_on_incoherent_claims(case, published):
    """Reject categorical forgery and malformed snapshots without recertifying old numbers."""
    geometry = asdict(published.geometry_report)
    dynamics = asdict(published.dynamics_report)
    if case == 'geometry_reason':
        geometry['reason'] = 'fabricated physical safety approval'
    elif case == 'geometry_curve':
        geometry['curve_digest'] = '0' * 64
    elif case == 'geometry_coefficients':
        geometry['coefficients_sha256'] = '0' * 64
    elif case == 'geometry_coverage':
        geometry['coverage'] += ('physical_clearance',)
    elif case == 'geometry_assumptions':
        geometry['assumptions'] = ()
    elif case == 'geometry_gap':
        geometry['intervals'] = geometry['intervals'][1:]
    elif case == 'geometry_overlap':
        geometry['intervals'] += (copy.deepcopy(geometry['intervals'][0]),)
    elif case == 'geometry_owner':
        geometry['intervals'][0]['occurrence_id'] = 'unrelated_occurrence'
    elif case == 'geometry_portal':
        geometry['intervals'][0]['portal_id'] = 'unrelated_portal'
    elif case == 'geometry_method':
        geometry['intervals'][0]['method'] = 'sampling_only'
    elif case == 'geometry_bound':
        geometry['intervals'][0]['clearance_lower_m'] = -1.
    elif case == 'geometry_rational':
        geometry['intervals'][0]['exact_t0'] = (0, 0)
    elif case == 'geometry_gate':
        geometry['gates'][0]['portal_id'] = 'unrelated_portal'
    elif case == 'dynamics_status':
        dynamics['status'] = 'INCONCLUSIVE'
    elif case == 'dynamics_model':
        dynamics['model_digest'] = '0' * 64
    elif case == 'dynamics_curve':
        dynamics['curve_digest'] = '0' * 64
    elif case == 'dynamics_support':
        dynamics['edges'][0]['support_occurrences'] = ('unrelated_occurrence',)
    elif case == 'dynamics_cap':
        dynamics['edges'][0]['cap_mps'] *= 2
    elif case == 'dynamics_distance':
        dynamics['edges'][0]['distance_lower_m'] = -1.
    elif case == 'dynamics_time':
        dynamics['edges'][0]['time_lower_s'] = -1.
    elif case == 'dynamics_acceleration':
        dynamics['edges'][0]['acceleration_lower_mps2'] = 1000.
    elif case == 'dynamics_work':
        dynamics['edges'][0]['bound_intervals'] = 0
    elif case == 'dynamics_residual':
        dynamics['edges'][0]['normalized_residual_upper'] = 1.
    elif case == 'dynamics_lap':
        dynamics['lap_time_lower_s'] = 1000.
        dynamics['lap_time_s'] = 1001.
        dynamics['lap_time_upper_s'] = 1002.
        dynamics['lap_time_error_s'] = 1.
    elif case == 'dynamics_error':
        dynamics['lap_time_error_s'] = -1.
    elif case == 'dynamics_residual_names':
        dynamics['worst_residuals'] = (('invented_physical_metric', -1.),)
    with pytest.raises(ArtifactError, match='stored historical'):
        if case.startswith('geometry'):
            artifact._historical_geometry(
                decode_record(type(published.geometry_report), geometry),
                published.geometry_report, published.ordered, published.footprint,
                published.policies.geometry)
        else:
            artifact._historical_dynamics(
                decode_record(type(published.dynamics_report), dynamics),
                published.dynamics_report, published.profile, published.policies.dynamics)


@pytest.mark.parametrize('checker,status', [
    ('geometry', 'FAIL'), ('geometry', 'INCONCLUSIVE'), ('geometry', 'UNSUPPORTED'),
    ('dynamics', 'FAIL'), ('dynamics', 'INCONCLUSIVE'), ('dynamics', 'UNSUPPORTED'),
])
def test_historical_PASS_never_overrides_failed_or_uncertain_fresh_proof(
        checker, status, published, monkeypatch):
    """Require both real checker calls and preserve every fresh non-PASS outcome."""
    approval = curve_digest(published.ordered)
    actual_geometry = artifact.validate_geometry
    actual_dynamics = artifact.validate_dynamics
    calls = []

    def replay_geometry(*args, **kwargs):
        """Run the actual geometry proof before injecting its declared non-PASS outcome."""
        calls.append(('geometry', kwargs['expected_curve_digest']))
        report = actual_geometry(*args, **kwargs)
        assert report.status == 'PASS'
        return replace(report, status=status) if checker == 'geometry' else report

    def replay_dynamics(*args, **kwargs):
        """Run the actual dynamics proof before injecting its declared non-PASS outcome."""
        calls.append(('dynamics', kwargs['expected_curve_digest']))
        report = actual_dynamics(*args, **kwargs)
        assert report.status == 'PASS'
        return replace(report, status=status) if checker == 'dynamics' else report

    monkeypatch.setattr(artifact, 'validate_geometry', replay_geometry)
    monkeypatch.setattr(artifact, 'validate_dynamics', replay_dynamics)
    with pytest.raises(ArtifactError, match=checker + ' replay ' + status) as result:
        load_reference(published.path, expected_H=published.H,
                       validation_context=ValidationContext())
    assert result.value.status == status
    assert calls == [('geometry', approval), ('dynamics', approval)]


def test_frozen_main_time_must_remain_inside_fresh_enclosure(published, monkeypatch):
    """Reject a replay enclosure excluding immutable main time despite interval overlap."""
    actual_dynamics = artifact.validate_dynamics
    calls = []

    def replay_dynamics(*args, **kwargs):
        """Run the real checker before injecting an enclosure that excludes main time."""
        report = actual_dynamics(*args, **kwargs)
        assert report.status == 'PASS'
        lower = math.nextafter(published.lap_time_s, math.inf)
        assert report.lap_time_lower_s < lower < report.lap_time_upper_s
        calls.append(kwargs['expected_curve_digest'])
        return replace(report, lap_time_s=lower, lap_time_lower_s=lower,
                       lap_time_error_s=report.lap_time_upper_s - lower)

    monkeypatch.setattr(artifact, 'validate_dynamics', replay_dynamics)
    with pytest.raises(ArtifactError, match='main lap time lies outside replay enclosure'):
        load_reference(published.path, expected_H=published.H,
                       validation_context=ValidationContext())
    assert calls == [curve_digest(published.ordered)]


def test_new_external_approval_can_authorize_a_different_independently_legal_body(
        authority, published, tmp_path):
    """Accept a caller-approved legal body only with fresh proof of the actual new body."""
    payload, context, ordered, _, _ = authority
    changed = mutate(payload, 'footprint')  # Deliberately small and still legal.
    # This controlled caller approves the new body before writing the test file.
    # Never derive a trusted expected H from an untrusted received envelope.
    expected_H = artifact_identity(changed)
    assert expected_H != published.H
    path, _ = write_reference(tmp_path / 'new-approved-body', changed, expected_H)
    reference = load_reference(path, expected_H=expected_H, validation_context=context)
    assert reference.geometry_report.status == reference.dynamics_report.status == 'PASS'
    assert reference.footprint.front_m == published.footprint.front_m + .01
    assert curve_digest(reference.ordered) == curve_digest(ordered)
    assert canonical_bytes(reference.payload['validation']) == canonical_bytes(
        payload['validation'])
    assert canonical_bytes(asdict(reference.geometry_report)) != canonical_bytes(
        payload['validation']['geometry'])
    assert published.path.read_bytes() != path.read_bytes()


@pytest.mark.parametrize('shared_ancestor', [False, True])
def test_publication_rejects_stage_swap_from_shared_directory(
        tmp_path, monkeypatch, shared_ancestor):
    """Reject mutable output ancestry before a different principal can swap the stage."""
    shared = tmp_path / 'shared'
    shared.mkdir(mode=0o777)
    shared.chmod(0o777)
    output = shared / 'private' if shared_ancestor else shared
    if shared_ancestor:
        output.mkdir(mode=0o700)
    # Isolate the filesystem transaction; numerical acceptance cannot bind a renamed name.
    payload = {'filesystem_transaction_test': True}
    expected_H = artifact_identity(payload)
    monkeypatch.setattr(artifact, '_load_bytes', lambda *args: object())
    actual_rename = artifact._rename_noreplace
    swapped = []

    def swap_then_rename(source, destination, parent_fd):
        """Replace the stage after the validated directory descriptor has been synced."""
        stage = output / source
        stage.rename(output / 'displaced-validated-stage')
        stage.mkdir()
        (stage / 'reference.json').write_text('{"unvalidated":true}')
        swapped.append(True)
        actual_rename(source, destination, parent_fd)

    monkeypatch.setattr(artifact, '_rename_noreplace', swap_then_rename)
    with pytest.raises(ArtifactError, match='publication directory'):
        publish_reference(payload, output, expected_H=expected_H,
                          expected_curve_digest='1' * 64)
    assert not swapped
    assert not (output / expected_H).exists()


@pytest.mark.parametrize('owner,mode,allow_sticky,accepted', [
    ('self', 0o755, False, True), ('root', 0o755, False, True),
    ('other', 0o755, False, False), ('self', 0o775, False, False),
    ('self', 0o757, False, False), ('self', 0o1777, True, False),
    ('root', 0o1777, True, True), ('root', 0o1777, False, False),
    ('other', 0o1777, True, False), ('root', 0o777, True, False),
])
def test_publication_namespace_owner_and_mode_contract(
        tmp_path, monkeypatch, owner, mode, allow_sticky, accepted):
    """Cover ownership and Linux ACL-mask mode gates without needing privileged chown."""
    descriptor = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    actual_fstat = os.fstat
    effective_uid = os.geteuid()
    selected_uid = {'self': effective_uid, 'root': 0, 'other': effective_uid + 1}[owner]

    def selected_info(fd):
        """Change only the selected directory's uid/mode for the permission contract."""
        info = actual_fstat(fd)
        if fd != descriptor:
            return info
        fields = list(info)
        fields[stat.ST_UID] = selected_uid
        fields[stat.ST_MODE] = stat.S_IFDIR | mode
        return os.stat_result(fields)

    monkeypatch.setattr(artifact.os, 'fstat', selected_info)
    try:
        if accepted:
            artifact._publication_directory(descriptor, allow_sticky_ancestor=allow_sticky)
        else:
            with pytest.raises(ArtifactError, match='publication directory'):
                artifact._publication_directory(descriptor, allow_sticky_ancestor=allow_sticky)
    finally:
        os.close(descriptor)


def test_publication_checks_ancestors_before_creating_output(tmp_path):
    """Leave an unsafe writable ancestor untouched instead of creating a private child."""
    shared = tmp_path / 'shared'
    shared.mkdir()
    shared.chmod(0o777)
    with pytest.raises(ArtifactError, match='publication directory'):
        artifact._open_directory(shared / 'absent' / 'output', create=True, publication=True)
    assert list(shared.iterdir()) == []


def test_publication_allows_private_tmp_child_but_rejects_shared_parent(tmp_path):
    """Support a private user directory below root-owned sticky /tmp, never /tmp itself."""
    assert os.stat('/tmp').st_uid == 0
    assert os.stat('/tmp').st_mode & stat.S_ISVTX
    descriptor = artifact._open_directory(tmp_path, publication=True)
    os.close(descriptor)
    with pytest.raises(ArtifactError, match='publication directory'):
        artifact._open_directory('/tmp', publication=True)
