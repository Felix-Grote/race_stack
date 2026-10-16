"""Fail closed when inherited legacy failure or skip identities change."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET


_EXPECTED_SKIPS = [
    'frenet_conversion.test.test_copyright test_copyright',
    'global_planner.test.test_copyright test_copyright',
]
_SKIP_REASON = 'No copyright header has been placed in the generated source file.'


def _read(path):
    data = path.read_bytes()
    return gzip.decompress(data).decode() if path.suffix == '.gz' else data.decode()


def _failures(text):
    return re.findall(r'^- ([^\n]+)\n  <<< failure message', text, re.MULTILINE)


def main():
    """Compare raw failure labels and actual JUnit skips with the W0 baseline."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--actual', type=Path, required=True)
    parser.add_argument('--build-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    arguments = parser.parse_args()
    baseline = _failures(_read(arguments.baseline))
    actual_text = _read(arguments.actual)
    actual = _failures(actual_text)
    summaries = re.findall(
        r'^Summary: (\d+) tests?, (\d+) errors?, (\d+) failures?, (\d+) skipped\s*$',
        actual_text, re.MULTILINE)
    skips = []
    for package in ('frenet_conversion', 'global_planner'):
        for case in ET.parse(arguments.build_root / package / 'pytest.xml').iter('testcase'):
            skipped = case.find('skipped')
            if skipped is not None:
                skips.append({'identity': case.get('classname') + ' ' + case.get('name'),
                              'reason': skipped.get('message')})
    identical = (
        len(baseline) == 10 and actual == baseline and len(summaries) == 1
        and tuple(map(int, summaries[0][1:])) == (0, 10, 2)
        and sorted(s['identity'] for s in skips) == _EXPECTED_SKIPS
        and all(s['reason'] == _SKIP_REASON for s in skips))
    report = {
        'identities_equal': identical, 'baseline': baseline, 'actual': actual,
        'skips': skips, 'summary': summaries,
        'baseline_sha256': hashlib.sha256(arguments.baseline.read_bytes()).hexdigest(),
        'actual_sha256': hashlib.sha256(arguments.actual.read_bytes()).hexdigest(),
        'scope': 'Inherited failures remain failures; any new identity rejects the run',
    }
    arguments.output.write_text(json.dumps(report, indent=2) + '\n')
    if not identical:
        raise SystemExit('Legacy failure/skip baseline changed; inspect raw results')


if __name__ == '__main__':
    main()
