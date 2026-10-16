"""Independently bind a completed push artifact to exact Git and legacy identities."""
import hashlib
import gzip
import json
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile


def git(*args):
    return subprocess.check_output(['git', *args])


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


def failure_ids(path):
    text = gzip.decompress(path.read_bytes()).decode() if path.suffix == '.gz' else path.read_text()
    return re.findall(r'^- (.+)\n  <<< failure message', text, re.M)


archive, output, ref = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
baseline = Path('docs/project_a/evidence/w2-baseline/legacy-results.txt.gz')
output.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(archive) as zipped:
    assert all(not Path(n).is_absolute() and '..' not in Path(n).parts
               for n in zipped.namelist())
    zipped.extractall(output)
assert (output / 'source-identity.txt').read_text().splitlines()[0] == ref
assert (output / 'exit-code.txt').read_text().strip() == '0'
runtime = json.loads((output / 'runtime-identity.json').read_text())
assert runtime['python'] == '3.10.12' and runtime['ros_distro'] == 'humble'
assert runtime['uid'] != 0 and runtime['cap_eff'] == '0000000000000000'
assert runtime['no_new_privs'] == '1' and runtime['root_and_source_readonly']
assert runtime['interfaces'] == [[1, 'lo']]
dependencies = set((output / 'dependencies.txt').read_text().splitlines())
assert {'numpy==1.26.4', 'scipy==1.11.4', 'quadprog==0.1.7',
        'trajectory-planning-helpers==0.79'} <= dependencies
before = json.loads((output / 'source-hashes-before.json').read_text())
assert before == json.loads((output / 'source-hashes-after.json').read_text())
submodule = 'planner/global_planner/global_planner/global_racetrajectory_optimization'
pin = git('rev-parse', ref + ':' + submodule).decode().strip()
for name, expected in before.items():
    if name.startswith(submodule + '/'):
        data = git('-C', submodule, 'show', pin + ':' + name[len(submodule) + 1:])
    else:
        data = git('show', ref + ':' + name)
    assert hashlib.sha256(data).hexdigest() == expected, name
summary = json.loads((output / 'summary.json').read_text())
groups = {k: v for k, v in summary.items() if isinstance(v, dict) and 'tests' in v}
for kind, counts in groups.items():
    assert all(int(counts[x]) == 0 for x in ('failures', 'errors', 'skipped'))
    root = ET.parse(output / (kind + '.xml')).getroot()
    suite = root.find('testsuite') if root.tag != 'testsuite' else root
    assert all(int(suite.attrib[x]) == int(counts[x]) for x in counts)
baseline_ids = failure_ids(baseline)
actual_ids = failure_ids(output / 'legacy-results.txt')
assert len(baseline_ids) == 10 and actual_ids == baseline_ids
pipeline = json.loads((output / 'w2-pipeline.json').read_text())
for name, case in pipeline['scenarios'].items():
    authority = digest({'coefficients': case['coefficients'], 'q': case['q'],
                        'owners': case['owners'], 'route_digest': case['route_sha256'],
                        'numeric_policy': case['numeric_policy']})
    assert case['expected_curve_digest'] == authority, name
    assert case['geometry']['status'] == case['dynamics']['status'] == 'PASS'
    assert case['geometry']['curve_digest'] == case['dynamics']['curve_digest'] == authority
    profile = case['retimer']['profile']
    assert profile['curve_digest'] == authority
    assert profile['model_digest'] == digest(case['model'])
    assert case['retimer']['metadata']['curve_digest'] == authority
installed = json.loads((output / 'w2-installed.json').read_text())
for name, record in installed['modules'].items():
    source = 'planner/global_planner/global_planner/' + name.rsplit('.', 1)[-1] + '.py'
    assert record['sha256'] == before[source]
novel_verified = False
if (output / 'w2-novel-pipeline.json').exists():
    novel = json.loads((output / 'w2-novel-pipeline.json').read_text())
    # The novel test uses the same explicit default NumericPolicy; bind that
    # documented policy to the actual exported fields and trusted digest too.
    policy = next(iter(pipeline['scenarios'].values()))['numeric_policy']
    authority = digest({'coefficients': novel['actual_coefficients'], 'q': novel['q'],
                        'owners': novel['owners'], 'route_digest': novel['route_digest'],
                        'numeric_policy': policy})
    assert novel['expected_curve_digest'] == authority
    assert novel['geometry']['status'] == novel['dynamics']['status'] == 'PASS'
    assert novel['geometry']['curve_digest'] == novel['dynamics']['curve_digest'] == authority
    assert novel['retimer']['profile']['curve_digest'] == authority
    assert novel['retimer']['profile']['model_digest'] == digest(novel['model'])
    novel_verified = True
record = {'exact_head': ref, 'artifact_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
          'functional_tests': sum(int(v['tests']) for v in groups.values()),
          'functional_groups': len(groups), 'all_functional_zero_failures_errors_skips': True,
          'source_entries': len(before), 'source_manifest_stable_and_git_exact': True,
          'source_manifest_sha256': hashlib.sha256(
              (output / 'source-hashes-before.json').read_bytes()).hexdigest(),
          'legacy_exact_ten_identities': actual_ids,
          'legacy_summary': (output / 'legacy-results.txt').read_text().splitlines()[-1],
          'same_authority_pipeline_cases': list(pipeline['scenarios']),
          'installed_source_hashes_match': True, 'novel_same_authority_verified': novel_verified}
record['pinned_runtime_and_isolation_verified'] = True
(output / 'independent-artifact-verification.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps(record, indent=2))
