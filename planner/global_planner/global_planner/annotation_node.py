# Copyright 2026 ForzaETH
"""Isolated ROS 2 adapter for the annotation tool (offline only).

Transport is std_msgs/String JSON on ``/planner_annotation/*`` - no
custom messages, no services on the driving graph. This node must run
in its own namespace / ROS_DOMAIN_ID, never inside the stack_master
driving launch. It reuses ``annotation_server`` operations verbatim, so
the ROS and local HTTP frontends cannot diverge. Commands carry a
``request_id``; duplicates within one node lifetime are acknowledged
without re-applying (bounded, process-local memory - not a persistent
idempotency log), and every command gets an authoritative-state reply on
``/planner_annotation/state`` (latched-style, depth 1) carrying the
session revision.

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

    class String:  # minimal stand-in so command handling stays testable
        """Headless stand-in for std_msgs/String (test/dev only)."""

        def __init__(self, data=''):
            self.data = data

from . import annotation_server as server_core

LATCHED = None  # built lazily when rclpy exists


class AnnotationNode(Node if rclpy else object):
    """Single-authority session node; see module docstring for safety."""

    # request_id memory is process-local and bounded: it only suppresses
    # accidental retries within one node lifetime. After a restart the set
    # is empty, so the first command must be ``open``; a resent pre-restart
    # id then fails closed on 'no open session' instead of mutating state.
    _SEEN_CAP = 4096

    def __init__(self, maps_dir=None, out_dir=None):
        """Subscribe to commands and publish authoritative state."""
        if rclpy:
            super().__init__('planner_annotation')
            self.declare_parameter('maps_dir', maps_dir or '')
            self.declare_parameter('out_dir', out_dir or '/tmp/annotation_out')
            maps_dir = self.get_parameter('maps_dir').value or maps_dir
            out_dir = self.get_parameter('out_dir').value or out_dir
        # Fail fast here so a misconfigured node never serves its first map
        # from an unconfigured backend (previously a late TypeError).
        server_core.configure(maps_dir or None, out_dir or None)
        self._seen = {}
        if rclpy:
            qos = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                             durability=DurabilityPolicy.TRANSIENT_LOCAL)
            self._pub = self.create_publisher(
                String, '/planner_annotation/state', qos)
            self.create_subscription(
                String, '/planner_annotation/command', self._on_command, 10)

    def _remember(self, request_id):
        """Record a request id, evicting the oldest past the cap."""
        self._seen[request_id] = True
        while len(self._seen) > self._SEEN_CAP:
            self._seen.pop(next(iter(self._seen)))

    def _on_command(self, msg):
        """Apply one JSON command once; always reply with full state.

        A repeated ``request_id`` is acknowledged as DUPLICATE without
        re-applying. The id is recorded only after the op succeeds, so a
        failed command stays retryable instead of being masked as a
        duplicate. Every reply carries the ``request_id`` (when given)
        and the authoritative session ``revision`` (when a session is
        open); use the ``state`` op to recover canonical state after a
        reconnect.
        """
        request_id = None
        try:
            body = json.loads(msg.data)
            request_id = body.pop('request_id', None)
            op_name = body.pop('op', '')
            if request_id is not None and request_id in self._seen:
                result = {'status': 'DUPLICATE',
                          'message': 'already applied; use the state op '
                                     'to recover canonical state',
                          'request_id': request_id}
            else:
                op = {'open': server_core.op_open,
                      'update': server_core.op_update,
                      'extract': server_core.op_extract,
                      'suggest': server_core.op_suggest,
                      'preview': server_core.op_preview,
                      'approve': server_core.op_approve,
                      'export': server_core.op_export,
                      'save': server_core.op_save,
                      'undo': server_core.op_undo,
                      'state': server_core.op_state}.get(op_name)
                if op is None:
                    raise ValueError(f'unknown op {op_name}')
                result = op(body)
                if request_id is not None:
                    self._remember(request_id)
                    result = dict(result, request_id=request_id)
            session = server_core.STATE.get('session')
            if session is not None:
                result = dict(result, revision=session.get('revision'))
        except Exception as exc:  # reply, never crash the session node
            result = {'status': 'FAIL', 'message': str(exc)}
            if request_id is not None:
                result = dict(result, request_id=request_id)
            session = server_core.STATE.get('session')
            if session is not None:
                result = dict(result, revision=session.get('revision'))
        out = String()
        out.data = json.dumps(result)
        self._pub.publish(out)


def main(args=None):
    """Entry point; refuses to start without ROS (use the HTTP server).

    Pass directories as ROS params, e.g.
    ``ros2 run global_planner annotation_node --ros-args
    -p maps_dir:=stack_master/maps -p out_dir:=/tmp/annotation_out``.
    """
    if rclpy is None:
        raise SystemExit('rclpy unavailable: run annotation_server locally, '
                         'or source ROS 2 Humble for the ROS adapter')
    rclpy.init(args=args)
    rclpy.spin(AnnotationNode())
    rclpy.shutdown()


if __name__ == '__main__':
    main()
