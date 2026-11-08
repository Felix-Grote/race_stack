# Copyright 2026 ForzaETH
"""Isolated ROS 2 adapter for the annotation tool (offline only).

Transport is std_msgs/String JSON on ``/planner_annotation/*`` - no
custom messages, no services on the driving graph. This node must run
in its own namespace / ROS_DOMAIN_ID, never inside the stack_master
driving launch. It reuses ``annotation_server`` operations verbatim, so
the ROS and local HTTP frontends cannot diverge. Commands carry a
``request_id``; duplicates are acknowledged without re-applying, and
every command gets an authoritative-state reply on
``/planner_annotation/state`` (latched-style, depth 1).

Foxglove Bridge / Lichtblick can expose these topics to a panel; the
geometry core does not depend on that choice.
"""
import json

try:
    import rclpy
    from rclpy.node import Node
    from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
    from std_msgs.msg import String
except ImportError:  # ROS not installed (e.g. headless dev container)
    rclpy = None

from . import annotation_server as server_core

LATCHED = None  # built lazily when rclpy exists


class AnnotationNode(Node if rclpy else object):
    """Single-authority session node; see module docstring for safety."""

    def __init__(self):
        """Subscribe to commands and publish authoritative state."""
        super().__init__('planner_annotation')
        qos = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                         durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self._seen = set()
        self._pub = self.create_publisher(
            String, '/planner_annotation/state', qos)
        self.create_subscription(
            String, '/planner_annotation/command', self._on_command, 10)

    def _on_command(self, msg):
        """Apply one JSON command once; always reply with full state."""
        try:
            body = json.loads(msg.data)
            request_id = body.pop('request_id', None)
            op_name = body.pop('op', '')
            if request_id is not None and request_id in self._seen:
                result = {'status': 'DUPLICATE', 'message': 'already applied'}
            else:
                if request_id is not None:
                    self._seen.add(request_id)
                op = {'open': server_core.op_open,
                      'update': server_core.op_update,
                      'extract': server_core.op_extract,
                      'export': server_core.op_export,
                      'save': server_core.op_save,
                      'undo': server_core.op_undo}.get(op_name)
                if op is None:
                    raise ValueError(f'unknown op {op_name}')
                result = op(body)
        except Exception as exc:  # reply, never crash the session node
            result = {'status': 'FAIL', 'message': str(exc)}
        out = String()
        out.data = json.dumps(result)
        self._pub.publish(out)


def main(args=None):
    """Entry point; refuses to start without ROS (use the HTTP server)."""
    if rclpy is None:
        raise SystemExit('rclpy unavailable: run annotation_server locally, '
                         'or source ROS 2 Humble for the ROS adapter')
    rclpy.init(args=args)
    rclpy.spin(AnnotationNode())
    rclpy.shutdown()


if __name__ == '__main__':
    main()
