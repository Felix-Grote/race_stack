#!/usr/bin/env bash
# Run a second container with only installed products, a minimal test and explicit outputs.
set -euo pipefail
cd "$(dirname "$0")/../.."
if [ "$#" -ne 1 ]; then
  echo 'Usage: isolated_runtime.sh existing-verification-output' >&2
  exit 2
fi
if [ "$(id -u)" -eq 0 ]; then
  echo 'Run installed-runtime verification as a nonroot user.' >&2
  exit 1
fi
out=$(realpath "$1")
test -d "$out/install"
test -d "$out/python"
runtime_out="$out/source-free"
if [ -e "$runtime_out" ] || [ -L "$runtime_out" ]; then
  echo 'Use a fresh source-free evidence directory; previous results are retained.' >&2
  exit 1
fi
mkdir -p "$runtime_out/harness" "$runtime_out/results"
cp scripts/project_a/tests/test_w3_installed.py "$runtime_out/harness/"
cp scripts/project_a/tests/test_w3_scenario_installed.py "$runtime_out/harness/"
cp scripts/project_a/w3_query_probe.py "$runtime_out/harness/"
cp scripts/project_a/runtime_verify.sh "$runtime_out/harness/"
runtime_image=$(cat "$out/image-id.txt")
if [[ ! "$runtime_image" =~ ^sha256:[0-9a-f]{64}$ ]]; then
  echo 'The recorded immutable Docker image ID is invalid.' >&2
  exit 1
fi
expected_commit=$(git rev-parse HEAD)
expected_clean=0
if [ -z "$(git status --porcelain)" ]; then expected_clean=1; fi
python3 - "$runtime_out/launch.json" "$expected_commit" "$runtime_image" <<'PY_LAUNCH'
import json
from pathlib import Path
import sys
Path(sys.argv[1]).write_text(json.dumps({
    'expected_commit': sys.argv[2], 'image_id': sys.argv[3],
    'source_or_build_mounts': [],
    'readonly_mounts': ['/work/install', '/work/python', '/runtime-harness'],
    'writable_mounts': ['/results', '/tmp'], 'network': 'none',
    'working_directory': '/results',
    'scope': 'Separate container; no repository, source, build or optimizer checkout mounted',
}, indent=2) + '\n')
PY_LAUNCH
unset DOCKER_HOST DOCKER_CONTEXT DOCKER_TLS DOCKER_TLS_VERIFY DOCKER_CERT_PATH
set +e
docker --host=unix:///var/run/docker.sock run --rm \
  --user "$(id -u):$(id -g)" --read-only --network none --ipc private \
  --cap-drop ALL --security-opt no-new-privileges --pids-limit 256 --memory 4g --cpus 2 \
  --workdir /results --tmpfs /tmp:rw,nosuid,nodev,size=256m,mode=1777 \
  -e PYTHONDONTWRITEBYTECODE=1 -e MPLBACKEND=Agg -e MPLCONFIGDIR=/tmp/project-a-mpl \
  -e OPENBLAS_NUM_THREADS=1 -e OMP_NUM_THREADS=1 \
  -e PROJECT_A_SOURCE_FREE=1 -e PROJECT_A_RUNTIME_OUTPUT=/results \
  -e "PROJECT_A_EXPECTED_COMMIT=$expected_commit" \
  -e "PROJECT_A_EXPECTED_CLEAN=$expected_clean" \
  --mount "type=bind,src=$out/install,dst=/work/install,readonly" \
  --mount "type=bind,src=$out/python,dst=/work/python,readonly" \
  --mount "type=bind,src=$runtime_out/harness,dst=/runtime-harness,readonly" \
  --mount "type=bind,src=$runtime_out/results,dst=/results" \
  --entrypoint /bin/bash "$runtime_image" /runtime-harness/runtime_verify.sh
runtime_rc=$?
set -e
printf '%s\n' "$runtime_rc" > "$runtime_out/exit-code.txt"
exit "$runtime_rc"
