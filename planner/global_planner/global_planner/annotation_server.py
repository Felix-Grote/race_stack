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
import os
import json
import math
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from .annotation_core import (AnnotationError, TrackMap, atomic_write_text,
                              build_and_validate, draft_name, export_name,
                              extract_boundaries, geometry_digest,
                              load_session, new_session, require_approved,
                              resolve_draft, save_session, suggest_route)

STATE = {'map': None, 'session': None, 'extraction': None, 'maps_dir': None,
         'out_dir': None, 'candidate_digest': None}

# Inbound request bounds. A lap seed needs only hundreds of points
# (0.75 m resampling of a ~164 m lap is ~220 samples); 20k points per
# field is generous headroom while bounding downstream CPU. The body cap
# covers several such fields plus JSON overhead.
MAX_BODY_BYTES = 4 * 1024 * 1024
MAX_POINTS_PER_FIELD = 20000
MAX_COORD_ABS = 1e6


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
    STATE['candidate_digest'] = None


def _reply(handler, payload, code=200):
    body = json.dumps(payload).encode()
    handler.send_response(code)
    handler.send_header('Content-Type', 'application/json')
    handler.send_header('Content-Length', str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _read_bounded(rfile, length):
    """Read at most ``MAX_BODY_BYTES + 1`` bytes from the request.

    Returns ``(data, overflow)``. An oversized body is detected from a
    bounded prefix instead of being loaded fully, so the reply stays
    predictable without unbounded memory.
    """
    if length <= MAX_BODY_BYTES:
        return (rfile.read(length) if length else b'{}'), False
    want, chunks = MAX_BODY_BYTES + 1, []
    while want > 0:
        chunk = rfile.read(min(65536, want))
        if not chunk:
            break
        chunks.append(chunk)
        want -= len(chunk)
    return b''.join(chunks), True


def _session_view():
    s = dict(STATE['session'])
    png = Path(STATE['map'].png_path).read_bytes()
    s['map_png_data_url'] = 'data:image/png;base64,' + base64.b64encode(png).decode()
    if STATE['extraction']:
        outer, inner = STATE['extraction']
        s['extraction'] = {'outer_px': outer.tolist(), 'inner_px': inner.tolist()}
    s['candidate_digest'] = STATE.get('candidate_digest')
    return s


def _resolve_map_yaml(name):
    """Resolve a map name to a YAML path confined under the maps dir.

    Nested relative paths (``a/b`` → ``maps/a/b/b.yaml``) keep working;
    absolute paths, ``..`` escapes, and symlink escapes are refused.
    """
    if not isinstance(name, str) or not name:
        raise AnnotationError('map name must be a nonempty relative path')
    if name.startswith(('/', '\\')) or any(
            p in ('..', '.', '') for p in Path(name).parts):
        raise AnnotationError(f'map name escapes the maps directory: {name!r}')
    base = Path(STATE['maps_dir']).resolve()
    leaf = Path(name).name
    if not leaf.endswith('.yaml'):
        leaf += '.yaml'
    candidates = [base / name / leaf, base / f'{name}.yaml']
    for cand in candidates:
        try:
            resolved = cand.resolve()
        except OSError:
            continue
        if resolved != base and base in resolved.parents and resolved.is_file():
            return resolved
    raise AnnotationError(f'map not found in maps directory: {name!r}')


def op_open(body):
    """Open (or reopen) a session for a map name inside the maps dir."""
    if not STATE.get('maps_dir') or not STATE.get('out_dir'):
        raise AnnotationError('backend not configured (set maps/out dirs first)')
    track_map = TrackMap(_resolve_map_yaml(body.get('map', '')))
    draft, legacy = resolve_draft(STATE['out_dir'], track_map)
    if legacy is None:
        if draft.exists():
            # Load validates the full map identity inside; a cross-map
            # file in this slot fails closed here and is left untouched.
            session = load_session(draft, track_map)
            message = 'reopened saved draft'
        else:
            session = new_session(track_map)
            message = 'new session'
    else:
        session = load_session(legacy, track_map)  # validates; raises closed
        draft.parent.mkdir(parents=True, exist_ok=True)
        tmp = draft.with_name(draft.name + f'.tmp-{os.getpid()}')
        try:
            tmp.write_bytes(legacy.read_bytes())
            os.replace(tmp, draft)
        except OSError:
            try:
                tmp.unlink()
            except OSError:
                pass
            raise AnnotationError(
                f'legacy draft could not be adopted: {legacy.name}')
        message = f'reopened legacy draft (adopted as {draft.name})'
    STATE.update(map=track_map, session=session, extraction=None,
                 candidate_digest=None)
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
        strokes = [value] if field == 'route_px' else value
        total = 0
        for stroke in strokes:
            if not isinstance(stroke, list):
                raise AnnotationError(f'{field} must be a list of point lists')
            for pt in stroke:
                total += 1
                if (not isinstance(pt, (list, tuple)) or len(pt) != 2
                        or any(isinstance(v, bool) or not isinstance(v, (int, float))
                               or not math.isfinite(v)
                               or abs(v) > MAX_COORD_ABS for v in pt)):
                    raise AnnotationError(
                        f'{field} points must be finite [x, y] pixel pairs')
        if total > MAX_POINTS_PER_FIELD:
            raise AnnotationError(
                f'{field} has {total} points (limit {MAX_POINTS_PER_FIELD})')
        if field == 'route_px' and 0 < total < 3:
            raise AnnotationError('route needs at least 3 points (or empty to clear)')
    session[field] = value
    _touch(session)  # any edit revokes approval
    note = 'cleared' if field == 'route_px' and not value else 'updated'
    return {'status': 'PASS',
            'message': f'{field} {note} (draft rev {session["revision"]}, unapproved)',
            'session': _session_view()}


def op_suggest(body):
    """Fill the route pencil with a computed centerline suggestion.

    An edit like any other: bumps the revision, revokes approval, clears
    the candidate. The operator inspects the suggestion in preview, may
    redraw it, and only an explicit approve authorizes export.
    """
    session, track_map = require_open()
    try:
        outer, inner = extract_boundaries(
            track_map, session['boundary_strokes_px'],
            session.get('stroke_width_px', 5))
    except AnnotationError:
        # No boundaries, no suggestion: drop any stale overlay so the
        # display never shows geometry from before the failure. The
        # operator's strokes are untouched (session not mutated).
        STATE['extraction'] = None
        STATE['candidate_digest'] = None
        raise
    suggested = suggest_route(outer, inner, session.get('route_px', []))
    session['route_px'] = suggested + [suggested[0]]  # explicit closure
    _touch(session)
    return {'status': 'PASS',
            'message': f'suggested centerline ({len(session["route_px"])} '
                       f'points, closed loop, draft rev '
                       f'{session["revision"]}, unapproved); inspect in '
                       'preview, redraw if it looks wrong',
            'session': _session_view()}


def op_extract(body):
    """Run boundary extraction on the patched raster copy.

    On failure the previous overlay is dropped (no stale display) while
    the operator's strokes are retained in the session, and the
    diagnostic is reported so the stroke can be repaired.
    """
    session, track_map = require_open()
    try:
        extraction = extract_boundaries(
            track_map, session['boundary_strokes_px'],
            session.get('stroke_width_px', 5))
    except AnnotationError:
        STATE['extraction'] = None
        STATE['candidate_digest'] = None
        raise
    STATE['extraction'] = extraction
    return {'status': 'CANDIDATE',
            'message': 'extracted boundaries are a CANDIDATE until approved; '
                       'inspect the overlay, then approve via export',
            'session': _session_view()}


def _validated_receipt(payload, route, prepared, info, track_map, out=None):
    """Shared VALIDATED receipt body (preview and export show the same).

    The receipt carries the exact final corridor geometry from the
    export candidate manifest: the per-occurrence left/right wall chains
    plus the directed seed centerline, all in file-pixel coordinates, so
    the browser can render the corridor bit-identically to the export
    without re-deriving anything.
    """
    def _px(chain):
        return [[float(track_map.world_to_pixel(pt)[0]),
                 float(track_map.world_to_pixel(pt)[1])] for pt in chain]
    validated_px = [_px(occ['seed']) for occ in payload['occurrences']]
    validated_left = [_px(occ['left']) for occ in payload['occurrences']]
    validated_right = [_px(occ['right']) for occ in payload['occurrences']]
    where = f'written to {out}. ' if out is not None else 'not written yet. '
    return {'status': 'VALIDATED',
            'message': f'validate_route + prepare_route PASS; route digest '
                       f'{route.digest[:16]}… {where}'
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
            'validated_left_px': validated_left,
            'validated_right_px': validated_right}


def op_preview(body):
    """Build the candidate manifest and show it WITHOUT approving.

    Read-only: writes no file, grants no approval, bumps no revision.
    The candidate is built with the exact approval provenance the export
    would write, so the shown route digest and validated geometry are
    bit-identical to the export output; only the file write and the
    session approval are withheld until approve/export.
    """
    session, track_map = require_open()
    if not session.get('route_px'):
        raise AnnotationError('draw the directed route loop first')
    try:
        outer, inner = extract_boundaries(
            track_map, session['boundary_strokes_px'],
            session.get('stroke_width_px', 5))
    except AnnotationError:
        # Boundary failure: nothing valid to show; drop the stale
        # overlay and candidate, keep the operator's strokes.
        STATE['extraction'] = None
        STATE['candidate_digest'] = None
        raise
    STATE['extraction'] = (outer, inner)
    try:
        payload, route, prepared, info = build_and_validate(
            track_map, outer, inner, session['route_px'],
            author=session.get('author', 'operator'),
            approval='operator-approved')
    except Exception:  # noqa: BLE001 - any build failure clears candidacy
        # Route/corridor failure: the extracted boundaries above are
        # still valid and stay visible, but there is no candidate to
        # approve until the route is redrawn and previewed again.
        STATE['candidate_digest'] = None
        raise
    digest = geometry_digest(session, track_map)
    STATE['candidate_digest'] = digest
    receipt = _validated_receipt(payload, route, prepared, info, track_map)
    receipt['candidate_digest'] = digest
    receipt['session'] = _session_view()
    return receipt


def op_approve(body):
    """Approve the exact candidate shown by the last preview.

    Fails closed unless the caller quotes the previewed candidate digest
    and the geometry is unchanged since that preview. Writes no file.
    """
    session, track_map = require_open()
    quoted = body.get('approval_digest')
    if not quoted or quoted != STATE.get('candidate_digest'):
        raise AnnotationError('approve refused: no fresh preview for this '
                              'geometry (preview the candidate first)')
    if quoted != geometry_digest(session, track_map):
        raise AnnotationError('approve refused: geometry changed since '
                              'preview (preview again)')
    session['approval'] = 'operator-approved'
    session['approval_digest'] = quoted
    session['revision'] = int(session.get('revision', 1)) + 1
    return {'status': 'PASS',
            'message': f'candidate {quoted[:16]}… approved '
                       f'(draft rev {session["revision"]})',
            'session': _session_view()}


def op_export(body):
    """Export exactly the approved candidate geometry.

    Approval must already be bound to a fresh preview of the current
    geometry; this op never grants approval itself. Re-runs extraction
    and validation so the file always matches the current geometry.
    """
    session, track_map = require_open()
    require_approved(session, track_map)
    if session.get('approval_digest') != STATE.get('candidate_digest'):
        raise AnnotationError('export refused: no fresh preview for the '
                              'approved geometry (preview, approve, then '
                              'export)')
    if not session.get('route_px'):
        raise AnnotationError('draw the directed route loop first')
    try:
        outer, inner = extract_boundaries(
            track_map, session['boundary_strokes_px'],
            session.get('stroke_width_px', 5))
    except AnnotationError:
        # Geometry broke after approval (should be unreachable: edits
        # revoke approval first). Drop the stale overlay either way.
        STATE['extraction'] = None
        STATE['candidate_digest'] = None
        raise
    STATE['extraction'] = (outer, inner)
    try:
        payload, route, prepared, info = build_and_validate(
            track_map, outer, inner, session['route_px'],
            author=session.get('author', 'operator'),
            approval='operator-approved')
    except Exception:  # noqa: BLE001 - failed build exports nothing
        STATE['candidate_digest'] = None
        raise
    out = Path(STATE['out_dir']) / export_name(track_map)
    atomic_write_text(out, json.dumps(payload, indent=1))
    receipt = _validated_receipt(payload, route, prepared, info, track_map,
                                 out=out)
    receipt['session'] = _session_view()
    return receipt


def op_state(body):
    """Return the canonical session state without mutating anything.

    Lets a (re)connecting ROS client or UI recover the authoritative
    revision, approval, and candidate digest after a disconnect.
    """
    session, _ = require_open()
    return {'status': 'PASS', 'message': 'canonical session state',
            'revision': session.get('revision'),
            'session': _session_view()}


def op_save(body):
    """Persist the editable draft (never the source map)."""
    session, track_map = require_open()
    path = Path(STATE['out_dir']) / draft_name(track_map)
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
       '/api/session/extract': op_extract, '/api/session/suggest': op_suggest,
       '/api/session/preview': op_preview, '/api/session/approve': op_approve,
       '/api/session/export': op_export, '/api/session/save': op_save,
       '/api/session/undo': op_undo, '/api/session/state': op_state}


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
            if length < 0:
                raise AnnotationError('negative Content-Length')
            raw, overflow = _read_bounded(self.rfile, length)
            if overflow:
                _reply(self, {'status': 'FAIL',
                              'message': f'request body exceeds '
                                         f'{MAX_BODY_BYTES} bytes'}, 413)
                return
            body = json.loads(raw)
            if not isinstance(body, dict):
                raise AnnotationError('request body must be a JSON object')
            op = OPS.get(self.path)
            if op is None:
                raise AnnotationError(f'unknown operation {self.path}')
            _reply(self, op(body))
        except (AnnotationError, ValueError, TypeError, OSError) as exc:
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
