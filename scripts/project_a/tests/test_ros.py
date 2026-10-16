"""Actual Humble installed-package/serialization checks. No nodes are started."""
import importlib
from pathlib import Path

import numpy as np
from ament_index_python.packages import get_package_share_directory
from f110_msgs.msg import Wpnt, WpntArray
from rclpy.serialization import deserialize_message, serialize_message
from rosidl_runtime_py.convert import message_to_ordereddict
from std_msgs.msg import Float32
from visualization_msgs.msg import MarkerArray


def waypoint():
    point = Wpnt(id=42)
    for i, field in enumerate(point.get_fields_and_field_types()):
        if field != 'id':
            setattr(point, field, float(i) / 8)
    return point


def test_generated_ros_messages_roundtrip():
    array = WpntArray(wpnts=[waypoint()])
    array.header.frame_id = 'synthetic_map'
    for original in (waypoint(), array):
        restored = deserialize_message(serialize_message(original), type(original))
        assert message_to_ordereddict(original) == message_to_ordereddict(restored)


def test_installed_packages_and_optimizer():
    for name in ('global_planner', 'frenet_conversion', 'f110_msgs'):
        module = importlib.import_module(name)
        assert str(Path(module.__file__).resolve()).startswith('/work/install/')
        assert Path(get_package_share_directory(name), 'package.xml').is_file()
    optimizer = importlib.import_module('global_racetrajectory_optimization.trajectory_optimizer')
    assert str(Path(optimizer.__file__).resolve()).startswith('/work/python/')
    assert callable(optimizer.trajectory_optimizer)
    # Planner utilities import without GUI construction or map access.
    importlib.import_module('global_planner.global_planner_utils')


def test_existing_nine_group_json_roundtrip(tmp_path):
    from global_planner.readwrite_global_waypoints import read_global_waypoints, write_global_waypoints
    wpnts = WpntArray(wpnts=[waypoint()])
    groups = (MarkerArray(), wpnts, MarkerArray(), wpnts, MarkerArray(), WpntArray(), MarkerArray())
    write_global_waypoints(str(tmp_path), 'W0 synthetic serialization only', Float32(data=12.5), *groups)
    result = read_global_waypoints(str(tmp_path))
    assert result[0].data == 'W0 synthetic serialization only'
    assert result[1].data == 12.5
    for expected, actual in zip(groups, result[2:]):
        assert message_to_ordereddict(expected) == message_to_ordereddict(actual)


def test_installed_frenet_straight_roundtrip():
    from frenet_conversion.frenet_converter import FrenetConverter
    x = np.arange(0., 10.1, .1)
    converter = FrenetConverter(x, np.zeros_like(x), np.zeros_like(x))
    expected = np.array([[2., 5.], [.2, -.3]])
    sd = converter.get_frenet(*expected)
    np.testing.assert_allclose(sd, expected, rtol=0, atol=1e-6)
    np.testing.assert_allclose(converter.get_cartesian(*sd), expected, rtol=0, atol=1e-6)
