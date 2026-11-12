#!/bin/bash
# Reproduce the baku-map full chain (ridge seed, walls thinned at 0.03 m).
#
# Usage (from the repository root): planner/global_planner/repro/repro_baku.sh [pinned-python]
# Same env contract as repro_test.sh. Expected: strict PASS (479 samples),
# compile PASS H=82f9b533..., independent geometry/dynamics PASS, query PASS.
# Shared generator gate: repro/env.sh (sets SYS, checks the env).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../../.." && pwd)"
cd "$REPO"
source "$HERE/env.sh"
PIN="${1:-${PINNED_PY:-$HOME/venvs/forza-pinned/bin/python}}"
OUT="${REPRO_OUT:-$HERE/out_baku}"
MAP=baku EXPECTED_H=82f9b533ce50ad3e7b974187f19e9c40d944ca8b87115d21eb34e5fb41ac03f0
COMMITTED="$HERE/manifests/manifest_baku_bal003.json"
REGEN="$OUT/manifest_baku_bal003.json"
mkdir -p "$OUT"
export PYTHONPATH="$REPO/planner/global_planner"
"$SYS" - "$MAP" "$REGEN" <<'EOF'
import json, sys
from pathlib import Path
from global_planner.annotation_core import (
    TrackMap, build_and_validate, extract_boundaries, ridge_seed)
name, out = sys.argv[1], Path(sys.argv[2])
tm = TrackMap(Path(f'stack_master/maps/{name}/{name}.yaml'))
outer, inner = extract_boundaries(tm)
seed = ridge_seed(tm, outer, inner)
payload, route, prepared, info = build_and_validate(
    tm, outer, inner, seed, approval='operator-approved',
    chain_dp_epsilon_m=0.03)
assert len(prepared.samples) == 479, len(prepared.samples)
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
echo "baku chain reproduced; outputs in $OUT"
