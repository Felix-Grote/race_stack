#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
mode=${1:-all}
case "$mode" in all|numerical|ros|legacy) ;; *) echo 'Usage: verify.sh [all|numerical|ros|legacy] [output-directory]' >&2; exit 2;; esac
if git submodule status --recursive | grep -Eq '^[+U-]'; then
  echo 'Submodule pin mismatch' >&2; exit 1
fi
out=${2:-work/project-a/$(date -u +%Y%m%dT%H%M%SZ)-$mode}
if [ -d "$out" ] && [ -n "$(ls -A "$out")" ]; then
  echo 'Use a fresh output directory to avoid stale install/evidence.' >&2; exit 1
fi
mkdir -p "$out"
export PROJECT_A_OUTPUT
PROJECT_A_OUTPUT=$(realpath "$out")
# Ownership is deliberate: runtime must not need root or writable source.
if [ "$(id -u)" = 0 ]; then echo 'Run verification as a nonroot user.' >&2; exit 1; fi
export PROJECT_A_UID=$(id -u) PROJECT_A_GID=$(id -g)
{
  git rev-parse HEAD
  git status --short
  git submodule status --recursive
  uname -sm
  cat /etc/os-release
  python3 --version
} > "$out/source-identity.txt"
unset DOCKER_HOST DOCKER_CONTEXT DOCKER_TLS DOCKER_TLS_VERIFY DOCKER_CERT_PATH
docker --host=unix:///var/run/docker.sock image inspect project-a-humble:w0 --format '{{.Id}}' > "$out/image-id.txt"
set +e
docker --host=unix:///var/run/docker.sock compose -p project-a-w0 -f docker-compose.test.yaml run --rm -T test "$mode" 2>&1 | tee "$out/run.log"
rc=${PIPESTATUS[0]}
set -e
printf '%s\n' "$rc" > "$out/exit-code.txt"
exit "$rc"
