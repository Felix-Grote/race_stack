"""Audit an already downloaded exact-merge CI ZIP; no network or product execution."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import stat
import subprocess
import sys
import zipfile

HOME = Path(__file__).resolve().parent
MERGE = '4bfcf35fcc08a80abbe72bdbc294cf3400e99df2'
ACCEPTED = 'b961d20ce4a803e55336fb5590c30574e23b2fad'
TREE = 'c15b269c58ff82a12f6fae6c2481a56ce317f9fb'
RUN = 39302290392
ARCHIVE = '4b222ff37101c72d79cd6da0467a562214817d79'
CASES = {'s0_route', 's0_reverse_route', 's0_rotated_route', 's2_upper_route',
         's2_lower_route', 's3_surfaces_route', 's3_notch_route',
         's4_repeated_route', 's6_competition_route'}
SKIPS = {'frenet_conversion.test.test_copyright test_copyright',
         'global_planner.test.test_copyright test_copyright'}
sha = lambda raw: hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-json', required=True, type=Path)
    parser.add_argument('--artifacts-json', required=True, type=Path)
    parser.add_argument('--zip', required=True, type=Path)
    parser.add_argument('--git-repository', default='/workspace/forza-w3-audit')
    parser.add_argument('--output', default=str(HOME / 'completed'), type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    assert HOME in output.parents and not output.exists(), 'Use an absent closure subdirectory'
    acceptance = json.loads((HOME / 'prepared-inputs/W3_ACCEPTANCE.json').read_bytes())
    assert acceptance['verdict'] == 'ACCEPT' and acceptance['accepted_source'] == ACCEPTED
    assert acceptance['accepted_tree'] == TREE
    readback = json.loads((HOME / 'prepared-inputs/remote-archive-readback.json').read_bytes())
    assert readback['status'] == 'PASS' and readback['archive_commit'] == ARCHIVE

    def git(*words):
        return subprocess.check_output(['git', '-C', args.git_repository, *words])

    # These are read-only object queries, never fetch/checkout/update operations.
    assert git('rev-parse', MERGE + '^{tree}').decode().strip() == TREE
    assert git('rev-parse', ACCEPTED + '^{tree}').decode().strip() == TREE
    parents = git('show', '-s', '--format=%P', MERGE).decode().split()
    assert parents == ['9fae5faed6ca62e0c943b6290babc50638477d9b', ACCEPTED]
    run_raw, api_raw, blob = (p.read_bytes() for p in
                              (args.run_json, args.artifacts_json, args.zip))
    run, api = json.loads(run_raw), json.loads(api_raw)
    assert run['id'] == RUN and run['head_sha'] == MERGE
    assert (run['event'], run['status'], run['conclusion'], run['run_attempt']) == (
        'push', 'completed', 'success', 1)
    assert run['repository']['full_name'] == 'Felix-Grote/race_stack'
    assert len(api['artifacts']) == 1 and api['total_count'] == 1
    artifact = api['artifacts'][0]
    assert artifact['workflow_run']['id'] == RUN
    assert artifact['workflow_run']['head_sha'] == MERGE and not artifact['expired']
    assert artifact['digest'] == 'sha256:' + sha(blob)
    assert artifact['size_in_bytes'] == len(blob)
    # The inherited byte/provenance auditor is frozen from the accepted-source
    # audit. It resolves Git and recursive gitlink objects, without imports of
    # product modules or numerical runtimes, and writes only into this output.
    output.mkdir()
    for name, raw in [('push-run.json', run_raw), ('push-artifacts.json', api_raw),
                      ('original-push.zip', blob)]:
        (output / name).write_bytes(raw)
    checked = subprocess.run(
        [sys.executable, str(HOME / 'audit_hosted_inherited.py'), '--directory',
         str(output), '--sha', MERGE, '--repository', args.git_repository],
        capture_output=True, text=True)
    (output / 'inherited-audit-console.json').write_text(json.dumps(
        dict(exit_code=checked.returncode, stdout=checked.stdout, stderr=checked.stderr),
        indent=2) + '\n')
    assert checked.returncode == 0, checked.stderr
    hosted = json.loads((output / 'hosted-audit.json').read_bytes())
    assert hosted['PASS'] and hosted['implementation'] == MERGE
    assert (hosted['tests'], hosted['groups']) == (612, 27)
    assert (hosted['source_hashes_equal_literal_git'],
            hosted['installed_resources_exact_Git'],
            hosted['dependency_locks_exact_Git'],
            hosted['recursive_gitlinks_exact_Git']) == (138, 21, 2, 7)
    assert len(hosted['source_free_runtime']['modules']) == 10

    with zipfile.ZipFile(args.zip) as archive:
        # No extraction occurs; names, CRCs, special types, duplicates and safe
        # member paths were checked by the inherited audit before any use.
        assert all(stat.S_IFMT(item.external_attr >> 16) in
                   (0, stat.S_IFREG, stat.S_IFDIR) for item in archive.infolist())
        files = {name: archive.read(name) for name in archive.namelist()
                 if not name.endswith('/')}
    summary = json.loads(files['summary.json'])
    xml = {('source-free/results/w3-source-free.xml' if label == 'w3-source-free'
            else label + '.xml') for label, value in summary.items()
           if isinstance(value, dict) and 'tests' in value}
    assert xml == {name for name in files if name.endswith('.xml')}
    assert len(xml) == 27 and int(summary['w3-source-free']['tests']) == 5
    assert files['exit-code.txt'] == b'0\n'
    legacy = json.loads(files['legacy-identity-comparison.json'])
    raw_legacy = files['legacy-results.txt']
    baseline = git('show', MERGE + ':docs/project_a/evidence/pinned-run/legacy-results.txt.gz')
    failures = lambda raw: re.findall(r'^- ([^\n]+)\n  <<< failure message',
                                      raw.decode(), re.MULTILINE)
    assert sha(raw_legacy) == legacy['actual_sha256']
    assert sha(baseline) == legacy['baseline_sha256']
    assert failures(raw_legacy) == failures(gzip.decompress(baseline)) == legacy['actual']
    assert legacy['actual'] == legacy['baseline'] and len(legacy['actual']) == 10
    assert re.findall(r'^Summary: (\d+) tests?, (\d+) errors?, (\d+) failures?, '
                      r'(\d+) skipped\s*$', raw_legacy.decode(), re.MULTILINE) == [
                          ('597', '0', '10', '2')]
    assert files['legacy-exit-codes.txt'] == b'colcon_test=1\ncolcon_test_result=1\n'
    assert {item['identity'] for item in legacy['skips']} == SKIPS
    assert all(item['reason'] == 'No copyright header has been placed in the generated source file.'
               for item in legacy['skips'])

    campaign = json.loads(files['source-free/results/w3-scenario-campaign.json'])
    assert campaign['source_commit'] == MERGE
    outcomes = campaign['outcomes']
    assert len(outcomes) == 9 and {item['case'] for item in outcomes} == CASES
    assert sum(item['query_count'] for item in outcomes) == 1488
    assert sum(len(item['commands']) for item in outcomes) == 36
    assert len({item['H'] for item in outcomes}) == 9
    build = json.loads(files['build-identity.json'])
    canonical_build = json.dumps(build, sort_keys=True, separators=(',', ':'),
                                 allow_nan=False).encode()
    for item in outcomes:
        assert [command['command'][1] for command in item['commands']] == [
            'compile', 'validate', 'query', 'export']
        assert item['status'] == item['geometry'] == item['dynamics'] == 'PASS'
        assert all(command['returncode'] == 0 and command['status'] == 'PASS'
                   for command in item['commands'])
        for command in item['commands']:
            for stream in ('stdout', 'stderr'):
                relative = 'source-free/results/' + command[stream].removeprefix('/results/')
                assert relative in files
        assert item['fixture_sha256'] == build['installed_resource_hashes'][
            'fixtures/' + item['case'] + '.json']
        assert item['model_sha256'] == build['installed_resource_hashes'][
            'models/' + item['case'] + '_model.json']
        policy_command = item['commands'][0]['command']
        policy_path = policy_command[policy_command.index('--policy') + 1]
        assert item['policy_sha256'] == build['installed_resource_hashes'][
            policy_path.removeprefix('/work/install/global_planner/share/global_planner/project_a/')]
        reference = ('source-free/results/w3-scenarios/' + item['case']
                     + '/references/' + item['H'] + '/reference.json')
        payload = json.loads(files[reference])['payload']
        provenance = payload['provenance']
        assert provenance['source_commit'] == MERGE
        assert provenance['build_manifest_sha256'] == sha(canonical_build)
        assert json.loads(provenance['gitlinks']) == build['gitlinks']
        module_hashes = payload['implementation']['module_sha256']
        assert len(module_hashes) == 11
        for module, digest in module_hashes.items():
            assert sha(git('show', MERGE + ':planner/global_planner/global_planner/'
                           + module + '.py')) == digest
    assert [{'case': item['case'], 'status': item['status'], 'H': item['H']}
            for item in outcomes] == summary['source_free_scenarios']
    launch = hosted['source_free_launch']
    runtime = hosted['source_free_runtime']
    assert launch['network'] == 'none' and launch['source_or_build_mounts'] == []
    assert set(launch['readonly_mounts']) == {
        '/work/install', '/work/python', '/runtime-harness'}
    assert runtime['uid'] != 0 and runtime['cap_eff'] == '0000000000000000'
    assert str(runtime['no_new_privileges']) == '1'
    installed = json.loads(files['source-free/results/w3-installed.json'])
    assert installed['source_free'] and installed['source_commit'] == MERGE
    assert not installed['source_dirty'] and installed['gitlinks'] == build['gitlinks']

    bindings = [{'case': item['case'], 'H': item['H'],
                 'curve_digest': item['curve_digest'],
                 'artifact_sha256': item['artifact_sha256']}
                for item in hosted['controlled_catalog']]
    report = dict(
        status='PASS', merge_commit=MERGE, accepted_source=ACCEPTED,
        tree=TREE, merge_tree_identical_to_accepted_source=True,
        merge_parents=parents, run_id=RUN, run_url=run['html_url'],
        artifact_id=artifact['id'], artifact_name=artifact['name'],
        original_zip_bytes=len(blob), original_zip_sha256=sha(blob),
        functional_tests=612, functional_groups=27,
        functional_failures_errors_skips=0,
        inherited_legacy_failures=10, inherited_copyright_skips=2,
        legacy_status='EXPECTED_FAILURES_RETAINED', legacy_raw_summary=[597, 0, 10, 2],
        source_free_tests=5, source_free_scenarios=9, source_free_queries=1488,
        source_free_scenario_cli_commands=36,
        literal_source_hashes=138, installed_resource_hashes=21,
        dependency_locks=2, recursive_gitlinks=7, installed_module_origins=10,
        source_before_after_equal=True, trusted_producer_validator_H_C_bindings=bindings,
        initial_archive_commit=ARCHIVE,
        archive_append_publication_status='PENDING_ROOT_PUBLICATION_AND_REMOTE_READBACK',
        scope='Exact research merge CI byte/provenance closure. Fresh H values bind actual '
              'merge identity; no H equality to accepted-source builds is required. '
              'No new numerical replay, production acceptance or physical claim.')
    (output / 'closure.json').write_text(json.dumps(report, indent=2) + '\n')
    text = (
        '# Research merge CI audit\n\n'
        f'PASS: research merge `{MERGE}` has tree `{TREE}`, identical to accepted '
        f'`{ACCEPTED}`. Exact push run [{RUN}]({run["html_url"]}) completed successfully; '
        f'its authenticated original artifact `{artifact["id"]}` is {len(blob):,} bytes, '
        f'SHA-256 `{sha(blob)}`.\n\n'
        'All 612 functional tests across 27 groups passed without errors or skips. '
        'The ten inherited legacy failures and two copyright skips remain separately '
        'retained as failures/skips. Source-free verification includes five tests, '
        'nine scenarios, 1,488 queries and 36 scenario CLI calls. Literal provenance '
        'checks bind 138 source hashes, 21 resources, two locks, seven recursive '
        'gitlinks, ten installed module origins and nine producer/validator H/C pairs.\n\n'
        'The research acceptance source tag remains unchanged. This audit does not '
        'claim H equality across separately identified builds, new numerical replay, '
        'production acceptance or physical validation. Archive append publication '
        'and new remote readback remain pending root action.\n')
    (output / 'REPORT.md').write_text(text)
    members = []
    for path in sorted(output.rglob('*')):
        if path.is_dir():
            continue
        assert path.is_file() and not path.is_symlink()
        raw = path.read_bytes()
        members.append(dict(path=str(path.relative_to(output)), bytes=len(raw), sha256=sha(raw)))
    (output / 'append-inventory.json').write_text(json.dumps(dict(
        status='READY_FOR_ROOT_ARCHIVE_APPEND', files=members,
        include_inventory_itself=True,
        destination='docs/project_a/evidence/w3-independent-final/research-merge-closure/completed',
        exclusion='Reconstructible worktrees/build/install/dependencies are not selected.'),
        indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
