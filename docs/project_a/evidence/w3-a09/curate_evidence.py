"""Preserve the exact-candidate A09 run and separate exploratory preflight evidence."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess


ROOT = Path('/workspace/race_stack')
CANDIDATE = '531667abc0ad38236ec46825a544a3644c324b4f'
FRESH = ROOT / 'work/w3/a09-fresh'
OUT = FRESH / 'verification'
DEST = ROOT / 'docs/project_a/evidence/w3-a09'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def copy_file(source, relative):
    target = DEST / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def artifact_record(directory, scope):
    receipt = load(directory / 'compile.json')
    assert receipt['status'] == 'PASS'
    identity = receipt['H']
    reference = directory / 'references' / identity / 'reference.json'
    envelope = load(reference)
    canonical = json.dumps(envelope['payload'], sort_keys=True, separators=(',', ':'),
                           ensure_ascii=False, allow_nan=False).encode()
    assert hashlib.sha256(canonical).hexdigest() == envelope['H'] == identity
    curve = envelope['payload']['approved_curve_digest']
    assert curve == receipt['geometry']['curve_digest'] == receipt['dynamics']['curve_digest']
    return {'scope': scope, 'H': identity, 'curve_digest': curve,
            'model_digest': envelope['payload']['speed_profile']['model_digest'],
            'file_sha256': sha(reference), 'file': str(reference.relative_to(DEST)),
            'trusted_identity_source': 'Controlled successful installed compile receipt',
            'compile_receipt': str((directory / 'compile.json').relative_to(DEST))}


for path in (FRESH / 'fresh-exit-code.txt', OUT / 'exit-code.txt',
             OUT / 'source-free/exit-code.txt'):
    assert path.read_text().strip() == '0', path
assert (FRESH / 'candidate.txt').read_text().strip() == CANDIDATE
assert (OUT / 'source-hashes-before.json').read_bytes() == (
    OUT / 'source-hashes-after.json').read_bytes()
head = subprocess.check_output(['git', '-C', str(FRESH / 'checkout'),
                                'rev-parse', 'HEAD'], text=True).strip()
dirty = subprocess.check_output(['git', '-C', str(FRESH / 'checkout'),
                                 'status', '--porcelain'], text=True).strip()
assert head == CANDIDATE and not dirty
build = load(OUT / 'source-free/results/build-identity.json')
assert build['source_commit'] == CANDIDATE and build['source_dirty'] is False
assert len(build['gitlinks']) == 7
assert not DEST.exists()
DEST.mkdir(parents=True)

for name in ('candidate.txt', 'fresh-exit-code.txt', 'setup.log'):
    copy_file(FRESH / name, Path('fresh') / name)
copy_file(ROOT / 'work/w3/a09-fresh-console.log', 'fresh/console.log')
for path in sorted(OUT.iterdir()):
    if path.is_file():
        copy_file(path, Path('verification') / path.name)
for package in ('frenet_conversion', 'global_planner'):
    copy_file(OUT / 'build' / package / 'pytest.xml',
              Path('verification/legacy-junit') / (package + '.xml'))
shutil.copytree(OUT / 'w3-installed', DEST / 'verification/w3-installed')
shutil.copytree(OUT / 'source-free', DEST / 'source-free')
shutil.copytree(OUT / 'install/global_planner/share/global_planner/project_a',
                DEST / 'installed-inputs')

preflight = ROOT / 'work/w3/a09-preflight'
for name in ('provenance.json', 'summary.json', 'image-id.txt', 'runtime.log',
             'guards.log', 'guards-retry.log'):
    copy_file(preflight / name, Path('exploratory-preflight') / name)
shutil.copytree(preflight / 'runtime-results', DEST / 'exploratory-preflight/runtime-results')
shutil.copytree(preflight / 'harness', DEST / 'exploratory-preflight/harness')
for name in ('guard-results', 'guard-results-retry'):
    copy_file(preflight / name / 'guard-preflight.xml',
              Path('exploratory-preflight') / name / 'guard-preflight.xml')
audit = ROOT / 'work/w3/final-scope-audit.json'
assert sha(audit) == '1e586ac167267f4cb3a589c5e05dbadd7135f75987a9c00a985715c0ac2c1e7d'
copy_file(audit, 'final-scope-audit.json')
copy_file(ROOT / 'work/w3/a09-legacy-diagnostic-comparison.json',
          'legacy-diagnostic-comparison.json')
hosted_zip = ROOT / 'work/w3/a09-candidate-ci.zip'
assert sha(hosted_zip) == '764a255ec0cad9456805e1480f9b30dab81823393a4f05014821b4c059f62595'
copy_file(hosted_zip, 'hosted-ci/original-artifact.zip')
copy_file(ROOT / 'work/w3/a09-candidate-ci-run.json', 'hosted-ci/run.json')
hosted = ROOT / 'work/w3/a09-candidate-ci'
for name in ('summary.json', 'source-identity.txt', 'source-hashes-before.json',
             'source-hashes-after.json', 'image-id.txt', 'build-identity.json',
             'dependencies.txt', 'legacy-identity-comparison.json'):
    copy_file(hosted / name, Path('hosted-ci') / name)
for name in ('runtime-identity.json', 'build-identity.json', 'w3-scenario-campaign.json',
             'w3-installed.json', 'w3-source-free.xml'):
    copy_file(hosted / 'source-free/results' / name, Path('hosted-ci/source-free') / name)
copy_file(Path(__file__), 'curate_evidence.py')

results = DEST / 'source-free/results'
campaign = load(results / 'w3-scenario-campaign.json')
assert campaign['source_commit'] == CANDIDATE and len(campaign['outcomes']) == 9
assert all(case['status'] == 'PASS' for case in campaign['outcomes'])
hosted_run = load(DEST / 'hosted-ci/run.json')
assert hosted_run['headSha'] == CANDIDATE and hosted_run['conclusion'] == 'success'
hosted_campaign = load(DEST / 'hosted-ci/source-free/w3-scenario-campaign.json')
hosted_cases = {case['case']: case for case in hosted_campaign['outcomes']}
cross_host = [{'case': case['case'], 'local_H': case['H'],
               'hosted_H': hosted_cases[case['case']]['H'],
               'identical': case['H'] == hosted_cases[case['case']]['H']}
              for case in campaign['outcomes']]
assert len(cross_host) == 9 and all(case['identical'] for case in cross_host)
records = [artifact_record(results / 'w3-installed', 'Installed S0 trust/mutation suite')]
sourceful_receipt = load(OUT / 'w3-installed/compile.json')
assert sourceful_receipt['H'] == records[0]['H']
for case in campaign['outcomes']:
    records.append(artifact_record(results / 'w3-scenarios' / case['case'], case['case']))
commands = load(results / 'w3-installed.json')['commands']
negative = [command for command in commands if command['status'] != 'PASS']
assert len(commands) == 21 and len(negative) == 15
summary = load(DEST / 'verification/summary.json')
counts = {key: sum(int(value[key]) for value in summary.values()
                   if isinstance(value, dict) and 'tests' in value)
          for key in ('tests', 'failures', 'errors', 'skipped')}
assert counts['failures'] == counts['errors'] == counts['skipped'] == 0
index = {'schema_version': 1, 'candidate_commit': CANDIDATE, 'candidate_dirty': False,
         'checkpoints': {'A07': '0c2d7c35fc50051a2ae96b9260de636610e280f4',
                         'A08': '6a3295753235889389be1374ce1195435afb7b74',
                         'A09': CANDIDATE},
         'accepted_w2': 'fe53365f86d660b4f6d4389925f9810cf33d41b3',
         'accepted_w2_merge_base': '9fae5faed6ca62e0c943b6290babc50638477d9b',
         'scope': 'Fresh recursive exact-candidate W0-W3 and separate source-free install',
         'independent_w3_adversarial_review': 'REQUIRED',
         'image_id': (DEST / 'verification/image-id.txt').read_text().strip(),
         'functional_junit_totals': counts, 'source_manifest_entry_count': len(
             load(DEST / 'verification/source-hashes-before.json')),
         'sourceful_sourcefree_S0_identity_equal': sourceful_receipt['H'] == records[0]['H'],
         'gitlinks': build['gitlinks'], 'artifacts': records,
         'source_free_scenarios': campaign['outcomes'],
         'S6_benchmark_curve_digest':
             '5246eda31c757ae728c7ba9deb03a40569590dd296a941aaacbaf15af2ac58da',
         'S6_installed_curve_matches_benchmark': next(
             record['curve_digest'] for record in records
             if record['scope'] == 's6_competition_route') ==
             '5246eda31c757ae728c7ba9deb03a40569590dd296a941aaacbaf15af2ac58da',
         'hosted_ci': {'run': hosted_run['url'], 'headSha': hosted_run['headSha'],
                       'conclusion': hosted_run['conclusion'],
                       'original_artifact_sha256': sha(hosted_zip),
                       'cross_host_nine_scenario_H_comparison': cross_host},
         'runtime_path_mapping': '/results maps to source-free/results; preflight /results '
             'maps separately to exploratory-preflight/runtime-results',
         'installed_cli_command_count': len(commands), 'negative_control_count': len(negative),
         'negative_controls': negative,
         'legacy': load(DEST / 'verification/legacy-identity-comparison.json'),
         'legacy_style_diagnostics': load(DEST / 'legacy-diagnostic-comparison.json'),
         'exploratory_preflight': 'Retained dirty A07 prefix; original noexec red guard run '
             'and explicit executable-scratch green retry are separate from clean acceptance',
         'downstream_trust': 'Artifact self-hash and stored PASS are insufficient; retain '
             'the controlled compile H independently and select supported external context',
         'limitations': 'Synthetic planar offline software only; no physical operation, '
             '3D clearance, tire/contact, localization, tracking or safety approval'}
(DEST / 'index.json').write_text(json.dumps(index, indent=2) + '\n')
(DEST / 'README.md').write_text(f'''# A09 exact-candidate evidence

The fresh recursive checkout at `{CANDIDATE}` completed setup, all project
verification groups and a separate source-free installed-runtime container.
The checkout was clean before setup, after setup and after verification. The
installed build manifest records the same exact commit and `source_dirty=false`.
Independent W3 adversarial review is still required.

`index.json` maps each controlled compile receipt to its retained immutable
reference and curve identity. The source-free suite contains the S0 trust and
mutation product plus nine scenario products, including S4 repeated occurrences
and the S6 0.52 m optimization policy. `source-free/results` preserves each
compile, new-process revalidation, query, API probe, export, actual legacy-reader
and generated-message CDR roundtrip acceptance. Its installed S0 matrix has 21
CLI subprocesses, including 15 rejected content/trust controls with asserted
reasons. The functional JUnit total is {counts['tests']}, with zero failures,
errors or skips. Legacy raw results and both actual package JUnit files are
retained separately with the exact inherited-ten comparison and two copyright
skips; inherited red tests are not counted as functional passes.

`installed-inputs` is copied from the installed share directory actually used.
It includes the route/model/policy resources and generated build identity.
`source-free/launch.json` records intended isolation; runtime assertions and
`source-free/results/runtime-identity.json` verify actual nonroot, capability,
network, absent-source/build and read-only filesystem facts. Runtime `/results`
paths in receipts map to this directory's `source-free/results`.

`hosted-ci` preserves the original artifact ZIP and exact-head metadata for
GitHub Actions run 38926539747, plus its summaries, identities and runtime
results. The local fresh run and hosted run produced identical H values for all
nine scenario products. This is measured reproducibility on these two pinned
hosts; no cross-architecture binary identity guarantee is inferred.

`exploratory-preflight` is explicitly separate evidence from the older dirty A07
installed prefix. Its original guard run failed because Docker's `/tmp` tmpfs
was noexec. The retry used executable scratch and passed three guards. The final
sourceful runner also selects executable scratch explicitly. The corrected
installed mutation tests passed before the fresh run, using valid per-attack
`reference.json` paths and intended parse/hash/policy/replay reasons.

`files-sha256.json` hashes every other retained evidence file. These checksums,
an artifact's embedded H and stored PASS reports do not authorize an incoming
reference. A consumer must retain its externally trusted expected H and select
an independently supported validation context, then rerun the loader's checks.
The preserved trusted H values originate from the controlled compile receipts.

This evidence covers synthetic planar offline software behavior under declared models.
It does not authorize physical operation or establish real-course geometry,
3D clearance, contact/tire behavior, localization, controller tracking or safety.
''')
ledger = {str(path.relative_to(DEST)): sha(path) for path in sorted(DEST.rglob('*'))
          if path.is_file()}
(DEST / 'files-sha256.json').write_text(json.dumps(ledger, indent=2, sort_keys=True) + '\n')
print(json.dumps({'candidate': CANDIDATE, 'functional': counts, 'artifacts': len(records),
                  'files': len(ledger), 'evidence': str(DEST)}, indent=2))
