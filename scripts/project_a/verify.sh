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
verification_commit=$(git rev-parse HEAD)
verification_status=$(git status --porcelain)
{
  printf '%s\n' "$verification_commit"
  if [ -n "$verification_status" ]; then printf '%s\n' "$verification_status"; fi
  git submodule status --recursive
  uname -sm
  cat /etc/os-release
  python3 --version
} > "$out/source-identity.txt"
python3 scripts/project_a/source_manifest.py > "$out/source-hashes-before.json"
unset DOCKER_HOST DOCKER_CONTEXT DOCKER_TLS DOCKER_TLS_VERIFY DOCKER_CERT_PATH
docker --host=unix:///var/run/docker.sock image inspect project-a-humble:w0 --format '{{.Id}}' > "$out/image-id.txt"
set +e
docker --host=unix:///var/run/docker.sock compose -p project-a-w0 -f docker-compose.test.yaml run --rm -T test "$mode" 2>&1 | tee "$out/run.log"
rc=${PIPESTATUS[0]}
set -e
if [ "$rc" -eq 0 ] && [[ "$mode" == all || "$mode" == ros ]]; then
  set +e
  scripts/project_a/isolated_runtime.sh "$PROJECT_A_OUTPUT" 2>&1 | tee "$out/isolated-runtime.log"
  runtime_rc=${PIPESTATUS[0]}
  set -e
  if [ "$runtime_rc" -ne 0 ]; then rc=1; fi
  python3 - "$out" "$runtime_rc" <<'PY_RUNTIME_SUMMARY'
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
output = Path(sys.argv[1])
path = output / 'summary.json'
summary = json.loads(path.read_text()) if path.exists() else {}
summary['scope'] = 'W0_THROUGH_A09'
summary['independent_w3_adversarial_review'] = 'REQUIRED'
report = output / 'source-free/results/w3-source-free.xml'
if report.exists():
    root = ET.parse(report).getroot()
    suite = root if root.tag == 'testsuite' else root.find('testsuite')
    summary['w3-source-free'] = {
        key: suite.attrib[key] for key in ('tests', 'failures', 'errors', 'skipped')}
else:
    summary['w3-source-free'] = {'status': 'NO_COMPLETE_TEST_REPORT'}
summary['w3-source-free']['container_exit_code'] = int(sys.argv[2])
campaign = output / 'source-free/results/w3-scenario-campaign.json'
if campaign.exists():
    summary['source_free_scenarios'] = [
        {key: case.get(key) for key in ('case', 'status', 'H')}
        for case in json.loads(campaign.read_text())['outcomes']]
path.write_text(json.dumps(summary, indent=2) + '\n')
PY_RUNTIME_SUMMARY
fi
python3 scripts/project_a/source_manifest.py > "$out/source-hashes-after.json"
if ! cmp -s "$out/source-hashes-before.json" "$out/source-hashes-after.json"; then
  echo 'Source changed during verification; discard this acceptance run.' >&2
  rc=1
fi
if [ "$(git rev-parse HEAD)" != "$verification_commit" ]; then
  echo 'Git HEAD changed during verification; discard this acceptance run.' >&2
  rc=1
fi
if [ "$(git status --porcelain)" != "$verification_status" ]; then
  echo 'Git clean/dirty state changed during verification; discard this acceptance run.' >&2
  rc=1
fi
printf '%s\n' "$rc" > "$out/exit-code.txt"
exit "$rc"
