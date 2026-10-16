#!/usr/bin/env bash
# Focused numerical checks with the same isolation and image as full verification.
set -euo pipefail
cd "$(dirname "$0")/../.."
if [ "$#" -lt 2 ]; then
  echo 'Usage: unit.sh fresh-output-directory repository-relative-test-path [pytest arguments...]' >&2
  exit 2
fi
out=$1
shift
if [ "$(id -u)" = 0 ]; then echo 'Run verification as a nonroot user.' >&2; exit 1; fi
if [ -d "$out" ] && [ -n "$(ls -A "$out")" ]; then
  echo 'Use a fresh output directory.' >&2
  exit 1
fi
if git submodule status --recursive | grep -Eq '^[+U-]'; then
  echo 'Submodule pin mismatch' >&2
  exit 1
fi
mkdir -p "$out"
export PROJECT_A_OUTPUT PROJECT_A_UID PROJECT_A_GID
PROJECT_A_OUTPUT=$(realpath "$out")
PROJECT_A_UID=$(id -u)
PROJECT_A_GID=$(id -g)
{
  printf 'pytest arguments: '
  printf '%q ' "$@"
  printf '\n'
  git rev-parse HEAD
  git status --short
  git submodule status --recursive
} > "$out/source-identity.txt"
python3 scripts/project_a/source_manifest.py > "$out/source-hashes-before.json"
unset DOCKER_HOST DOCKER_CONTEXT DOCKER_TLS DOCKER_TLS_VERIFY DOCKER_CERT_PATH
docker --host=unix:///var/run/docker.sock image inspect project-a-humble:w0 \
  --format '{{.Id}}' > "$out/image-id.txt"
set +e
docker --host=unix:///var/run/docker.sock compose -p project-a-unit \
  -f docker-compose.test.yaml run --rm -T --entrypoint /bin/bash test -c '
    set -euo pipefail
    export PYTHONPATH=/src/planner/global_planner PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
    python /src/scripts/project_a/identity.py > /work/runtime-identity.json
    python -m pip freeze --all > /work/dependencies.txt
    cd /src
    python -m pytest -q -p no:cacheprovider "$@" --junitxml=/work/unit.xml
  ' project-a-unit "$@" 2>&1 | tee "$out/run.log"
rc=${PIPESTATUS[0]}
set -e
python3 scripts/project_a/source_manifest.py > "$out/source-hashes-after.json"
if ! cmp -s "$out/source-hashes-before.json" "$out/source-hashes-after.json"; then
  echo 'Source changed during verification; discard this acceptance run.' >&2
  printf '1\n' > "$out/exit-code.txt"
  exit 1
fi
printf '%s\n' "$rc" > "$out/exit-code.txt"
exit "$rc"
