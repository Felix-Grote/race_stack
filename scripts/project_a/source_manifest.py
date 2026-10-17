"""Hash Project A inputs and optionally stage exact build provenance."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_hashes(repository):
    paths = set(repository.joinpath('planner/global_planner').rglob('*.py'))
    paths.update(repository.joinpath('scripts/project_a').rglob('*.py'))
    for folder in ('planner/global_planner/test/fixtures/project_a',
                   'planner/global_planner/config/project_a'):
        paths.update(p for p in repository.joinpath(folder).rglob('*') if p.is_file())
    paths.update(repository.joinpath('scripts/project_a').glob('*.sh'))
    paths.update(repository.joinpath('scripts/project_a').glob('requirements*'))
    for name in ('docker-compose.test.yaml', '.github/workflows/project-a.yml',
                 'scripts/project_a/Dockerfile', 'planner/global_planner/package.xml',
                 'utilities/libraries/f110_msgs/msg/Wpnt.msg',
                 'utilities/libraries/f110_msgs/msg/WpntArray.msg'):
        paths.add(repository / name)
    return {str(p.relative_to(repository)): _sha256(p) for p in sorted(paths)}


def _git(repository, *arguments):
    return subprocess.check_output(
        ['git', '-C', str(repository), *arguments], text=True).strip()


def _build_identity(repository, source_hashes):
    gitlinks = {}
    for line in _git(repository, 'submodule', 'status', '--recursive').splitlines():
        if line.startswith(('+', '-', 'U')):
            raise ValueError('uninitialized or mismatched recursive gitlink')
        fields = line.split()
        gitlinks[fields[1]] = fields[0]
    resources = repository / 'planner/global_planner/config/project_a'
    return {
        'schema_version': 1,
        'source_commit': _git(repository, 'rev-parse', 'HEAD'),
        'source_dirty': bool(_git(repository, 'status', '--porcelain')),
        'gitlinks': gitlinks,
        'source_hashes': source_hashes,
        'installed_resource_hashes': {
            str(p.relative_to(resources)): _sha256(p)
            for p in sorted(resources.rglob('*'))
            if p.is_file() and p.name != 'build_identity.json'
        },
        'dependency_lock_hashes': {
            p.name: _sha256(p)
            for p in sorted(repository.joinpath('scripts/project_a').glob('*.lock'))
        },
        'scope': 'Build provenance; runtime semantic support is independently checked',
    }


def main():
    """Print source hashes or write provenance into an explicitly staged copy."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', type=Path, default=Path.cwd())
    parser.add_argument('--build-identity', type=Path)
    arguments = parser.parse_args()
    repository = arguments.repository.resolve()
    hashes = _source_hashes(repository)
    if arguments.build_identity is None:
        print(json.dumps(hashes, indent=2, sort_keys=True))
    else:
        destination = arguments.build_identity.resolve()
        if (destination.is_relative_to(repository) and
                not destination.is_relative_to(repository / 'work')):
            raise ValueError('build identity must be staged under work/ or outside the repository')
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(_build_identity(repository, hashes),
                                          indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
