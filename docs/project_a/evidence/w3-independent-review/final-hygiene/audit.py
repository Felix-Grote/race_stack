#!/usr/bin/env python3
"""Read exact Git objects; quantify W3 source/evidence without changing them."""
import collections
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import subprocess

BASE = '9fae5faed6ca62e0c943b6290babc50638477d9b'
HEAD = '67fbcc8283e59649d38dc9318291634089df3741'
EVIDENCE = 'origin/w3-evidence-17e4ec4'
OUT = Path(__file__).resolve().parent


def git(*args):
    return subprocess.check_output(['git', *args])


def tree(ref):
    result = {}
    for record in git('ls-tree', '-r', '-z', '--long', ref).split(b'\0'):
        if record:
            meta, path = record.split(b'\t', 1)
            mode, kind, oid, size = meta.split()
            if kind == b'blob':
                result[path.decode()] = {'oid': oid.decode(), 'bytes': int(size)}
    return result


trees = {ref: tree(ref) for ref in (BASE, HEAD, EVIDENCE)}
oids = sorted({entry['oid'] for data in trees.values() for entry in data.values()})
batch = subprocess.check_output(
    ['git', 'cat-file', '--batch'], input=''.join(oid + '\n' for oid in oids).encode())
blobs = {}
stream = io.BytesIO(batch)
for oid in oids:
    actual, kind, size = stream.readline().split()
    assert actual.decode() == oid and kind == b'blob'
    blobs[oid] = stream.read(int(size))
    assert stream.read(1) == b'\n'


def category(path):
    if path.startswith('docs/project_a/evidence/'):
        return 'evidence'
    if path.startswith('planner/global_planner/global_planner/') and path.endswith('.py'):
        return 'production_python'
    if ('/test/' in path or '/tests/' in path) and path.endswith('.py'):
        return 'test_python'
    if path.startswith('scripts/project_a/'):
        return 'verification_benchmark_harness'
    if path.startswith('docs/'):
        return 'documentation'
    if path.startswith('planner/global_planner/config/project_a/'):
        return 'installed_fixtures_models_policies'
    return 'other_integration'


def metrics(paths, data):
    result = collections.Counter(files=0, bytes=0, text_files=0, physical_lines=0,
                                 nonblank_lines=0)
    for path in paths:
        raw = blobs[data[path]['oid']]
        result['files'] += 1
        result['bytes'] += len(raw)
        try:
            text = raw.decode('utf-8')
            if '\0' in text:
                continue
        except UnicodeDecodeError:
            continue
        result['text_files'] += 1
        result['physical_lines'] += len(text.splitlines())
        result['nonblank_lines'] += sum(bool(line.strip()) for line in text.splitlines())
    return dict(result)


numstats = []
for line in git('diff', '--numstat', BASE, HEAD).decode().splitlines():
    add, delete, path = line.split('\t', 2)
    numstats.append({'path': path, 'category': category(path),
                     'added': int(add) if add != '-' else None,
                     'deleted': int(delete) if delete != '-' else None})
changed = [n['path'] for n in numstats]
groups = collections.defaultdict(list)
for path in changed:
    groups[category(path)].append(path)
breakdown = {}
for group, paths in sorted(groups.items()):
    ns = [n for n in numstats if n['category'] == group]
    breakdown[group] = metrics([p for p in paths if p in trees[HEAD]], trees[HEAD])
    breakdown[group].update(added_lines=sum(n['added'] or 0 for n in ns),
                            deleted_lines=sum(n['deleted'] or 0 for n in ns),
                            binary_files=sum(n['added'] is None for n in ns))

evidence_paths = [p for p in changed if category(p) == 'evidence']
subgroups = collections.defaultdict(list)
for p in evidence_paths:
    subgroups[p.split('/')[3]].append(p)

new_modules = [p for p in changed if category(p) == 'production_python']
project_a_modules = [p for p in trees[HEAD]
                     if p.startswith('planner/global_planner/global_planner/')
                     and (PurePosixPath(p).name.startswith('route_') or
                          PurePosixPath(p).name in (
                              '_route_geometry.py', 'cyclic_retime.py', 'iqp_route_adapter.py'))
                     and p.endswith('.py')]
all_tests = [p for p in trees[HEAD] if category(p) == 'test_python'
             and (p.startswith('planner/global_planner/') or p.startswith('scripts/project_a/'))]

duplicate_groups = collections.defaultdict(list)
for p in evidence_paths:
    duplicate_groups[trees[HEAD][p]['oid']].append(p)
duplicates = sorted(
    [{'paths': paths, 'bytes_each': trees[HEAD][paths[0]]['bytes'],
      'redundant_bytes': trees[HEAD][paths[0]]['bytes'] * (len(paths) - 1)}
     for paths in duplicate_groups.values() if len(paths) > 1],
    key=lambda x: x['redundant_bytes'], reverse=True)

manifests = []
coverage = set()
for path in evidence_paths:
    if path.endswith('/SHA256SUMS') or path.endswith('/files-sha256.json'):
        raw = blobs[trees[HEAD][path]['oid']]
        if path.endswith('/SHA256SUMS'):
            entries = dict((line.split(maxsplit=1)[1].lstrip('*'), line.split()[0])
                           for line in raw.decode().splitlines() if line.strip())
        else:
            entries = json.loads(raw)
            if entries.get('algorithm') == 'sha256':
                entries = entries['files']
        failures = []
        parent = str(PurePosixPath(path).parent)
        for relative, expected in entries.items():
            target = str(PurePosixPath(parent) / relative)
            if target not in trees[HEAD]:
                failures.append({'path': relative, 'error': 'missing'})
            elif hashlib.sha256(blobs[trees[HEAD][target]['oid']]).hexdigest() != expected:
                failures.append({'path': relative, 'error': 'hash mismatch'})
            else:
                coverage.add(target)
        manifests.append({'path': path, 'entries': len(entries), 'failures': failures})

largest = sorted(evidence_paths, key=lambda p: trees[HEAD][p]['bytes'], reverse=True)
largest_text = sorted([p for p in evidence_paths if p.endswith('.json')],
                      key=lambda p: len(blobs[trees[HEAD][p]['oid']].splitlines()), reverse=True)
totals = {'changed_files': len(changed),
          'added_lines': sum(n['added'] or 0 for n in numstats),
          'deleted_lines': sum(n['deleted'] or 0 for n in numstats),
          'binary_changed_files': sum(n['added'] is None for n in numstats)}
result = {
    'reviewed_final_sha': HEAD, 'accepted_w2_merge': BASE,
    'companion_sha': git('rev-parse', EVIDENCE).decode().strip(),
    'method': 'Exact git ls-tree/cat-file objects; physical LOC counts splitlines; '
              'git diff --numstat line totals; bytes are uncompressed tracked blob sizes; '
              'gitlink contents excluded. Categories are mutually exclusive.',
    'totals': totals, 'diff_breakdown': breakdown,
    'new_production_modules': {p: metrics([p], trees[HEAD]) for p in new_modules},
    'all_project_a_production_modules': metrics(project_a_modules, trees[HEAD]),
    'all_project_a_production_module_paths': project_a_modules,
    'all_planner_and_harness_test_python': metrics(all_tests, trees[HEAD]),
    'new_test_python_paths': [p for p in changed if category(p) == 'test_python'],
    'evidence_subdirectories': {g: metrics(ps, trees[HEAD]) for g, ps in sorted(subgroups.items())},
    'all_evidence_baseline': metrics([p for p in trees[BASE]
                                    if category(p) == 'evidence'], trees[BASE]),
    'all_evidence_delivered_head': metrics([p for p in trees[HEAD]
                                        if category(p) == 'evidence'], trees[HEAD]),
    'companion_additional_evidence': metrics([p for p in trees[EVIDENCE]
                                            if p not in trees[HEAD]], trees[EVIDENCE]),
    'largest_evidence': [{'path': p, **metrics([p], trees[HEAD])} for p in largest[:20]],
    'largest_json_by_lines': [{'path': p, **metrics([p], trees[HEAD])}
                              for p in largest_text[:12]],
    'exact_duplicate_groups': duplicates,
    'duplicate_redundant_bytes': sum(d['redundant_bytes'] for d in duplicates),
    'manifests': manifests,
    'manifest_coverage': {'covered': len(coverage & set(evidence_paths)),
                          'total': len(evidence_paths),
                          'uncovered': sorted(set(evidence_paths) - coverage)},
}
(OUT / 'git-size-audit.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({k: result[k] for k in ('totals', 'diff_breakdown',
                                       'all_project_a_production_modules',
                                       'all_planner_and_harness_test_python',
                                       'manifest_coverage', 'duplicate_redundant_bytes')}, indent=2))
