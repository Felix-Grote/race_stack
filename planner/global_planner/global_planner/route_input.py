"""
Strict, immutable selected directed legal-route input (schema v1).

Approval is an annotation assertion, never authenticated physical evidence.
Canonical numbers are binary64, integral values encode as integers, -0 becomes 0;
IDs are NFC strings. No unknown fields or inferred connectivity are accepted.
"""
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re
import unicodedata

from ._route_geometry import (EPS, cross, distance, inside, on_segment,
                              segments_touch, signed_area_twice, simple_polygon, sub)


class RouteError(ValueError):
    """Malformed or semantically inconsistent annotation."""


def _require(condition, message):
    if not condition:
        raise RouteError(message)


def _keys(obj, names, where):
    _require(type(obj) is dict and set(obj) == set(names.split()),
             where + ': missing/unknown fields')


def _id(value):
    _require(type(value) is str and value and value == value.strip()
             and len(value) <= 128 and not any(ord(c) < 32 for c in value), 'invalid ID/text')
    return unicodedata.normalize('NFC', value)


def _number(v):
    _require(type(v) in (int, float), 'expected number, not boolean')
    try:
        f = float(v)
    except (OverflowError, ValueError) as exc:
        raise RouteError('number outside binary64') from exc
    _require(math.isfinite(f) and abs(f) <= 1e12, 'nonfinite/out-of-range number')
    return int(f) if f.is_integer() else f


def _normalize(v):
    if type(v) is dict:
        _require(all(type(k) is str for k in v), 'object key must be string')
        keys = [_id(k) for k in v]
        _require(len(set(keys)) == len(keys), 'normalized duplicate key')
        return {k: _normalize(x) for k, x in zip(keys, v.values())}
    if type(v) is list:
        return [_normalize(x) for x in v]
    if type(v) is str:
        return _id(v)
    return _number(v)


def canonical_bytes(payload):
    """Canonical UTF-8 JSON contract for input identity (no own digest field)."""
    return json.dumps(_normalize(payload), sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode('utf-8')


def _points(v, minimum=2):
    _require(type(v) is list and len(v) >= minimum, 'invalid point chain')
    result = []
    for p in v:
        _require(type(p) is list and len(p) == 2, 'point must be XY')
        q = tuple(_number(x) for x in p)
        _require(max(abs(x) for x in q) <= 1e5, 'coordinate range exceeded')
        result.append(q)
    _require(all(distance(a, b) > EPS for a, b in zip(result, result[1:])),
             'zero-length consecutive edge')
    return tuple(result)


def _provenance(v):
    _keys(v, 'author source revision approval', 'provenance')
    for x in v.values():
        _id(x)


@dataclass(frozen=True)
class Occurrence:
    id: str
    surface_id: str
    seed: tuple
    left: tuple
    right: tuple
    caps: tuple  # (local piecewise-linear seed arclength, m/s); right-hand knots

    @property
    def polygon(self):
        return self.right + self.left[::-1]

    @property
    def length(self):
        return sum(distance(a, b) for a, b in zip(self.seed, self.seed[1:]))


@dataclass(frozen=True)
class Portal:
    id: str
    source: str
    target: str
    gate: tuple  # right -> left; cross(gate vector, travel) must be negative
    support: tuple
    before: float  # local seed metres before source end
    after: float  # local seed metres after target start


@dataclass(frozen=True)
class Route:
    occurrences: tuple
    portals: tuple
    encoded: bytes

    @property
    def digest(self):
        return hashlib.sha256(self.encoded).hexdigest()

    @property
    def payload(self):
        """Return a fresh copy; modifying it cannot mutate the validated input."""
        return json.loads(self.encoded)


def validate_route(payload):
    """Validate one complete selected cycle; return frozen geometry and identity."""
    p = _normalize(payload)
    _keys(p, 'schema_version course_id route_id frame_id units conventions physical_map '
          'provenance surfaces occurrences transitions gate_sequence finish initialization',
          'route')
    _require(type(p['schema_version']) is int and p['schema_version'] == 1, 'unsupported version')
    for k in ('course_id', 'route_id', 'frame_id'):
        _id(p[k])
    _require(p['units'] == 'm' and p['conventions'] == 'x-forward_y-left_heading-ccw',
             'unsupported units/conventions')
    _provenance(p['provenance'])
    pm = p['physical_map']
    _keys(pm, 'sha256 frame_id registration coverage provenance', 'physical_map')
    _require(type(pm['sha256']) is str and re.fullmatch('[0-9a-f]{64}', pm['sha256']), 'map hash')
    _id(pm['frame_id'])
    _require(type(pm['registration']) is list and len(pm['registration']) == 3,
             'map SE2 registration')
    for v in pm['registration']:
        _number(v)
    _require(pm['coverage'] in ('unknown', 'partial', 'complete'), 'physical coverage declaration')
    _provenance(pm['provenance'])
    _require(type(p['surfaces']) is list and len(p['surfaces']) > 0, 'surfaces required')
    surfaces = []
    for s in p['surfaces']:
        _keys(s, 'id kind provenance', 'surface')
        surfaces.append(_id(s['id']))
        _require(s['kind'] in ('planar', 'ramp', 'bridge'), 'surface kind')
        _provenance(s['provenance'])
    _require(len(set(surfaces)) == len(surfaces), 'duplicate surface')
    _require(type(p['occurrences']) is list and len(p['occurrences']) >= 2,
             'cycle needs >=2 occurrences')
    occs = []
    for o in p['occurrences']:
        _keys(o, 'id surface_id seed left right caps provenance', 'occurrence')
        _provenance(o['provenance'])
        _require(o['surface_id'] in surfaces, 'unknown surface')
        seed, left, right = (_points(o[k]) for k in ('seed', 'left', 'right'))
        poly = right + left[::-1]
        _require(simple_polygon(poly), 'invalid/simple ribbon polygon (holes unsupported)')
        _require(signed_area_twice(poly) > EPS,
                 'inconsistent left/right orientation')
        _require(on_segment(seed[0], right[0], left[0]) and
                 on_segment(seed[-1], right[-1], left[-1]), 'seed must meet directed end caps')
        _require(all(inside(x, poly) for x in seed), 'seed outside legal ribbon')
        # Seeds may meet caps, but never cross/touch a legal side or leave a concavity.
        for index, (a, b) in enumerate(zip(seed, seed[1:])):
            for c, d, allowed in ((right[0], left[0], index == 0),
                                  (right[-1], left[-1], index == len(seed) - 2)):
                if segments_touch(a, b, c, d) and not allowed:
                    raise RouteError('seed illegally recrosses ownership end cap')
            for chain in (left, right):
                _require(not any(segments_touch(a, b, c, d) for c, d in zip(chain, chain[1:])),
                         'seed intersects legal side')
            _require(inside(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2), poly), 'seed exits ribbon')
        length = sum(distance(a, b) for a, b in zip(seed, seed[1:]))
        caps = o['caps']
        _require(type(caps) is list and len(caps) > 0, 'caps required')
        parsed = []
        for cap in caps:
            _keys(cap, 'at_m max_speed_mps', 'cap')
            q, v = _number(cap['at_m']), _number(cap['max_speed_mps'])
            _require(0 <= q < length and v > 0, 'cap outside occurrence or nonpositive')
            parsed.append((q, v))
        _require(parsed[0][0] == 0 and all(a[0] < b[0] for a, b in zip(parsed, parsed[1:])),
                 'caps must start at zero and increase')
        occs.append(Occurrence(_id(o['id']), o['surface_id'], seed, left, right, tuple(parsed)))
    ids = [o.id for o in occs]
    _require(len(set(ids)) == len(ids), 'duplicate occurrence ID')
    _require(type(p['transitions']) is list and len(p['transitions']) == len(occs),
             'one portal per edge')
    portals = []
    for i, tr in enumerate(p['transitions']):
        _keys(tr, 'id from to gate support before_m after_m continuity provenance', 'transition')
        _provenance(tr['provenance'])
        a, b = occs[i], occs[(i + 1) % len(occs)]
        _require((tr['from'], tr['to']) == (a.id, b.id), 'nonconsecutive/wrong directed portal')
        _require(tr['continuity'] == 'shared_endcap', 'unsupported border continuity')
        gate, support = _points(tr['gate']), _points(tr['support'], 3)
        _require(len(gate) == 2 and simple_polygon(support), 'invalid gate/support polygon')
        _require(distance(a.seed[-1], b.seed[0]) <= EPS, 'disconnected portal seeds')
        _require(all(distance(x, y) <= EPS for x, y in
                     ((gate[0], a.right[-1]), (gate[1], a.left[-1]),
                      (gate[0], b.right[0]), (gate[1], b.left[0]))), 'invalid portal end caps')
        travel = sub(b.seed[1], a.seed[-2])
        _require(cross(sub(gate[1], gate[0]), travel) < -EPS, 'wrong directed gate')
        _require(inside(a.seed[-1], support, False) and all(inside(x, support) for x in gate),
                 'gate not covered by portal support')
        before, after = _number(tr['before_m']), _number(tr['after_m'])
        _require(0 < before < a.length and 0 < after < b.length, 'invalid portal support progress')
        portals.append(Portal(_id(tr['id']), a.id, b.id, gate, support, before, after))
    pids = [x.id for x in portals]
    _require(len(set(pids)) == len(pids), 'duplicate portal ID')
    _require(p['gate_sequence'] == pids, 'gate sequencing must follow selected cycle')
    _require(p['finish'] == pids[-1], 'finish must be closing gate at seam')
    init = p['initialization']
    _keys(init, 'occurrence_id seed_interval_m zone heading_interval_rad', 'initialization')
    _require(init['occurrence_id'] == ids[0], 'initial occurrence must be route origin')
    bracket, heading = init['seed_interval_m'], init['heading_interval_rad']
    _require(type(bracket) is list and type(heading) is list, 'invalid initial interval types')
    bracket, heading = ([_number(x) for x in values] for values in (bracket, heading))
    _require(type(bracket) is list and len(bracket) == 2 and
             0 <= bracket[0] < bracket[1] <= occs[0].length, 'initial seed interval')
    _require(type(heading) is list and len(heading) == 2 and
             -math.pi <= heading[0] < heading[1] <= math.pi, 'initial heading interval')
    zone = _points(init['zone'], 3)
    _require(simple_polygon(zone), 'invalid initialization zone')
    return Route(tuple(occs), tuple(portals), canonical_bytes(p))


def load_route(path):
    """Read strict UTF-8 JSON, rejecting duplicate keys before normalization."""
    def pairs(items):
        result = {}
        for k, v in items:
            _require(k not in result, 'duplicate JSON key: ' + k)
            result[k] = v
        return result

    def invalid(value):
        raise RouteError('nonfinite JSON number: ' + value)

    try:
        payload = json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=pairs,
                             parse_constant=invalid)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise RouteError('invalid UTF-8 JSON') from exc
    return validate_route(payload)
