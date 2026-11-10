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
"$PIN" - "$MAP" "$REGEN" "$OUT" "$EXPECTED_H" <<'EOF'
import json, math, sys
from global_planner.route_artifact import decode_record, load_reference
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
ref = load_reference(receipt.artifact_path, expected_H=expected,
                     validation_context=context)
smp = ref.sample(5.0)
assert smp.H == expected, (smp.H, expected)
assert smp.s == 5.0 and math.isfinite(smp.curvature)
assert math.isfinite(smp.speed_mps) and math.isfinite(smp.time_s)
print(f'query PASS s={smp.s} occ={smp.occurrence_id} '
      f'v={smp.speed_mps:.3f} k={smp.curvature:.4f}')
EOF
echo "test chain reproduced; outputs in $OUT"
