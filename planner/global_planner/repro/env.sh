#!/bin/bash
# Shared generator-environment contract for the repro scripts (sourced).
#
# The manifest is the env-independent handoff: generation (map
# extraction, seeds, strict validation) runs on the system Python +
# OpenCV 5.x, whose distance-transform numerics define ridge-seed
# geometry (opencv 4.8.1 moves seeds up to ~2.5 m), while compilation
# runs in the pinned venv (requirements-pinned.txt). This file resolves
# SYS and fails closed when the generator env drifts from receipts.json.
# Bypass only to measure drift: REPRO_ALLOW_ENV_MISMATCH=1.
set -euo pipefail
HERE_ENV="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYS="${SYSTEM_PY:-python3.12}"
ALLOW="${REPRO_ALLOW_ENV_MISMATCH:-0}"
if ! "$SYS" - "$HERE_ENV/receipts.json" "$ALLOW" <<'EOF'
import json, sys
rec = json.load(open(sys.argv[1]))['generator']
import cv2, numpy
have = {'python': sys.version.split()[0], 'cv2': cv2.__version__,
        'numpy': numpy.__version__}
print('generator env: ' +
      ' '.join(f'{k}={have[k]}' for k in ('python', 'cv2', 'numpy')) +
      f' (recorded: {rec["python"]} {rec["cv2"]} {rec["numpy"]})')
key = lambda v: tuple(v.split('.')[:2])  # noqa: E731
drift = [k for k in ('python', 'cv2', 'numpy')
         if key(have[k]) != key(rec[k])]
if drift and sys.argv[2] != '1':
    raise SystemExit(
        f'generator env drift on {drift}: have {have}, '
        f'recorded {rec}. Provision: {sys.executable} -m pip '
        f'install --user "opencv-python-headless==5.*" "numpy==2.5.4"; '
        'or re-run with REPRO_ALLOW_ENV_MISMATCH=1 to measure drift.')
if drift:
    print(f'WARNING: proceeding despite generator drift on {drift}')
EOF
then
    echo 'env.sh: generator gate failed; see above.' >&2
    exit 1
fi
