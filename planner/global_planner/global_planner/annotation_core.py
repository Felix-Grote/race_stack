# Copyright 2026 ForzaETH
"""Core of the map annotation tool: raster edits in, route manifest out.

Pipeline (planar single loop only):

1. Load a Cartographer occupancy PNG/YAML read-only. Never write to it.
2. Raster-patch a *copy* with the operator's boundary strokes (occupied
   only), then keep the one free component the operator selected with
   the bucket. Legal free space only ever shrinks:
   ``Flegal ⊆ Fpatched ⊆ Foriginal``.
3. Extract the legal boundaries as the two loops of that region (outer
   boundary + one hole). Anything that is not one enclosed annulus -
   open gap, split, extra island - is rejected, never guessed at.
4. Split the loops into sections at joints placed along the operator's
   directed guide loop and emit a ``global_planner.route`` manifest
   (``{name, map, start, sections}``) directly. The guide only sets
   travel direction and cut positions; each section's centreline is
   derived from its walls by the route package, not exported.
5. Check the candidate in this order, failing closed at the first bad
   stage: final-polygon legality against the selected raster, then the
   route package's own ``validate_route``, ``centre_curve``,
   ``portal_crossings`` and ``sample_lap`` (plus car portal zones when
   a car was explicitly supplied). There is no optimizer or dynamics
   checker in the route package; receipts say so instead of implying
   a certified trajectory.

Coordinate convention (verified against ``global_planner_node.py``,
which vertically flips the file image on load and then applies
``x = origin_x + u * res``, ``y = origin_y + v_internal * res``):
for a file pixel ``(u, v)`` with ``v = 0`` at the top row,

    x = origin_x + u * resolution
    y = origin_y + (height - 1 - v) * resolution

Only zero-yaw maps are supported; a nonzero ``origin[2]`` is rejected
instead of being silently approximated.
"""
import hashlib
import json
import math
import os
from pathlib import Path

import numpy as np

try:
    import cv2
except ImportError as exc:  # pragma: no cover - exercised by env check
    raise ImportError(
        'annotation_core needs opencv-python-headless (cv2)') from exc


class AnnotationError(ValueError):
    """Operator-correctable annotation or unsupported-geometry failure."""


# --------------------------------------------------------------------------
# Map loading and pixel/world conversion
# --------------------------------------------------------------------------

def _parse_map_yaml(text):
    """Parse the small flat subset of map YAML this tool accepts."""
    meta, origin = {}, []
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if ':' not in line:
            continue
        key, _, rest = line.partition(':')
        key, rest = key.strip(), rest.strip()
        if key == 'origin':
            try:
                if rest.startswith('['):
                    origin = [float(x)
                              for x in rest.strip('[]').split(',')
                              if x.strip()]
                else:  # block sequence "- value" lines
                    for nxt in lines[i + 1:]:
                        nxt = nxt.strip()
                        if nxt.startswith('- '):
                            origin.append(float(nxt[2:]))
                        else:
                            break
            except (TypeError, ValueError) as exc:
                raise AnnotationError(
                    'map origin is not a list of numbers') from exc
        elif key in ('resolution', 'negate', 'occupied_thresh',
                     'free_thresh'):
            meta[key] = rest
        elif key == 'image':
            meta[key] = rest
    if 'image' not in meta or 'resolution' not in meta or len(origin) != 3:
        raise AnnotationError('map YAML missing image/resolution/origin')
    if not all(math.isfinite(v) for v in origin):
        # float() accepts nan/inf, and abs(nan) > 1e-12 is False, so a
        # non-finite origin would slip past the yaw check below and
        # poison pixel_to_world, map_identity, and saved drafts (nan
        # != nan trips the identity check on reopen). Same finite guard
        # as resolution.
        raise AnnotationError('map origin must be finite numbers (m)')
    # The image entry is a bare file name: strip a trailing YAML comment
    # and one layer of surrounding quotes. A '#' inside a quoted name is
    # kept; the result must still resolve to a readable file below, so a
    # mis-parse fails closed instead of rebinding the map.
    image = meta['image'].strip()
    head, hash_, _ = image.partition('#')
    if hash_ and (not head or head.endswith((' ', '\t'))):
        image = head.strip()
    if (len(image) >= 2 and image[0] == image[-1]
            and image[0] in ('"', "'")):
        image = image[1:-1].strip()
    if not image:
        raise AnnotationError('map YAML has an empty image entry')
    meta['image'] = image
    try:
        meta['resolution'] = float(meta['resolution'])
    except (TypeError, ValueError) as exc:
        raise AnnotationError('map resolution is not a number') from exc
    if not (math.isfinite(meta['resolution']) and meta['resolution'] > 0):
        raise AnnotationError(
            'map resolution must be a finite positive number (m/px)')
    meta['origin'] = origin
    # Occupancy interpretation: only the Cartographer-style binary convention
    # (negate 0/1, single thresholds pair) is supported. Anything else risks
    # reading unknown/gray cells as legal free space, so it is rejected here
    # instead of being silently approximated downstream.
    try:
        meta['negate'] = int(meta.get('negate', '0'))
    except (TypeError, ValueError) as exc:
        raise AnnotationError('UNSUPPORTED: map negate must be 0 or 1') from exc
    if meta['negate'] not in (0, 1):
        raise AnnotationError('UNSUPPORTED: map negate must be 0 or 1')
    for thresh_key, default in (('occupied_thresh', 0.65),
                                ('free_thresh', 0.196)):
        try:
            meta[thresh_key] = float(meta.get(thresh_key, default))
        except (TypeError, ValueError) as exc:
            raise AnnotationError(
                f'map {thresh_key} is not a number') from exc
    return meta


class TrackMap:
    """Read-only occupancy map plus its pixel/world transform."""

    def __init__(self, yaml_path):
        yaml_path = Path(yaml_path)
        meta = _parse_map_yaml(yaml_path.read_text(encoding='utf-8'))
        if abs(float(meta['origin'][2])) > 1e-12:
            raise AnnotationError('UNSUPPORTED: nonzero map yaw (origin[2])')
        png_path = (yaml_path.parent / meta['image']).resolve()
        image = cv2.imread(str(png_path), cv2.IMREAD_GRAYSCALE)
        if image is None:
            raise AnnotationError(f'cannot read map image: {png_path}')
        self.yaml_path, self.png_path = yaml_path, png_path
        self.resolution = float(meta['resolution'])
        self.origin = (float(meta['origin'][0]), float(meta['origin'][1]))
        self.negate = int(meta['negate'])
        self.occupied_thresh = float(meta['occupied_thresh'])
        self.free_thresh = float(meta['free_thresh'])
        self.image = image  # uint8, file order: row 0 = top
        self.height, self.width = image.shape
        self.sha256 = hashlib.sha256(png_path.read_bytes()).hexdigest()

    def map_identity(self):
        """Full source-map interpretation contract bound by sessions."""
        return {'map_sha256': self.sha256,
                'image_size': [int(self.width), int(self.height)],
                'resolution': float(self.resolution),
                'origin': [float(self.origin[0]), float(self.origin[1])],
                'negate': int(self.negate)}

    def pixel_to_world(self, uv):
        """Convert file pixel (u, v) to world (x, y) in metres."""
        u, v = float(uv[0]), float(uv[1])
        return (self.origin[0] + u * self.resolution,
                self.origin[1] + (self.height - 1 - v) * self.resolution)

    def world_to_pixel(self, xy):
        """Convert world (x, y) to file pixel (u, v); inverse of above."""
        x, y = float(xy[0]), float(xy[1])
        return ((x - self.origin[0]) / self.resolution,
                (self.height - 1) - (y - self.origin[1]) / self.resolution)


# --------------------------------------------------------------------------
# Session persistence (annotation_project.json - the editable truth)
# --------------------------------------------------------------------------

SESSION_VERSION = 4

# Bump when the emitted geometry for identical session input changes;
# it is part of the approval digest, so old approvals stop authorizing
# output of a newer generator.
GENERATOR_VERSION = 'route-v1'

# Wall-simplification settings the explicit validation tries, in order.
# 0.02 is the default; 0.03 is the envelope edge (eps/res = 0.6) for
# dense maps whose unthinned walls make centreline derivation slow.
# No other settings exist.
VALIDATE_THINNINGS = (0.02, 0.03)
DEFAULT_CHAIN_DP_EPSILON_M = VALIDATE_THINNINGS[0]

DEFAULT_SURFACE = 'ground'
DEFAULT_MAX_SPEED_MPS = 2.5


def _checked_text(value, what):
    """Return a manifest text field, or raise (mirrors the route schema)."""
    if (not isinstance(value, str) or not 1 <= len(value) <= 128
            or value != value.strip()
            or any(ord(c) < 0x20 or 0x7f <= ord(c) <= 0x9f for c in value)):
        raise AnnotationError(
            f'{what} must be 1-128 characters, no surrounding whitespace '
            'or control characters')
    return value


def _checked_speed(value):
    """Return a section speed limit in m/s, or raise."""
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or value <= 0):
        raise AnnotationError('max_speed_mps must be a finite positive number')
    return float(value)


def new_session(track_map, author='operator'):
    """Create an empty session dict bound to one map by full identity."""
    return {
        'version': SESSION_VERSION,
        'map_yaml': track_map.yaml_path.name,
        'map_png': track_map.png_path.name,
        'map_sha256': track_map.sha256,
        'image_size': [int(track_map.width), int(track_map.height)],
        'resolution': track_map.resolution,
        'origin': list(track_map.origin),
        'negate': int(track_map.negate),
        'boundary_strokes_px': [],   # list of polylines [[u, v], ...]
        'route_px': [],              # directed guide loop (direction + cuts)
        'stroke_width_px': 5,
        'chain_dp_epsilon_m': DEFAULT_CHAIN_DP_EPSILON_M,  # part of identity
        'retained_region_px': None,  # operator-selected legal component seed
        # Manifest metadata (editable; every field is approval-bound).
        'route_name': Path(track_map.png_path).stem,
        'surface': DEFAULT_SURFACE,
        'max_speed_mps': DEFAULT_MAX_SPEED_MPS,
        'approval': 'none',
        'approval_digest': None,     # geometry digest the approval was granted for
        'approval_route_digest': None,  # Route.digest approved with it
        'preview_digest': None,      # geometry digest of the last preview;
                                     # approve/export bind to it (fresh-preview
                                     # rule, same as the server candidate)
        'preview_route_digest': None,  # Route.digest that preview produced
        'revision': 1,               # incremented on every session mutation
        'author': author,
    }


def _migrate_session(session):
    """Upgrade old drafts; approval never survives migration.

    v1 bound approval to a bare string with no geometry digest and bound the
    map to hash+size only. v2 lacks the retained-region seed, so an approval
    granted without it cannot authorize the selected-component geometry.
    Carrying such an approval forward would authorize an unknown geometry
    under a stronger contract, so it is revoked here.
    """
    if session.get('version') == 1:
        session = dict(session)
        session['version'] = 2
        session.setdefault('negate', 0)
        session['approval'] = 'none'
        session['approval_digest'] = None
        session.setdefault('revision', 1)
    if session.get('version') == 2:
        session = dict(session)
        session['version'] = 3
        session['retained_region_px'] = None
        session['approval'] = 'none'
        session['approval_digest'] = None
        session.setdefault('revision', 1)
    if session.get('version') == 3:
        # v3 approvals authorized the retired schema-v1 manifest; under
        # the route manifest they would authorize different geometry.
        session = dict(session)
        session['version'] = 4
        session.setdefault('route_name',
                           Path(str(session.get('map_png', 'route'))).stem)
        session.setdefault('surface', DEFAULT_SURFACE)
        session.setdefault('max_speed_mps', DEFAULT_MAX_SPEED_MPS)
        session['approval'] = 'none'
        session['approval_digest'] = None
        session['approval_route_digest'] = None
        session['preview_digest'] = None
        session['preview_route_digest'] = None
        session.setdefault('revision', 1)
    return session


def check_session_map(session, track_map):
    """Reject a session reopened against a differently interpreted map.

    The PNG hash and dimensions alone do not pin the metric registration:
    the same bytes under another resolution, origin, or negate flag would
    silently reinterpret every stored stroke and approval. All of them are
    bound, so such a map is rejected instead of rebound.
    """
    if session.get('map_sha256') != track_map.sha256:
        raise AnnotationError('map identity mismatch: session was created '
                              'for a different map PNG (sha256 differs)')
    if list(session.get('image_size', [])) != [track_map.width, track_map.height]:
        raise AnnotationError('map identity mismatch: image size differs')
    if abs(float(session.get('resolution', -1)) - track_map.resolution) > 1e-12:
        raise AnnotationError('map identity mismatch: resolution differs; '
                              'strokes cannot be reinterpreted')
    if [float(v) for v in session.get('origin', [])] != list(track_map.origin):
        raise AnnotationError('map identity mismatch: origin differs; '
                              'strokes cannot be reinterpreted')
    if int(session.get('negate', 0)) != int(track_map.negate):
        raise AnnotationError('map identity mismatch: negate flag differs; '
                              'occupied/free would invert')


def _checked_seed(retained_region_px, track_map):
    """Return the seed as [u, v] ints, or raise for malformed input.

    Shape and bounds are checked here; whether the pixel is free is
    checked against the patched mask by ``effective_free_mask``.
    """
    seed = retained_region_px
    if seed is None:
        return None
    if (not isinstance(seed, (list, tuple)) or len(seed) != 2
            or any(isinstance(v, bool) for v in seed)):
        raise AnnotationError('retained region must be null or [u, v]')
    try:
        f0, f1 = float(seed[0]), float(seed[1])
    except (TypeError, ValueError):
        raise AnnotationError('retained region must be null or [u, v]')
    if not (math.isfinite(f0) and math.isfinite(f1)):
        raise AnnotationError('retained region must be null or [u, v]')
    try:
        u, v = int(f0), int(f1)
    except OverflowError:
        raise AnnotationError('retained region must be null or [u, v]')
    if f0 != u or f1 != v:
        raise AnnotationError('retained region must be integer pixels')
    if not (0 <= u < track_map.width and 0 <= v < track_map.height):
        raise AnnotationError('retained region is outside the map')
    return [u, v]


# Raster coordinates are int32: stroke points are bounded well inside
# it so the float-to-int32 conversion in patched_free_mask can never
# wrap a huge stored coordinate onto unintended pixels. Far above any
# real map (the HTTP layer caps tighter via MAX_COORD_ABS).
_MAX_STROKE_COORD = 2 ** 30


def _checked_strokes(boundary_strokes_px):
    """Return strokes as validated point lists, or raise AnnotationError.

    Mirrors ``_checked_seed`` for the raster input: every point must be
    a finite ``[u, v]`` pair (floats allowed, rounded only by the
    rasterizer). Non-numeric entries raised raw ValueError from the
    numpy conversion before; they fail closed here instead.
    """
    if not isinstance(boundary_strokes_px, (list, tuple)):
        raise AnnotationError('boundary strokes must be a list of polylines')
    checked = []
    for stroke in boundary_strokes_px:
        if not isinstance(stroke, (list, tuple)):
            raise AnnotationError(
                'boundary strokes must be a list of polylines')
        pts = []
        for pt in stroke:
            if (not isinstance(pt, (list, tuple)) or len(pt) != 2
                    or any(isinstance(v, bool) for v in pt)):
                raise AnnotationError(
                    'stroke points must be [u, v] pixel pairs')
            try:
                f = [float(pt[0]), float(pt[1])]
            except (TypeError, ValueError) as exc:
                raise AnnotationError(
                    'stroke points must be [u, v] pixel pairs') from exc
            if not all(math.isfinite(v) for v in f):
                raise AnnotationError(
                    'stroke points must be finite pixels')
            # The rasterizer converts to int32, where out-of-range
            # float-to-int32 conversion wraps instead of raising: a
            # huge stored coordinate would land the line on unintended
            # pixels. Bound the magnitude well inside int32, far above
            # any real map (HTTP already caps tighter via MAX_COORD_ABS).
            if any(abs(v) > _MAX_STROKE_COORD for v in f):
                raise AnnotationError(
                    'stroke coordinate magnitude exceeds %d px'
                    % _MAX_STROKE_COORD)
            pts.append(f)
        checked.append(pts)
    return checked


def _checked_width(stroke_width_px):
    """Return the raster width, or raise AnnotationError.

    The width selects the occupied rasterization, so a non-integer or
    out-of-range value must fail closed here instead of escaping as a
    ValueError or cv2.error from the drawing call.
    """
    if (isinstance(stroke_width_px, bool)
            or not isinstance(stroke_width_px, int)
            or not 1 <= stroke_width_px <= 31):
        raise AnnotationError('stroke width must be an integer 1..31')
    return stroke_width_px


def geometry_digest(session, track_map):
    """Digest of everything editable an approval refers to.

    Covers the source-map identity, every stroke, the retained region,
    the guide loop, the stroke width, the wall-simplification setting,
    the manifest metadata and the generator version. Any edit changes
    this digest, so an approval granted for one candidate can never
    authorize a different one. Paired with the manifest's own
    ``Route.digest`` at preview/approve/export time.
    """
    canonical = json.dumps({
        'generator': GENERATOR_VERSION,
        'map': track_map.map_identity(),
        'stroke_width_px': session.get('stroke_width_px', 5),
        'boundary_strokes_px': session.get('boundary_strokes_px', []),
        'retained_region_px': session.get('retained_region_px'),
        'route_px': session.get('route_px', []),
        'chain_dp_epsilon_m': session.get('chain_dp_epsilon_m',
                                            DEFAULT_CHAIN_DP_EPSILON_M),
        'route_name': session.get('route_name'),
        'surface': session.get('surface', DEFAULT_SURFACE),
        'max_speed_mps': session.get('max_speed_mps', DEFAULT_MAX_SPEED_MPS),
    }, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def check_source_current(track_map):
    """Refuse when the on-disk source no longer matches this snapshot.

    A ``TrackMap`` is an immutable in-memory snapshot taken at open.
    A long-lived server keeps that snapshot while the PNG/YAML on disk
    can change underneath it; every digest computed from the snapshot
    then still matches itself, so approval alone cannot notice. This
    reloads the source and compares the full interpreted identity
    (PNG bytes, size, resolution, origin, negate). Byte-identical
    restoration passes; interpretation-irrelevant YAML fields (the
    occupancy thresholds, which the binary interpretation never reads)
    are not bound. Raises ``AnnotationError`` on drift or read failure.
    Guarantee: the source matched at this check instant only - a writer
    racing the check itself is not excluded (see ANNOTATION_TOOL.md).
    """
    try:
        fresh = TrackMap(track_map.yaml_path)
    except AnnotationError:
        raise
    except (OSError, ValueError) as exc:
        raise AnnotationError(
            f'source map unreadable since it was opened: {exc}') from exc
    if fresh.map_identity() != track_map.map_identity():
        raise AnnotationError(
            'source map changed on disk since it was opened; reopen the '
            'map and re-preview (approval does not carry over)')


def require_approved(session, track_map):
    """Refuse export unless approval is bound to the current candidate.

    Both identities must match: the editor-input digest (nothing
    editable changed) and the preview binding (the approval was
    granted for the last previewed manifest, not an older one).
    Export additionally rebuilds and compares ``Route.digest``.
    """
    check_source_current(track_map)
    if session.get('approval') != 'operator-approved':
        raise AnnotationError(
            'export refused: session approval is not '
            "'operator-approved' (approve in the UI first)")
    if session.get('approval_digest') != geometry_digest(session, track_map):
        raise AnnotationError(
            'export refused: geometry changed since approval '
            '(re-extract and approve again)')
    if (not session.get('approval_route_digest')
            or session.get('approval_route_digest')
            != session.get('preview_route_digest')):
        raise AnnotationError(
            'export refused: approval is not bound to the last '
            'previewed manifest (preview, approve, then export)')


def save_session(session, path):
    """Write a session atomically; validates map-independent shape."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Pid-qualified tmp name plus failure cleanup live in one place;
    # a shared deterministic sibling would let concurrent writers
    # interleave in one tmp file and publish a corrupt draft.
    atomic_write_text(path, json.dumps(session, indent=1))


def load_session(path, track_map):
    """Load a session and bind it to the map it was created for."""
    try:
        session = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise AnnotationError(f'cannot load session: {exc}') from exc
    if not isinstance(session, dict):
        raise AnnotationError(
            'cannot load session: top level must be an object')
    session = _migrate_session(session)
    if session.get('version') != SESSION_VERSION:
        raise AnnotationError('unsupported session version')
    check_session_map(session, track_map)
    session['retained_region_px'] = _checked_seed(
        session.get('retained_region_px'), track_map)
    return session


def _safe_component(text):
    """Filesystem-safe readable name fragment (stem/dir names)."""
    return ''.join(c if c.isalnum() or c in ('-', '_', '.') else '_'
                   for c in str(text)) or 'map'


def map_namespace(track_map):
    """Filesystem-safe identity prefix distinguishing same-stem maps.

    ``{parentdir}__{stem}__{bytesha8}__{ctxsha8}``: readable layout
    location plus the PNG content hash plus a context hash binding the
    full session identity that ``check_session_map`` enforces
    (resolved parent directory, resolution, origin, negate, image
    size), so two semantically distinct source-map interpretations can
    never silently share a draft or export slot — not even same-stem
    maps in same-named directories, nor identical PNG bytes under
    different YAML interpretations. Loading a session still binds the
    FULL identity via ``check_session_map``; the namespace only selects
    the file, and any residual collision degrades to fail-closed open.
    """
    png = Path(track_map.png_path)
    try:
        parent = str(png.resolve().parent)
    except OSError:
        parent = str(png.parent)
    ctx = '|'.join((parent, repr(float(track_map.resolution)),
                    repr(tuple(float(v) for v in track_map.origin)),
                    repr(int(track_map.negate)),
                    repr(int(track_map.width)), repr(int(track_map.height))))
    ctxsha = hashlib.sha256(ctx.encode('utf-8')).hexdigest()[:8]
    return (f'{_safe_component(png.parent.name)}__'
            f'{_safe_component(png.stem)}__{track_map.sha256[:8]}'
            f'__{ctxsha}')


def draft_name(track_map):
    """Per-map draft filename (replaces the legacy bare-stem name)."""
    return f'{map_namespace(track_map)}_annotation.json'


def export_name(track_map):
    """Per-map export filename (replaces the legacy bare-stem name)."""
    return f'{map_namespace(track_map)}_legal_route.json'


def _legacy_draft_names(track_map):
    """Older draft filename schemes, newest first (migration chain)."""
    png = Path(track_map.png_path)
    stem = _safe_component(png.stem)
    return [
        # Commit 9ccf4b2 scheme: parent + stem + PNG hash, no context.
        f'{_safe_component(png.parent.name)}__{stem}'
        f'__{track_map.sha256[:8]}_annotation.json',
        # Original bare-stem scheme.
        f'{stem}_annotation.json',
    ]


def resolve_draft(out_dir, track_map):
    """Draft path for a map, with non-destructive legacy migration.

    Prefers the namespaced name; falls back through older schemes when
    the namespaced file is absent. A legacy file is adopted only after
    it loads AND validates against this map, then atomically renamed to
    the new name so the ambiguous slot cannot trap a later map. Files
    that fail validation are left untouched and opening fails closed.
    Returns ``(path, migrate_from)`` with ``migrate_from`` None when no
    rename is needed.
    """
    out_dir = Path(out_dir)
    new = out_dir / draft_name(track_map)
    if new.exists():
        return new, None
    for name in _legacy_draft_names(track_map):
        cand = out_dir / name
        if cand != new and cand.exists():
            return new, cand
    return new, None


def atomic_write_text(path, text):
    """Write a file atomically; readers never see a partial file."""
    path = Path(path)
    tmp = path.with_name(path.name + f'.tmp-{os.getpid()}')
    try:
        tmp.write_text(text, encoding='utf-8')
        os.replace(tmp, path)
    except OSError:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


# --------------------------------------------------------------------------
# Raster patch + free-space boundary extraction
# --------------------------------------------------------------------------

def patched_free_mask(track_map, boundary_strokes_px, stroke_width_px=5):
    """Return uint8 free mask (255=free) of the patched in-memory copy.

    The source image must be strictly binary: any gray/unknown level is
    rejected instead of being read as legal free space. The YAML negate
    flag selects which level counts as occupied.
    """
    base = (track_map.image if track_map.negate == 0
            else (255 - track_map.image).astype(track_map.image.dtype))
    levels = np.unique(base)
    if any(int(v) not in (0, 255) for v in levels):
        raise AnnotationError(
            'UNSUPPORTED: map image is not binary '
            f'(levels {sorted(int(v) for v in levels)}); unknown cells '
            'must not be read as legal free space')
    boundary_strokes_px = _checked_strokes(boundary_strokes_px)
    stroke_width_px = _checked_width(stroke_width_px)
    occupied = base < 128
    patched = occupied.copy()
    for stroke in boundary_strokes_px:
        pts = np.array(stroke, dtype=np.int32).reshape(-1, 1, 2)
        if len(pts) >= 2:
            cv2.polylines(patched.view(np.uint8), [pts], False, 1,
                          thickness=stroke_width_px, lineType=cv2.LINE_8)
        elif len(pts) == 1:
            cv2.circle(patched.view(np.uint8), tuple(pts[0, 0]),
                       max(1, stroke_width_px // 2), 1, -1)
    return np.where(patched, 0, 255).astype(np.uint8)


def effective_free_mask(track_map, boundary_strokes_px, stroke_width_px=5,
                        retained_region_px=None):
    """Free mask with an optional operator-selected component retained.

    Without a seed this returns ``patched_free_mask()`` unchanged, so
    unedited maps and references are byte-identical. With a seed pixel
    ``[u, v]`` in the free space ``F``, it returns the 8-connected
    component containing that pixel: ``Flegal = C(p)`` with
    ``Flegal ⊆ F ⊆ F0`` (restriction only; no new free space). Other
    disconnected pockets become occupied in the returned mask.
    """
    free = patched_free_mask(
        track_map, boundary_strokes_px, stroke_width_px)
    seed = _checked_seed(retained_region_px, track_map)
    if seed is None:
        return free
    u, v = seed
    if free[v, u] == 0:
        raise AnnotationError(
            'retained pixel is occupied (stroke or wall); '
            'click free track instead')
    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        (free > 0).astype(np.uint8), connectivity=8)
    label = int(labels[v, u])
    if label <= 0 or count <= label:
        raise AnnotationError('retained pixel is not in free space')
    return np.where(labels == label, 255, 0).astype(np.uint8)


def free_components(free_mask):
    """8-connected free regions, largest first: area + centroid in px."""
    count, labels, stats, centroids = cv2.connectedComponentsWithStats(
        (free_mask > 0).astype(np.uint8), connectivity=8)
    regions = [{'area_px': int(stats[i, cv2.CC_STAT_AREA]),
                'centroid_px': [float(centroids[i][0]),
                                float(centroids[i][1])]}
               for i in range(1, count)]
    regions.sort(key=lambda r: (-r['area_px'], r['centroid_px']))
    return regions


def _annulus_loops(mask):
    """Split a free mask into (outer, inner) closed loops or reject."""
    contours, hierarchy = cv2.findContours(
        mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    if hierarchy is None or len(contours) == 0:
        raise AnnotationError('extraction failed: no free space found')
    hier = hierarchy[0]
    outer_idx = [i for i in range(len(contours)) if hier[i][3] == -1]
    if len(outer_idx) != 1:
        raise AnnotationError(
            f'UNSUPPORTED: free space has {len(outer_idx)} separate regions '
            '(expected 1 enclosed track; check gaps or splits)')
    holes = [i for i in range(len(contours)) if hier[i][3] == outer_idx[0]]
    if len(holes) != 1:
        raise AnnotationError(
            f'extraction failed: enclosed track needs exactly 1 inner '
            f'boundary, found {len(holes)} (draw a boundary stroke to '
            'close any open section, or remove stray marks)')
    outer = contours[outer_idx[0]].reshape(-1, 2).astype(float)
    inner = contours[holes[0]].reshape(-1, 2).astype(float)
    return outer, inner


def _touches_frame(mask):
    return (bool(mask[0, :].any()) or bool(mask[-1, :].any())
            or bool(mask[:, 0].any()) or bool(mask[:, -1].any()))


def extract_boundaries(track_map, boundary_strokes_px=(), stroke_width_px=5,
                        retained_region_px=None):
    """Extract (outer, inner) closed loops in file-pixel coordinates.

    The free space must be exactly one connected region with exactly one
    hole (a planar annulus). Any other topology is rejected - an open
    gap merges the hole with the outside, a split adds regions - rather
    than being guessed at.

    Strokes that cut off pockets fragment the mask; without a retained
    seed that raises NEEDS_REGION_SELECTION (select one component, do
    not approve). With a seed, only its component is checked.
    """
    free = effective_free_mask(track_map, boundary_strokes_px,
                               stroke_width_px, retained_region_px)
    if _touches_frame(free):
        raise AnnotationError(
            'extraction failed: free space touches the image frame '
            '(open outer wall at the map edge; draw a boundary stroke '
            'to close the gap)')
    try:
        return _annulus_loops(free)
    except AnnotationError as exc:
        if retained_region_px is None and 'separate regions' in str(exc):
            regions = free_components(free)
            areas = ', '.join(str(r['area_px']) for r in regions)
            raise AnnotationError(
                'NEEDS_REGION_SELECTION: free space has '
                f'{len(regions)} separate regions '
                f'(areas px: {areas}); select the legal track component '
                'before extraction') from exc
        raise


def _arc(chain_closed, start_idx, end_idx, step_sign):
    """Walk a closed chain from start to end (inclusive) in step_sign dir."""
    n = len(chain_closed)
    out, i = [], start_idx
    while True:
        out.append(chain_closed[i])
        if i == end_idx:
            break
        i = (i + step_sign) % n
        if len(out) > n + 1:  # pragma: no cover - defensive
            raise AnnotationError('boundary arc walk failed')
    return out


def _circular_gap(a, b, n):
    """Shortest index distance between two samples of a closed n-loop."""
    return min((a - b) % n, (b - a) % n)


def _simplify(points, min_spacing_px, eps_m=0.0, chord_ok=None):
    """Drop consecutive points closer than min_spacing_px (keep last).

    The radial pass alone is unbounded: it can silently remove a
    sub-spacing feature before RDP ever sees it (the annexing chord
    then hits RDP's zero-deviation shortcut, which skips the raster
    gate). Callers that simplify legal walls must therefore pass a
    deviation bound and chord predicate: every shortcut chord over
    dropped points is then verified (deviation within eps_m, predicate
    holds), and violations re-instate the farthest dropped vertex
    RDP-style, so the output stays within eps_m of the input with
    gate-checked chords. The wall chain passes the envelope's
    quantization floor (0.6 raster cells: pixel staircase is <= ~0.5
    px) here and the wall epsilon to RDP below. The guide loop
    intentionally uses the unbounded form (it carries no legality;
    it only places joints, and the walls are judged downstream).
    """
    pts = [np.array(p, float) for p in points]
    n = len(pts)
    if n < 2:
        return [tuple(p) for p in pts]
    keep = [0]
    for i in range(1, n):
        if float(np.linalg.norm(pts[i] - pts[keep[-1]])) >= min_spacing_px:
            keep.append(i)
    if keep[-1] != n - 1:
        keep.append(n - 1)
    if not (eps_m > 0 and chord_ok is not None):
        return [tuple(pts[i]) for i in keep]
    kept = [False] * n
    for i in keep:
        kept[i] = True
    stack = [(keep[j], keep[j + 1]) for j in range(len(keep) - 1)]
    while stack:
        a, b = stack.pop()
        if b - a < 2:
            continue
        seg = pts[b] - pts[a]
        denom = float(np.dot(seg, seg))
        dist, idx = 0.0, -1
        for i in range(a + 1, b):
            t = 0.0 if denom < 1e-18 else float(
                np.dot(pts[i] - pts[a], seg) / denom)
            proj = pts[a] + min(1.0, max(0.0, t)) * seg
            d = float(np.linalg.norm(pts[i] - proj))
            if d > dist:
                dist, idx = d, i
        if dist <= 1e-9:
            continue
        if dist > eps_m or not chord_ok(pts[a], pts[b]):
            kept[idx] = True
            stack.append((a, idx))
            stack.append((idx, b))
    return [tuple(pts[i]) for i in range(n) if kept[i]]


#: Wall-simplification envelope in raster cells. Walls pass two bounded
#: stages: a radial pre-filter that only removes deviations below this
#: quantization floor (pixel staircase peaks at ~0.5 px), then RDP
#: bounded by the wall epsilon with raster-gate-checked chords. End to
#: end the gain against the extracted dense wall is bounded by floor +
#: epsilon (<= 1.2 cells inside the envelope); the chord gate
#: additionally rejects crossings of occupied spans >= ~3 cells wide.
#: A 576-run fixture sweep measured worst gain 0.50 cells at ratio 0.6
#: for the RDP stage, and the full chain keeps the pinned 1x1.2-cell
#: notch fixture at ~0 gain (above the floor, then kept by RDP).
#: build_route enforces the envelope; the bare primitives carry no
#: resolution bound (unit fixtures intentionally exceed it).
MAX_DP_EPS_PER_CELL = 0.6


def _douglas_peucker(points, epsilon, _chord_ok=None):
    """Shape-preserving decimation: keep the fewest points whose polyline
    stays within epsilon of the original (metres).

    Raster-extracted walls carry a vertex every pixel; the route
    package densifies walls again for its Voronoi centreline, so dense
    walls cost real time without adding geometry. Uniform coarsening
    instead cuts bends. RDP keeps bend vertices and drops redundant
    straight-run points. Endpoints are always kept; callers re-pin the
    exact shared end-caps afterwards. Epsilon 0.02 m is the default;
    dense maps use 0.03 m (see VALIDATE_THINNINGS).

    Plain RDP bounds deviation but not side: a chord may cut occupied
    space. When ``_chord_ok(a, b)`` is given, a within-epsilon chord is
    still rejected unless the predicate holds; rejection keeps the
    farthest vertex and recurses exactly like an epsilon violation, so in
    the limit this falls back to the exact polyline. The gate is
    raster-grounded, not strictly inward: it rejects chords crossing
    occupied spans >= ~3 cells wide (axis; ~4 diagonal), while a removed
    feature narrower than that is annexed up to its own height, which
    this stage bounds by epsilon against its own input. The wall chain
    pairs this with a floor-bounded ``_simplify`` (deviations below 0.6
    raster cells are pixel-staircase quantization, verified the same
    way), so the end-to-end gain against the extracted dense wall is
    bounded by floor + epsilon; the build_route envelope
    (epsilon/resolution <= MAX_DP_EPS_PER_CELL = 0.6) tightens that to
    ~1.2 raster cells worst case. RDP alone (the swept primitive) holds
    gain <= eps; see ``_chord_stays_free`` for the predicate's resolving
    power.
    """
    pts = [np.array(p, float) for p in points]
    if len(pts) < 3 or epsilon <= 0:
        return [tuple(p) for p in pts]
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        if b - a < 2:
            continue
        seg = pts[b] - pts[a]
        denom = float(np.dot(seg, seg))
        dist, idx = 0.0, -1
        for i in range(a + 1, b):
            t = 0.0 if denom < 1e-18 else float(
                np.dot(pts[i] - pts[a], seg) / denom)
            proj = pts[a] + min(1.0, max(0.0, t)) * seg
            d = float(np.linalg.norm(pts[i] - proj))
            if d > dist:
                dist, idx = d, i
        if dist <= 1e-9:
            # Chord coincides with the original chain: zero deviation
            # means zero gain; no raster check needed (and wall-coincident
            # samples would false-reject). Note idx is -1 here, which must
            # never reach the split below.
            continue
        if dist > epsilon or (_chord_ok is not None
                              and not _chord_ok(pts[a], pts[b])):
            keep[idx] = True
            stack.append((a, idx))
            stack.append((idx, b))
    return [tuple(pts[i]) for i, k in enumerate(keep) if k]


def _loop_reference_mask(track_map, outer_px, inner_px):
    """Rasterize the extracted loops back to the map pixel grid.

    ``outer_px``/``inner_px`` are file-pixel loops; this reconstructs the
    annotated free region (map + operator strokes) from them, up to
    contour rasterization (~0.5 px). Chords of simplified walls are
    tested against this mask, so the exported corridor cannot gain space
    across occupied spans the mask resolves (>= ~3 cells wide); narrower
    features are bounded by the build_route envelope (quantization
    floor plus epsilon), not by this mask alone. Frame-touching free
    space is rejected upstream, so no loop legitimately reaches the
    image border.
    """
    width, height = int(track_map.width), int(track_map.height)
    mask = np.zeros((height, width), np.uint8)
    cv2.fillPoly(mask, [np.int32(np.round(np.asarray(outer_px, float)))], 1)
    cv2.fillPoly(mask, [np.int32(np.round(np.asarray(inner_px, float)))], 0)
    return mask


def _chord_stays_free(a, b, free, to_px_uv, res_m):
    """Check a simplified wall chord against the (dilated) free mask.

    Samples the chord every half pixel; every sample must land on free
    space. The caller passes a free mask dilated by one raster cell, so
    boundary straddle up to one pixel is tolerated while deeper cuts are
    rejected. Resolving power, measured: crossings of occupied spans
    >= 3 cells wide (axis; >= 4 diagonal) are rejected, and a chord
    hugging the true wall passes. Narrower occupied features are
    invisible to the one-cell dilation: a chord over one is accepted,
    and its annexation is bounded by the calling stage's epsilon (each
    wall stage requires removed-feature height <= epsilon, verified
    against its own input). For example, a 2-cell-wide 8 mm peninsula
    at 2 mm raster is annexed only if its height fits the stage bound,
    while a 15 mm tooth 7+ cells wide is kept. Out-of-bounds
    samples fail closed. Intrusions below one raster cell are
    unresolvable by construction (the grid cannot represent them) and
    documented. The sub-cell remainder is bounded by the build_route
    envelope (epsilon/resolution <= MAX_DP_EPS_PER_CELL).
    """
    seg = np.asarray(b, float) - np.asarray(a, float)
    length = float(np.linalg.norm(seg))
    if length < 1e-12:
        return True
    step = 0.5 * res_m
    count = max(2, int(math.ceil(length / step)))
    frac = np.linspace(0.0, 1.0, count + 1)[1:-1]
    if len(frac) == 0:
        return True
    pts = np.asarray(a, float)[None, :] + frac[:, None] * seg[None, :]
    uv = np.round(np.array([to_px_uv(p) for p in pts])).astype(int)
    height, width = free.shape
    if bool((uv[:, 0] < 0).any()) or bool((uv[:, 0] >= width).any()) or \
            bool((uv[:, 1] < 0).any()) or bool((uv[:, 1] >= height).any()):
        return False
    return bool((free[uv[:, 1], uv[:, 0]] > 0).all())


def _resample_closed(points_px, spacing_px):
    """Resample a closed polyline at near-uniform spacing (pixel units)."""
    pts = [np.array(p, float) for p in points_px]
    if len(pts) < 3:
        raise AnnotationError('route loop needs at least 3 points')
    if np.linalg.norm(pts[0] - pts[-1]) < 1e-9:
        pts = pts[:-1]
    seg, total = [], 0.0
    for a, b in zip(pts, pts[1:] + pts[:1]):
        d = float(np.linalg.norm(b - a))
        if d < 1e-9:
            raise AnnotationError('route loop has a zero-length segment')
        seg.append(d)
        total += d
    count = max(12, int(total / spacing_px))
    out, target, acc, i = [], 0.0, 0.0, 0
    while len(out) < count:
        while acc + seg[i] < target:
            acc += seg[i]
            i = (i + 1) % len(pts)
        f = (target - acc) / seg[i]
        out.append(pts[i] + f * (pts[(i + 1) % len(pts)] - pts[i]))
        target += total / count
    return out, total


# --------------------------------------------------------------------------
# Centerline seed generation (distance-transform ridge)
# --------------------------------------------------------------------------

def ridge_seed(track_map, outer_px, inner_px, boundary_strokes_px=(),
               stroke_width_px=5, spacing_m=0.75, count=160, iters=60,
               retained_region_px=None):
    """Relax a crude midline seed onto the free-space ridge.

    The correspondence-based midline (each outer point paired with its
    nearest inner point) kinks at hairpins and S-bends, where nearest
    matching flips discontinuously. Instead this walks the seed uphill
    on the distance transform of the free mask - the gradient always
    points at the local centerline - while a closed-loop Laplacian keeps
    it smooth. Every step is confined to free space; a point that would
    leave it keeps its previous position. The result is a deterministic
    closed seed in file-pixel coordinates following the outer loop's
    direction; ``check_payload`` remains the acceptance gate.
    """
    free = effective_free_mask(track_map, boundary_strokes_px,
                                 stroke_width_px, retained_region_px)
    height, width = free.shape
    dist = cv2.distanceTransform(free, cv2.DIST_L2, 3)
    gradu = cv2.Sobel(dist, cv2.CV_64F, 1, 0, ksize=3)
    gradv = cv2.Sobel(dist, cv2.CV_64F, 0, 1, ksize=3)
    outer = np.asarray(outer_px, float)
    inner = np.asarray(inner_px, float)
    step = max(1, len(outer) // count)
    crude = []
    for p in outer[::step]:
        j = int(np.argmin(np.linalg.norm(inner - p, axis=1)))
        crude.append((p + inner[j]) / 2.0)
    pts, _ = _resample_closed([tuple(p) for p in crude],
                              spacing_m / track_map.resolution)
    pts = np.array([p for p in pts], float)
    n = len(pts)

    def sample(p):
        u = min(width - 1, max(0, int(round(p[0]))))
        v = min(height - 1, max(0, int(round(p[1]))))
        return u, v

    for _ in range(iters):
        # Gentle closed-loop smoothing (kink removal) with most weight
        # on the current point so the loop cannot collapse off the
        # track; then snap each point back to its local DT maximum.
        pts = 0.8 * pts + 0.1 * (np.roll(pts, 1, 0) + np.roll(pts, -1, 0))
        for i in range(n):
            p = pts[i].copy()
            u, v = sample(p)
            best = float(dist[v, u])
            for _ in range(40):
                g = np.array([gradu[v, u], gradv[v, u]])
                norm = float(np.linalg.norm(g))
                if norm < 1e-9:
                    break
                q = p + 0.5 * g / norm
                qu, qv = sample(q)
                if free[qv, qu] == 0:
                    break
                val = float(dist[qv, qu])
                if val < best - 1e-9:
                    break
                p, u, v, best = q, qu, qv, val
            pts[i] = p
    return [[float(p[0]), float(p[1])] for p in pts]


# --------------------------------------------------------------------------
# Centerline suggestion (dense pairing + heavy spline)
# --------------------------------------------------------------------------

def _signed_area(pts):
    pts = np.asarray(pts, float)
    return 0.5 * float(np.sum(pts[:, 0] * np.roll(pts[:, 1], -1)
                               - np.roll(pts[:, 0], -1) * pts[:, 1]))


def suggest_route(outer_px, inner_px, route_px=(), eval_points=240,
                  smooth_factor=6.0):
    """Propose a smooth centerline seed from the extracted loops.

    Each outer-loop vertex is paired with its nearest inner-loop vertex
    and averaged (dense correspondence: no subsampling flip), then a
    heavy periodic smoothing spline removes the pairing overshoot.

    The suggestion follows the operator's drawn direction when a route
    exists (reversed when their loop runs the other way); otherwise it
    follows the outer loop order. It is a starting point, not an
    approval: the operator inspects it in preview, may redraw it, and
    ``check_payload`` remains the acceptance gate.
    """
    outer = np.asarray(outer_px, float)
    inner = np.asarray(inner_px, float)
    dense = np.array([((p + inner[int(np.argmin(
        np.linalg.norm(inner - p, axis=1)))]) / 2.0) for p in outer])
    if route_px is not None and len(route_px) >= 3:
        try:
            if _signed_area(route_px) * _signed_area(dense) < 0:
                dense = dense[::-1]
        except Exception:  # noqa: BLE001 - unusable route: keep loop order
            pass
    try:
        from scipy.interpolate import splev, splprep
    except ImportError as exc:
        raise AnnotationError(
            'route suggestion needs scipy (not installed here)') from exc
    n = len(dense)
    tck, _ = splprep([dense[:, 0], dense[:, 1]], s=n * smooth_factor,
                     per=True)
    u = np.linspace(0, 1, int(eval_points), endpoint=False)
    x, y = splev(u, tck)
    return [[float(a), float(b)] for a, b in zip(x, y)]


# --------------------------------------------------------------------------
# Route construction
# --------------------------------------------------------------------------

def build_route(track_map, outer_px, inner_px, route_px, *,
                name=None, surface=DEFAULT_SURFACE,
                max_speed_mps=DEFAULT_MAX_SPEED_MPS, n_sections=4,
                spacing_m=0.75, chain_dp_epsilon_m=0.02, _smoothing_passes=4):
    """Build a route manifest payload from extracted loops + guide loop.

    Emits exactly the live ``global_planner.route`` shape
    (``{name, map, start, sections}``); approval and provenance live in
    the session, because the schema admits no extra fields. The guide
    loop sets travel direction and where the section cuts fall; it is
    not exported - the route package derives each centreline from the
    walls. Returns ``(payload, info)``; validation is ``check_payload``.

    Geometry contract (enforced): wall simplification runs two bounded,
    gate-checked stages. The radial pre-filter only removes deviations
    below the envelope's quantization floor (0.6 raster cells: pixel
    staircase peaks at ~0.5 px), while real features above the floor
    survive. RDP then bounds the remainder within epsilon with
    raster-gate-checked chords. End to end the gain against the
    extracted dense wall is bounded by floor + epsilon (<= ~1.2 raster
    cells inside the envelope), and only across features narrower than
    the chord gate resolves (~3 cells); ``check_payload`` re-measures
    the gain on the final polygons. Under the enforced precondition
    ``chain_dp_epsilon_m / resolution <= MAX_DP_EPS_PER_CELL`` (0.6).
    Configs above the ratio are rejected instead of producing a
    purportedly valid export. Epsilon 0 skips RDP (radial decimation
    still applies) and is exempt.
    """
    if n_sections < 3:
        raise AnnotationError('a route needs at least 3 sections')
    if name is None:
        name = Path(track_map.png_path).stem
    name = _checked_text(name, 'route name')
    surface = _checked_text(surface, 'surface')
    max_speed_mps = _checked_speed(max_speed_mps)
    if chain_dp_epsilon_m > 0 and chain_dp_epsilon_m / track_map.resolution > \
            MAX_DP_EPS_PER_CELL * (1.0 + 1e-9):
        raise AnnotationError(
            f'chain simplification epsilon {chain_dp_epsilon_m} m exceeds '
            f'{MAX_DP_EPS_PER_CELL} raster cells at '
            f'{track_map.resolution} m/px; reduce chain_dp_epsilon_m '
            '(supported envelope: epsilon/resolution <= 0.6)')
    spacing_px = spacing_m / track_map.resolution
    seed_px, _ = _resample_closed(route_px, spacing_px)
    # Smooth the operator's rough loop (circular moving average). The
    # drawing order/direction is untouched; only pixel jitter that would
    # fold the corridor chart (curvature x half-width >= 1) is removed.
    arr = np.array(seed_px, float)
    kernel = np.array([1., 2., 3., 2., 1.])
    kernel /= kernel.sum()
    for _ in range(_smoothing_passes):
        arr = np.stack([sum(kernel[k] * np.roll(arr[:, c], k - 2)
                            for k in range(5)) for c in range(2)], axis=1)
    seed = [np.array(track_map.pixel_to_world(p)) for p in arr]
    # Direction comes from the operator's drawing order, untouched.
    # Project each seed point into the corridor between the two loops:
    # smoothing may cut a corner across a boundary, so clamp the lateral
    # offset to the middle half of the local width. Longitudinal intent
    # and direction are preserved; a point still outside after this is
    # rejected later by the strict validator, never hidden.
    outer_w = np.array([track_map.pixel_to_world(p) for p in outer_px])
    inner_w = np.array([track_map.pixel_to_world(p) for p in inner_px])

    def _nearest(chain, p):
        return chain[int(np.argmin(np.linalg.norm(chain - p, axis=1)))]

    corrected = []
    max_correction_m = 0.0
    for i, p in enumerate(seed):
        lo = _nearest(outer_w, p)
        li = _nearest(inner_w, p)
        mid, half = (lo + li) / 2.0, (lo - li) / 2.0
        denom = float(np.dot(half, half))
        alpha = 0.0 if denom < 1e-12 else float(
            np.clip(np.dot(p - mid, half) / denom, -0.5, 0.5))
        q = mid + alpha * half
        max_correction_m = max(max_correction_m, float(np.linalg.norm(q - p)))
        corrected.append(q)
    seed = corrected
    seed_info = {'seed_samples': len(seed),
                 'max_correction_m': max_correction_m}

    def nearest(chain, p):
        d = np.linalg.norm(chain - np.array(p), axis=1)
        return int(np.argmin(d))

    outer = np.array([track_map.pixel_to_world(p) for p in outer_px])
    inner = np.array([track_map.pixel_to_world(p) for p in inner_px])
    # Classify each seed sample's left/right chain by the travel normal.
    # Place split joints on locally straight seed points near each
    # quarter of the lap: gates on straights keep portal charts unfolded.
    turn = []
    for i, p in enumerate(seed):
        a = seed[i] - seed[i - 1]
        b = seed[(i + 1) % len(seed)] - p
        turn.append(abs(math.atan2(a[0] * b[1] - a[1] * b[0],
                                   float(np.dot(a, b)))))
    # Joints must be well separated around the lap: adjacent windows
    # overlap, so unconstrained straight-snapping can pile two joints a
    # few samples apart and leave a degenerate sliver occurrence whose
    # nearly coincident gates leave a degenerate sliver section.
    min_sep = max(8, len(seed) // 8)
    joint_at = []
    for k in range(n_sections):
        target = int(round(k * len(seed) / n_sections))
        window = range(target - len(seed) // 8, target + len(seed) // 8)
        cand = [j % len(seed) for j in window]
        if joint_at:
            cand = [j for j in cand
                    if min(_circular_gap(j, c, len(seed)) for c in joint_at)
                    >= min_sep]
        if not cand:
            raise AnnotationError('could not place well-separated split joints; '
                                  'redraw the route loop more evenly')
        # Quantize the turn before comparing: near-straight samples tie
        # to within float noise, and an unquantized min() picks
        # different joints on different CPUs/BLAS builds for identical
        # input. 1e-6 rad is far above that noise and far below any
        # curvature that matters for cut placement.
        joint_at.append(min(cand, key=lambda j: round(turn[j], 6)))
    joint_at = sorted(joint_at)
    if len(set(joint_at)) != n_sections or \
            any(_circular_gap(a, b, len(seed)) < min_sep
                for a, b in zip(joint_at, joint_at[1:] + joint_at[:1])):
        raise AnnotationError('could not place well-separated split joints; '
                              'redraw the route loop more evenly')
    joints = []  # (seed_idx, left_pt, right_pt, left_chain, left_idx, ...)
    for idx in joint_at:
        p = seed[idx]
        nxt = seed[(idx + 1) % len(seed)]
        prv = seed[(idx - 1) % len(seed)]
        tangent = nxt - prv
        norm = np.linalg.norm(tangent)
        if norm < 1e-12:
            raise AnnotationError('degenerate route loop at a split point')
        tangent /= norm
        normal = np.array([-tangent[1], tangent[0]])  # left of travel
        cand = []
        for label, chain in (('outer', outer), ('inner', inner)):
            j = nearest(chain, p)
            cand.append((label, chain, j, chain[j]))
        # Left = the candidate whose offset from the seed points left.
        cand.sort(key=lambda c: float(np.dot(c[3] - p, normal)), reverse=True)
        (lname, lchain, lj, lpt), (rname, rchain, rj, rpt) = cand
        if joints:  # left/right chain identity is global for a simple lap
            lchain = joints[0]['lchain']
            rchain = joints[0]['rchain']
            lj, rj = nearest(lchain, p), nearest(rchain, p)
            lpt, rpt = lchain[lj], rchain[rj]
        if float(np.dot(lpt - p, normal)) <= 0 or float(np.dot(rpt - p, normal)) >= 0:
            raise AnnotationError(
                'route loop is not between the two boundaries at a split '
                'point; redraw it inside the track')
        mid = (lpt + rpt) / 2.0
        joints.append({'idx': idx, 'left': lpt, 'right': rpt, 'mid': mid,
                       'lchain': lchain, 'lj': lj, 'rchain': rchain, 'rj': rj})

    sections, seeds = [], []
    min_spacing_px = max(2.0, 0.05 / track_map.resolution)
    # Reference free mask for the containment gate: chords of simplified
    # walls must stay within one raster cell of the extracted legal
    # region (see helpers). Dilation by exactly one cell is the grid
    # quantum, not an arbitrary margin: anything smaller is
    # unrepresentable on this raster.
    ref_free = cv2.dilate(
        _loop_reference_mask(track_map, outer_px, inner_px),
        np.ones((3, 3), np.uint8))

    def wall_chord_ok(a, b):
        return _chord_stays_free(a, b, ref_free, track_map.world_to_pixel,
                                track_map.resolution)
    for k in range(n_sections):
        a, b = joints[k], joints[(k + 1) % n_sections]
        # Seed fragment: from joint a to joint b along travel, with the
        # endpoints replaced by gate midpoints (exact shared end-caps).
        idxs, i = [], a['idx']
        while True:
            idxs.append(i)
            if i == b['idx']:
                break
            i = (i + 1) % len(seed)
        frag = [a['mid']] + [seed[i] for i in idxs[1:-1]] + [b['mid']]
        frag = _simplify(frag, min_spacing_px * track_map.resolution)
        # Boundary arcs follow the same direction of travel.
        def arc_pts(chain, j0, j1, ref):
            fwd = _arc(chain, j0, j1, +1)
            rev = _arc(chain, j0, j1, -1)
            # Pick the arc whose midpoint is nearer the seed fragment.
            midref = ref[len(ref) // 2]
            pick = fwd if np.linalg.norm(fwd[len(fwd) // 2] - midref) <= \
                np.linalg.norm(rev[len(rev) // 2] - midref) else rev
            # Prefilter bound is the envelope's quantization floor
            # (0.6 raster cells: pixel staircase is <= ~0.5 px), not eps:
            # an eps-bounded prefilter reinstates every quantization jag
            # and explodes the wall vertex counts. RDP below still
            # enforces eps with the raster gate; real features above the
            # floor survive both stages (pinned by regression test).
            floor_m = MAX_DP_EPS_PER_CELL * track_map.resolution
            return _simplify(pick, min_spacing_px * track_map.resolution,
                             floor_m, wall_chord_ok)
        left = arc_pts(a['lchain'], a['lj'], b['lj'], frag)
        right = arc_pts(a['rchain'], a['rj'], b['rj'], frag)
        if chain_dp_epsilon_m > 0:
            left = _douglas_peucker(left, chain_dp_epsilon_m,
                                    _chord_ok=wall_chord_ok)
            right = _douglas_peucker(right, chain_dp_epsilon_m,
                                     _chord_ok=wall_chord_ok)
        # Force exact shared endpoints regardless of arc simplification:
        # one cap, stored as this section's end and the next one's start,
        # must be the same point in both (the route validator forgives
        # only 1e-9 m, and the manifest digest follows the raw numbers).
        left[0], left[-1] = tuple(a['left']), tuple(b['left'])
        right[0], right[-1] = tuple(a['right']), tuple(b['right'])
        seeds.append(frag)
        sections.append({
            'uid': f's{k}', 'surface': surface,
            'max_speed_mps': float(max_speed_mps),
            'left': [[float(x), float(y)] for x, y in left],
            'right': [[float(x), float(y)] for x, y in right]})
    first = seeds[0]
    t0 = np.array(first[1]) - np.array(first[0])
    heading = math.atan2(t0[1], t0[0])

    def _at(chain, dist_m):
        """Point at arc length dist_m along a wall chain (clamped)."""
        pts = [np.array(p, float) for p in chain]
        left_m = dist_m
        for a, b in zip(pts, pts[1:]):
            d = float(np.linalg.norm(b - a))
            if left_m <= d:
                return a + (b - a) * (left_m / d if d > 0 else 0.0)
            left_m -= d
        return pts[-1]

    # Start zone: the middle half of the road over the first 1.2 m of
    # the first section, following its actual walls so the box stays
    # on the road around a bend (a fixed rectangle does not). It is a
    # starting suggestion, not a surveyed grid slot; check_payload
    # still verifies it against the legal raster.
    s0 = sections[0]
    r0, l0 = np.array(s0['right'][0]), np.array(s0['left'][0])
    r1, l1 = _at(s0['right'], 1.2), _at(s0['left'], 1.2)
    zone = [[float(x), float(y)] for x, y in (
        r0 + 0.25 * (l0 - r0), r1 + 0.25 * (l1 - r1),
        r1 + 0.75 * (l1 - r1), r0 + 0.75 * (l0 - r0))]
    payload = {
        'name': name,
        'map': {'frame_id': 'map', 'sha256': track_map.sha256},
        'start': {'heading_range_rad': [max(-math.pi, heading - 0.3),
                                        min(math.pi, heading + 0.3)],
                  'zone': zone},
        'sections': sections}
    info = dict(seed_info)
    info['smoothing_passes'] = _smoothing_passes
    return payload, info


# --------------------------------------------------------------------------
# Candidate checks: final-polygon legality + the route package pipeline
# --------------------------------------------------------------------------

#: Checks this tool cannot run because the route package has no such
#: stage yet. Named in every receipt so a PASS here is never read as a
#: certified racing trajectory.
NOT_CHECKED = (
    'trajectory optimization and speed profile (not in the route package)',
    'continuous vehicle-body / dynamics certification (not in the route package)',
)


def _fill_px(track_map, chain_world, scale=1):
    """Rasterize one world polygon: filled mask at ``scale`` x resolution."""
    mask = np.zeros((track_map.height * scale, track_map.width * scale),
                    np.uint8)
    pts = np.array([track_map.world_to_pixel(p) for p in chain_world],
                   float) * scale
    cv2.fillPoly(mask, [np.round(pts).astype(np.int32)], 1)
    return mask


def _vector_legality(track_map, payload, legal_mask):
    """Measure final-polygon gain over the selected legal raster.

    The chord gate in the simplification stages is a prefilter; this
    checks the exact emitted polygons (after thinning and cap
    re-pinning) and the start zone. Policy, stated plainly: every
    exported pixel centre must lie within one raster cell of legal
    free space - the same one-cell quantum the chord gate uses - and
    the gained area over occupied cells is rasterized at 4x and
    reported (boundary subcells included, so it overstates the true
    geometric gain). Strict cell-square containment is
    *not* claimed: a straight chord along a diagonal staircase wall
    necessarily covers occupied corner subcells, so the measured gain
    is small but nonzero on real maps. Returns the gain in m².
    """
    legal = (legal_mask > 0).astype(np.uint8)
    near = cv2.dilate(legal, np.ones((3, 3), np.uint8))
    scale = 4
    legal4 = np.repeat(np.repeat(legal, scale, axis=0), scale, axis=1)
    gain_cells = 0
    for section in payload['sections']:
        polygon = list(section['right']) + list(reversed(section['left']))
        filled = _fill_px(track_map, polygon)
        outside = int((filled & (near == 0)).sum())
        if outside:
            v, u = (int(x) for x in np.argwhere(filled & (near == 0))[0])
            x, y = track_map.pixel_to_world((u, v))
            raise AnnotationError(
                f'VECTOR_LEGAL: section {section["uid"]} covers '
                f'{outside} pixel(s) more than one cell outside the '
                f'selected legal region, e.g. near ({x:.2f}, {y:.2f}); '
                'the simplified wall annexes excluded or occupied space')
        filled4 = _fill_px(track_map, polygon, scale)
        gain_cells += int((filled4 & (legal4 == 0)).sum())
    zone = _fill_px(track_map, payload['start']['zone'])
    if int((zone & (near == 0)).sum()):
        raise AnnotationError(
            'VECTOR_LEGAL: the start zone reaches off the selected '
            'legal road; move the guide loop start or redraw it')
    first = payload['sections'][0]
    outline = np.array(
        [track_map.world_to_pixel(p)
         for p in list(first['right']) + list(reversed(first['left']))],
        np.float32)
    centre = tuple(np.mean(payload['start']['zone'], axis=0))
    if cv2.pointPolygonTest(
            outline, tuple(float(v) for v in
                           track_map.world_to_pixel(centre)), False) < 0:
        raise AnnotationError(
            'VECTOR_LEGAL: the start zone centre is not inside the '
            'first section')
    return gain_cells * (track_map.resolution / scale) ** 2


def check_payload(payload, track_map, legal_mask, car=None):
    """Run every available check on one candidate; return (route, receipt).

    Stages, in order: ``vector_legal`` (final polygons vs the selected
    raster), ``manifest`` (route ``validate_route``: schema, walls,
    derived centrelines, portals, contacts), ``lap``
    (``centre_curve``), ``portals`` (``portal_crossings``),
    ``samples`` (``sample_lap`` at 0.25 m), and ``car_zones``
    (``portal_zones`` + ``reach_boundaries`` + anchored samples) only
    when a ``Car`` was explicitly supplied. The first failure raises
    ``AnnotationError`` naming its stage; nothing is repaired silently.
    """
    from .route.errors import LapError, RouteError
    from .route.lap import centre_curve
    from .route.manifest import validate_route
    from .route.portals import portal_crossings
    from .route.sampling import sample_lap

    gain = _vector_legality(track_map, payload, legal_mask)
    stages = {'vector_legal': {'status': 'PASS', 'gain_m2': round(gain, 4),
                               'policy': 'within one raster cell of the '
                                         'selected legal region'}}

    def run(stage, fn):
        try:
            return fn()
        except (RouteError, LapError, ValueError) as exc:
            raise AnnotationError(f'{stage}: {exc}') from exc

    route = run('MANIFEST_VALID', lambda: validate_route(payload))
    stages['manifest'] = 'PASS'
    lap = run('LAP_CONSTRUCTED', lambda: centre_curve(route))
    stages['lap'] = 'PASS'
    run('PORTALS_VALID', lambda: portal_crossings(lap))
    stages['portals'] = 'PASS'
    samples = run('SAMPLES_READY', lambda: sample_lap(lap, 0.25))
    stages['samples'] = len(samples)
    car_info = None
    if car is not None:
        from .route.zones import portal_zones, reach_boundaries

        def car_stages():
            zones = portal_zones(route, car.reach_m)
            anchors = [q for zone in zones
                       for q in reach_boundaries(lap, zone)]
            return sample_lap(lap, 0.25, extra_anchors=anchors)
        anchored = run('VEHICLE_ZONES_READY', car_stages)
        stages['car_zones'] = 'PASS'
        stages['car_samples'] = len(anchored)
        car_info = {'name': car.name, 'reach_m': round(car.reach_m, 4),
                    'margin_m': car.margin_m}
    else:
        stages['car_zones'] = 'NOT_CHECKED (no car supplied)'
    receipt = {'route_digest': route.digest,
               'sections': len(route.sections),
               'lap_length_m': round(lap.period, 3),
               'stages': stages, 'car': car_info,
               'not_checked': list(NOT_CHECKED)}
    return route, receipt


def build_candidate(track_map, session, car=None, chain_dp_epsilon_m=None):
    """Extract, build and check the session's candidate in one place.

    The single path preview, validate and export all use (server and
    CLI alike), so the transports cannot disagree about validity.
    Returns ``(payload, route, receipt, extraction)``.
    """
    if not session.get('route_px'):
        raise AnnotationError('draw the directed route loop first')
    strokes = session.get('boundary_strokes_px', [])
    width = session.get('stroke_width_px', 5)
    retained = session.get('retained_region_px')
    extraction = extract_boundaries(track_map, strokes, width, retained)
    legal = effective_free_mask(track_map, strokes, width, retained)
    payload, info = build_route(
        track_map, extraction[0], extraction[1], session['route_px'],
        name=session.get('route_name'),
        surface=session.get('surface', DEFAULT_SURFACE),
        max_speed_mps=session.get('max_speed_mps', DEFAULT_MAX_SPEED_MPS),
        chain_dp_epsilon_m=(session.get('chain_dp_epsilon_m',
                                        DEFAULT_CHAIN_DP_EPSILON_M)
                            if chain_dp_epsilon_m is None
                            else chain_dp_epsilon_m))
    route, receipt = check_payload(payload, track_map, legal, car=car)
    receipt.update(seed_samples=info['seed_samples'],
                   max_correction_m=round(info['max_correction_m'], 4),
                   smoothing_passes=info['smoothing_passes'])
    return payload, route, receipt, extraction


def try_thinnings(track_map, session, car=None):
    """Try VALIDATE_THINNINGS in order; return (eps, candidate, attempts).

    Each attempt is a full ``build_candidate`` at that thinning. The
    first passing setting wins; the caller stores it in the session
    (it is part of the approval digest). Raises with every attempt's
    reason when none passes.
    """
    attempts = []
    for eps in VALIDATE_THINNINGS:
        try:
            candidate = build_candidate(track_map, session, car=car,
                                        chain_dp_epsilon_m=eps)
            return eps, candidate, attempts
        except Exception as exc:  # noqa: BLE001 - record and try next
            attempts.append('eps %.2f: %s' % (eps, exc))
    raise AnnotationError('no thinning passed the route checks (%s)'
                          % '; '.join(attempts))
