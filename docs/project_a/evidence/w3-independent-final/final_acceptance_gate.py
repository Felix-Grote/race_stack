"""Verify completed independent W3 release evidence; make no Git mutations."""
from pathlib import Path
import datetime
import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path('/workspace/forza-audit-records')
SHA = 'b961d20ce4a803e55336fb5590c30574e23b2fad'
REPO = ROOT / 'final-checkout'
OUT = ROOT / 'release-preparation'
inputs = {}


def bind(relative):
    path = ROOT / relative
    assert path.is_file() and not path.is_symlink(), path
    raw = path.read_bytes()
    inputs[relative] = {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
    return raw


def read(relative):
    return json.loads(bind(relative))


def command(*args):
    return subprocess.check_output(args, text=True).strip()


assert not (OUT / 'W3_ACCEPTANCE.json').exists(), 'Never replace an acceptance receipt'
assert command('git', '-C', str(REPO), 'rev-parse', 'HEAD') == SHA
assert command('git', '-C', str(REPO), 'status', '--porcelain') == ''
fresh = ROOT / 'fresh-b961d20-complete'
verification = fresh / 'verification'
for path in (fresh / 'fresh-exit-code.txt', verification / 'exit-code.txt',
             verification / 'source-free/exit-code.txt'):
    assert bind(str(path.relative_to(ROOT))).decode().strip() == '0', path
assert (verification / 'source-hashes-before.json').read_bytes() == (
    verification / 'source-hashes-after.json').read_bytes()
assert command('git', '-C', str(fresh / 'checkout'), 'rev-parse', 'HEAD') == SHA
assert command('git', '-C', str(fresh / 'checkout'), 'status', '--porcelain') == ''
summary = read('fresh-b961d20-complete/verification/summary.json')
groups = {name: value for name, value in summary.items()
          if isinstance(value, dict) and 'tests' in value}
assert len(groups) == 27
assert sum(int(value['tests']) for value in groups.values()) == 612
for name, value in groups.items():
    assert all(int(value[key]) == 0 for key in ('failures', 'errors', 'skipped'))
    path = verification / (name + '.xml')
    if name == 'w3-source-free':
        path = verification / 'source-free/results/w3-source-free.xml'
    suites = list(ET.parse(path).getroot().iter('testsuite'))
    for key in ('tests', 'failures', 'errors', 'skipped'):
        assert sum(int(suite.get(key, '0')) for suite in suites) == int(value[key])
    bind(str(path.relative_to(ROOT)))
campaign = read('fresh-b961d20-complete/verification/source-free/results/'
                'w3-scenario-campaign.json')
assert campaign['source_commit'] == SHA
expected_cases = {'s0_route', 's0_reverse_route', 's0_rotated_route', 's2_upper_route',
                  's2_lower_route', 's3_surfaces_route', 's3_notch_route',
                  's4_repeated_route', 's6_competition_route'}
assert len(campaign['outcomes']) == 9
assert {case['case'] for case in campaign['outcomes']} == expected_cases
assert all(case['status'] == case['geometry'] == case['dynamics'] == 'PASS'
           for case in campaign['outcomes'])
complete = read('final-runtime-b961d20/complete-audit.json')
assert complete['status'] == 'PASS' and complete['source_commit'] == SHA
assert complete['functional_tests'] == 612 and complete['functional_groups'] == 27
controls = read('final-runtime-b961d20/sourcefree-15-controls.json')
assert controls['status'] == 'PASS' and controls['source_free']
assert controls['source_commit'] == SHA and controls['command_count'] == 21
assert controls['negative_controls_checked'] == len(controls['controls']) == 15
assert all(row['status'] == 'PASS' and row['actual_reason'] for row in controls['controls'])
assert controls['accepted_artifact_unchanged']
ordinary_controls = read('final-runtime-b961d20/complete-15-controls.json')
assert ordinary_controls['status'] == 'PASS' and not ordinary_controls['source_free']
assert ordinary_controls['negative_controls_checked'] == 15
sourcefree_records = read('final-runtime-b961d20/sourcefree-record-audit.json')
assert sourcefree_records['status'] == 'PASS' and sourcefree_records['source_commit'] == SHA
assert sourcefree_records['source_free'] and sourcefree_records['scenario_count'] == 9
assert sourcefree_records['command_count'] == 36 and sourcefree_records['query_count'] > 0
assert sourcefree_records['sourcefree_negative_controls'] == controls['negative_controls_checked']
namespace = read('final-runtime-b961d20/actual-sourcefree-namespace-closure.json')
assert namespace['status'] == 'PASS' and namespace['source_commit'] == SHA
assert namespace['source_free'] and len(namespace['modules']) == 12
assert namespace['implementation_module_count'] == 11 and len(namespace['resources']) == 21
assert all(row['origin'].startswith('/work/install/') and row['not_symlink']
           for row in namespace['modules'])
legacy = read('final-runtime-b961d20/complete-legacy.json')
assert legacy['status'] == 'PASS' and len(legacy['failure_identities']) == 10
assert len(legacy['skips']) == 2 and legacy['no_added_or_removed_style_diagnostics']
assert legacy['exact_style_lines_including_repeats'] == 1173
isolation = read('final-runtime-b961d20/live-sourcefree-controls-audit.json')
assert isolation['status'] == 'PASS' and isolation['source_free']
assert isolation['mount_count'] == 4 and isolation['network'] == 'none'
assert isolation['implementation_module_count'] == 11 and isolation['actual_resources'] == 21
inspect = read('final-runtime-b961d20/actual-sourcefree-inspect.json')
assert sourcefree_records['actual_inspect_id'] == isolation['actual_container'] == inspect['Id']
assert sourcefree_records['image_id'] == isolation['image_id'] == inspect['Image']
assert namespace['manifest_sha256'] == hashlib.sha256(
    bind('fresh-b961d20-complete/verification/build-identity.json')).hexdigest()
hosted = read('final-evidence-b961d20/hosted-audit.json')
raw_hosted = read('final-evidence-b961d20/raw-hosted-audit.json')
benchmark = read('final-benchmarks/audit-final96.json')
for result in (hosted, raw_hosted, benchmark):
    assert result['PASS'] is True and result['implementation'] == SHA
for relative, result in (
        ('final-evidence-b961d20/original-push.zip', hosted),
        ('final-benchmarks/original-final96.zip', benchmark)):
    raw = bind(relative)
    assert len(raw) == result['zip_bytes']
    assert hashlib.sha256(raw).hexdigest() == result['zip_sha256']
assert benchmark['status_counts'] == {'PASS': 58, 'STOCK_PREPARATION_FAILURE': 28,
                                     'RESOURCE_LIMIT': 8, 'SOLVER_FAILURE': 2}
replay = read('final-runtime-b961d20/hosted-replay-audit.json')
assert replay['status'] == 'PASS' and replay['source_commit'] == SHA
for key in ('hosted_cases', 'actual_geometry_validator_calls',
            'actual_dynamics_validator_calls', 'actual_reader_CDR_exports'):
    assert replay[key] == 9
assert replay['unchanged_authenticated_inputs'] and replay['frozen_main_T_binary64_exact']
assert replay['frozen_main_T_Float32_exact'] and not replay['source_free']
numerical = read('resume-numerical/RESULTS.json')
assert all(code == 0 for code in numerical['commands_exit_codes'].values())
module = subprocess.check_output([
    'git', '-C', str(REPO), 'show',
    SHA + ':planner/global_planner/global_planner/route_artifact.py'])
assert hashlib.sha256(module).hexdigest() == numerical['route_artifact_sha256']
ci = {}
for run_id, event in ((39110306747, 'push'), (39110310707, 'pull_request')):
    result = json.loads(command('gh', 'api',
                                f'repos/Felix-Grote/race_stack/actions/runs/{run_id}'))
    assert result['status'] == 'completed' and result['conclusion'] == 'success'
    assert result['head_sha'] == SHA and result['event'] == event
    ci[str(run_id)] = {key: result[key] for key in
                       ('head_sha', 'event', 'status', 'conclusion', 'html_url', 'run_attempt')}
    snapshot = OUT / f'acceptance-ci-{run_id}.json'
    snapshot.write_text(json.dumps(result, indent=2) + '\n')
    bind(str(snapshot.relative_to(ROOT)))
# Bind the raw completed products and receipts, not merely their aggregate PASS.
# Source/build/install/dependency caches remain reproducible from the Git-bound manifest.
for path in sorted(fresh.iterdir()):
    if path.is_file():
        bind(str(path.relative_to(ROOT)))
for path in sorted(verification.iterdir()):
    if path.is_file():
        bind(str(path.relative_to(ROOT)))
for folder in ('source-free/harness', 'source-free/results'):
    for path in sorted((verification / folder).rglob('*')):
        assert not path.is_symlink(), path
        if path.is_file():
            bind(str(path.relative_to(ROOT)))
for path in sorted((ROOT / 'final-runtime-b961d20').iterdir()):
    if path.is_file():
        bind(str(path.relative_to(ROOT)))
receipt = {
    'verdict': 'ACCEPT', 'label': 'W3_RESEARCH_ACCEPTED', 'accepted_source': SHA,
    'accepted_tree': command('git', '-C', str(REPO), 'rev-parse', SHA + '^{tree}'),
    'recorded_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'functional_tests': 612, 'functional_groups': 27,
    'all_functional_failures_errors_skips': 0,
    'source_free_campaign_cases': sourcefree_records['scenario_count'],
    'source_free_negative_controls': controls['negative_controls_checked'],
    'hosted_unchanged_artifact_replays': 9,
    'final96_status_counts': benchmark['status_counts'], 'exact_head_ci': ci,
    'evidence_inputs': inputs,
    'scope': 'Explicit supported synthetic planar offline inputs and pinned runtime only',
    'limitations': ['S6 mesh/origin/scale sensitivity; no optimum or general robustness proof',
                    'Adapted legacy certificates do not approve raw/native legacy geometry',
                    'Existing metric inversion accuracy remains bounded, not arbitrary precision',
                    'No calibrated vehicle, real course, 3D/grade/contact, controller or driving validation'],
    'subsequent_obligations': ['Research archive publication and personal PR3 merge/CI',
                               'Current-upstream clean production extraction and verification',
                               'Independent production integration challenge',
                               'Reviewable upstream PR; no upstream auto-merge'],
}
(OUT / 'W3_ACCEPTANCE.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps({key: receipt[key] for key in
                  ('verdict', 'label', 'accepted_source', 'functional_tests', 'functional_groups')}))
