"""Deterministically package stable independent review evidence without extraction."""
from pathlib import Path, PurePosixPath
import hashlib
import io
import json
import os
import stat
import tarfile
import gzip

BASE = Path('/workspace/w3-review/work/independent-review')
OUTPUT = BASE / 'release-handoff/package'
SCOPES = ('artifact', 'publication', 'queries-export', 'filesystem', 'hygiene', 'installed', 'benchmarks')
OUTPUT.mkdir(parents=True, exist_ok=True)


def canonical(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + '\n').encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def exclusion(relative):
    parts = relative.parts
    if '__pycache__' in parts:
        return 'Python bytecode cache; reconstructible'
    if any(part.endswith('-tmp') for part in parts):
        return 'Ephemeral temporary fixture repository/tree; reconstructible'
    if parts[0] == 'installed' and 'checkout' in parts:
        return 'Source checkout; reconstructible from recorded SHA, pins and scripts'
    if len(parts) >= 2 and parts[:2] == ('benchmarks', 'ros-interfaces'):
        return 'ROS interface source/build/install/log tree; reconstructible from pinned source'
    if parts[0] == 'installed' and 'fresh-clean-commit-guards' in parts and parts[-1] == 'origin':
        return 'Synthetic guard origin fixture repository; reconstructible from guard source/summary'
    if '.git' in parts:
        return 'Git administrative metadata of a reconstructible fixture repository'
    return None


excluded = [
    {'path': 'installed-final/', 'reason': 'Active final verification; outside stable initial review scope'},
    {'path': 'a08-independent-evidence.zip', 'reason': 'Optional duplicate benchmark bundle; raw benchmark evidence is included instead'},
    {'path': 'release-handoff/', 'reason': 'Package output, draft reports and packaging scripts; outside evidence inputs'},
]
paths = []
for scope in SCOPES:
    root = BASE / scope
    if not root.is_dir() or root.is_symlink():
        raise RuntimeError('Invalid evidence root: ' + scope)
    for directory, directories, files in os.walk(root, topdown=True, followlinks=False):
        parent = Path(directory)
        kept = []
        for name in sorted(directories):
            path = parent / name
            relative = path.relative_to(BASE)
            reason = exclusion(relative)
            if reason:
                excluded.append({'path': relative.as_posix() + '/', 'reason': reason})
                continue
            if path.is_symlink():
                raise RuntimeError('Selected symlink directory rejected: ' + str(relative))
            if not stat.S_ISDIR(path.lstat().st_mode):
                raise RuntimeError('Selected non-directory rejected: ' + str(relative))
            kept.append(name)
        directories[:] = kept
        for name in sorted(files):
            path = parent / name
            relative = path.relative_to(BASE)
            reason = exclusion(relative)
            if reason:
                excluded.append({'path': relative.as_posix(), 'reason': reason})
                continue
            mode = path.lstat().st_mode
            if stat.S_ISLNK(mode):
                raise RuntimeError('Selected symlink rejected: ' + str(relative))
            if not stat.S_ISREG(mode):
                raise RuntimeError('Selected non-regular evidence rejected: ' + str(relative))
            paths.append((relative.as_posix(), path))
paths.sort()
excluded.sort(key=lambda row: row['path'])

# Read once for the manifest and once while packing, requiring an exact match.
records = []
initial_stats = {}
for name, path in paths:
    before = path.stat()
    data = path.read_bytes()
    after = path.stat()
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
        raise RuntimeError('Input changed during first read: ' + name)
    initial_stats[name] = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    records.append({'path': name, 'size_bytes': len(data), 'sha256': digest(data)})
manifest = {
    'schema_version': 1,
    'scope': 'Stable initial independent W3 review evidence; corrected dirty-tree scoped runs are labeled by their individual records. Exact committed-SHA fresh and delivered-head CI gates remain pending.',
    'source_root': 'work/independent-review',
    'included_roots': list(SCOPES),
    'selection': 'Regular files only. Excluded directory prefixes are pruned. Selected symlinks and special files are fatal errors.',
    'archive_format': 'POSIX USTAR inside gzip; gzip mtime=0; uid/gid/mtime=0; uname/gname empty; mode=0644; lexical payload order with MANIFEST.json first.',
    'payload_file_count': len(records),
    'payload_bytes': sum(row['size_bytes'] for row in records),
    'excluded_paths': excluded,
    'files': records,
    'manifest_self_hash': 'MANIFEST.json is excluded from its own member ledger; its SHA256/size are in receipt.json outside the archive.',
}
manifest_data = canonical(manifest)
archive = OUTPUT / 'initial-independent.tar.gz'
partial = OUTPUT / 'initial-independent.tar.gz.partial'


def add(tar, name, data):
    item = tarfile.TarInfo(name)
    item.size = len(data)
    item.mode = 0o644
    item.uid = item.gid = item.mtime = 0
    item.uname = item.gname = ''
    tar.addfile(item, io.BytesIO(data))


with partial.open('wb') as destination:
    with gzip.GzipFile(filename='', mode='wb', fileobj=destination, compresslevel=9, mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode='w|', format=tarfile.USTAR_FORMAT) as tar:
            add(tar, 'MANIFEST.json', manifest_data)
            for row, (name, path) in zip(records, paths):
                data = path.read_bytes()
                current = path.stat()
                identity = (current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns)
                if identity != initial_stats[name] or len(data) != row['size_bytes'] or digest(data) != row['sha256']:
                    raise RuntimeError('Input changed while packing: ' + name)
                add(tar, name, data)

# Full independent archive readback: name safety, regular-only, exact count/size/hash.
expected = {row['path']: row for row in records}
expected['MANIFEST.json'] = {'size_bytes': len(manifest_data), 'sha256': digest(manifest_data)}
seen = set()
readback_bytes = 0
with tarfile.open(partial, mode='r:gz') as tar:
    for member in tar:
        name = member.name
        if not member.isfile() or name in seen:
            raise RuntimeError('Non-regular/duplicate archive member: ' + name)
        pure = PurePosixPath(name)
        if pure.is_absolute() or '..' in pure.parts or name not in expected:
            raise RuntimeError('Unsafe or unexpected archive member: ' + name)
        row = expected[name]
        body = tar.extractfile(member)
        hasher = hashlib.sha256()
        actual_size = 0
        while chunk := body.read(1024 * 1024):
            hasher.update(chunk)
            actual_size += len(chunk)
        if actual_size != row['size_bytes'] or member.size != actual_size or hasher.hexdigest() != row['sha256']:
            raise RuntimeError('Member hash/size mismatch: ' + name)
        seen.add(name)
        readback_bytes += actual_size
if seen != set(expected):
    raise RuntimeError('Missing member(s): ' + repr(set(expected) - seen))

# Rehash every selected input after full readback and reject changed/additional selections.
for row, (name, path) in zip(records, paths):
    if digest(path.read_bytes()) != row['sha256']:
        raise RuntimeError('Source evidence changed before completion: ' + name)
partial.replace(archive)
archive_data = archive.read_bytes()
receipt = {
    'schema_version': 1,
    'archive': archive.name,
    'archive_size_bytes': len(archive_data),
    'archive_sha256': digest(archive_data),
    'archive_member_count': len(seen),
    'payload_file_count': len(records),
    'payload_bytes': manifest['payload_bytes'],
    'manifest_size_bytes': len(manifest_data),
    'manifest_sha256': digest(manifest_data),
    'readback_member_count': len(seen),
    'readback_uncompressed_bytes': readback_bytes,
    'readback_result': 'PASS: all archive members read in full, exact SHA256/size, regular-only, safe paths, no duplicates, complete member set; all selected source files rehashed after readback.',
    'selected_symlinks': 0,
    'selected_special_files': 0,
    'exact_committed_candidate_fresh_gate': 'PENDING',
    'exact_delivered_head_hosted_CI_gate': 'PENDING',
}
(OUTPUT / 'MANIFEST.json').write_bytes(manifest_data)
(OUTPUT / 'selection.json').write_bytes(canonical({'included_roots': list(SCOPES), 'included_paths': [row['path'] for row in records], 'excluded_paths': excluded}))
(OUTPUT / 'receipt.json').write_bytes(canonical(receipt))
print(json.dumps(receipt, indent=2))
print('Exclusion entries:', len(excluded))
