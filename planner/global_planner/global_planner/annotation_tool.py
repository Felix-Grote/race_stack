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
                              extract_boundaries, load_session)


def main(argv=None):
    """Run one headless annotation operation and print a JSON receipt."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('extract', 'export'))
    parser.add_argument('--map', required=True)
    parser.add_argument('--session', required=True,
                        help='annotation_project.json with strokes + route')
    parser.add_argument('--out', required=True)
    args = parser.parse_args(argv)
    try:
        track_map = TrackMap(args.map)
        session = load_session(args.session, track_map)
        outer, inner = extract_boundaries(
            track_map, session['boundary_strokes_px'],
            session.get('stroke_width_px', 5))
        result = {'status': 'CANDIDATE', 'outer_points': len(outer),
                  'inner_points': len(inner)}
        if args.command == 'export':
            if session.get('approval') != 'operator-approved':
                raise AnnotationError(
                    'export refused: session approval is not '
                    "'operator-approved' (approve in the UI first)")
            payload, route, prepared = build_and_validate(
                track_map, outer, inner, session['route_px'],
                author=session.get('author', 'operator'),
                approval='operator-approved')
            out = Path(args.out)
            out.mkdir(parents=True, exist_ok=True)
            (out / 'legal_route.json').write_text(
                json.dumps(payload, indent=1), encoding='utf-8')
            result = {'status': 'VALIDATED', 'route_digest': route.digest,
                      'occurrences': len(route.occurrences),
                      'prepared_samples': len(prepared.samples),
                      'meaning': 'strict input + corridor preparation PASS; '
                                 'not optimizer or on-car qualification'}
        print(json.dumps(result, sort_keys=True))
        return 0
    except (AnnotationError, ValueError, OSError) as exc:
        print(json.dumps({'status': 'FAIL', 'reason': str(exc)}, sort_keys=True))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
