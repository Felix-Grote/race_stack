"""Independent metric, side-distance and actual legacy ROS projection checks."""

from bisect import bisect_right
from dataclasses import FrozenInstanceError
import errno
import gzip
import json
import math
import os
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from scipy.integrate import quad

from global_planner import route_legacy_export as exporting
from global_planner.cyclic_retime import (
    DynamicsModel, ModelRegion, RegionLimits, RetimePolicy, curve_digest, retime)
from global_planner.iqp_route_adapter import SolverPolicy
from global_planner.route_artifact import artifact_identity, build_payload, publish_reference
from global_planner.route_corridor import OrderedCurve
from global_planner.route_input import load_route
from global_planner.route_reference import Curve
from global_planner.route_validate import (
    Footprint, GeometryValidationPolicy, validate_geometry)
from global_planner.route_validate_dynamics import DynamicsValidationPolicy, validate_dynamics


FIX = Path(__file__).parent / 'fixtures/project_a'


@pytest.fixture(scope='module')
def references(tmp_path_factory):
    """Reapprove immutable archived W2 coefficient fixtures with both current checkers."""
    archive = json.loads(gzip.decompress((FIX / 'w2_a04_candidates.json.gz').read_bytes()))
    accepted = {}

    def get(name='s0_route'):
        if name not in accepted:
            candidate = archive['candidates'][name]
            route = load_route(FIX / (name + '.json'))
            ordered = OrderedCurve(route, Curve(candidate['coefficients'], candidate['owners']),
                                   candidate['q'])
            approval = curve_digest(ordered)
            footprint = Footprint(.1, .1, .12, .01)
            limits = RegionLimits(.05, 4., 2., 3., 4., 2.5, .02,
                                  'Explicit synthetic exporter software budgets')
            model = DynamicsModel(tuple(ModelRegion(o.id, o.surface_id, limits)
                                        for o in route.occurrences),
                                  'Synthetic export test; no physical calibration')
            geometry = validate_geometry(ordered, route, footprint,
                                         expected_curve_digest=approval)
            timed = retime(ordered, model, spacing_m=.57)
            assert timed.status == 'CANDIDATE', timed.message
            dynamics = validate_dynamics(ordered, timed.profile, model, metadata=timed.metadata,
                                         expected_curve_digest=approval)
            assert geometry.status == dynamics.status == 'PASS', (geometry, dynamics)
            payload = build_payload(
                ordered, timed.profile, model, footprint, solver_policy=SolverPolicy(),
                retime_policy=RetimePolicy(), geometry_policy=GeometryValidationPolicy(),
                dynamics_policy=DynamicsValidationPolicy(), approved_curve_digest=approval,
                geometry_report=geometry, dynamics_report=dynamics,
                provenance={'scope': 'Approved archived synthetic W2 test coefficients'})
            expected_H = artifact_identity(payload)
            accepted[name] = publish_reference(payload, tmp_path_factory.mktemp(name),
                                               expected_H=expected_H,
                                               expected_curve_digest=approval)
        return accepted[name]
    return get


def _arc(coefficients, low=0., high=1.):
    c = np.asarray(coefficients)

    def speed(t):
        derivative = c[:, 1] + t * (2 * c[:, 2] + 3 * t * c[:, 3])
        return math.hypot(*derivative)
    distance, error = quad(speed, low, high, epsabs=1e-12, epsrel=1e-12)
    assert error < 1e-9
    return distance


def _ray_distance(xy, direction, chain):
    distances = []
    for first, second in zip(chain, chain[1:]):
        edge = np.subtract(second, first)
        matrix = np.column_stack((direction, -edge))
        if abs(np.linalg.det(matrix)) < 1e-12:
            continue
        distance, fraction = np.linalg.solve(matrix, np.subtract(first, xy))
        if distance > 0 and -1e-10 <= fraction <= 1 + 1e-10:
            distances.append(float(distance))
    assert distances
    return min(distances)


@pytest.mark.parametrize('name', ['s0_route', 's0_reverse_route', 's0_rotated_route',
                                  's3_surfaces_route'])
def test_fields_follow_saved_coefficients_true_metric_and_original_owned_sides(references, name):
    """Compare exported fields with independent coefficient, arc and side-ray oracles."""
    reference = references(name)
    view = exporting.waypoint_view(reference, step_m=.71)
    curve = reference.ordered.curve
    knots = reference.profile.knots
    profile_stations = tuple(curve.station(k.segment, k.t) for k in knots)
    edge_lengths, edge_times = [], []
    for index, knot in enumerate(knots):
        following = knots[(index + 1) % len(knots)]
        high = following.t if following.segment == knot.segment else 1.
        distance = _arc(curve.coefficients[knot.segment], knot.t, high)
        edge_lengths.append(distance)
        edge_times.append(2 * distance / (math.sqrt(knot.u) + math.sqrt(following.u)))
    occurrences = {o.id: o for o in reference.ordered.route.occurrences}
    assert view.frame_id == reference.ordered.route.payload['frame_id']
    expected_sign = 0 if name == 's3_surfaces_route' else (-1 if name == 's0_reverse_route' else 1)
    if name == 's3_surfaces_route':
        assert len({p.surface_id for p in view.waypoints}) > 1
    for point in view.waypoints[1:-1:7]:
        segment, parameter = curve.locate(point.s_m)
        c = np.asarray(curve.coefficients[segment])
        derivative = c[:, 1] + parameter * (2 * c[:, 2] + 3 * parameter * c[:, 3])
        second = 2 * c[:, 2] + 6 * parameter * c[:, 3]
        heading = math.atan2(derivative[1], derivative[0])
        curvature = np.linalg.det(np.stack((derivative, second))) / math.hypot(*derivative) ** 3
        station = math.fsum(_arc(coeff) for coeff in curve.coefficients[:segment])
        station += _arc(curve.coefficients[segment], high=parameter)
        assert point.s_m == pytest.approx(station, abs=2e-8)
        assert point.psi_rad == pytest.approx(heading, abs=2e-12)
        assert point.kappa_radpm == pytest.approx(curvature, abs=2e-12)
        if expected_sign:
            assert point.kappa_radpm * expected_sign > 0
        edge = bisect_right(profile_stations, point.s_m) - 1
        knot, following = knots[edge], knots[(edge + 1) % len(knots)]
        assert segment == knot.segment
        local = _arc(curve.coefficients[segment], knot.t, parameter)
        squared = knot.u + (following.u - knot.u) * local / edge_lengths[edge]
        assert point.vx_mps == pytest.approx(math.sqrt(squared), abs=2e-8)
        assert point.ax_mps2 == pytest.approx(
            (following.u - knot.u) / (2 * edge_lengths[edge]), abs=2e-8)
        elapsed = math.fsum(edge_times[:edge]) + 2 * local / (
            math.sqrt(knot.u) + math.sqrt(squared))
        assert point.time_s == pytest.approx(elapsed, abs=2e-8)
        assert point.d_m == 0.
        if not point.portal_support:
            owner = occurrences[point.occurrence_id]
            normal = np.array((-derivative[1], derivative[0])) / math.hypot(*derivative)
            left = _ray_distance((point.x_m, point.y_m), normal, owner.left)
            right = _ray_distance((point.x_m, point.y_m), -normal, owner.right)
            assert point.d_left == pytest.approx(left - 1e-9, abs=2e-9)
            assert point.d_right == pytest.approx(right - 1e-9, abs=2e-9)


def test_profile_boundaries_and_terminal_use_independent_closing_acceleration_and_main_time(
        references):
    """Check all right-hand profile edges, seam duplication and main Float32 lap time."""
    reference = references()
    view = exporting.waypoint_view(reference, step_m=.73)
    by_station = {p.s_m: p for p in view.waypoints}
    curve, knots = reference.ordered.curve, reference.profile.knots
    times = []
    for index, knot in enumerate(knots):
        following = knots[(index + 1) % len(knots)]
        high = following.t if following.segment == knot.segment else 1.
        distance = _arc(curve.coefficients[knot.segment], knot.t, high)
        point = by_station[curve.station(knot.segment, knot.t)]
        assert point.vx_mps == pytest.approx(math.sqrt(knot.u), abs=2e-10)
        assert point.ax_mps2 == pytest.approx((following.u - knot.u) / (2 * distance), abs=2e-8)
        assert point.time_s == pytest.approx(math.fsum(times), abs=2e-8)
        times.append(2 * distance / (math.sqrt(knot.u) + math.sqrt(following.u)))
    first, last = view.waypoints[0], view.waypoints[-1]
    assert last.s_m == reference.length and last.time_s == reference.lap_time_s
    for name in exporting.WAYPOINT_FIELDS[2:]:
        assert getattr(last, name) == getattr(first, name)
    assert last.occurrence_id == first.occurrence_id
    assert view.lap_time_s == pytest.approx(math.fsum(times), abs=2e-8)
    assert view.legacy_lap_time_float32_s == float(np.float32(view.lap_time_s))
    assert [p.id for p in view.waypoints] == list(range(len(view.waypoints)))
    assert all(0 < b.s_m - a.s_m <= .73 + 1e-8
               for a, b in zip(view.waypoints, view.waypoints[1:]))
    metadata = json.loads(view.map_info)
    assert tuple(metadata['unavailable_groups']) == exporting.UNAVAILABLE_GROUPS
    assert metadata['main_lap_time_s'] == reference.lap_time_s
    assert metadata['side_distance_inward_allowance_m'] == 1e-9


def test_every_original_cap_and_portal_support_event_is_a_metric_export_station(references):
    """Require exact metric export stations for every original semantic event."""
    reference = references()
    ordered = reference.ordered
    stations = {p.s_m for p in exporting.waypoint_view(reference, step_m=.83).waypoints}
    start = 0.
    for index, occurrence in enumerate(ordered.route.occurrences):
        end = start + occurrence.length
        assert ordered.station_at_q(start) in stations
        for local, _ in occurrence.caps:
            assert ordered.station_at_q(start + local) in stations
        portal = ordered.route.portals[index]
        assert ordered.station_at_q(end - portal.before) in stations
        target_start = end if index + 1 < len(ordered.route.occurrences) else 0.
        assert ordered.station_at_q(target_start + portal.after) in stations
        start = end


def test_projection_is_immutable_and_never_refits(references, monkeypatch):
    """Reject mutable views, unaccepted references and any attempted spline refit."""
    reference = references()

    def forbidden(*args, **kwargs):
        raise AssertionError('export attempted another spline fit')
    monkeypatch.setattr(Curve, 'interpolate', forbidden)
    view = exporting.waypoint_view(reference, step_m=1.)
    with pytest.raises(FrozenInstanceError):
        view.waypoints[0].s_m = 4.
    with pytest.raises(FrozenInstanceError):
        view.waypoints = ()
    with pytest.raises(exporting.ExportError, match='accepted Reference'):
        exporting.waypoint_view(SimpleNamespace(), step_m=1.)


@pytest.mark.parametrize('step', [True, 0., -1., math.inf, math.nan, 1e-300])
def test_bad_or_unbounded_metric_sampling_fails_closed(references, step):
    """Reject invalid steps and retain the distinct finite sample-budget outcome."""
    with pytest.raises(exporting.ExportError) as error:
        exporting.waypoint_view(references(), step_m=step)
    assert error.value.status == ('RESOURCE_LIMIT' if step == 1e-300 else 'FAIL')


def test_unsupported_normal_chart_never_publishes(references, tmp_path, monkeypatch):
    """Leave the output absent when an original legal normal chart is unsupported."""
    def unsupported(*args):
        raise exporting.CorridorError('injected unsupported local chart')
    monkeypatch.setattr(exporting, 'normal_interval', unsupported)
    target = tmp_path / 'unsupported'
    with pytest.raises(exporting.ExportError) as error:
        exporting.export_waypoints(references(), step_m=1., output_dir=target)
    assert error.value.status == 'UNSUPPORTED'
    assert not target.exists()


def _fake_ros_product(view, stage):
    (stage / 'global_waypoints.json').write_text('{"test_atomicity_only":true}')


@pytest.mark.parametrize('kind', ['directory', 'file', 'symlink', 'dangling'])
def test_existing_targets_including_dangling_symlinks_are_never_replaced(
        references, tmp_path, monkeypatch, kind):
    """Preserve every pre-existing destination inode, including dangling symlinks."""
    target = tmp_path / 'export'
    if kind == 'directory':
        target.mkdir()
    elif kind == 'file':
        target.write_text('original')
    else:
        target.symlink_to(tmp_path / ('missing' if kind == 'dangling' else 'original'))
    before = target.lstat()
    monkeypatch.setattr(exporting, '_write_ros_product', _fake_ros_product)
    with pytest.raises(exporting.ExportError, match='already exists'):
        exporting.export_waypoints(references(), step_m=1., output_dir=target)
    assert target.lstat().st_ino == before.st_ino
    assert not list(tmp_path.glob('.tmp-export-*'))


def test_failed_writer_or_fsync_leaves_no_partial_export(references, tmp_path, monkeypatch):
    """Remove private stages after interrupted serialization or failed persistence."""
    reference = references()

    def interrupted(view, stage):
        (stage / 'global_waypoints.json').write_text('{')
        raise OSError('injected writer interruption')
    monkeypatch.setattr(exporting, '_write_ros_product', interrupted)
    with pytest.raises(exporting.ExportError, match='interruption'):
        exporting.export_waypoints(reference, step_m=1., output_dir=tmp_path / 'interrupted')
    assert not (tmp_path / 'interrupted').exists()
    monkeypatch.setattr(exporting, '_write_ros_product', _fake_ros_product)

    def failed_sync(fd):
        raise OSError('injected fsync failure')
    monkeypatch.setattr(exporting.os, 'fsync', failed_sync)
    with pytest.raises(exporting.ExportError, match='fsync'):
        exporting.export_waypoints(reference, step_m=1., output_dir=tmp_path / 'unsynced')
    assert not (tmp_path / 'unsynced').exists()
    assert not list(tmp_path.glob('.tmp-export-*'))


def test_uncooperating_target_race_cannot_replace_existing_content(
        references, tmp_path, monkeypatch):
    """Preserve a destination created after inspection by an uncooperative writer."""
    from global_planner import route_artifact

    target = tmp_path / 'export'
    monkeypatch.setattr(exporting, '_write_ros_product', _fake_ros_product)
    original_rename = route_artifact._rename_noreplace

    def competing_rename(source_name, target_name, parent_fd):
        target.mkdir()
        (target / 'sentinel').write_text('concurrent original')
        return original_rename(source_name, target_name, parent_fd)
    monkeypatch.setattr(route_artifact, '_rename_noreplace', competing_rename)
    with pytest.raises(exporting.ExportError):
        exporting.export_waypoints(references(), step_m=1., output_dir=target)
    assert (target / 'sentinel').read_text() == 'concurrent original'
    assert not (target / 'global_waypoints.json').exists()
    assert not list(tmp_path.glob('.tmp-export-*'))


def test_symlink_parent_and_writer_lock_are_rejected(references, tmp_path, monkeypatch):
    """Refuse symlink traversal through the output parent or publication lock."""
    real_parent = tmp_path / 'parent'
    real_parent.mkdir()
    linked_parent = tmp_path / 'linked'
    linked_parent.symlink_to(real_parent, target_is_directory=True)
    monkeypatch.setattr(exporting, '_write_ros_product', _fake_ros_product)
    with pytest.raises(exporting.ExportError):
        exporting.export_waypoints(references(), step_m=1., output_dir=linked_parent / 'export')
    (real_parent / '.export.export.lock').symlink_to(tmp_path / 'missing-lock')
    with pytest.raises(exporting.ExportError):
        exporting.export_waypoints(references(), step_m=1., output_dir=real_parent / 'export')
    assert not (real_parent / 'export').exists()


@pytest.mark.parametrize('kind', ['hardlink', 'fifo'])
def test_nonprivate_or_nonregular_writer_lock_fails_closed(
        references, tmp_path, monkeypatch, kind):
    """Reject hard-linked and FIFO locks without publishing an export."""
    lock = tmp_path / '.export.export.lock'
    if kind == 'hardlink':
        source = tmp_path / 'shared-lock'
        source.touch()
        os.link(source, lock)
    else:
        os.mkfifo(lock)
    monkeypatch.setattr(exporting, '_write_ros_product', _fake_ros_product)
    with pytest.raises(exporting.ExportError, match='private regular file'):
        exporting.export_waypoints(references(), step_m=1., output_dir=tmp_path / 'export')
    assert not (tmp_path / 'export').exists()


def test_actual_nine_group_reader_and_generated_ros_cdr(references, tmp_path):
    """Roundtrip all nine groups through the existing reader and generated ROS CDR."""
    pytest.importorskip('f110_msgs.msg')
    from rclpy.serialization import deserialize_message, serialize_message
    from rosidl_runtime_py.convert import message_to_ordereddict
    from global_planner.readwrite_global_waypoints import read_global_waypoints

    reference = references()
    result = exporting.export_waypoints(reference, step_m=.5, output_dir=tmp_path / 'legacy')
    assert result.status == 'PASS'
    encoded = json.loads(Path(result.output_path).read_text())
    assert set(encoded) == {
        'map_info_str', 'est_lap_time', 'centerline_markers', 'centerline_waypoints',
        'global_traj_markers_iqp', 'global_traj_wpnts_iqp', 'global_traj_markers_sp',
        'global_traj_wpnts_sp', 'trackbounds_markers'}
    groups = read_global_waypoints(str(Path(result.output_path).parent))
    main = groups[5]
    assert len(main.wpnts) == result.waypoint_count
    assert groups[1].data == float(np.float32(reference.lap_time_s))
    assert main.wpnts[-1].s_m == reference.length
    assert main.wpnts[-1].x_m == main.wpnts[0].x_m
    assert main.wpnts[-1].ax_mps2 == main.wpnts[0].ax_mps2
    assert not groups[2].markers and not groups[3].wpnts
    assert not groups[6].markers and not groups[7].wpnts
    for original in groups:
        restored = deserialize_message(serialize_message(original), type(original))
        assert message_to_ordereddict(restored) == message_to_ordereddict(original)


def test_corrupt_staged_ros_serialization_is_never_published(references, tmp_path, monkeypatch):
    """Reject corrupt staged legacy JSON before publishing any accepted export."""
    pytest.importorskip('f110_msgs.msg')
    from global_planner import readwrite_global_waypoints

    def corrupt_writer(directory, *args):
        Path(directory, 'global_waypoints.json').write_text('{"map_info_str":{"data":"bad"}}')
    monkeypatch.setattr(readwrite_global_waypoints, 'write_global_waypoints', corrupt_writer)
    target = tmp_path / 'corrupt'
    with pytest.raises(exporting.ExportError, match='legacy export failed'):
        exporting.export_waypoints(references(), step_m=1., output_dir=target)
    assert not target.exists()
    assert not list(tmp_path.glob('.tmp-export-*'))


def test_rename_error_does_not_leave_export_staging(references, tmp_path, monkeypatch):
    """Remove the private stage when atomic publication reports a filesystem error."""
    from global_planner import route_artifact

    monkeypatch.setattr(exporting, '_write_ros_product', _fake_ros_product)

    def failed_rename(*args):
        raise OSError(errno.EXDEV, 'injected cross-filesystem rename failure')
    monkeypatch.setattr(route_artifact, '_rename_noreplace', failed_rename)
    with pytest.raises(exporting.ExportError, match='cross-filesystem'):
        exporting.export_waypoints(references(), step_m=1., output_dir=tmp_path / 'export')
    assert not (tmp_path / 'export').exists()
    assert not list(tmp_path.glob('.tmp-export-*'))
