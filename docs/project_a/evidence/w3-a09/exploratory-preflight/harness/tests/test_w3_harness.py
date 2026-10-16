"""Challenge exact-candidate checks with tiny local Git repositories, without Docker."""
from pathlib import Path
import shutil
import subprocess

import pytest


def _run(*command, cwd):
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=True)


@pytest.mark.parametrize('mutation_stage', ('none', 'setup', 'verification'))
def test_fresh_candidate_rejects_source_mutation_at_each_boundary(tmp_path, mutation_stage):
    """A successful subprocess cannot approve a candidate that changed during setup or tests."""
    repository = tmp_path / 'origin'
    scripts = repository / 'scripts/project_a'
    scripts.mkdir(parents=True)
    helper = scripts / 'fresh_verify.sh'
    shutil.copy2(Path(__file__).parents[1] / 'fresh_verify.sh', helper)
    setup = '#!/usr/bin/env bash\nset -eu\n'
    verify = '#!/usr/bin/env bash\nset -eu\nmkdir -p "$2"\necho invoked > "$2/marker.txt"\n'
    mutation = 'echo changed >> payload.txt\n'
    if mutation_stage == 'setup':
        setup += mutation
    if mutation_stage == 'verification':
        verify += mutation
    (scripts / 'setup.sh').write_text(setup)
    (scripts / 'verify.sh').write_text(verify)
    for path in scripts.iterdir():
        path.chmod(0o755)
    (repository / 'payload.txt').write_text('committed payload\n')
    _run('git', 'init', '-q', cwd=repository)
    _run('git', 'add', '.', cwd=repository)
    _run('git', '-c', 'user.name=Project A guard regression',
         '-c', 'user.email=guard-regression@example.invalid',
         'commit', '-qm', 'fixture', cwd=repository)
    candidate = _run('git', 'rev-parse', 'HEAD', cwd=repository).stdout.strip()
    destination = tmp_path / 'release'
    result = subprocess.run([str(helper), candidate, str(destination)],
                            cwd=repository, text=True, capture_output=True, check=False)
    (tmp_path / 'fresh.stdout.txt').write_text(result.stdout)
    (tmp_path / 'fresh.stderr.txt').write_text(result.stderr)
    marker = destination / 'verification/marker.txt'
    assert (destination / 'candidate.txt').read_text().strip() == candidate
    assert (destination / 'fresh-exit-code.txt').read_text().strip() == str(result.returncode)
    if mutation_stage == 'none':
        assert result.returncode == 0, result.stderr
        assert marker.read_text().strip() == 'invoked'
    else:
        assert result.returncode != 0
        assert 'Candidate checkout is not exact and clean' in result.stderr
        assert marker.exists() is (mutation_stage == 'verification')
