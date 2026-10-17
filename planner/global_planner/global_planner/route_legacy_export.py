"""Lossy, occurrence-owned ROS waypoint projection of an accepted reference."""

from bisect import bisect_left
from contextlib import redirect_stdout
from dataclasses import asdict, dataclass
import fcntl
import io
import json
import math
import os
from pathlib import Path
import shutil
import stat
import struct
import uuid

from ._route_geometry import EPS
from .route_corridor import CorridorError, _layout, _sample, normal_interval


UNAVAILABLE_GROUPS = ('centerline_markers', 'centerline_waypoints',
                      'global_traj_markers_sp', 'global_traj_wpnts_sp')
LIMITATIONS = (
    'Lossy planar ROS projection; no occurrence, surface, q or mathematical certificate in Wpnt.',
    'Artifact H in export metadata is informational; independently trusted H is required to load.',
    'True metric station is authoritative; waypoint index times nominal step is not station.',
    'Legacy geometry refits and nearest-XY association do not preserve reference approval.',
    'No physical clearance, contact, localization, controller tracking or operation approval.',
)
WAYPOINT_FIELDS = ('id', 's_m', 'd_m', 'x_m', 'y_m', 'd_right', 'd_left',
                   'psi_rad', 'kappa_radpm', 'vx_mps', 'ax_mps2')


class ExportError(ValueError):
    """Unsupported export, invalid metric request or failed atomic publication."""

    def __init__(self, reason, status='FAIL'):
        """Retain an explicit fail-closed CLI outcome and diagnostic reason."""
        super().__init__(str(reason))
        self.reason, self.status = str(reason), status


@dataclass(frozen=True)
class LegacyWaypoint:
    """Immutable waypoint fields with audit-only identity and model time."""

    id: int
    s_m: float
    d_m: float
    x_m: float
    y_m: float
    d_right: float
    d_left: float
    psi_rad: float
    kappa_radpm: float
    vx_mps: float
    ax_mps2: float
    time_s: float
    occurrence_id: str
    surface_id: str
    portal_support: tuple


@dataclass(frozen=True)
class LegacyView:
    """Pure deterministic compatibility view, without another geometry authority."""

    H: str
    frame_id: str
    waypoints: tuple
    boundaries: tuple
    length_m: float
    lap_time_s: float
    legacy_lap_time_float32_s: float
    map_info: str


@dataclass(frozen=True)
class ExportResult:
    """Receipt for a complete serialized export, independent of artifact approval."""

    status: str
    reason: str
    H: str
    output_path: str
    waypoint_count: int
    length_m: float
    lap_time_s: float
    legacy_lap_time_float32_s: float
    unavailable_groups: tuple = UNAVAILABLE_GROUPS
    limitations: tuple = LIMITATIONS


def _stations(reference, step_m):
    curve, ordered = reference.ordered.curve, reference.ordered
    maximum = curve.policy.max_samples
    if type(step_m) not in (int, float) or not math.isfinite(step_m) or step_m <= 0:
        raise ExportError('invalid metric step')
    if step_m < reference.length / maximum:
        raise ExportError('export sample budget exhausted', 'RESOURCE_LIMIT')
    count = math.ceil(reference.length / step_m)
    if count + 1 > maximum:
        raise ExportError('export sample budget exhausted', 'RESOURCE_LIMIT')
    # Every event is transported into physical metres through the same saved
    # coefficients; original q never supplies a waypoint station.
    anchors = set(curve.cumulative)
    anchors.update(curve.station(k.segment, k.t) for k in reference.profile.knots)
    ends = _layout(ordered.route)
    for i, occurrence in enumerate(ordered.route.occurrences):
        anchors.update(ordered.station_at_q(ends[i] + cap[0]) for cap in occurrence.caps)
        portal = ordered.route.portals[i]
        anchors.add(ordered.station_at_q(ends[i + 1] - portal.before))
        anchors.add(ordered.station_at_q(ends[(i + 1) % len(ends[:-1])] + portal.after))
    if len(anchors) > maximum:
        raise ExportError('semantic export sample budget exhausted', 'RESOURCE_LIMIT')
    fixed = tuple(sorted(anchors))
    for i in range(1, count):
        station = i * step_m
        index = bisect_left(fixed, station)
        nearby = fixed[max(0, index - 1):index + 1]
        if all(abs(station - event) > curve.policy.station_abs for event in nearby):
            anchors.add(station)
        if len(anchors) > maximum:
            raise ExportError('combined export sample budget exhausted', 'RESOURCE_LIMIT')
    return tuple(sorted(anchors))


def waypoint_view(reference, *, step_m):
    """Project an accepted reference using metric samples and exact semantic events."""
    from .route_artifact import Reference

    if not isinstance(reference, Reference):
        raise ExportError('export requires an independently accepted Reference')
    points = []
    for index, station in enumerate(_stations(reference, step_m)):
        terminal = station == reference.length
        sample = reference.sample(0. if terminal else station)
        try:
            corridor = normal_interval(reference.ordered,
                                       _sample(reference.ordered, 0. if terminal else station))
        except CorridorError as exc:
            raise ExportError('unsupported original legal normal chart: ' + str(exc),
                              'UNSUPPORTED') from exc
        points.append(LegacyWaypoint(
            index, station, 0., sample.xy[0], sample.xy[1], corridor.right, corridor.left,
            sample.heading, sample.curvature, sample.speed_mps, sample.acceleration_mps2,
            reference.lap_time_s if terminal else sample.time_s,
            sample.occurrence_id, sample.surface_id, sample.portal_support))
    route = reference.ordered.route
    try:
        legacy_time = struct.unpack('!f', struct.pack('!f', reference.lap_time_s))[0]
    except (OverflowError, struct.error) as exc:
        raise ExportError('main lap time is not representable as Float32', 'UNSUPPORTED') from exc
    if not math.isfinite(legacy_time):
        raise ExportError('main lap time is not finite Float32', 'UNSUPPORTED')
    metadata = {
        'format': 'project-a-legacy-waypoints-v1', 'H': reference.H,
        'route_id': route.payload['route_id'], 'frame_id': route.payload['frame_id'],
        'units': 'm,s,rad', 'heading': '+X zero; counterclockwise positive',
        'curvature': 'signed analytic curvature of saved coefficients',
        'station': 'true metric metres; terminal duplicate has unwrapped s=L',
        'acceleration': 'right-hand affine-squared-speed edge, including closure',
        'side_distances': 'original owned legal normal interval; active portal restriction; '
                          'strict inward numerical allowance, not physical wall distances',
        'side_distance_inward_allowance_m': EPS,
        'sampling': 'nominal metric grid plus exact coefficient/profile/semantic events',
        'nominal_step_m': step_m, 'main_lap_time_s': reference.lap_time_s,
        'legacy_lap_time_float32_s': legacy_time,
        'unavailable_groups': UNAVAILABLE_GROUPS, 'limitations': LIMITATIONS,
    }
    return LegacyView(
        reference.H, route.payload['frame_id'], tuple(points),
        tuple((o.id, o.left, o.right) for o in route.occurrences), reference.length,
        reference.lap_time_s, legacy_time,
        json.dumps(metadata, sort_keys=True, separators=(',', ':'), allow_nan=False))


def _write_ros_product(view, stage_path):
    # These imports are deliberately confined to serialization. Pure compilation,
    # loading and querying never import a ROS node, GUI or legacy planner helper.
    from f110_msgs.msg import Wpnt, WpntArray
    from geometry_msgs.msg import Point
    from rclpy.serialization import deserialize_message, serialize_message
    from rosidl_runtime_py.convert import message_to_ordereddict
    from std_msgs.msg import Float32, String
    from visualization_msgs.msg import Marker, MarkerArray

    from .readwrite_global_waypoints import read_global_waypoints, write_global_waypoints

    main = WpntArray()
    main.header.frame_id = view.frame_id
    for point in view.waypoints:
        main.wpnts.append(Wpnt(**{key: getattr(point, key) for key in WAYPOINT_FIELDS}))

    def line_marker(identifier, namespace, coordinates, color):
        marker = Marker()
        marker.header.frame_id = view.frame_id
        marker.id, marker.ns = identifier, namespace
        marker.type, marker.action = Marker.LINE_STRIP, Marker.ADD
        marker.pose.orientation.w = 1.
        marker.scale.x = .03
        marker.color.r, marker.color.g, marker.color.b, marker.color.a = color
        marker.points = [Point(x=float(x), y=float(y), z=0.) for x, y in coordinates]
        return marker

    main_markers = MarkerArray(markers=[line_marker(
        0, 'project_a_main', tuple((p.x_m, p.y_m) for p in view.waypoints), (1., 0., 0., 1.))])
    bounds = MarkerArray()
    for index, (owner, left, right) in enumerate(view.boundaries):
        for side, chain, color in ((0, left, (0., 0., 1., 1.)),
                                   (1, right, (0., 1., 0., 1.))):
            bounds.markers.append(line_marker(2 * index + side,
                                              'project_a_legal_' + owner, chain, color))
    groups = (MarkerArray(), WpntArray(), main_markers, main,
              MarkerArray(), WpntArray(), bounds)
    lap_time = Float32(data=view.legacy_lap_time_float32_s)
    with redirect_stdout(io.StringIO()):
        write_global_waypoints(str(stage_path), view.map_info, lap_time, *groups)
        restored = read_global_waypoints(str(stage_path))
    expected = (String(data=view.map_info), lap_time) + groups
    if len(restored) != 9:
        raise ExportError('existing reader did not return all nine ROS groups')
    for original, actual in zip(expected, restored):
        desired = message_to_ordereddict(original)
        if message_to_ordereddict(actual) != desired:
            raise ExportError('existing reader changed exported ROS fields')
        roundtrip = deserialize_message(serialize_message(actual), type(actual))
        if message_to_ordereddict(roundtrip) != desired:
            raise ExportError('ROS CDR changed exported waypoint fields')


def export_waypoints(reference, *, step_m, output_dir):
    """Write, read and CDR-check nine ROS groups before atomic no-replace export."""
    from .route_artifact import ArtifactError, _open_directory, _rename_noreplace

    view = waypoint_view(reference, step_m=step_m)
    target = Path(output_dir)
    if target.name in ('', '.', '..'):
        raise ExportError('export output must name a new directory')
    parent_fd = lock_fd = stage_fd = None
    stage_name = None
    try:
        parent_fd = _open_directory(target.parent, publication=True)
        lock_fd = os.open('.' + target.name + '.export.lock',
                          os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK,
                          0o600, dir_fd=parent_fd)
        lock_info = os.fstat(lock_fd)
        if not stat.S_ISREG(lock_info.st_mode) or lock_info.st_nlink != 1:
            raise ExportError('export writer lock is not a private regular file')
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        try:
            os.stat(target.name, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise ExportError('export target already exists; content is immutable')
        stage_name = '.tmp-export-' + uuid.uuid4().hex
        os.mkdir(stage_name, 0o700, dir_fd=parent_fd)
        stage_fd = os.open(stage_name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                           dir_fd=parent_fd)
        stage_path = Path('/proc/self/fd', str(parent_fd), stage_name)
        _write_ros_product(view, stage_path)
        receipt = ExportResult(
            'PASS', 'Existing nine-group reader and ROS CDR roundtrip passed', view.H,
            str(target.absolute() / 'global_waypoints.json'), len(view.waypoints),
            view.length_m, view.lap_time_s, view.legacy_lap_time_float32_s)
        with open(stage_path / 'export.json', 'x', encoding='utf-8') as stream:
            json.dump(asdict(receipt), stream, sort_keys=True, separators=(',', ':'),
                      allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        for name in ('global_waypoints.json', 'export.json'):
            descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=stage_fd)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        os.fsync(stage_fd)
        _rename_noreplace(stage_name, target.name, parent_fd)
        stage_name = None
        os.fsync(parent_fd)
        return receipt
    except (OSError, ArtifactError, ImportError, ValueError, RuntimeError,
            KeyError, TypeError, AttributeError) as exc:
        if isinstance(exc, ExportError):
            raise
        raise ExportError('legacy export failed: ' + str(exc),
                          'UNSUPPORTED' if isinstance(exc, ImportError) else 'FAIL') from exc
    finally:
        if stage_fd is not None:
            os.close(stage_fd)
        if stage_name is not None and parent_fd is not None:
            shutil.rmtree(Path('/proc/self/fd', str(parent_fd), stage_name))
        if lock_fd is not None:
            os.close(lock_fd)
        if parent_fd is not None:
            os.close(parent_fd)
