"""A03 original-border, directed-ownership and monotone-lineage adversaries."""
from dataclasses import replace
import json
import math
from pathlib import Path

import numpy as np
import pytest

from global_planner.route_corridor import (CorridorError, OrderedCurve, _normal_geometry,
                                           normal_interval, portal_crossings, prepare_route,
                                           refit_ordered, resample_ordered, seed_curve)
from global_planner.route_input import Occurrence, load_route, validate_route
from global_planner.route_reference import Curve

FIX = Path(__file__).parent / 'fixtures' / 'project_a'


def route(name='s0_route'):
    return load_route(FIX / (name + '.json'))


@pytest.mark.parametrize('name', ['s0_route', 's0_reverse_route', 's0_rotated_route',
                                  's2_upper_route', 's2_lower_route', 's3_surfaces_route'])
def test_all_fixed_routes(name):
    p = prepare_route(route(name), spacing=.4)
    assert len(p.samples) == len(p.reftrack) == len(p.corridors)
    assert all(c.left > 0 and c.right > 0 for c in p.corridors)
    assert all(a.q < b.q for a, b in zip(p.samples, p.samples[1:]))
    assert {c.occurrence_id for c in p.corridors} == {'o0', 'o1', 'o2', 'o3'}
    assert [g[0] for g in p.gates] == p.ordered.route.payload['gate_sequence']
    for v, c, row, nr in zip(p.samples, p.corridors, p.reftrack, p.normals_right):
        assert row == v.xy + (c.right, c.left)
        assert nr == (v.tangent[1], -v.tangent[0])
        assert c.lower == -c.right and c.upper == c.left
        assert c.occurrence_id in c.support_occurrences
        if c.portal_id:
            assert len(c.support_occurrences) == 2
        else:
            assert len(c.support_occurrences) == 1
    if name.startswith('s0'):
        # Original polyline borders, not the fitted circle's inferred radius.
        # Reversal swaps the directed widths.
        expected_left, expected_right = (.9, .7) if 'reverse' in name else (.7, .9)
        for v, c in zip(p.samples, p.corridors):
            assert c.left <= expected_left + .003
            assert c.right <= expected_right + .003
            assert c.left > expected_left - .005
            assert c.right > expected_right - .005
            assert math.copysign(1, v.curvature) == (-1 if 'reverse' in name else 1)


def test_nonuniform_resampling_q_caps_and_refit():
    raw = route().payload
    raw['occurrences'][0]['caps'].append({'at_m': 1.2345, 'max_speed_mps': 1.7})
    r = validate_route(raw)
    original = seed_curve(r)
    samples = resample_ordered(original, .37)
    assert any(abs(v.q - 1.2345) < 1e-9 and v.cap_mps == 1.7 for v in samples)
    rebuilt = refit_ordered(original, samples, [v.xy for v in samples])
    again = resample_ordered(rebuilt, .23)
    for v in samples:
        assert original.progress(v.segment, v.t) == pytest.approx(v.q, abs=1e-12)
    for v in again:
        assert rebuilt.progress(v.segment, v.t) == pytest.approx(v.q, abs=1e-12)
        assert v.q >= 0
    assert any(abs(v.q - 1.2345) < 1e-9 and v.cap_mps == 1.7 for v in again)
    prepare_route(r, ordered=rebuilt, spacing=.37)
    bad = list(samples)
    bad[2] = replace(bad[2], q=bad[1].q)
    with pytest.raises(CorridorError):
        refit_ordered(original, bad, [v.xy for v in bad])
    q = list(original.q)
    q[3] = q[2]
    with pytest.raises(CorridorError):
        OrderedCurve(r, original.curve, tuple(q))


def test_crossing_surfaces_do_not_share_widths_or_ownership():
    r = route('s3_surfaces_route')
    o = seed_curve(r)
    # Crossing lies at the middle of occurrence 0 and 2: exactly same XY.
    qs = []
    for i in (0, 2):
        seed = r.occurrences[i].seed
        local = sum(math.dist(a, b) for a, b in zip(seed[:16], seed[1:17]))
        qs.append(sum(x.length for x in r.occurrences[:i]) + local)
    from global_planner.route_corridor import _sample
    a, b = [_sample(o, o.station_at_q(q)) for q in qs]
    assert a.xy == pytest.approx(b.xy, abs=1e-12)
    ca, cb = normal_interval(o, a), normal_interval(o, b)
    assert (ca.occurrence_id, ca.surface_id) == ('o0', 'ground')
    assert (cb.occurrence_id, cb.surface_id) == ('o2', 'upper-deck')
    assert ca.right > cb.right + .1
    assert ca.support_occurrences == ('o0',) and cb.support_occurrences == ('o2',)
    with pytest.raises(CorridorError):
        normal_interval(o, replace(a, occurrence_id='o2', surface_id='upper-deck'))
    owners = list(o.curve.owners)
    owners[0] = ('o2', 'upper-deck')
    with pytest.raises(CorridorError):
        OrderedCurve(r, Curve(o.curve.coefficients, owners), o.q)


def test_analytic_rectangle_notch_rotated_normal_and_disconnected_intervals():
    # Independent straight-strip analytic oracle, with a narrow notch only on left.
    occ = Occurrence('strip', 'ground', ((0, 0), (10, 0)),
                     ((0, 2), (4.9, 2), (4.9, .4), (5.1, .4), (5.1, 2), (10, 2)),
                     ((0, -1), (10, -1)), ((0, 4),))
    assert _normal_geometry((occ,), (5, 0), (1, 0)) == pytest.approx((-1, .4), abs=2e-9)
    lo, hi = _normal_geometry((occ,), (3, 0), (math.cos(.3), math.sin(.3)))
    assert lo == pytest.approx(-1 / math.cos(.3), abs=2e-9)
    assert hi == pytest.approx(2 / math.cos(.3), abs=2e-9)
    # A concave ribbon whose normal has two legal components: retain only one.
    folded = Occurrence('concave', 'ground', ((0, 0), (4, 0)),
                        ((0, 1), (1, 1), (1, 3), (3, 3), (3, 1), (4, 1)),
                        ((0, -1), (4, -1)), ((0, 4),))
    lo, hi = _normal_geometry((folded,), (2, 0), (1, 0))
    assert (lo, hi) == pytest.approx((-1, 3), abs=2e-9)
    # Disconnected extra region cannot bridge a gap even when explicitly listed.
    second = Occurrence('extra', 'other', ((0, 4), (4, 4)),
                        ((0, 5), (4, 5)), ((0, 3), (4, 3)), ((0, 4),))
    straight = replace(occ, left=((0, 1), (10, 1)))
    lo, hi = _normal_geometry((straight, second), (2, 0), (1, 0),
                              support=((-1, -2), (11, -2), (11, 6), (-1, 6)))
    assert (lo, hi) == pytest.approx((-1, 1), abs=2e-9)
    with pytest.raises(CorridorError):
        _normal_geometry((occ,), (5, 1), (1, 0))  # outside notch, no nearest repair
    with pytest.raises(CorridorError):
        _normal_geometry((occ,), (.01, 0), (0, 1))  # cap-parallel invalid local chart


def test_physical_wall_gap_does_not_inflate_legal_bounds():
    r = route()
    raw = r.payload
    raw['physical_map']['coverage'] = 'partial'
    raw['physical_map']['sha256'] = 'f' * 64
    p, q = prepare_route(r, .5), prepare_route(validate_route(raw), .5)
    assert p.reftrack == q.reftrack


def test_illegal_portals_offroute_fold_and_no_inflation():
    o = seed_curve(route())
    samples = resample_ordered(o, .4)
    bad = [list(v.xy) for v in samples]
    bad[10][0] *= 2
    bad[10][1] *= 2
    shifted = refit_ordered(o, samples, bad)
    with pytest.raises(CorridorError):
        prepare_route(o.route, ordered=shifted, spacing=.2)
    # Declared support cannot authorize more than the original legal polygons.
    raw = o.route.payload
    raw['transitions'][0]['support'] = [[-100, -100], [100, -100], [100, 100], [-100, 100]]
    big = prepare_route(validate_route(raw), .4)
    assert max(c.left for c in big.corridors) < .71
    # Full width violates the local curvature chart: reject, never shrink to pass.
    from global_planner.route_corridor import _sample
    v = _sample(o, 2.)
    sharp = replace(v, curvature=100.)
    with pytest.raises(CorridorError):
        normal_interval(o, sharp)  # stale/corrupt frame is rejected too
    from global_planner.route_reference import NumericPolicy
    small = seed_curve(o.route, NumericPolicy())
    with pytest.raises(CorridorError):
        normal_interval(small, _sample(small, 2.), chart_min=.99)
    raw = o.route.payload
    raw['transitions'][0]['before_m'] = 9.2
    raw['transitions'][-1]['after_m'] = 9.2
    with pytest.raises(CorridorError):
        seed_curve(validate_route(raw))
    # A geometry shifted within the ribbon must still pass the declared gate.
    shifted_xy = [tuple(np.array(v.xy) * .94) for v in samples]
    legal_shift = refit_ordered(o, samples, shifted_xy)
    assert len(portal_crossings(legal_shift)) == 4
    with pytest.raises(CorridorError):
        resample_ordered(o, 1e-12)


def test_repeatability_report():
    p = prepare_route(route('s3_surfaces_route'), .4)
    q = prepare_route(route('s3_surfaces_route'), .4)
    assert p.reftrack == q.reftrack
    assert p.gates == q.gates
    Path('/work/a03-metrics.json').write_text(json.dumps({
        'route_sha256': p.ordered.route.digest, 'samples': len(p.samples),
        'seed_period_m': p.ordered.period, 'curve_length_m': p.ordered.curve.length,
        'min_left_m': min(c.left for c in p.corridors),
        'min_right_m': min(c.right for c in p.corridors),
        'gates': p.gates, 'repeatable': True, 'numerical_inward_allowance_m': 1e-9,
        'chart_jacobian_min_required': .05, 'scope': 'GEOMETRIC_PREPARATION_ONLY',
    }, indent=2))


def test_s3_notch_is_owned_and_survives_repeated_resampling():
    from global_planner.route_corridor import _sample
    r = route('s3_notch_route')
    o = seed_curve(r)
    notch_q = r.occurrences[0].caps[1][0]
    v = _sample(o, o.station_at_q(notch_q))
    c = normal_interval(o, v)
    # Independent 2x2 ray/edge solves against the actual fitted normal. The
    # analytic generating normal differs slightly from the interpolant normal.
    n = np.array([-v.tangent[1], v.tangent[0]])
    hits = []
    for a, b in zip(r.occurrences[0].left, r.occurrences[0].left[1:]):
        matrix = np.column_stack((n, np.array(a) - np.array(b)))
        if abs(np.linalg.det(matrix)) > 1e-10:
            alpha, t = np.linalg.solve(matrix, np.array(a) - np.array(v.xy))
            if alpha > 0 and 0 <= t <= 1:
                hits.append(alpha)
    assert c.left == pytest.approx(min(hits), abs=2e-9)
    assert c.left == pytest.approx(.18, abs=1e-6)  # separate interpolation error
    p = prepare_route(r, .37)
    assert any(abs(v.q - notch_q) < 1e-9 and c.left < .181
               for v, c in zip(p.samples, p.corridors))
    shifted = refit_ordered(o, p.samples, [v.xy for v in p.samples])
    again = prepare_route(r, .29, ordered=shifted)
    assert any(abs(v.q - notch_q) < 1e-9 and c.left < .181
               for v, c in zip(again.samples, again.corridors))
    # The other deck still has its original wider left border.
    assert min(c.left for c in again.corridors if c.occurrence_id == 'o2') > .3


def test_actual_folded_chart_and_gate_failures():
    raw = route().payload
    for o in raw['occurrences']:
        o['left'] = [[x * .01 / 5.3, y * .01 / 5.3] for x, y in o['left']]
    for i, t in enumerate(raw['transitions']):
        t['gate'][1] = raw['occurrences'][i]['left'][-1]
        t['support'] = [[-100, -100], [100, -100], [100, 100], [-100, 100]]
    with pytest.raises(CorridorError, match='folded/degenerate'):
        prepare_route(validate_route(raw), .4)
    o = seed_curve(route())
    samples = resample_ordered(o, .05)
    missing = refit_ordered(o, samples, [tuple(np.array(v.xy) * .5) for v in samples])
    with pytest.raises(CorridorError, match='missing/ambiguous'):
        portal_crossings(missing)
    gate_q = o.route.occurrences[0].length
    xy = []
    for v in samples:
        d = v.q - gate_q
        xy.append((.08 * math.sin(35 * d), 6 + .2 * d) if abs(d) < .3 else v.xy)
    oscillating = refit_ordered(o, samples, xy)
    with pytest.raises(CorridorError, match='reverse|ambiguous'):
        portal_crossings(oscillating)


def test_chart_pair_budget_is_fail_closed():
    with pytest.raises(CorridorError, match='pair budget'):
        prepare_route(route(), .4, chart_pair_budget=1)


def test_tangent_gate_roots_cannot_hide_as_complex_pairs():
    from global_planner.route_corridor import _gate_parameters
    from global_planner.route_reference import CubicSegment
    # y=(t-.25)^2*(t-.75): double contact and one genuine crossing.
    f = np.polynomial.polynomial.polymul([-.25, 1], [-.25, 1])
    f = np.polynomial.polynomial.polymul(f, [-.75, 1])
    segment = CubicSegment(((0, 1, 0, 0), tuple(f)))
    try:
        roots = _gate_parameters(segment, ((-1, 0), (2, 0)))
    except CorridorError as exc:
        assert 'tangent' in str(exc)
    else:
        assert any(abs(t - .25) < 1e-7 for t in roots)
        # Portal passage will reject this zero directed derivative, even if
        # the cubic root solver omitted the double root itself.
        t = min(roots, key=lambda t: abs(t - .25))
        assert abs(segment.evaluate(t, 1)[1]) < 1e-8


def test_identical_xy_heading_visits_stay_distinct():
    import copy
    raw = route().payload
    more = copy.deepcopy(raw['occurrences'])
    for o in more:
        o['id'] = 'repeat-' + o['id']
    raw['occurrences'] += more
    more_transitions = copy.deepcopy(raw['transitions'])
    raw['transitions'][-1]['to'] = 'repeat-o0'
    for t in more_transitions:
        t['id'] = 'repeat-' + t['id']
        t['from'] = 'repeat-' + t['from']
        t['to'] = 'repeat-' + t['to']
    more_transitions[-1]['to'] = 'o0'
    raw['transitions'] += more_transitions
    raw['gate_sequence'] = [t['id'] for t in raw['transitions']]
    raw['finish'] = raw['gate_sequence'][-1]
    o = seed_curve(validate_route(raw))
    a, b = o.curve.sample(.5), o.curve.sample(o.curve.length / 2 + .5)
    assert a.xy == pytest.approx(b.xy, abs=1e-8)
    assert a.heading == pytest.approx(b.heading, abs=1e-8)
    assert (a.occurrence_id, b.occurrence_id) == ('o0', 'repeat-o0')
    assert len(prepare_route(o.route, .5).gates) == 8


def test_gate_endpoint_contact_is_ambiguous():
    o = seed_curve(route())
    coefficients = np.asarray(o.curve.coefficients) * (5.3 / 6)
    endpoint_curve = OrderedCurve(o.route, Curve(coefficients, o.curve.owners), o.q)
    with pytest.raises(CorridorError, match='endpoint'):
        portal_crossings(endpoint_curve)
