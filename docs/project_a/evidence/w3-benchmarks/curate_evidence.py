#!/usr/bin/env python3
"""Preserve exact A08 run products as compact deterministic review evidence."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil


def main():
    """Copy immutable records and losslessly compress bulky authority and exports."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True)
    parser.add_argument('--target', required=True)
    args = parser.parse_args()
    source, target = Path(args.source), Path(args.target)
    target.mkdir(parents=True, exist_ok=True)
    index = []
    for path in sorted(source.rglob('*')):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(source)
        if any(part.startswith(('.lock-', '.tmp-')) or part == '__pycache__'
               for part in relative.parts):
            continue
        raw = path.read_bytes()
        bulky = (relative.parts[0] in ('artifacts', 'legacy', 'mutations') or
                 (path.suffix in ('.stdout', '.stderr', '.jsonl') and len(raw) > 0
                  and path.name != 'attempts.jsonl'))
        destination = target / relative
        if bulky and path.suffix != '.gz':
            destination = destination.with_name(destination.name + '.gz')
            encoded = gzip.compress(raw, compresslevel=1, mtime=0)
        else:
            encoded = raw
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(encoded)
        index.append({'source_relative_path': relative.as_posix(),
                      'evidence_relative_path': destination.relative_to(target).as_posix(),
                      'original_bytes': len(raw), 'stored_bytes': len(encoded),
                      'original_sha256': hashlib.sha256(raw).hexdigest(),
                      'evidence_sha256': hashlib.sha256(encoded).hexdigest(),
                      'compression': 'gzip-mtime0' if encoded != raw else 'none'})
    (target / 'files.json').write_text(json.dumps(index, indent=2, sort_keys=True))
    print(json.dumps({'source': str(source), 'target': str(target), 'files': len(index),
                      'original_bytes': sum(row['original_bytes'] for row in index),
                      'stored_bytes': sum(row['stored_bytes'] for row in index)}))
    shutil.copystat(source, target)


if __name__ == '__main__':
    main()
