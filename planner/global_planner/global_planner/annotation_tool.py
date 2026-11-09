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

from .annotation_core import (AnnotationError, TrackMap, build_and_validate,
                              extract_boundaries, geometry_digest,
                              load_session, require_approved, save_session)


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
                        choices=('extract', 'preview', 'approve', 'export'))
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
                approval='operator-approved')
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
                author=session.get('author', 'operator'), approval='none')
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
                approval='operator-approved')
            out = Path(args.out)
            out.mkdir(parents=True, exist_ok=True)
            (out / 'legal_route.json').write_text(
                json.dumps(payload, indent=1), encoding='utf-8')
            result = _validated_receipt(route, prepared, info)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (AnnotationError, ValueError, OSError) as exc:
        print(json.dumps({'status': 'FAIL', 'reason': str(exc)}, sort_keys=True))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
