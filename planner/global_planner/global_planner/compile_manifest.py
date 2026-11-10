# Copyright 2026 ForzaETH
"""Compile one manifest file with the pinned optimizer stack.

Subprocess entry point: the annotation server and CLI run under the
system interpreter (exact generator numerics), while optimization is
only valid under the pinned stack. This module runs there and nowhere
else: it reads a strict Project A manifest, runs the unchanged
compile_reference plus the independent checkers, and prints a JSON
receipt. It never generates geometry.
"""

import json
import sys
from pathlib import Path


def main(argv):
    """Compile argv[1] into argv[2]; print the receipt as JSON."""
    from global_planner.route_artifact import decode_record
    from global_planner.route_compile import compile_reference, load_policy
    from global_planner.route_input import validate_route
    from global_planner.route_validate import Footprint
    from global_planner.cyclic_retime import DynamicsModel

    manifest_path, out_dir, map_name, eps = argv[1:5]
    cfg = Path(__file__).parents[1] / 'config' / 'project_a'
    policies, context, spacing = load_policy(
        str(cfg / 'policies' / 'synthetic_policy.json'))
    md = json.loads((cfg / 'models' / 'synthetic_model.json')
                    .read_text(encoding='utf-8'))
    model = decode_record(DynamicsModel, md['model'], 'model')
    footprint = decode_record(Footprint, md['footprint'], 'footprint')
    route = validate_route(json.loads(Path(manifest_path).read_text()))
    receipt = compile_reference(
        route, model, footprint, policies, output_dir=out_dir,
        retime_spacing_m=spacing, validation_context=context,
        provenance={'map': map_name,
                    'chain_dp_epsilon_m': repr(float(eps))})
    print(json.dumps({
        'status': receipt.status,
        'reason': receipt.reason,
        'H': receipt.H,
        'geometry_status': (None if receipt.geometry is None
                            else receipt.geometry.status),
        'dynamics_status': (None if receipt.dynamics is None
                            else receipt.dynamics.status),
    }, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
