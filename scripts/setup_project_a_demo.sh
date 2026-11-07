#!/usr/bin/env bash
# Clean-room setup for the Project A demo's pinned environment.
#
# The planner itself only accepts CPython 3.10.12 with numpy 1.26.4,
# scipy 1.11.4, quadprog 0.1.7 and trajectory-planning-helpers 0.79
# (route_artifact._supported_context; it also hash-checks helper
# sources). This script creates .venv-demo with exactly those pins,
# plus matplotlib/pytest for figures and tests.
#
# Prerequisites: bash, curl, tar, sha256sum, a C compiler, and uv
# (https://astral.sh/uv) OR any CPython 3.10.12 already on PATH as
# $PYTHON_BIN. Network access to PyPI is required on first run.
#
# quadprog provenance: the 0.1.7 sdist is fetched from PyPI and its
# SHA-256 is verified before building. Two documented local patches:
#   1. setup.py language='c++' -> 'c'  (the C++ build mangles the
#      Fortran qpgen2_ symbol on modern toolchains)
#   2. quadprog.pyx work-array size '/' -> '//' (under Cython 3 /
#      language_level=3 semantics the float result makes np.zeros
#      raise TypeError at runtime)
# Version and algorithm sources are otherwise unchanged.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$ROOT/.venv-demo"
QUADPROG_SHA256="f308b9a4f0368c956fd48e480dfadad7a9497ed7c1bb3059a2777b7deb4fbff9"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/qp" "$WORK/qpx"

PYTHON_BIN="${PYTHON_BIN:-}"
if [ -z "$PYTHON_BIN" ]; then
  if command -v uv >/dev/null 2>&1; then
    uv python install 3.10.12
    PYTHON_BIN="$(uv python find 3.10.12)"
  elif [ -x "$HOME/.local/share/uv/python/cpython-3.10.12-linux-x86_64-gnu/bin/python3.10" ]; then
    PYTHON_BIN="$HOME/.local/share/uv/python/cpython-3.10.12-linux-x86_64-gnu/bin/python3.10"
  else
    echo "error: need uv (curl -LsSf https://astral.sh/uv/install.sh | sh)" >&2
    echo "       or set PYTHON_BIN to a CPython 3.10.12 binary" >&2
    exit 1
  fi
fi
"$PYTHON_BIN" -c 'import sys; assert sys.version_info[:3] == (3, 10, 12), sys.version'

"$PYTHON_BIN" -m venv "$VENV"
PIP="$VENV/bin/pip"
"$PIP" install "numpy==1.26.4" "scipy==1.11.4" \
  "trajectory-planning-helpers==0.79" "matplotlib==3.10.9" \
  "pytest==8.3.4" "Cython==0.29.37"

"$PIP" download quadprog==0.1.7 --no-binary :all: -d "$WORK/qp" --no-deps
echo "$QUADPROG_SHA256  $WORK/qp/quadprog-0.1.7.tar.gz" | sha256sum -c -
tar xzf "$WORK/qp/quadprog-0.1.7.tar.gz" -C "$WORK/qpx"
sed -i "s/language='c++'/language='c'/" "$WORK/qpx/quadprog-0.1.7/setup.py"
sed -i 's|(min(n1, m1)+5)/2|(min(n1, m1)+5)//2|' \
  "$WORK/qpx/quadprog-0.1.7/quadprog/quadprog.pyx"
"$PIP" install --no-build-isolation --no-deps "$WORK/qpx/quadprog-0.1.7"

# Self-check: the exact failure mode of an unpatched/misbuilt quadprog
# is a TypeError inside solve_qp, so exercise a tiny QP end to end.
"$VENV/bin/python" - <<'EOF'
import numpy as np, quadprog, sys
sol = quadprog.solve_qp(np.eye(2), np.array([1.0, 1.0]),
                        np.array([[1., 0., -1., 0.], [0., 1., 0., -1.]]),
                        np.zeros(4))[0]
assert np.allclose(sol, [0.0, 0.0]), sol
print(f"quadprog self-check ok (python {sys.version.split()[0]})")
EOF
echo "environment ready: $VENV"
