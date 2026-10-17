"""Run the broader installed scenario handoff in the separate runtime container."""
import json
import os
from pathlib import Path
import subprocess
import sys

from test_w3_installed import _canonical, _hash, _inputs, _invoke


_CASES = ('s0_route', 's0_reverse_route', 's0_rotated_route', 's2_upper_route',
          's2_lower_route', 's3_surfaces_route', 's3_notch_route', 's4_repeated_route',
          's6_competition_route')


def test_installed_w3_scenario_campaign():
    """Compile, reload, query and export every installed supported synthetic case."""
    assert os.environ.get('PROJECT_A_SOURCE_FREE') == '1'
    share, manifest, executable = _inputs()
    output = Path('/results/w3-scenarios')
    output.mkdir()
    s4 = share / 'fixtures/s4_repeated_route.json'
    outcomes = []
    for name in _CASES:
        case_output = output / name
        case_output.mkdir()
        state = {'share': share, 'manifest': manifest, 'executable': executable,
                 'output': case_output, 'commands': []}
        outcome = {'case': name, 'commands': state['commands']}
        try:
            route = share / ('fixtures/' + name + '.json')
            model = share / ('models/' + name + '_model.json')
            policy = share / ('policies/s6_coarse_policy.json' if name == 's6_competition_route'
                              else 'policies/synthetic_policy.json')
            if name == 's6_competition_route':
                expected = json.loads((share / 'policies/synthetic_policy.json').read_text())
                expected['solver']['spacing_m'] = .52
                assert _canonical(expected) == _canonical(json.loads(policy.read_text()))
            for path in (route, model, policy):
                key = str(path.relative_to(share))
                assert _hash(path) == manifest['installed_resource_hashes'][key]
            compiled = _invoke(state, 'compile', (
                'compile', '--manifest', route, '--vehicle-config', model,
                '--policy', policy, '--build-manifest', share / 'build_identity.json',
                '--output', case_output / 'references'))
            trusted_h = compiled['H']
            artifact = Path(compiled['artifact_path'])
            common = ('--artifact', artifact, '--expected-h', trusted_h, '--policy', policy)
            validated = _invoke(state, 'validate', ('validate', *common))
            assert validated['geometry']['status'] == validated['dynamics']['status'] == 'PASS'
            queried = _invoke(state, 'query', ('query', *common, '--s-m', -.137), query=True)
            assert queried['sample']['speed_mps'] > 0
            probe = subprocess.run(
                [sys.executable, '/runtime-harness/w3_query_probe.py',
                 str(artifact), trusted_h, str(policy)], capture_output=True,
                text=True, timeout=240, check=False)
            (case_output / 'public-api.stdout.txt').write_text(probe.stdout)
            (case_output / 'public-api.stderr.txt').write_text(probe.stderr)
            assert probe.returncode == 0, probe.stderr
            api = json.loads(probe.stdout)
            assert api['status'] == 'PASS' and api['H'] == trusted_h
            exported = _invoke(state, 'export', (
                'export', *common, '--step-m', .5, '--output', case_output / 'legacy'))
            from global_planner.readwrite_global_waypoints import read_global_waypoints
            from rclpy.serialization import deserialize_message, serialize_message
            from rosidl_runtime_py.convert import message_to_ordereddict
            groups = read_global_waypoints(str(Path(exported['output_path']).parent))
            assert len(groups) == 9
            for message in groups:
                decoded = deserialize_message(serialize_message(message), type(message))
                assert message_to_ordereddict(decoded) == message_to_ordereddict(message)
            assert groups[5].wpnts[-1].s_m == exported['length_m']
            outcome.update(status='PASS', H=trusted_h, artifact_path=str(artifact),
                           geometry=validated['geometry']['status'],
                           dynamics=validated['dynamics']['status'],
                           owner_samples=api['owner_samples'], query_count=api['samples'],
                           policy_sha256=_hash(policy), model_sha256=_hash(model),
                           fixture_sha256=_hash(route),
                           curve_digest=validated['geometry']['curve_digest'],
                           length_m=exported['length_m'], lap_time_s=exported['lap_time_s'],
                           waypoint_count=exported['waypoint_count'])
        except (AssertionError, OSError, ValueError, subprocess.SubprocessError) as error:
            outcome.update(status='FAIL', reason=type(error).__name__ + ': ' + str(error))
        outcomes.append(outcome)
        Path('/results/w3-scenario-campaign.json').write_text(json.dumps({
            'source_commit': manifest['source_commit'], 'outcomes': outcomes,
            'S4_installed_resource': 'AVAILABLE' if s4.is_file() else 'UNAVAILABLE',
            'scope': 'Installed synthetic planar software, no physical acceptance',
        }, indent=2) + '\n')
    assert all(outcome['status'] == 'PASS' for outcome in outcomes), outcomes
