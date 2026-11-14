"""
Read a manifest into a validated, immutable Route.

1. structure:   fields, types, ranges and text rules against manifest.schema.json.
2. geometry:    walls, centrelines, gates, section contacts and starting zone, checked here.

Section i's portal joins it to section i + 1; the last portal closes the lap.
A portal's gate is the section's end cap, from right wall to left wall.
"""
from collections import Counter
import hashlib
from itertools import combinations
import json
from pathlib import Path
import reprlib
from typing import NoReturn

from jsonschema import Draft7Validator
from jsonschema.exceptions import best_match
import shapely
from shapely.geometry import LinearRing, LineString, Polygon
from shapely.ops import unary_union

from .centreline import centreline
from .errors import require, RouteError
from .geometry import (Chain, chains_touch, counterclockwise, covers, cross, distance, EPS,
                       outline, simple_polygon, sub)
from .track import Portal, Route, Section, Start

# Walls closer than EPS for longer than this count as a shared wall.
_SHARED_WALL_M = 1e-3

_SCHEMA = json.loads(Path(__file__).with_name('manifest.schema.json').read_text())
Draft7Validator.check_schema(_SCHEMA)
_VALIDATOR = Draft7Validator(_SCHEMA)


def _check_structure(payload: object) -> None:
    """Check fields, types, ranges and text rules against the schema."""
    error = best_match(_VALIDATOR.iter_errors(payload))
    if error is None:
        return

    where = '/'.join(str(x) for x in error.absolute_path) or 'manifest'
    # A definition's message states its rules in words, instead of jsonschema's raw regex.
    rules = error.schema.get('message')
    message = f'{reprlib.repr(error.instance)} {rules}' if rules else error.message[:200]

    raise RouteError(f'{where}: {message}')


def _points(value: list, what: str) -> Chain:
    """Return the points of what as tuples; consecutive points must differ."""
    points = tuple(tuple(p) for p in value)
    require(all(distance(a, b) > EPS for a, b in zip(points, points[1:])),
            f'{what}: two consecutive points coincide')

    return points


def _centreline(uid: str, left: Chain, right: Chain, polygon: Chain) -> Chain:
    """Derive the section's centreline and check it runs inside, clear of both walls."""
    try:
        line = centreline(left, right)
    except ValueError as exc:
        raise RouteError(f'section {uid}: {exc}') from exc

    require(not chains_touch(line, left) and not chains_touch(line, right),
            f'section {uid} narrows to zero width')
    require(covers(polygon, line), f'centreline of section {uid} leaves the section')

    return line


def _snap_caps(walls: list[tuple[Chain, Chain]]) -> list[tuple[Chain, Chain]]:
    """
    Snap each section's start cap onto the previous section's end cap.

    One cap is stored twice, as the end of one section and the start of the next. Copies
    within EPS are the same cap; making them identical lets the two section outlines share
    the edge exactly, which shapely needs to glue them. Mismatches beyond EPS are left for
    _portal to reject.
    """
    snapped = [list(w) for w in walls]
    for i in range(len(walls)):
        target = snapped[(i + 1) % len(walls)]
        for side in (0, 1):
            end = walls[i][side][-1]
            if distance(end, target[side][0]) <= EPS:
                target[side] = (end,) + target[side][1:]

    return [tuple(w) for w in snapped]


def _section(value: dict, left: Chain, right: Chain) -> Section:
    """Build one section from its walls, checking its outline and its centreline."""
    polygon = outline(left, right)
    require(simple_polygon(polygon), f'section {value["uid"]}: its walls cross or touch')
    require(counterclockwise(polygon), f'section {value["uid"]}: left and right walls are swapped')
    line = _centreline(value['uid'], left, right, polygon)

    return Section(value['uid'], value['surface'], line, left, right, value['max_speed_mps'])


def _portal(source: Section, target: Section) -> Portal:
    """Return the portal from source into target, checking the shared cap and its direction."""
    gate = (source.right[-1], source.left[-1])
    require(distance(gate[0], target.right[0]) <= EPS and distance(gate[1], target.left[0]) <= EPS,
            f'sections {source.uid} and {target.uid} do not share their cap')

    # Dividing by the gate length makes the cross product a distance, comparable with EPS.
    travel = sub(target.centreline[1], source.centreline[-2])
    require(cross(sub(gate[1], gate[0]), travel) / distance(*gate) < -EPS,
            f'section {target.uid} does not continue forward from {source.uid}')

    return Portal(f'{source.uid}_to_{target.uid}', source.uid, target.uid, gate)


def _check_neighbours(a: Section, b: Section) -> None:
    """Check that neighbours glued at their gate neither overlap nor enclose a gap."""
    areas = (Polygon(a.polygon), Polygon(b.polygon))
    require(areas[0].intersection(areas[1]).area <= EPS ** 2,
            f'sections {a.uid} and {b.uid} overlap beyond their gate; redraw the cut between '
            f'them, or, where the road crosses itself, put the two passes in sections that are '
            f'not neighbours')

    # Walls within EPS count as touching, so grow both by EPS / 2 before looking for a gap.
    grown = unary_union([g.buffer(EPS / 2) for g in areas])
    holes = [h for part in shapely.get_parts(grown) for h in part.interiors]
    if holes:
        x, y = Polygon(holes[0]).representative_point().coords[0]
        raise RouteError(f'sections {a.uid} and {b.uid} also touch away from their gate, '
                         f'around a gap at ({x:.2f}, {y:.2f}); move one wall off the other')


def _check_section_contacts(sections: list[Section], portals: list[Portal]) -> None:
    """
    Check that sections meet only at their gates.

    shared walls:   two sections may cross at points (a bridge over the road), but their
                    walls must not run within EPS of each other for more than
                    _SHARED_WALL_M; a barrier between them needs a thickness.
    neighbours:     glued together at their gate, so their areas must not overlap, which
                    would dissolve a wall, nor touch elsewhere around a gap, which would
                    turn the gap into road.
    """
    n = len(sections)
    rings = [LinearRing(s.polygon) for s in sections]
    gates = {frozenset((i, (i + 1) % n)): LineString(p.gate) for i, p in enumerate(portals)}

    for i, j in combinations(range(n), 2):
        if rings[i].envelope.distance(rings[j].envelope) > EPS:
            continue

        gate = gates.get(frozenset((i, j)))
        shared = rings[i].intersection(rings[j].buffer(EPS))
        if gate is not None:
            shared = shared.difference(gate.buffer(EPS))

        if shared.length > _SHARED_WALL_M:
            part = max(shapely.get_parts(shapely.line_merge(shared)), key=lambda g: g.length)
            (x0, y0), (x1, y1) = part.coords[0], part.coords[-1]
            raise RouteError(f'sections {sections[i].uid} and {sections[j].uid} share '
                             f'{shared.length:.2f} m of wall, from ({x0:.2f}, {y0:.2f}) to '
                             f'({x1:.2f}, {y1:.2f}); a barrier between sections needs a '
                             f'thickness: move one of the two walls off the other')

        if gate is not None:
            _check_neighbours(sections[i], sections[j])


def _start(value: dict) -> Start:
    """Check the start zone and heading range."""
    heading = value['heading_range_rad']
    require(heading[0] < heading[1], 'start heading range must run from a smaller to a larger '
            'angle')

    zone = _points(value['zone'], 'start zone')
    require(simple_polygon(zone), 'start zone must be a polygon with an area that does not '
            'cross itself')

    return Start(zone, tuple(heading))


def validate_route(payload: object) -> Route:
    """Validate one complete closed lap; return its frozen geometry and identity."""
    _check_structure(payload)

    try:
        text = json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False)
    except ValueError as exc:
        raise RouteError('manifest contains NaN or infinity') from exc

    digest = hashlib.sha256(text.encode('utf-8')).hexdigest()

    # With two sections, gluing neighbours at both shared caps closes a ring
    # around the infield, which the independent checker cannot represent.
    require(len(payload['sections']) >= 3, 'a route needs at least 3 sections')
    counts = Counter(v['uid'] for v in payload['sections'])
    repeated = sorted(u for u, n in counts.items() if n > 1)
    require(not repeated, 'duplicate section uid: ' + ', '.join(repeated))

    walls = _snap_caps([(_points(v['left'], f'section {v["uid"]} left wall'),
                         _points(v['right'], f'section {v["uid"]} right wall'))
                        for v in payload['sections']])
    sections = [_section(v, left, right) for v, (left, right) in zip(payload['sections'], walls)]

    # Each section's end cap is the gate into the next; the last closes the lap.
    portals = [_portal(sections[i], sections[(i + 1) % len(sections)])
               for i in range(len(sections))]
    named = {}
    for portal in portals:
        other = named.setdefault(portal.uid, portal)
        require(other is portal,
                f'portals {other.source} -> {other.target} and {portal.source} -> '
                f'{portal.target} would both be called {portal.uid}; rename a section')

    _check_section_contacts(sections, portals)

    start = _start(payload['start'])

    return Route(tuple(sections), tuple(portals), start, digest)


def load_route(path: str | Path) -> Route:
    """Read strict UTF-8 JSON, rejecting duplicate keys, then validate it."""
    def pairs(items: list[tuple[str, object]]) -> dict:
        result = {}
        for k, v in items:
            require(k not in result, 'duplicate JSON key: ' + k)
            result[k] = v

        return result

    def invalid(value: str) -> NoReturn:
        raise RouteError('nonfinite JSON number: ' + value)

    try:
        payload = json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=pairs,
                             parse_constant=invalid)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise RouteError('invalid UTF-8 JSON') from exc

    return validate_route(payload)
