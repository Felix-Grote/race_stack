#!/bin/bash
# Reproduce the baku-map full chain (ridge seed, walls thinned at 0.03 m).
#
# Usage (from the repository root): planner/global_planner/repro/repro_baku.sh [pinned-python]
# Same env contract as repro_test.sh. Expected: strict PASS (479 samples),
# compile PASS H=82f9b533..., independent geometry/dynamics PASS.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../../.." && pwd)"
cd "$REPO"
SYS="${SYSTEM_PY:-python3.12}"
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
"$PIN" - "$MAP" "$REGEN" "$OUT" "$EXPECTED_H" <<'EOF'
import json, sys
from global_planner.route_artifact import decode_record
from global_planner.route_compile import compile_reference, load_policy
from global_planner.route_input import validate_route
from global_planner.route_validate import Footprint
from global_planner.cyclic_retime import DynamicsModel
from pathlib import Path
name, man, out, expected = sys.argv[1:5]
cfg = Path('planner/global_planner/config/project_a')
policies, context, spacing = load_policy(cfg / 'policies/synthetic_policy.json')
md = json.loads((cfg / 'models/synthetic_model.json').read_text())
model = decode_record(DynamicsModel, md['model'], 'model')
footprint = decode_record(Footprint, md['footprint'], 'footprint')
route = validate_route(json.loads(Path(man).read_text()))
receipt = compile_reference(
    route, model, footprint, policies, output_dir=f'{out}/{name}_out',
    retime_spacing_m=spacing, validation_context=context,
    provenance={'map': name, 'manifest': Path(man).name})
assert receipt.status == 'PASS', receipt.reason
assert receipt.geometry.status == 'PASS', receipt.geometry.reason
assert receipt.dynamics.status == 'PASS', receipt.dynamics.reason
assert receipt.H == expected, (receipt.H, expected)
print(f'compile PASS H={receipt.H} geom=PASS dyn=PASS (matches {expected})')
EOF
echo "baku chain reproduced; outputs in $OUT"
