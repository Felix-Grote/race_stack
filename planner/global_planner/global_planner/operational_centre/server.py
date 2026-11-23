"""Serve the ForzaETH Operational Centre on the local machine."""
import argparse
from http.server import ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
from threading import Lock
from urllib.parse import parse_qs, urlsplit

from .workspace import Workspace
from ..annotation.server import handler as annotation_handler

_ASSETS = {'/': ('index.html', 'text/html'), '/centre.css': ('centre.css', 'text/css'),
           **{f'/{name}': (name, 'text/javascript')
              for name in ('centre.js', 'common.js', 'constraints.js', 'graph.js', 'plots.js',
                           'worksheet.js')}}
_MAX_BODY = 2 * 1024 * 1024


def handler(workspace: Workspace, lock: Lock):
    """Mount the existing editor and serialize access to the workspace."""
    base = annotation_handler(workspace.editor, workspace.prepare_annotation)

    class Handler(base):
        def end_headers(self) -> None:
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('X-Frame-Options', 'SAMEORIGIN')
            super().end_headers()

        def _json(self, code: int, payload: dict) -> None:
            self._send(code, json.dumps(payload, allow_nan=False).encode(), 'application/json')

        def _local(self) -> bool:
            port = self.server.server_port
            host = self.headers.get('Host')
            if host not in {f'localhost:{port}', f'127.0.0.1:{port}'}:
                self._json(403, {'error': 'Use the local address printed by the server.'})
                return False
            origin = self.headers.get('Origin')
            if origin and origin != f'http://{host}':
                self._json(403, {'error': 'The request must come from the local workspace.'})
                return False
            return True

        def do_GET(self) -> None:
            if not self._local():
                return
            url = urlsplit(self.path)
            if url.path in _ASSETS:
                name, content_type = _ASSETS[url.path]
                self._send(200, Path(__file__).with_name(name).read_bytes(),
                           f'{content_type}; charset=utf-8')
            elif url.path.startswith('/annotator/'):
                self.path = url.path.removeprefix('/annotator')
                with lock:
                    super().do_GET()
            elif url.path == '/api/centre/state':
                query = parse_qs(url.query)
                try:
                    with lock:
                        state = workspace.state(query.get('map', [None])[0],
                                                query.get('view', [None])[0])
                        self._json(200, state)
                except (OSError, ValueError) as exc:
                    self._json(400, {'error': str(exc)})
            else:
                self._json(404, {'error': 'Page not found.'})

        def do_POST(self) -> None:
            if not self._local():
                return
            try:
                length = int(self.headers.get('Content-Length', 0))
                if (self.headers.get_content_type() != 'application/json'
                        or not 0 < length <= _MAX_BODY):
                    raise ValueError('Send a JSON object with a valid content length.')

                if self.path.startswith('/annotator/api/'):
                    self.path = self.path.removeprefix('/annotator')
                    with lock:
                        super().do_POST()
                    return

                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict):
                    raise TypeError('Send a JSON object.')
                actions = {'/api/centre/settings': lambda: workspace.save_settings(body),
                           '/api/centre/generate': lambda: workspace.generate(body),
                           '/api/centre/stop': lambda: workspace.stop(body.get('id'))}
                action = actions.get(self.path)
                if action is None:
                    self._json(404, {'error': 'Command not found.'})
                    return
                with lock:
                    action()
                self._json(200, {'ok': True})
            except (OSError, ValueError, OverflowError, TypeError) as exc:
                self._json(400, {'error': str(exc)})

    return Handler


def main(argv: list[str] | None = None) -> None:
    """Start the offline workspace without a ROS graph."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--maps', type=Path, required=True, help='directory of map folders')
    parser.add_argument('--car', type=Path, help='car_model.yaml for optimization')
    parser.add_argument('--margin', type=float, default=0.05,
                        help='minimum body clearance in metres (Aggressive profile)')
    parser.add_argument('--workspace', type=Path, default=Path('.forzaeth/operational-centre'),
                        help='directory for the optimizer worksheet and cached results')
    parser.add_argument('--port', type=int, default=8767)
    args = parser.parse_args(argv)
    if not math.isfinite(args.margin) or args.margin < 0:
        parser.error('--margin must be finite and nonnegative')
    workspace = Workspace(args.maps, args.workspace.resolve(),
                          args.car.resolve() if args.car else None, args.margin)
    os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
    lock = Lock()
    with ThreadingHTTPServer(('127.0.0.1', args.port), handler(workspace, lock)) as server:
        print(f'ForzaETH Operational Centre: http://127.0.0.1:{server.server_port}', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            with lock:
                workspace.update_job(cancel=True)


if __name__ == '__main__':
    main()
