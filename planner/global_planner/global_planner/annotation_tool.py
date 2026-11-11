# Copyright 2026 ForzaETH
"""Headless CLI for the annotation pipeline (same core as the web/ROS UI).

Examples:
    python3 -m global_planner.annotation_tool extract \
        --map stack_master/maps/test/test.yaml \
        --session draft.json --out out/
"""
import argparse
import json
from pathlib import Path

from .annotation_core import (AnnotationError, TrackMap, atomic_write_text,
                              build_and_validate, effective_free_mask,
                              export_name, extract_boundaries,
                              geometry_digest, load_session, require_approved,
                              save_session, select_thinning)


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
                                 'validate', 'select-region'))
    parser.add_argument('--map', required=True)
    parser.add_argument('--session', required=True,
                        help='annotation_project.json with strokes + route')
    parser.add_argument('--out', required=False, default=None)
    parser.add_argument('--candidate', default=None,
                        help='candidate digest quoted by approve '
                             '(from preview)')
    parser.add_argument('--pixel', default=None,
                        help='retained region seed for select-region as u,v '
                             '(omit with --clear)')
    parser.add_argument('--clear', action='store_true',
                        help='clear the retained region (select-region only)')
    args = parser.parse_args(argv)
    try:
        track_map = TrackMap(args.map)
        session = load_session(args.session, track_map)
        if args.command == 'select-region':
            if args.clear:
                session['retained_region_px'] = None
            elif args.pixel is None:
                raise AnnotationError(
                    'select-region needs --pixel u,v or --clear')
            else:
                try:
                    parts = [float(c) for c in args.pixel.split(',')]
                except ValueError:
                    raise AnnotationError(
                        'select-region --pixel must be u,v integers')
                if (len(parts) != 2
                        or any(p != int(p) for p in parts)):
                    raise AnnotationError(
                        'select-region --pixel must be u,v integers')
                seed = [int(p) for p in parts]
                effective_free_mask(
                    track_map, session.get('boundary_strokes_px', []),
                    session.get('stroke_width_px', 5), seed)
                outer, inner = extract_boundaries(
                    track_map, session.get('boundary_strokes_px', []),
                    session.get('stroke_width_px', 5), seed)
                session['retained_region_px'] = seed
            session['revision'] = int(session.get('revision', 1)) + 1
            session['approval'] = 'none'
            session['approval_digest'] = None
            save_session(session, args.session)
            print(json.dumps({'status': 'PASS',
                              'retained_region_px':
                                  session.get('retained_region_px'),
                              'revision': session['revision']}, sort_keys=True))
            return 0
        if args.command in ('export', 'validate') and not args.out:
            raise AnnotationError('this command needs --out <dir>')
        outer, inner = extract_boundaries(
            track_map, session['boundary_strokes_px'],
            session.get('stroke_width_px', 5),
            session.get('retained_region_px'))
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
            # Explicit offline validation; the winner is saved into the
            # session, see op_validate.
            if not session.get('route_px'):
                raise AnnotationError('draw the directed route loop first')
            eps, artifact_h, attempts = select_thinning(
                track_map, outer, inner, session['route_px'],
                session.get('author', 'operator'),
                session.get('map_png', ''), args.out)
            session['chain_dp_epsilon_m'] = eps
            session['revision'] = int(session.get('revision', 1)) + 1
            session['approval'] = 'none'
            session['approval_digest'] = None
            save_session(session, args.session)
            result = {'status': 'PASS',
                      'chain_dp_epsilon_m': eps,
                      'artifact_H': artifact_h,
                      'attempts': attempts,
                      'revision': session['revision']}
        print(json.dumps(result, sort_keys=True))
        return 0
    except (AnnotationError, ValueError, TypeError, OSError,
            KeyError, OverflowError) as exc:
        print(json.dumps({'status': 'FAIL', 'reason': str(exc)}, sort_keys=True))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
