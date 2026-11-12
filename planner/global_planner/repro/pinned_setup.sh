#!/bin/bash
# Pinned Project A optimizer environment (CPython 3.10, exact pins).
#
# The runtime gate in iqp_route_adapter._helpers() requires numpy 1.26.4,
# scipy 1.11.4, quadprog 0.1.7 and trajectory-planning-helpers 0.79.
# This script builds an isolated venv with the exact contract instead of
# changing it or touching the team devcontainer.
#
# Usage: ./pinned_setup.sh [venv-dir]
# Env overrides: PYTHON310 (default: python3.10), TMPDIR, UV_CACHE_DIR.
# Verify: [venv]/bin/python -m pip freeze | diff requirements-pinned.txt -
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="${1:-$HOME/venvs/forza-pinned}"
PY310="${PYTHON310:-python3.10}"
export TMPDIR="${TMPDIR:-${XDG_CACHE_HOME:-$HOME/.cache}/forza-annot/tmp}"
export UV_CACHE_DIR="${UV_CACHE_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}/forza-annot/uv-cache}"
mkdir -p "$TMPDIR"
uv venv --python "$PY310" --seed "$VENV"
# quadprog 0.1.7 must be cythonized with Cython 0.29.x: its setup.py uses
# setup_requires (unconstrained), so an isolated build silently fetches
# Cython 3.x, whose extern-C qpgen2_ declaration does not link against the
# C++-mangled solve.QP.c definition (undefined symbol at import).
# Pre-install the toolchain; the per-package flag builds only quadprog
# against it while everything else keeps build isolation.
uv pip install --python "$VENV/bin/python" setuptools "Cython==0.29.37" "numpy==1.26.4"
uv pip install --python "$VENV/bin/python" --no-build-isolation-package quadprog \
  --refresh-package quadprog \
  --requirement "$HERE/requirements-pinned.txt"
"$VENV/bin/python" - <<'EOF'
import numpy, scipy, quadprog, trajectory_planning_helpers, cv2
import importlib.metadata as md
assert numpy.__version__ == '1.26.4', numpy.__version__
assert scipy.__version__ == '1.11.4', scipy.__version__
assert md.version('quadprog') == '0.1.7', md.version('quadprog')
assert md.version('trajectory-planning-helpers') == '0.79'
print('pinned env OK:', numpy.__version__, scipy.__version__,
      md.version('quadprog'), md.version('trajectory-planning-helpers'),
      cv2.__version__)
EOF
