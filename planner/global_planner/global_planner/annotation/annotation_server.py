# Copyright 2026 ForzaETH
"""Local offline backend + web frontend for the annotation tool.

Stdlib-only HTTP transport. The same session operations are exposed by
``annotation_node`` over ROS (std_msgs/String JSON on the relative
topics ``planner_annotation/command`` / ``planner_annotation/state``)
when rclpy is available; geometry never depends on either transport.
Binds to loopback only, never touches the driving stack, and never
writes to the source map files.

Run: ``python3 -m global_planner.annotation.annotation_server --maps <dir> --port 8766``
then open http://127.0.0.1:8766/ in a browser.
"""
import argparse
import base64
import json
import math
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import cv2
import numpy as np

from .annotation_core import (AnnotationError, TrackMap,
                              atomic_write_text, build_candidate, draft_name,
                              require_closed_guide,
                              effective_free_mask, export_name,
                              extract_boundaries, free_components,
                              geometry_digest, load_session, new_session,
                              patched_free_mask, require_approved,
                              revoke_approval, ridge_seed, save_session,
                              snapped_guide,
                              suggest_route, try_thinnings, _checked_seed,
                              _checked_speed, _checked_text, _checked_width,
                              _signed_area)
from ..route.manifest import load_route

STATE = {'map': None, 'session': None, 'extraction': None, 'maps_dir': None,
         'out_dir': None, 'candidate_digest': None, 'car': None}

# Inbound request bounds. A lap seed needs only hundreds of points
# (0.75 m resampling of a ~164 m lap is ~220 samples); 20k points per
# field is generous headroom while bounding downstream CPU. The body cap
# covers several such fields plus JSON overhead.
MAX_BODY_BYTES = 4 * 1024 * 1024
MAX_POINTS_PER_FIELD = 20000
MAX_COORD_ABS = 1e6
# Per-connection socket timeout (s): the single-threaded server blocks
# in rfile.read, so a client advertising Content-Length then sending
# slowly would stall every op without this bound.
REQUEST_TIMEOUT_S = 30


def configure(maps_dir, out_dir, car=None):
    """Bind the shared backend to directories (HTTP and ROS entry points).

    Both transports reuse these operations, so both must configure them:
    without this, opening a map fails with an explicit error instead of a
    late ``TypeError`` on an unconfigured path. ``car`` is an optional
    ``global_planner.car.Car``; when given, previews also run the
    vehicle portal-zone stages for that exact car and margin. There is
    no default car.
    """
    if not maps_dir or not Path(maps_dir).is_dir():
        raise AnnotationError(f'maps directory not found: {maps_dir}')
    STATE['maps_dir'], STATE['out_dir'] = str(maps_dir), str(out_dir)
    STATE['car'] = car
    Path(out_dir).mkdir(parents=True, exist_ok=True)


def require_open():
    """Fail closed when no session is open yet."""
    if STATE['session'] is None or STATE['map'] is None:
        raise AnnotationError('no open session (open a map first)')
    return STATE['session'], STATE['map']


def _touch(session):
    """Record an edit: revoke approval (core), drop server-side display."""
    revoke_approval(session)
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


def _region_view():
    """Region-selection status for the current strokes.

    Reports the free-component count, the retained seed (if any), and
    the excluded pockets with a striped overlay image. Never raises:
    failures are reported as an ``error`` string for the status line.
    """
    session, track_map = STATE['session'], STATE['map']
    view = {'retained_region_px': session.get('retained_region_px'),
            'free_regions': None, 'excluded': [],
            'excluded_png_data_url': None}
    try:
        strokes = session.get('boundary_strokes_px', [])
        width = session.get('stroke_width_px', 5)
        # Any backend failure here (cv2, allocation, encode) must not
        # propagate: _session_view runs after the session was mutated,
        # so a raise would turn an applied edit into a FAIL with a
        # bumped revision. Report it as an error string instead.
        free = patched_free_mask(track_map, strokes, width)
        view['free_regions'] = len(free_components(free))
        seed = session.get('retained_region_px')
        if seed is None:
            return view
        legal = effective_free_mask(track_map, strokes, width, seed)
        view['retained_area_px'] = int((legal > 0).sum())
        excl = ((free > 0) & (legal == 0)).astype(np.uint8)
        view['excluded'] = free_components(excl * 255)
        if view['excluded']:
            height, width_px = excl.shape
            uu, vv = np.meshgrid(np.arange(width_px), np.arange(height))
            stripe = (((uu + vv) & 7) < 4).astype(np.uint8)
            overlay = np.zeros((height, width_px, 4), np.uint8)
            overlay[excl > 0] = (255, 128, 0, 200)
            overlay[(excl > 0) & (stripe == 0)] = (255, 128, 0, 90)
            ok, buf = cv2.imencode('.png', overlay)
            if ok:
                view['excluded_png_data_url'] = (
                    'data:image/png;base64,'
                    + base64.b64encode(bytes(buf)).decode())
    except AnnotationError as exc:
        view['error'] = str(exc)
    except Exception as exc:  # noqa: BLE001 - overlay must never break a view
        view['error'] = 'region overlay unavailable: %s' % exc
    return view


def _session_view():
    s = dict(STATE['session'])
    # Display the exact PNG snapshot TrackMap loaded (never re-read the
    # file): the browser must show the same bytes the geometry uses.
    try:
        png = STATE['map'].png_bytes
    except Exception as exc:  # noqa: BLE001 - applied ops stay viewable
        s['map_png_data_url'] = None
        s['map_view_error'] = 'map image unavailable: %s' % exc
    else:
        s['map_png_data_url'] = (
            'data:image/png;base64,' + base64.b64encode(png).decode())
    if STATE['extraction']:
        outer, inner = STATE['extraction']
        s['extraction'] = {'outer_px': outer.tolist(), 'inner_px': inner.tolist()}
    s['candidate_digest'] = STATE.get('candidate_digest')
    s['region'] = _region_view()
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
    draft = Path(STATE['out_dir']) / draft_name(track_map)
    if draft.exists():
        # Load validates the full map identity inside; a cross-map
        # file in this slot fails closed here and is left untouched.
        session = load_session(draft, track_map)
        message = 'reopened saved draft'
    else:
        session = new_session(track_map)
        message = 'new session'
    # Restore the persisted preview when it still matches the current
    # geometry: the digest binds every editable field, so a preview from
    # before a restart authorizes exactly the same candidate as a fresh
    # one. Without this, HTTP would force a re-preview after every
    # restart while the CLI accepts the persisted digest for the same
    # draft. Both transports now bind the same persisted preview.
    candidate = None
    if (session.get('preview_route_digest')
            and session.get('preview_digest')
            == geometry_digest(session, track_map)):
        try:
            require_closed_guide(session.get('route_px') or [])
        except AnnotationError:
            pass  # OPEN guide: no candidacy to restore or approve
        else:
            candidate = session['preview_digest']
    STATE.update(map=track_map, session=session, extraction=None,
                 candidate_digest=candidate)
    return {'status': 'PASS', 'message': message, 'session': _session_view()}


def op_update(body):
    """Accept one completed stroke/route/width, or reject it with a reason.

    An empty route clears the draft route (approval revoked either way).
    The stroke width is operator-visible and deterministic: changing it
    alters patched geometry, so it revokes approval like any other edit.
    """
    session, track_map = require_open()
    field, value = body.get('field'), body.get('value')
    if field not in ('boundary_strokes_px', 'route_px', 'stroke_width_px',
                     'retained_region_px', 'route_name', 'surface',
                     'max_speed_mps'):
        raise AnnotationError(f'unknown editable field: {field}')
    if field in ('route_name', 'surface', 'max_speed_mps'):
        # Manifest metadata: validated against the same rules the route
        # schema applies, stored canonically, approval revoked.
        session[field] = (_checked_speed(value) if field == 'max_speed_mps'
                          else _checked_text(value, field))
        _touch(session)
        return {'status': 'PASS',
                'message': f'{field} updated (draft rev '
                           f'{session["revision"]}, unapproved)',
                'session': _session_view()}
    if field == 'retained_region_px':
        # Selection update: validate against the current mask first, so a
        # bad click never overwrites the stored selection. Setting or
        # clearing revokes approval like any other edit.
        if value is not None:
            strokes = session.get('boundary_strokes_px', [])
            width = session.get('stroke_width_px', 5)
            effective_free_mask(track_map, strokes, width, value)
            # The selected component must itself be a valid track; a
            # pocket without annular topology is rejected here, before
            # anything is stored.
            extract_boundaries(track_map, strokes, width, value)
        # Store the canonical [u, v] ints: an in-memory float seed
        # (e.g. 100.0 from a Python client) would digest differently
        # after save/reload normalization and break re-approval.
        session[field] = _checked_seed(value, track_map)
        _touch(session)  # selection change revokes approval
        note = 'cleared' if value is None else f'set to {value}'
        return {'status': 'PASS',
                'message': f'retained region {note} '
                           f'(draft rev {session["revision"]}, unapproved)',
                'session': _session_view()}
    if field == 'stroke_width_px':
        _checked_width(value)
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
    if field == 'route_px' and value:
        # Commit-boundary normalization (shared closure contract):
        # a near-closed guide is stored exactly closed, so reversal,
        # digests and the UI closure test all see one representation.
        value = snapped_guide(value)
    session[field] = value
    if field in ('boundary_strokes_px', 'stroke_width_px'):
        # Boundary edits change the component layout; the stored seed no
        # longer refers to a known component.
        session['retained_region_px'] = None
    _touch(session)  # any edit revokes approval
    note = 'cleared' if field == 'route_px' and not value else 'updated'
    return {'status': 'PASS',
            'message': f'{field} {note} (draft rev {session["revision"]}, unapproved)',
            'session': _session_view()}


def op_suggest(body):
    """Fill the route pencil with a computed centerline suggestion.

    Tries the seed methods in a fixed deterministic order (suggest, then
    ridge) and keeps the first seed the strict validator accepts, so the
    operator never names a seed algorithm. Each attempt is gated by the
    same strict build preview enforces; nothing is optimized here.
    An edit like any other: bumps the revision, revokes approval, clears
    the candidate. The operator inspects the suggestion in preview, may
    redraw it, and only an explicit approve authorizes export.
    """
    session, track_map = require_open()
    retained = session.get('retained_region_px')
    try:
        outer, inner = extract_boundaries(
            track_map, session['boundary_strokes_px'],
            session.get('stroke_width_px', 5), retained)
    except AnnotationError:
        # No boundaries, no suggestion: drop any stale overlay so the
        # display never shows geometry from before the failure. The
        # operator's strokes are untouched (session not mutated).
        STATE['extraction'] = None
        STATE['candidate_digest'] = None
        raise
    strokes = session['boundary_strokes_px']
    width = session.get('stroke_width_px', 5)
    hint = session.get('route_px', [])
    hint_sign = _signed_area(hint) if len(hint) >= 3 else 0.0
    methods = (
        ('suggest',
         lambda: suggest_route(outer, inner, hint)),
        ('ridge',
         lambda: ridge_seed(track_map, outer, inner, strokes, width,
                            retained_region_px=retained)),
    )
    failures = []
    for name, make in methods:
        try:
            seed = make()
            if not seed:
                raise AnnotationError('empty seed')
            pts = [[float(v) for v in p] for p in seed]
            closed = pts + [pts[0]] if pts[0] != pts[-1] else pts
            if hint_sign and _signed_area(closed) * hint_sign < 0:
                raise AnnotationError(
                    'seed runs against the drawn travel direction')
            build_candidate(track_map, dict(session, route_px=closed),
                            car=STATE.get('car'))
        except Exception as exc:  # noqa: BLE001 - try the next method
            failures.append('%s: %s' % (name, exc))
            continue
        session['route_px'] = closed
        _touch(session)
        return {'status': 'PASS',
                'message': f'suggested guide loop ({len(closed)} points, '
                           f'closed loop, {name} seed, draft rev '
                           f'{session["revision"]}, unapproved); inspect '
                           'in preview, redraw if it looks wrong',
                'session': _session_view()}
    raise AnnotationError('no seed method produced a strict-valid route '
                          '(%s)' % '; '.join(failures))


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
            session.get('stroke_width_px', 5),
            session.get('retained_region_px'))
    except AnnotationError:
        STATE['extraction'] = None
        STATE['candidate_digest'] = None
        raise
    STATE['extraction'] = extraction
    return {'status': 'CANDIDATE',
            'message': 'extracted boundaries are a CANDIDATE until approved; '
                       'inspect the overlay, then approve via export',
            'session': _session_view()}


def _candidate_receipt(payload, route, receipt, track_map, out=None):
    """Shared VALIDATED receipt body (preview and export show the same).

    Carries the exact exported geometry in file-pixel coordinates -
    per-section walls, the wall-derived centrelines, the portal gates
    and the start zone - so the browser renders bit-identically to the
    export without re-deriving anything. The stage list states what
    was checked; ``not_checked`` states what no stage here can prove.
    """
    def _px(chain):
        return [[float(track_map.world_to_pixel(pt)[0]),
                 float(track_map.world_to_pixel(pt)[1])] for pt in chain]
    where = f'written to {out}. ' if out is not None else 'not written yet. '
    annexed = receipt['stages']['vector_legal']['annexed_m2']
    car = receipt.get('car')
    car_text = (f'car zones PASS for {car["name"]} (reach '
                f'{car["reach_m"]:.2f} m). ' if car else
                'no car supplied: vehicle zones NOT checked. ')
    return {'status': 'VALIDATED',
            'message': f'route checks PASS (vector legality, manifest, '
                       f'lap, portals, samples); route digest '
                       f'{route.digest[:16]}… {where}'
                       f'exported polygons annex {annexed:.6f} m² '
                       f'outside the selected legal cells. {car_text}'
                       f'guide correction max '
                       f'{receipt["max_correction_m"]:.3f} m over '
                       f'{receipt["seed_samples"]} samples. Not an '
                       'optimized or dynamics-certified trajectory.',
            'route_digest': route.digest,
            'sections': receipt['sections'],
            'samples': receipt['stages']['samples'],
            'lap_length_m': receipt['lap_length_m'],
            'stages': receipt['stages'],
            'car': car,
            'not_checked': receipt['not_checked'],
            'max_correction_m': receipt['max_correction_m'],
            'smoothing_passes': receipt['smoothing_passes'],
            'validated_route_px': [_px(s.centreline)
                                   for s in route.sections],
            'validated_left_px': [_px(s['left'])
                                  for s in payload['sections']],
            'validated_right_px': [_px(s['right'])
                                   for s in payload['sections']],
            'gates_px': [_px(p.gate) for p in route.portals],
            'start_zone_px': _px(payload['start']['zone'])}


def op_preview(body):
    """Build the candidate manifest and show it WITHOUT approving.

    Read-only: writes no file, grants no approval, bumps no revision.
    The candidate is built exactly as export builds it, so the shown
    route digest and geometry are bit-identical to the export output;
    only the file write and the session approval are withheld until
    approve/export.
    """
    session, track_map = require_open()
    if not session.get('route_px'):
        raise AnnotationError('draw the directed route loop first')
    try:
        outer, inner = extract_boundaries(
            track_map, session['boundary_strokes_px'],
            session.get('stroke_width_px', 5),
            session.get('retained_region_px'))
    except AnnotationError:
        # Boundary failure: nothing valid to show; drop the stale
        # overlay and candidate, keep the operator's strokes.
        STATE['extraction'] = None
        STATE['candidate_digest'] = None
        raise
    STATE['extraction'] = (outer, inner)
    try:
        payload, route, checked, _ = build_candidate(
            track_map, session, car=STATE.get('car'))
    except Exception:  # noqa: BLE001 - any build failure clears candidacy
        # Route failure: the extracted boundaries above are still valid
        # and stay visible, but there is no candidate to approve until
        # the route is redrawn and previewed again.
        STATE['candidate_digest'] = None
        raise
    digest = geometry_digest(session, track_map)
    STATE['candidate_digest'] = digest
    # Persist the previewed candidate in the session (written forward on
    # save) so the headless CLI enforces the same fresh-preview binding.
    # Both identities are stored: the editor-input digest and the
    # manifest digest this preview produced.
    session['preview_digest'] = digest
    session['preview_route_digest'] = route.digest
    receipt = _candidate_receipt(payload, route, checked, track_map)
    receipt['candidate_digest'] = digest
    receipt['session'] = _session_view()
    return receipt


def op_approve(body):
    """Approve the exact candidate shown by the last preview.

    Fails closed unless the caller quotes the previewed candidate digest
    and the geometry is unchanged since that preview. Writes no file.
    """
    session, track_map = require_open()
    # Approval-state invariant: no OPEN guide may enter operator-
    # approved, however it was loaded or previewed (persisted
    # digests included). Checked before any state mutation.
    require_closed_guide(session.get('route_px') or [])
    quoted = body.get('approval_digest')
    if not quoted or quoted != STATE.get('candidate_digest'):
        raise AnnotationError('approve refused: no fresh preview for this '
                              'geometry (preview the candidate first)')
    if quoted != geometry_digest(session, track_map):
        raise AnnotationError('approve refused: geometry changed since '
                              'preview (preview again)')
    if not session.get('preview_route_digest'):
        raise AnnotationError('approve refused: preview produced no '
                              'manifest digest (preview again)')
    session['approval'] = 'operator-approved'
    session['approval_digest'] = quoted
    session['approval_route_digest'] = session['preview_route_digest']
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
            session.get('stroke_width_px', 5),
            session.get('retained_region_px'))
    except AnnotationError:
        # Geometry broke after approval (should be unreachable: edits
        # revoke approval first). Drop the stale overlay either way.
        STATE['extraction'] = None
        STATE['candidate_digest'] = None
        raise
    STATE['extraction'] = (outer, inner)
    try:
        payload, route, checked, _ = build_candidate(
            track_map, session, car=STATE.get('car'))
    except Exception:  # noqa: BLE001 - failed build exports nothing
        STATE['candidate_digest'] = None
        raise
    if route.digest != session.get('approval_route_digest'):
        raise AnnotationError(
            'export refused: rebuilt manifest digest differs from the '
            'approved preview (preview and approve again)')
    out = Path(STATE['out_dir']) / export_name(track_map)
    atomic_write_text(out, json.dumps(payload, indent=1))
    if load_route(out).digest != route.digest:
        raise AnnotationError(
            'export readback mismatch: file does not reload to the '
            'approved manifest digest')
    receipt = _candidate_receipt(payload, route, checked, track_map,
                                 out=out)
    receipt['session'] = _session_view()
    return receipt


def op_validate(body):
    """Explicit validation over the bounded thinning settings.

    Tries VALIDATE_THINNINGS in order; each attempt is a full candidate
    build plus every route check (and the car stages when a car is
    configured). The first passing setting becomes the session's
    chain_dp_epsilon_m, which is part of the approval digest, so any
    approval is revoked and preview/approve/export all use it
    afterwards. Reports why each rejected setting failed. Invoke it
    explicitly, never per mouse movement: centreline derivation over
    dense walls is the expensive part.
    """
    session, track_map = require_open()
    if not session.get('route_px'):
        raise AnnotationError('draw the directed route loop first')
    try:
        outer, inner = extract_boundaries(
            track_map, session['boundary_strokes_px'],
            session.get('stroke_width_px', 5),
            session.get('retained_region_px'))
    except AnnotationError:
        STATE['extraction'] = None
        STATE['candidate_digest'] = None
        raise
    STATE['extraction'] = (outer, inner)
    eps, (_, route, checked, _), attempts = try_thinnings(
        track_map, session, car=STATE.get('car'))
    session['chain_dp_epsilon_m'] = eps
    _touch(session)
    return {'status': 'PASS',
            'message': f'route checks PASS at thinning {eps} '
                       f'(digest {route.digest[:16]}…); re-preview, '
                       'then approve and export',
            'chain_dp_epsilon_m': eps, 'route_digest': route.digest,
            'stages': checked['stages'],
            'attempts': attempts, 'session': _session_view()}


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
    session['retained_region_px'] = None
    _touch(session)
    return {'status': 'PASS',
            'message': 'last boundary stroke removed; approval revoked '
                       f'(draft rev {session["revision"]}, unapproved)',
            'session': _session_view()}


OPS = {'/api/session/open': op_open, '/api/session/update': op_update,
       '/api/session/extract': op_extract, '/api/session/suggest': op_suggest,
       '/api/session/preview': op_preview, '/api/session/approve': op_approve,
       '/api/session/validate': op_validate,
       '/api/session/export': op_export, '/api/session/save': op_save,
       '/api/session/undo': op_undo, '/api/session/state': op_state}


class Handler(BaseHTTPRequestHandler):
    """Loopback-only JSON API plus the single-page frontend."""

    def setup(self):
        # Bound every phase (header parse + body read): socketserver
        # only applies self.timeout here, so setting it per connection
        # is what keeps a slow sender from stalling the server.
        self.timeout = REQUEST_TIMEOUT_S
        super().setup()

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
                # Close the connection: the unread remainder must never
                # be parsed as a pipelined next request.
                self.close_connection = True
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
        # The geometry stack can raise beyond the usual suspects
        # (cv2.error, RuntimeError, ...): every transport failure must
        # still reach the operator as an explicit JSON FAIL, never as
        # a bare 500 with no body.
        except Exception as exc:  # noqa: BLE001 - transport is fail-closed
            _reply(self, {'status': 'FAIL', 'message': str(exc)}, 400)


def main(argv=None):
    """Start the loopback annotation backend."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--maps', required=True, help='directory of map folders')
    parser.add_argument('--out', default='/tmp/annotation_out')
    parser.add_argument('--port', type=int, default=8766)
    parser.add_argument('--car', default=None,
                        help='car_model.yaml for vehicle portal-zone checks '
                             '(omit: car stages are reported NOT checked)')
    parser.add_argument('--car-margin', type=float, default=0.05,
                        help='clearance margin in metres around the car body')
    args = parser.parse_args(argv)
    car = None
    if args.car:
        from ..car import Car
        car = Car.load(args.car, margin_m=args.car_margin)
        print(f'vehicle checks on: {car.name}, reach {car.reach_m:.3f} m '
              f'(margin {car.margin_m} m)')
    configure(args.maps, args.out, car=car)
    server = HTTPServer(('127.0.0.1', args.port), Handler)
    print(f'annotation backend on http://127.0.0.1:{args.port}/ (loopback only)')
    server.serve_forever()


if __name__ == '__main__':
    main()
