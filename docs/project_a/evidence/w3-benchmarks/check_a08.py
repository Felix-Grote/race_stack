#!/usr/bin/env python3
"""Verify final A08 tests from a copied package location and strict new-source lint."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def main():
    """Check the copied-package regression without a source-shaped test path."""
    source = Path('/src')
    output = Path('/work/a08-tests')
    package = output / 'copied/global_planner'
    tests = package / 'test'
    tests.mkdir(parents=True, exist_ok=True)
    original_test = source / 'planner/global_planner/test/test_w3_benchmarks.py'
    copied_test = tests / original_test.name
    shutil.copy2(original_test, copied_test)
    shutil.copytree(original_test.parent / 'fixtures/project_a',
                    tests / 'fixtures/project_a', dirs_exist_ok=True)
    optimizer = ('global_planner/global_racetrajectory_optimization/'
                 'global_racetrajectory_optimization/helper_funcs_glob/src')
    (package / optimizer).mkdir(parents=True, exist_ok=True)
    for filename in ('check_traj.py', 'interp_track.py', 'calc_min_bound_dists.py'):
        shutil.copy2(original_test.parent.parent / optimizer / filename,
                     package / optimizer / filename)
    sources = [original_test, source / 'scripts/project_a/benchmark_w3.py',
               source / 'scripts/project_a/w3_benchmark_support.py']
    commands = {
        'copied_package_tests': [sys.executable, '-m', 'pytest', str(copied_test), '-q',
                                 '--junitxml', str(output / 'a08-final.xml')],
        'strict_flake8': [sys.executable, '-m', 'flake8', '--max-line-length=99',
                          *(str(path) for path in sources)],
        'strict_pep257': ['ament_pep257', '--convention', 'pep257',
                          *(str(path) for path in sources)]}
    results = {'source_sha256': {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                                 for path in sources},
               'copied_test_sha256': hashlib.sha256(copied_test.read_bytes()).hexdigest(),
               'source_context': os.environ['PROJECT_A_TEST_REPO'], 'checks': {}}
    for name, command in commands.items():
        completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   check=False)
        (output / (name + '.log')).write_bytes(completed.stdout)
        results['checks'][name] = {'command': command, 'exit_code': completed.returncode}
        print(json.dumps({'check': name, 'exit_code': completed.returncode}), flush=True)
    (output / 'final-checks.json').write_text(json.dumps(results, indent=2, sort_keys=True) + '\n')
    return int(any(value['exit_code'] for value in results['checks'].values()))


if __name__ == '__main__':
    raise SystemExit(main())
