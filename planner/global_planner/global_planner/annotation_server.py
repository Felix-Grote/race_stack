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
                              extract_boundaries, load_session, new_session,
                              save_session)

STATE = {'map': None, 'session': None, 'extraction': None, 'maps_dir': None,
         'out_dir': None}


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
    """Accept one completed stroke/route, or reject it with a reason."""
    if STATE['session'] is None:
        raise AnnotationError('no open session')
    field, value = body.get('field'), body.get('value')
    if field not in ('boundary_strokes_px', 'route_px'):
        raise AnnotationError(f'unknown editable field: {field}')
    if field == 'route_px' and len(value) < 3:
        raise AnnotationError('route needs at least 3 points')
    STATE['session'][field] = value
    STATE['session']['approval'] = 'none'  # any edit revokes approval
    STATE['extraction'] = None
    return {'status': 'PASS', 'message': f'{field} updated (draft, unapproved)',
            'session': _session_view()}


def op_extract(body):
    """Run boundary extraction on the patched raster copy."""
    if STATE['session'] is None:
        raise AnnotationError('no open session')
    s = STATE['session']
    extraction = extract_boundaries(STATE['map'], s['boundary_strokes_px'],
                                    s.get('stroke_width_px', 5))
    STATE['extraction'] = extraction
    return {'status': 'CANDIDATE',
            'message': 'extracted boundaries are a CANDIDATE until approved',
            'session': _session_view()}


def op_export(body):
    """Approve, build the Project A manifest, and validate it strictly."""
    if STATE['session'] is None or STATE['map'] is None:
        raise AnnotationError('no open session')
    s = STATE['session']
    if not s.get('route_px'):
        raise AnnotationError('draw the directed route loop first')
    outer, inner = extract_boundaries(STATE['map'], s['boundary_strokes_px'],
                                      s.get('stroke_width_px', 5))
    STATE['extraction'] = (outer, inner)
    payload, route, _prepared = build_and_validate(
        STATE['map'], outer, inner, s['route_px'],
        author=s.get('author', 'operator'), approval='operator-approved')
    out = Path(STATE['out_dir']) / 'legal_route.json'
    out.write_text(json.dumps(payload, indent=1), encoding='utf-8')
    s['approval'] = 'operator-approved'
    return {'status': 'VALIDATED',
            'message': f'validate_route + prepare_route PASS; route digest '
                       f'{route.digest[:16]}… written to {out}. This is '
                       'input/topology validation, not optimizer or '
                       'on-car qualification.',
            'session': _session_view()}


def op_save(body):
    """Persist the editable draft (never the source map)."""
    if STATE['session'] is None:
        raise AnnotationError('no open session')
    path = Path(STATE['out_dir']) / f"{STATE['map'].png_path.stem}_annotation.json"
    save_session(STATE['session'], path)
    return {'status': 'PASS', 'message': f'draft saved to {path}'}


def op_undo(body):
    """Drop the last boundary stroke."""
    if STATE['session'] is None:
        raise AnnotationError('no open session')
    strokes = STATE['session'].get('boundary_strokes_px', [])
    if strokes:
        strokes.pop()
    STATE['extraction'] = None
    return {'status': 'PASS', 'message': 'last boundary stroke removed',
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
    STATE['maps_dir'], STATE['out_dir'] = args.maps, args.out
    Path(args.out).mkdir(parents=True, exist_ok=True)
    server = HTTPServer(('127.0.0.1', args.port), Handler)
    print(f'annotation backend on http://127.0.0.1:{args.port}/ (loopback only)')
    server.serve_forever()


if __name__ == '__main__':
    main()
