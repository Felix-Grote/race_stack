#!/bin/bash
# Reproduce the test-map full chain with pinned provenance labels so the
# artifact hash matches the documented identity exactly.
#
# Usage (from the repository root): planner/global_planner/repro/repro_test.sh [pinned-python]
# Env: SYSTEM_PY (default python3.12) for generation; the manifest is the
# env-independent handoff (system opencv 5.0), compilation runs pinned.
# Shared generator gate: repro/env.sh (sets SYS, checks the env).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../../.." && pwd)"
cd "$REPO"
source "$HERE/env.sh"
PIN="${1:-${PINNED_PY:-$HOME/venvs/forza-pinned/bin/python}}"
OUT="${REPRO_OUT:-$HERE/out_test}"
MAP=test EXPECTED_H=e80c49b669a148f0d5b49829c9387e73e471c02ed94685ad8459ce99543a2f4e
COMMITTED="$HERE/manifests/manifest_test_current.json"
REGEN="$OUT/manifest_test_current.json"
mkdir -p "$OUT"
export PYTHONPATH="$REPO/planner/global_planner"
"$SYS" - "$MAP" "$REGEN" <<'EOF'
import json, sys
from pathlib import Path
from global_planner.annotation_core import (
    TrackMap, build_and_validate, extract_boundaries, suggest_route)
name, out = sys.argv[1], Path(sys.argv[2])
tm = TrackMap(Path(f'stack_master/maps/{name}/{name}.yaml'))
outer, inner = extract_boundaries(tm)
seed = suggest_route(outer, inner)
payload, route, prepared, info = build_and_validate(
    tm, outer, inner, seed, approval='operator-approved')
assert len(prepared.samples) == 345, len(prepared.samples)
out.write_text(json.dumps(payload))
print(f'strict PASS prep={len(prepared.samples)} digest={route.digest}')
EOF
cmp "$COMMITTED" "$REGEN" && echo "regen byte-identical to committed manifest"
# Compile through the shipped entry point (never an inline copy): the
# single provenance-label rule in compile_manifest.py keeps H identical.
RECEIPT="$("$PIN" -m global_planner.compile_manifest \
    "$REGEN" "$OUT/${MAP}_out" "$MAP")"
echo "$RECEIPT"
"$SYS" - "$REGEN" "$OUT/${MAP}_out" "$EXPECTED_H" "$RECEIPT" <<'EOF'
import json, math, sys
from pathlib import Path
from global_planner.route_artifact import load_reference
from global_planner.route_compile import load_policy
man, out, expected, receipt_s = sys.argv[1:5]
receipt = json.loads(receipt_s)
assert receipt['status'] == 'PASS', receipt
assert receipt['geometry_status'] == 'PASS', receipt
assert receipt['dynamics_status'] == 'PASS', receipt
assert receipt['H'] == expected, (receipt['H'], expected)
print(f'compile PASS H={receipt["H"]} geom=PASS dyn=PASS (matches {expected})')
cfg = Path('planner/global_planner/config/project_a')
policies, context, spacing = load_policy(
    str(cfg / 'policies/synthetic_policy.json'))
ref = load_reference(out, expected_H=expected,
                     validation_context=context)
smp = ref.sample(5.0)
assert smp.H == expected, (smp.H, expected)
assert smp.s == 5.0 and math.isfinite(smp.curvature)
assert math.isfinite(smp.speed_mps) and math.isfinite(smp.time_s)
print(f'query PASS s={smp.s} occ={smp.occurrence_id} '
      f'v={smp.speed_mps:.3f} k={smp.curvature:.4f}')
EOF
echo "test chain reproduced; outputs in $OUT"
