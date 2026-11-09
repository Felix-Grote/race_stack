# Copyright 2026 ForzaETH
"""Local offline backend + web frontend for the annotation tool.

Stdlib-only HTTP transport. The same session operations are exposed by
``annotation_node`` over ROS (std_msgs/String JSON on
``/planner_annotation/*``) when rclpy is available; geometry never
depends on either transport. Binds to loopback only, never touches the
driving stack, and never writes to the source map files.

Run: ``python3 -m global_planner.annotation_server --maps <dir> --port 8766``
then open http://127.0.0.1:8766/ in a browser.
"""
import argparse
import base64
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from .annotation_core import (AnnotationError, TrackMap, build_and_validate,
                              extract_boundaries, geometry_digest,
                              load_session, new_session, save_session)

STATE = {'map': None, 'session': None, 'extraction': None, 'maps_dir': None,
         'out_dir': None}


def configure(maps_dir, out_dir):
    """Bind the shared backend to directories (HTTP and ROS entry points).

    Both transports reuse these operations, so both must configure them:
    without this, opening a map fails with an explicit error instead of a
    late ``TypeError`` on an unconfigured path.
    """
    if not maps_dir or not Path(maps_dir).is_dir():
        raise AnnotationError(f'maps directory not found: {maps_dir}')
    STATE['maps_dir'], STATE['out_dir'] = str(maps_dir), str(out_dir)
    Path(out_dir).mkdir(parents=True, exist_ok=True)


def require_open():
    """Fail closed when no session is open yet."""
    if STATE['session'] is None or STATE['map'] is None:
        raise AnnotationError('no open session (open a map first)')
    return STATE['session'], STATE['map']


def _touch(session):
    """Record an edit: bump revision, revoke approval, drop extraction.

    Every geometry mutation funnels through here, so no edit path (update,
    undo, clear) can retain an approval granted to a previous geometry.
    """
    session['revision'] = int(session.get('revision', 1)) + 1
    session['approval'] = 'none'
    session['approval_digest'] = None
    STATE['extraction'] = None


def _reply(handler, payload, code=200):
    body = json.dumps(payload).encode()
    handler.send_response(code)
    handler.send_header('Content-Type', 'application/json')
    handler.send_header('Content-Length', str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _session_view():
    s = dict(STATE['session'])
    png = Path(STATE['map'].png_path).read_bytes()
    s['map_png_data_url'] = 'data:image/png;base64,' + base64.b64encode(png).decode()
    if STATE['extraction']:
        outer, inner = STATE['extraction']
        s['extraction'] = {'outer_px': outer.tolist(), 'inner_px': inner.tolist()}
    return s


def op_open(body):
    """Open (or reopen) a session for a map name inside the maps dir."""
    if not STATE.get('maps_dir') or not STATE.get('out_dir'):
        raise AnnotationError('backend not configured (set maps/out dirs first)')
    name = body.get('map', '')
    yaml_path = Path(STATE['maps_dir']) / name / f'{name}.yaml'
    if not yaml_path.exists():
        yaml_path = Path(STATE['maps_dir']) / f'{name}.yaml'
    track_map = TrackMap(yaml_path)
    draft = Path(STATE['out_dir']) / f'{track_map.png_path.stem}_annotation.json'
    if draft.exists():
        session = load_session(draft, track_map)
        message = 'reopened saved draft'
    else:
        session = new_session(track_map)
        message = 'new session'
    STATE.update(map=track_map, session=session, extraction=None)
    return {'status': 'PASS', 'message': message, 'session': _session_view()}


def op_update(body):
    """Accept one completed stroke/route/width, or reject it with a reason.

    An empty route clears the draft route (approval revoked either way).
    The stroke width is operator-visible and deterministic: changing it
    alters patched geometry, so it revokes approval like any other edit.
    """
    session, _ = require_open()
    field, value = body.get('field'), body.get('value')
    if field not in ('boundary_strokes_px', 'route_px', 'stroke_width_px'):
        raise AnnotationError(f'unknown editable field: {field}')
    if field == 'stroke_width_px':
        if (isinstance(value, bool) or not isinstance(value, int)
                or not 1 <= value <= 31):
            raise AnnotationError('stroke_width_px must be an integer 1..31')
    else:
        if not isinstance(value, list):
            raise AnnotationError(f'{field} must be a list of points')
        if field == 'route_px' and 0 < len(value) < 3:
            raise AnnotationError('route needs at least 3 points (or empty to clear)')
    session[field] = value
    _touch(session)  # any edit revokes approval
    note = 'cleared' if field == 'route_px' and not value else 'updated'
    return {'status': 'PASS',
            'message': f'{field} {note} (draft rev {session["revision"]}, unapproved)',
            'session': _session_view()}


def op_extract(body):
    """Run boundary extraction on the patched raster copy."""
    session, track_map = require_open()
    extraction = extract_boundaries(track_map, session['boundary_strokes_px'],
                                    session.get('stroke_width_px', 5))
    STATE['extraction'] = extraction
    return {'status': 'CANDIDATE',
            'message': 'extracted boundaries are a CANDIDATE until approved; '
                       'inspect the overlay, then approve via export',
            'session': _session_view()}


def op_export(body):
    """Approve, build the Project A manifest, and validate it strictly.

    Approval is bound to the exact exported geometry via a digest: any
    later edit revokes it, and the headless CLI re-checks the digest
    before exporting the same session.
    """
    session, track_map = require_open()
    if not session.get('route_px'):
        raise AnnotationError('draw the directed route loop first')
    outer, inner = extract_boundaries(track_map, session['boundary_strokes_px'],
                                      session.get('stroke_width_px', 5))
    STATE['extraction'] = (outer, inner)
    payload, route, prepared, info = build_and_validate(
        track_map, outer, inner, session['route_px'],
        author=session.get('author', 'operator'), approval='operator-approved')
    out = Path(STATE['out_dir']) / 'legal_route.json'
    out.write_text(json.dumps(payload, indent=1), encoding='utf-8')
    session['approval'] = 'operator-approved'
    session['approval_digest'] = geometry_digest(session, track_map)
    session['revision'] = int(session.get('revision', 1)) + 1
    validated_px = [[list(map(float, track_map.world_to_pixel(pt)))
                     for pt in occ['seed']] for occ in payload['occurrences']]
    return {'status': 'VALIDATED',
            'message': f'validate_route + prepare_route PASS; route digest '
                       f'{route.digest[:16]}… written to {out}. '
                       f'seed correction max {info["max_correction_m"]:.3f} m '
                       f'over {info["seed_samples"]} samples '
                       f'(smoothing {info["smoothing_passes"]}). This is '
                       'input/topology validation, not optimizer or '
                       'on-car qualification.',
            'route_digest': route.digest,
            'occurrences': len(route.occurrences),
            'prepared_samples': len(prepared.samples),
            'max_correction_m': info['max_correction_m'],
            'smoothing_passes': info['smoothing_passes'],
            'validated_route_px': validated_px,
            'session': _session_view()}


def op_save(body):
    """Persist the editable draft (never the source map)."""
    session, track_map = require_open()
    path = Path(STATE['out_dir']) / f"{track_map.png_path.stem}_annotation.json"
    save_session(session, path)
    return {'status': 'PASS',
            'message': f'draft rev {session.get("revision")} '
                       f'({session.get("approval")}) saved to {path}'}


def op_undo(body):
    """Drop the last boundary stroke; approval is revoked with the edit."""
    session, _ = require_open()
    strokes = session.get('boundary_strokes_px', [])
    if strokes:
        strokes.pop()
    _touch(session)
    return {'status': 'PASS',
            'message': 'last boundary stroke removed; approval revoked '
                       f'(draft rev {session["revision"]}, unapproved)',
            'session': _session_view()}


OPS = {'/api/session/open': op_open, '/api/session/update': op_update,
       '/api/session/extract': op_extract, '/api/session/export': op_export,
       '/api/session/save': op_save, '/api/session/undo': op_undo}


class Handler(BaseHTTPRequestHandler):
    """Loopback-only JSON API plus the single-page frontend."""

    def log_message(self, *args):
        """Keep the console quiet."""

    def do_GET(self):
        """Serve the frontend page."""
        if self.path in ('/', '/index.html'):
            html = (Path(__file__).parent / 'annotation_ui.html').read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(html)))
            self.end_headers()
            self.wfile.write(html)
        else:
            _reply(self, {'status': 'FAIL', 'message': 'not found'}, 404)

    def do_POST(self):
        """Dispatch one session operation; errors are explicit replies."""
        try:
            length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(length) or b'{}')
            op = OPS.get(self.path)
            if op is None:
                raise AnnotationError(f'unknown operation {self.path}')
            _reply(self, op(body))
        except (AnnotationError, ValueError, OSError) as exc:
            _reply(self, {'status': 'FAIL', 'message': str(exc)}, 400)


def main(argv=None):
    """Start the loopback annotation backend."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--maps', required=True, help='directory of map folders')
    parser.add_argument('--out', default='/tmp/annotation_out')
    parser.add_argument('--port', type=int, default=8766)
    args = parser.parse_args(argv)
    configure(args.maps, args.out)
    server = HTTPServer(('127.0.0.1', args.port), Handler)
    print(f'annotation backend on http://127.0.0.1:{args.port}/ (loopback only)')
    server.serve_forever()


if __name__ == '__main__':
    main()
