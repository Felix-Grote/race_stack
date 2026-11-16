# Copyright 2026 ForzaETH
"""Headless CLI for the annotation pipeline (same core as the web/ROS UI).

Examples:
    python3 -m global_planner.annotation_tool extract \
        --map stack_master/maps/test/test.yaml \
        --session draft.json --out out/

Preview, approve and export enforce the same digest binding as the
server: approval must quote the last preview's candidate digest, and
export rebuilds and refuses unless the manifest digest still matches
the approved preview.
"""
import argparse
import json
from pathlib import Path

from .annotation_core import (AnnotationError, TrackMap,
                              atomic_write_text, build_candidate,
                              effective_free_mask, export_name,
                              extract_boundaries, geometry_digest,
                              load_session, require_approved, revoke_approval,
                              save_session, try_thinnings)
from .route.manifest import load_route


def _receipt(checked):
    """Headless receipt shared by preview and export."""
    return {'status': 'VALIDATED', 'route_digest': checked['route_digest'],
            'sections': checked['sections'],
            'lap_length_m': checked['lap_length_m'],
            'samples': checked['stages']['samples'],
            'stages': checked['stages'], 'car': checked['car'],
            'not_checked': checked['not_checked'],
            'max_correction_m': checked['max_correction_m'],
            'smoothing_passes': checked['smoothing_passes'],
            'meaning': 'vector legality + route manifest/lap/portal/'
                       'sample checks PASS; not an optimized or '
                       'dynamics-certified trajectory'}


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
    parser.add_argument('--car', default=None,
                        help='car_model.yaml for vehicle portal-zone checks')
    parser.add_argument('--car-margin', type=float, default=0.05,
                        help='clearance margin in metres around the car body')
    args = parser.parse_args(argv)
    try:
        track_map = TrackMap(args.map)
        session = load_session(args.session, track_map)
        car = None
        if args.car:
            from .car import Car
            car = Car.load(args.car, margin_m=args.car_margin)
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
                extract_boundaries(
                    track_map, session.get('boundary_strokes_px', []),
                    session.get('stroke_width_px', 5), seed)
                session['retained_region_px'] = seed
            revoke_approval(session)
            save_session(session, args.session)
            print(json.dumps({'status': 'PASS',
                              'retained_region_px':
                                  session.get('retained_region_px'),
                              'revision': session['revision']}, sort_keys=True))
            return 0
        if args.command == 'extract':
            outer, inner = extract_boundaries(
                track_map, session['boundary_strokes_px'],
                session.get('stroke_width_px', 5),
                session.get('retained_region_px'))
            print(json.dumps({'status': 'CANDIDATE',
                              'outer_points': len(outer),
                              'inner_points': len(inner)}, sort_keys=True))
            return 0
        if args.command == 'preview':
            # Show the exact candidate and its digests without granting
            # approval or writing any export file. Both digests persist
            # in the session so approve/export bind to this preview.
            _, route, checked, _ = build_candidate(
                track_map, session, car=car)
            result = _receipt(checked)
            digest = geometry_digest(session, track_map)
            result['candidate_digest'] = digest
            session['preview_digest'] = digest
            session['preview_route_digest'] = route.digest
            session['revision'] = int(session.get('revision', 1)) + 1
            save_session(session, args.session)
        elif args.command == 'approve':
            # Mirror annotation_server.op_approve: the quoted digest must
            # be the persisted last preview and still match the geometry,
            # and the candidate must still pass every route check.
            if (not args.candidate
                    or args.candidate != session.get('preview_digest')):
                raise AnnotationError('approve refused: no fresh preview '
                                      'for this geometry '
                                      '(preview the candidate first)')
            if args.candidate != geometry_digest(session, track_map):
                raise AnnotationError('approve refused: geometry changed '
                                      'since preview (preview again)')
            _, route, _, _ = build_candidate(track_map, session, car=car)
            if route.digest != session.get('preview_route_digest'):
                raise AnnotationError('approve refused: rebuilt manifest '
                                      'digest differs from the preview '
                                      '(preview again)')
            session['approval'] = 'operator-approved'
            session['approval_digest'] = args.candidate
            session['approval_route_digest'] = route.digest
            session['revision'] = int(session.get('revision', 1)) + 1
            save_session(session, args.session)
            result = {'status': 'PASS',
                      'approval_digest': args.candidate,
                      'route_digest': route.digest,
                      'revision': session['revision']}
        elif args.command == 'export':
            if not args.out:
                raise AnnotationError('this command needs --out <dir>')
            require_approved(session, track_map)
            if (session.get('approval_digest')
                    != session.get('preview_digest')):
                raise AnnotationError('export refused: no fresh preview '
                                      'for the approved geometry (preview, '
                                      'approve, then export)')
            payload, route, checked, _ = build_candidate(
                track_map, session, car=car)
            if route.digest != session.get('approval_route_digest'):
                raise AnnotationError(
                    'export refused: rebuilt manifest digest differs '
                    'from the approved preview')
            out = Path(args.out)
            out.mkdir(parents=True, exist_ok=True)
            path = out / export_name(track_map)
            atomic_write_text(path, json.dumps(payload, indent=1))
            if load_route(path).digest != route.digest:
                raise AnnotationError(
                    'export readback mismatch: file does not reload to '
                    'the approved manifest digest')
            result = _receipt(checked)
            result['written_to'] = str(path)
        else:  # validate
            # Explicit thinning selection; the winner is saved into the
            # session and approval is revoked (see op_validate).
            eps, (_, route, checked, _), attempts = try_thinnings(
                track_map, session, car=car)
            session['chain_dp_epsilon_m'] = eps
            revoke_approval(session)
            save_session(session, args.session)
            result = {'status': 'PASS',
                      'chain_dp_epsilon_m': eps,
                      'route_digest': route.digest,
                      'stages': checked['stages'],
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
