# Copyright 2026 ForzaETH
"""Headless CLI for the annotation pipeline (same core as the web/ROS UI).

Examples:
    python3 -m global_planner.annotation_tool extract \
        --map stack_master/maps/test/test.yaml \
        --session draft.json --out out/
"""
import argparse
import json
import os
import time
from pathlib import Path

from .annotation_core import (AnnotationError, TrackMap, VALIDATE_THINNINGS,
                              atomic_write_text, build_and_validate,
                              export_name, extract_boundaries,
                              geometry_digest, load_session,
                              require_approved, run_pinned_compile,
                              save_session)


def _validated_receipt(route, prepared, info):
    """Shared headless receipt for preview and export."""
    return {'status': 'VALIDATED', 'route_digest': route.digest,
            'occurrences': len(route.occurrences),
            'prepared_samples': len(prepared.samples),
            'max_correction_m': info['max_correction_m'],
            'smoothing_passes': info['smoothing_passes'],
            'meaning': 'strict input + corridor preparation PASS; '
                       'not optimizer or on-car qualification'}


def main(argv=None):
    """Run one headless annotation operation and print a JSON receipt."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',
                        choices=('extract', 'preview', 'approve', 'export',
                                 'validate'))
    parser.add_argument('--map', required=True)
    parser.add_argument('--session', required=True,
                        help='annotation_project.json with strokes + route')
    parser.add_argument('--out', required=True)
    parser.add_argument('--candidate', default=None,
                        help='candidate digest quoted by approve '
                             '(from preview)')
    args = parser.parse_args(argv)
    try:
        track_map = TrackMap(args.map)
        session = load_session(args.session, track_map)
        outer, inner = extract_boundaries(
            track_map, session['boundary_strokes_px'],
            session.get('stroke_width_px', 5))
        result = {'status': 'CANDIDATE', 'outer_points': len(outer),
                  'inner_points': len(inner)}
        if args.command == 'preview':
            # Read-only: show the exact transformed geometry and its
            # digest without granting approval or writing any file.
            # Built with the export approval provenance so the receipt
            # matches what export will write.
            if not session.get('route_px'):
                raise AnnotationError('draw the directed route loop first')
            _, route, prepared, info = build_and_validate(
                track_map, outer, inner, session['route_px'],
                author=session.get('author', 'operator'),
                approval='operator-approved',
                chain_dp_epsilon_m=session.get('chain_dp_epsilon_m', 0.02))
            result = _validated_receipt(route, prepared, info)
            result['candidate_digest'] = geometry_digest(session, track_map)
        elif args.command == 'approve':
            # Bind approval to the previewed candidate digest; the
            # geometry must be unchanged since that preview.
            if not args.candidate:
                raise AnnotationError('approve needs --candidate <digest> '
                                      'from a preview')
            if args.candidate != geometry_digest(session, track_map):
                raise AnnotationError('approve refused: geometry changed '
                                      'since preview (preview again)')
            if not session.get('route_px'):
                raise AnnotationError('draw the directed route loop first')
            # Gate on strict validation so only a valid candidate can be
            # approved; the payload itself is written by export.
            build_and_validate(
                track_map, outer, inner, session['route_px'],
                author=session.get('author', 'operator'), approval='none',
                chain_dp_epsilon_m=session.get('chain_dp_epsilon_m', 0.02))
            session['approval'] = 'operator-approved'
            session['approval_digest'] = args.candidate
            session['revision'] = int(session.get('revision', 1)) + 1
            save_session(session, args.session)
            result = {'status': 'PASS',
                      'approval_digest': args.candidate,
                      'revision': session['revision']}
        elif args.command == 'export':
            # Approval must be bound to this exact geometry; a stale
            # approval from before the last edit is refused, not honored.
            require_approved(session, track_map)
            payload, route, prepared, info = build_and_validate(
                track_map, outer, inner, session['route_px'],
                author=session.get('author', 'operator'),
                approval='operator-approved',
                chain_dp_epsilon_m=session.get('chain_dp_epsilon_m', 0.02))
            out = Path(args.out)
            out.mkdir(parents=True, exist_ok=True)
            atomic_write_text(out / export_name(track_map),
                              json.dumps(payload, indent=1))
            result = _validated_receipt(route, prepared, info)
        elif args.command == 'validate':
            # Explicit offline step: full optimizer + independent checkers
            # over bounded thinning settings; the winner is saved into the
            # session so preview/approve/export all use it afterwards.
            # Generation runs here; optimization runs pinned, like repro.
            if not session.get('route_px'):
                raise AnnotationError('draw the directed route loop first')
            attempts = []
            tag = (time.strftime('%Y%m%d-%H%M%S') + '-%d'
                   % (os.getpid() % 10000))
            work = Path(args.out) / 'validation' / tag
            for index, eps in enumerate(VALIDATE_THINNINGS):
                try:
                    payload, _, _, _ = build_and_validate(
                        track_map, outer, inner, session['route_px'],
                        author=session.get('author', 'operator'),
                        approval='operator-approved',
                        chain_dp_epsilon_m=eps)
                    manifest = work / ('candidate-%d.json' % index)
                    manifest.parent.mkdir(parents=True, exist_ok=True)
                    atomic_write_text(manifest, json.dumps(payload, indent=1))
                    receipt = run_pinned_compile(
                        manifest, work / ('compile-%d' % index),
                        session.get('map_png', ''), eps)
                except Exception as exc:  # noqa: BLE001 - try next
                    attempts.append('eps %.2f: %s' % (eps, exc))
                    continue
                if (receipt['status'] == 'PASS'
                        and receipt.get('geometry_status') == 'PASS'
                        and receipt.get('dynamics_status') == 'PASS'):
                    session['chain_dp_epsilon_m'] = eps
                    session['revision'] = int(session.get('revision', 1)) + 1
                    session['approval'] = 'none'
                    session['approval_digest'] = None
                    save_session(session, args.session)
                    result = {'status': 'PASS',
                              'chain_dp_epsilon_m': eps,
                              'artifact_H': receipt['H'],
                              'attempts': attempts,
                              'revision': session['revision']}
                    break
                attempts.append('eps %.2f: %s'
                                % (eps, receipt.get('reason')
                                   or receipt['status']))
            else:
                raise AnnotationError(
                    'no thinning reached full validation (%s)'
                    % '; '.join(attempts))
        print(json.dumps(result, sort_keys=True))
        return 0
    except (AnnotationError, ValueError, OSError) as exc:
        print(json.dumps({'status': 'FAIL', 'reason': str(exc)}, sort_keys=True))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
