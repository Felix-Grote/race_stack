"""Preserve completed final-candidate raw evidence without changing its source commit."""
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile

candidate = '17e4ec4e8fedfa736467d02f6204b04e8552decb'
source = Path('work/w3/postfix-fresh')
verification = source / 'verification'
output = Path('work/w3/final-evidence-publication/docs/project_a/evidence/w3-final-verification')
for path in (source / 'fresh-exit-code.txt', verification / 'exit-code.txt',
             verification / 'source-free/exit-code.txt'):
    assert path.read_text().strip() == '0', path
assert (source / 'candidate.txt').read_text().strip() == candidate
assert (verification / 'source-hashes-before.json').read_bytes() == (
    verification / 'source-hashes-after.json').read_bytes()
summary = json.loads((verification / 'summary.json').read_text())
groups = {key: value for key, value in summary.items()
          if isinstance(value, dict) and 'tests' in value and 'failures' in value}
assert len(groups) == 27, groups.keys()
assert sum(int(value['tests']) for value in groups.values()) == 591
for value in groups.values():
    assert all(int(value[key]) == 0 for key in ('failures', 'errors', 'skipped'))
assert len(summary['source_free_scenarios']) == 9
assert all(value['status'] == 'PASS' for value in summary['source_free_scenarios'])
selected = {'fresh-wrapper/console.log': Path('work/w3/postfix-fresh-console.log')}
for path in source.glob('*'):
    if path.is_file() and not path.is_symlink():
        selected['fresh-wrapper/' + path.name] = path
for path in verification.glob('*'):
    if path.is_file() and not path.is_symlink():
        selected['verification/' + path.name] = path
for name in ('source-free', 'w3-installed'):
    for path in (verification / name).rglob('*'):
        if path.is_file() and not path.is_symlink():
            selected['verification/' + str(path.relative_to(verification))] = path
for path in (verification / 'build').rglob('*.xml'):
    if path.is_file() and not path.is_symlink():
        selected['verification/' + str(path.relative_to(verification))] = path
archive = output / 'fresh-17e4ec4e.tar.gz'
assert not archive.exists()
members = {}
with archive.open('xb') as raw:
    with gzip.GzipFile(filename='', fileobj=raw, mode='wb', mtime=0, compresslevel=9) as zipped:
        with tarfile.open(fileobj=zipped, mode='w') as tar:
            for name, path in sorted(selected.items()):
                data = path.read_bytes()
                info = tarfile.TarInfo(name)
                info.size, info.mode, info.mtime = len(data), 0o644, 0
                tar.addfile(info, io.BytesIO(data))
                members[name] = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
with tarfile.open(archive, 'r:gz') as tar:
    assert len(tar.getmembers()) == len(members)
    for member in tar:
        assert hashlib.sha256(tar.extractfile(member).read()).hexdigest() == members[member.name]['sha256']
record = {'candidate': candidate, 'scope': 'Completed clean recursive full verification and source-free runtime',
          'archive': archive.name, 'archive_bytes': archive.stat().st_size,
          'archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
          'functional_tests': 591, 'groups': 27, 'members': members}
(output / 'fresh-archive.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps({key: value for key, value in record.items() if key != 'members'}, indent=2))
