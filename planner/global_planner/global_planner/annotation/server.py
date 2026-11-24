"""
The annotation editor's web page and command line.

Run:        ros2 run global_planner annotation --maps stack_master/maps
            then open http://127.0.0.1:8766 in a browser. With --export <folder>/<map>, it
            instead checks and exports that map's saved draft, without a browser.
serving:    the page and its script, and one action per request, one request at a time, on
            the loopback address only.
"""
import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path

from .editor import Editor
from .track_map import AnnotationError
from ..car import Car

# The files the page is made of, and their content types.
_FILES = {'/': ('ui.html', 'text/html; charset=utf-8'),
          '/ui.js': ('ui.js', 'text/javascript; charset=utf-8'),
          '/menubar.js': ('menubar.js', 'text/javascript; charset=utf-8'),
          '/checklist.js': ('checklist.js', 'text/javascript; charset=utf-8'),
          '/ui.css': ('ui.css', 'text/css; charset=utf-8'),
          '/win95.css': ('win95.css', 'text/css; charset=utf-8')}


def handler(editor: Editor, before_action=None) -> type[BaseHTTPRequestHandler]:
    """Return the request handler serving the page and the editor's actions."""
    actions = {'open': lambda b: editor.open(b.get('map')),
               'edit': lambda b: editor.edit(b.get('field'), b.get('value')),
               'suggest': lambda b: editor.suggest(),
               'reverse': lambda b: editor.reverse(),
               'export': lambda b: editor.export(), 'save': lambda b: editor.save()}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args) -> None:
            """Keep the terminal quiet."""

        def _send(self, code: int, body: bytes, kind: str) -> None:
            self.send_response(code)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802 - the name http.server calls
            """Serve the page, or the current view."""
            if self.path in _FILES:
                name, kind = _FILES[self.path]
                self._send(200, Path(__file__).with_name(name).read_bytes(), kind)
            elif self.path == '/api/view':
                self._send(200, json.dumps(editor.view()).encode(), 'application/json')
            else:
                self._send(404, b'not found', 'text/plain')

        def do_POST(self) -> None:  # noqa: N802 - the name http.server calls
            """Run one action; the reply is its message, or why it failed, and the new view."""
            action = actions.get(self.path.removeprefix('/api/'))
            at_px = []
            try:
                if action is None:
                    raise AnnotationError(f'no action {self.path}')

                body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0)))
                                  or b'{}')
                if not isinstance(body, dict):
                    raise AnnotationError('the request must be a JSON object')

                if before_action is not None:
                    before_action(self.path.removeprefix('/api/'))
                reply = {'ok': True, 'message': action(body)}
            except (AnnotationError, ValueError, OSError) as exc:
                reply = {'ok': False, 'message': str(exc)}
                at_px = list(getattr(exc, 'at_px', []))
            except Exception as exc:  # noqa: BLE001 - a bug must reach the page, not hang it
                reply = {'ok': False, 'message': f'unexpected {type(exc).__name__}: {exc}'}

            reply['view'] = editor.view()
            if at_px:
                # A refused edit is marked where it fails, until the next reply.
                reply['view']['problem_px'] = at_px
            self._send(200, json.dumps(reply).encode(), 'application/json')

    return Handler


def main(argv: list[str] | None = None) -> None:
    """Serve the editor on the loopback address until interrupted."""
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--maps', required=True, help='folder holding one folder per map')
    parser.add_argument('--port', type=int, default=8766)
    parser.add_argument('--car', help="car_model.yaml: also check the portal zones for the car's "
                                      'reach')
    parser.add_argument('--margin', type=float, default=.05,
                        help='clearance kept around the car body, in metres')
    parser.add_argument('--export', metavar='MAP', nargs='+',
                        help='check and export the saved drafts of these maps, e.g. test/test, '
                             'and exit')
    args = parser.parse_args(argv)
    car = Car.load(args.car, margin_m=args.margin) if args.car else None
    editor = Editor(args.maps, car)
    if args.export:
        failed = False
        for name in args.export:
            try:
                print(f'{name}: {editor.open(name)}; {editor.export()}')
            except (AnnotationError, ValueError, OSError) as exc:
                print(f'{name}: FAILED: {exc}')
                failed = True

        raise SystemExit(1 if failed else 0)

    server = HTTPServer(('127.0.0.1', args.port), handler(editor))
    print(f'annotation editor on http://127.0.0.1:{args.port}')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
