# Copyright 2026 ForzaETH
"""Compile one manifest file with the pinned optimizer stack.

Subprocess entry point: the annotation server and CLI run under the
system interpreter (exact generator numerics), while optimization is
only valid under the pinned stack. This module runs there and nowhere
else: the gate below checks the interpreter and package versions
against repro/receipts.json before anything is imported or compiled,
so a wrong-interpreter run fails closed instead of silently producing
invalid optimization. It reads a strict Project A manifest, runs the
unchanged compile_reference plus the independent checkers, and prints
a JSON receipt. It never generates geometry.
"""

import importlib.metadata
import json
import sys
from pathlib import Path

USAGE = 'usage: compile_manifest.py <manifest.json> <out_dir> <map>'

# Informational provenance labels (single shared rule, also used by the
# repro scripts): the artifact H hashes the payload including this
# block, so every entry point must label identically for H to match.
# Map and manifest file name only — never temp paths or settings, which
# differ between the UI validate flow and the repro chains.
_PINNED_PACKAGES = (('numpy', 'numpy'), ('scipy', 'scipy'),
                    ('quadprog', 'quadprog'),
                    ('trajectory-planning-helpers',
                     'trajectory-planning-helpers'))


def _check_pinned_stack():
    """Return an error string when this is not the pinned stack, else None.

    The pinned record lives in repro/receipts.json (single source of
    truth); anything unreadable or mismatched fails closed.
    """
    try:
        record = json.loads(
            (Path(__file__).parents[1] / 'repro' / 'receipts.json')
            .read_text(encoding='utf-8'))['pinned_env']
    except (OSError, ValueError, KeyError) as exc:
        return 'cannot read pinned record repro/receipts.json (%s)' % exc
    problems = []
    have_python = sys.version.split()[0]
    if have_python != record.get('cpython'):
        problems.append('cpython %s (need %s)'
                        % (have_python, record.get('cpython')))
    for key, dist in _PINNED_PACKAGES:
        try:
            have = importlib.metadata.version(dist)
        except importlib.metadata.PackageNotFoundError:
            have = 'missing'
        if have != record.get(key):
            problems.append('%s %s (need %s)'
                            % (key, have, record.get(key)))
    return '; '.join(problems) or None


def main(argv):
    """Compile argv into a receipt; print the receipt as JSON."""
    if len(argv) != 4:
        print(USAGE, file=sys.stderr)
        return 2
    gate = _check_pinned_stack()
    if gate is not None:
        print('compile_manifest refused: %s' % gate, file=sys.stderr)
        return 1
    from global_planner.route_artifact import decode_record
    from global_planner.route_compile import compile_reference, load_policy
    from global_planner.route_input import validate_route
    from global_planner.route_validate import Footprint
    from global_planner.cyclic_retime import DynamicsModel

    manifest_path, out_dir, map_name = argv[1:4]
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
                    'manifest': Path(manifest_path).name})
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
