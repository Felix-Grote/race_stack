"""Replay unchanged hosted references in an isolated locally installed runtime."""
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess

from ament_index_python.packages import get_package_prefix, get_package_share_directory
from global_planner.route_artifact import load_reference
from global_planner.route_compile import load_policy
from global_planner.cyclic_retime import curve_digest


assert os.getuid() == 1000
for absent in ('/src', '/workspace', '/work/src', '/work/build', '/work/optimizer'):
    assert not Path(absent).exists(), absent
share = Path(get_package_share_directory('global_planner')) / 'project_a'
catalog = json.loads(Path('/catalog.json').read_text())
outcomes = []
for case in catalog:
    path = Path('/incoming') / case['relative_artifact']
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    policy_name = 's6_coarse_policy.json' if case['case'] == 's6_competition_route' else 'synthetic_policy.json'
    policy = share / 'policies' / policy_name
    _, context, _ = load_policy(policy)
    reference = load_reference(path, expected_H=case['H'], validation_context=context)
    assert reference.H == case['H']
    assert reference.geometry_report.status == reference.dynamics_report.status == 'PASS'
    assert curve_digest(reference.ordered) == case['curve_digest']
    for station in (-.137, 0., reference.length, 2 * reference.length + .137):
        state = reference.sample(station)
        assert math.isfinite(state.curvature) and state.speed_mps > 0
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    outcomes.append(dict(case=case['case'], H=case['H'], curve_digest=case['curve_digest'],
                         geometry='PASS', dynamics='PASS', unchanged_input_sha256=before))
    Path('/results/portability.json').write_text(json.dumps(outcomes, indent=2) + '\n')

case = next(x for x in catalog if x['case'] == 's6_competition_route')
executable = Path(get_package_prefix('global_planner')) / 'lib/global_planner/compile_route'
command = [str(executable), 'export', '--artifact', str(Path('/incoming') / case['relative_artifact']),
           '--expected-h', case['H'], '--policy', str(share / 'policies/s6_coarse_policy.json'),
           '--step-m', '.5', '--output', '/results/legacy', '--report', '/results/export.json']
process = subprocess.run(command, capture_output=True, text=True, timeout=240)
Path('/results/export.stdout.txt').write_text(process.stdout)
Path('/results/export.stderr.txt').write_text(process.stderr)
assert process.returncode == 0, process.stderr
exported = json.loads(Path('/results/export.json').read_text())
from global_planner.readwrite_global_waypoints import read_global_waypoints
from rclpy.serialization import deserialize_message, serialize_message
from rosidl_runtime_py.convert import message_to_ordereddict
groups = read_global_waypoints(str(Path(exported['output_path']).parent))
assert len(groups) == 9
for message in groups:
    restored = deserialize_message(serialize_message(message), type(message))
    assert message_to_ordereddict(restored) == message_to_ordereddict(message)
assert groups[5].wpnts[-1].s_m == exported['length_m']
Path('/results/reader-cdr.json').write_text(json.dumps(dict(status='PASS', groups=9,
    H=case['H'], terminal_station=groups[5].wpnts[-1].s_m)) + '\n')
print(json.dumps(dict(status='PASS', validated_hosted_products=len(outcomes),
                     S6_reader_CDR='PASS', expected_H_source='controlled hosted compile receipts')))
