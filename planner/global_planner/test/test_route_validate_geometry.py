"""A05 actual candidate certificates and independent false-positive controls."""
from dataclasses import asdict, replace
from fractions import Fraction
import copy
import gzip
import hashlib
import json
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

from global_planner.route_corridor import OrderedCurve
from global_planner.route_input import load_route, validate_route
from global_planner.route_reference import Curve, NumericPolicy
import global_planner.route_validate as validator
from global_planner.route_validate import (
    Footprint, GeometryValidationPolicy, interval_bounds, validate_geometry)

FIX = Path(__file__).parent / 'fixtures' / 'project_a'
BODY = Footprint(front_m=.10, rear_m=.10, width_m=.12, margin_m=.01)
NAMES = ('s0_route', 's0_reverse_route', 's0_rotated_route', 's2_upper_route',
         's2_lower_route', 's3_surfaces_route', 's3_notch_route')


@pytest.fixture(scope='module')
def candidates():
    frozen = (FIX / 'w2_a04_candidates.json.gz').read_bytes()
    assert hashlib.sha256(frozen).hexdigest() == (
        '2a506953026b75fc5be4defb1b018577faa46cebdbdfcd767c0103e733b2279b')
    evidence = json.loads(gzip.decompress(frozen))
    assert evidence['source_commit'] == '604ad5da4cefd2ce5f052a4e71d30d5b5467bd27'
    values = {}
    for name in NAMES:
        route = load_route(FIX / (name + '.json'))
        record = evidence['candidates'][name]
        assert record['fixture_sha256'] == route.digest
        values[name] = OrderedCurve(
            route, Curve(record['coefficients'], record['owners']), record['q'])
    return values


@pytest.fixture(scope='module')
def reports(candidates):
    result = {name: validate_geometry(candidate, candidate.route, BODY)
              for name, candidate in candidates.items()}
    Path('/work/a05-geometry.json').write_text(json.dumps({
        'scope': 'SYNTHETIC PLANAR SOFTWARE ONLY; no physical evidence',
        'footprint': asdict(BODY), 'validation_policy': asdict(GeometryValidationPolicy()),
        'reports': {name: asdict(value) for name, value in result.items()},
    }, indent=2, allow_nan=False))
    return result


@pytest.mark.parametrize('name', NAMES)
def test_actual_whole_lap_candidates_have_independent_swept_certificates(
        name, candidates, reports):
    candidate, report = candidates[name], reports[name]
    assert report.status == 'PASS', (name, report.reason, report.offending_interval)
    assert report.route_sha256 == candidate.route.digest
    assert report.coefficients_sha256
    assert len(report.gates) == len(candidate.route.portals)
    assert {c.occurrence_id for c in report.intervals} == {
        o.id for o in candidate.route.occurrences}
    assert {c.segment for c in report.intervals} == set(range(len(candidate.curve.segments)))
    for i in range(len(candidate.curve.segments)):
        leaves = sorted((Fraction(*c.exact_t0), Fraction(*c.exact_t1))
                        for c in report.intervals if c.segment == i)
        assert leaves[0][0] == 0 and leaves[-1][1] == 1
        assert all(a[1] == b[0] for a, b in zip(leaves, leaves[1:]))
    assert all(c.clearance_lower_m >
               c.displacement_upper_m + c.required_margin_m + c.numeric_error_m
               for c in report.intervals)
    assert all(c.curvature_upper <= 1. and c.speed_lower > 1e-7 for c in report.intervals)
    assert all(g.signed_direction_upper < -1e-9 for g in report.gates)
    assert any(c.portal_id for c in report.intervals)
    assert 'no physical obstacle/contact/3D/tracking certificate' in report.assumptions


def test_disconnected_projected_crossing_preserves_occurrence_surface_authority(
        candidates, reports):
    candidate, report = candidates['s3_notch_route'], reports['s3_notch_route']
    assert report.status == 'PASS'
    for c in report.intervals:
        owner = candidate.curve.owners[c.segment]
        assert owner[0] == c.occurrence_id
        if owner[0] == 'o2':
            assert owner[1] == 'upper-deck'
    # No global XY normal/nearest-border source is called by the validator.
    assert {g.portal_id for g in report.gates} == {'p0', 'p1', 'p2', 'p3'}


def _fake(candidate, **changes):
    values = dict(route=candidate.route, curve=candidate.curve, q=candidate.q)
    values.update(changes)
    return SimpleNamespace(**values)


def test_solver_flags_widths_and_untrusted_metadata_cannot_authorize_acceptance(
        candidates, reports):
    base = candidates['s0_route']
    poisoned = _fake(base)
    poisoned.success = False
    poisoned.corridors = ((float('inf'), -1e30),)
    poisoned.heading = (float('nan'),)
    poisoned.curvature = (0.,)
    actual = validate_geometry(poisoned, base.route, BODY)
    assert actual == reports['s0_route']


def test_forged_route_record_retaining_canonical_digest_is_rejected(candidates):
    base = candidates['s0_route']
    occurrence = replace(base.route.occurrences[0], surface_id='forged-deck')
    forged = replace(base.route, occurrences=(occurrence,) + base.route.occurrences[1:])
    assert forged.digest == base.route.digest
    for candidate, approved in ((_fake(base, route=forged), base.route), (base, forged)):
        report = validate_geometry(candidate, approved, BODY)
        assert report.status == 'FAIL' and 'authority' in report.reason


def test_stale_curve_metadata_and_relaxed_candidate_numeric_policy_are_rejected(candidates):
    base = candidates['s0_route']
    corrupt = copy.deepcopy(base.curve)
    object.__setattr__(corrupt, 'cumulative', tuple(x * 2 for x in corrupt.cumulative))
    assert validate_geometry(_fake(base, curve=corrupt), base.route, BODY).status == 'FAIL'
    relaxed = copy.deepcopy(base.curve)
    object.__setattr__(relaxed, 'policy', replace(NumericPolicy(), join_abs=10.))
    report = validate_geometry(_fake(base, curve=relaxed), base.route, BODY)
    assert report.status == 'FAIL' and 'policy' in report.reason


@pytest.mark.parametrize('kind', ['period', 'boundary', 'owner', 'surface'])
def test_corrupt_q_and_declared_owners_fail_independently(kind, candidates):
    base = candidates['s0_route']
    if kind in ('period', 'boundary'):
        q = list(base.q)
        index = len(q) - 1 if kind == 'period' else next(
            i for i in range(1, len(base.curve.owners))
            if base.curve.owners[i] != base.curve.owners[i - 1])
        q[index] = math.nextafter(q[index], math.inf)
        bad = _fake(base, q=q)
    else:
        curve = copy.deepcopy(base.curve)
        owners = list(curve.owners)
        owners[0] = ('o2', owners[0][1]) if kind == 'owner' else (owners[0][0], 'other-deck')
        object.__setattr__(curve, 'owners', tuple(owners))
        bad = _fake(base, curve=curve)
    report = validate_geometry(bad, base.route, BODY)
    assert report.status == 'FAIL' and ('q lineage' in report.reason or 'owner' in report.reason)


@pytest.mark.parametrize('kind', ['seam', 'zero_derivative', 'join'])
def test_exact_coefficients_reconstructed_instead_of_trusting_existing_curve(kind, candidates):
    base = candidates['s0_route']
    coefficients = [[list(row) for row in c] for c in base.curve.coefficients]
    if kind == 'seam':
        coefficients[0][0][0] += .05
    elif kind == 'zero_derivative':
        for row in coefficients[0]:
            row[1:] = [0., 0., 0.]
    else:
        coefficients[3][0][2] += .1
    forged_curve = SimpleNamespace(
        coefficients=coefficients, owners=base.curve.owners,
        policy=base.curve.policy, segments=base.curve.segments)
    report = validate_geometry(_fake(base, curve=forged_curve), base.route, BODY)
    assert report.status in ('FAIL', 'INCONCLUSIVE')
    assert 'coefficient reconstruction' in report.reason


@pytest.mark.parametrize('policy', [
    GeometryValidationPolicy(max_intervals=0), GeometryValidationPolicy(max_gate_boxes=0),
    GeometryValidationPolicy(max_segments=0), GeometryValidationPolicy(max_route_bytes=1),
    GeometryValidationPolicy(max_polygon_vertices=0),
])
def test_all_resource_exhaustion_is_explicitly_inconclusive(policy, candidates):
    base = candidates['s0_route']
    report = validate_geometry(base, base.route, BODY, policy)
    assert report.status == 'INCONCLUSIVE' and 'budget' in report.reason


def test_required_physical_coverage_cannot_be_invented(candidates):
    base = candidates['s0_route']
    report = validate_geometry(
        base, base.route, BODY, GeometryValidationPolicy(require_physical_coverage=True))
    assert report.status == 'INCONCLUSIVE' and 'physical' in report.reason


def test_actual_rectangle_overhang_and_independent_curvature_limit_reject(candidates):
    base = candidates['s0_route']
    overhang = validate_geometry(base, base.route, Footprint(4., 4., .12, .01))
    assert overhang.status == 'FAIL' and 'rectangle' in overhang.reason
    curvature = validate_geometry(
        base, base.route, BODY, GeometryValidationPolicy(max_curvature=.01))
    assert curvature.status == 'FAIL' and 'interior curvature' in curvature.reason


def test_full_rectangle_edges_are_checked_when_all_four_corners_are_inside():
    p = validator._point
    polygon = tuple(map(p, ((0, 0), (4, 0), (4, 4), (2.1, 4),
                            (2.1, 1), (1.9, 1), (1.9, 4), (0, 4))))
    rectangle = tuple(map(p, ((.5, .5), (3.5, .5), (3.5, 3.5), (.5, 3.5))))
    assert validator._simple(polygon)
    assert all(validator._inside(corner, polygon) for corner in rectangle)
    assert validator._rectangle_clearance2(rectangle, polygon) is None


def test_tiny_narrow_notch_between_legal_cubic_endpoints_is_not_sampling_evidence():
    p = validator._point
    # Both endpoints and any mesh omitting the 20-micrometre notch are legal.
    polygon = tuple(map(p, ((-.1, -1), (1.1, -1), (1.1, 1), (.50001, 1),
                            (.50001, -.01), (.49999, -.01), (.49999, 1), (-.1, 1))))
    coefficient = validator._coefficient_records(((0, 1, 0, 0), (0, 0, 0, 0)))
    assert all(validator._inside(validator._position(coefficient, Fraction(t)), polygon)
               for t in (0, 1))
    assert not validator._inside(validator._position(coefficient, Fraction(1, 2)), polygon)
    bounds = interval_bounds(coefficient)
    assert bounds.speed_upper >= 1
    assert validator._point_clearance2(
        validator._position(coefficient, Fraction(1, 2)), polygon) is None


def test_bernstein_root_isolation_keeps_distinct_very_close_extra_crossings():
    f = Fraction
    delta = f(1, 2 ** 36)  # closer than the 1e-8 metric query tolerance
    pair = validator._multiply((-f(1, 2) - delta, f(1)), (-f(1, 2), f(1)))
    poly = validator._multiply(pair, (-f(1, 2) + delta, f(1)))
    roots = validator._root_intervals(poly, (f(1, 2),), f(1), GeometryValidationPolicy(), [0])
    assert len(roots) == 3
    assert all(a[1] < b[0] for a, b in zip(roots, roots[1:]))


def test_holes_are_never_silently_filled(candidates):
    base = candidates['s0_route']
    payload = base.route.payload
    payload['occurrences'][0]['holes'] = [[[5.9, .01], [6.1, .01], [6.1, .1], [5.9, .1]]]
    forged = SimpleNamespace(encoded=json.dumps(payload).encode(), payload=payload)
    report = validate_geometry(base, forged, BODY)
    assert report.status == 'FAIL' and 'geometry' in report.reason


def test_nonexact_cap_gap_cannot_be_removed_by_shared_endcap_annotation(candidates):
    base = candidates['s0_route']
    payload = base.route.payload
    # Shift the target cap in the forward gate-normal direction within W1 EPS.
    gate = payload['transitions'][0]['gate']
    dx, dy = gate[1][0] - gate[0][0], gate[1][1] - gate[0][1]
    norm = math.hypot(dx, dy)
    for side in ('seed', 'left', 'right'):
        payload['occurrences'][1][side][0][0] += 5e-10 * dy / norm
        payload['occurrences'][1][side][0][1] -= 5e-10 * dx / norm
    route = validate_route(payload)
    # The resulting q differs slightly, so use its seed (factory-valid) curve.
    from global_planner.route_corridor import seed_curve
    report = validate_geometry(seed_curve(route), route, BODY)
    assert report.status == 'INCONCLUSIVE' and 'nonexact shared endcap' in report.reason


def test_initialization_zone_and_heading_are_validated_on_final_curve(candidates):
    base = candidates['s0_route']
    for kind in ('zone', 'heading'):
        payload = base.route.payload
        if kind == 'zone':
            payload['initialization']['zone'] = [[30, 30], [31, 30], [31, 31], [30, 31]]
        else:
            payload['initialization']['heading_interval_rad'] = [-.1, .1]
        route = validate_route(payload)
        candidate = OrderedCurve(route, base.curve, base.q)
        report = validate_geometry(candidate, route, BODY)
        assert report.status == 'FAIL' and 'initialization' in report.reason


def test_bad_footprint_and_boolean_numeric_inputs_are_rejected():
    with pytest.raises(ValueError):
        Footprint(True, .1, .12, .01)
    with pytest.raises(ValueError):
        GeometryValidationPolicy(max_curvature=True)
    with pytest.raises(validator.BoundUncertain):
        interval_bounds(((0, True, 0, 0), (0, 0, 0, 0)))


def _between_node_notch(base, reference_exit):
    """Modify original legal authority while retaining seed/q/exact cubics."""
    segment_index = 12
    segment = base.curve.segments[segment_index]
    xy = segment.evaluate(.5)
    angle = math.atan2(xy[1], xy[0])
    payload = base.route.payload
    left = payload['occurrences'][0]['left']
    edge = next(i for i in range(len(left) - 1)
                if math.atan2(left[i][1], left[i][0]) < angle <
                math.atan2(left[i + 1][1], left[i + 1][0]))
    a, b = left[edge], left[edge + 1]
    vector = b[0] - a[0], b[1] - a[1]

    def shoulder(theta):
        ray = math.cos(theta), math.sin(theta)
        radius = ((a[0] * vector[1] - a[1] * vector[0]) /
                  (ray[0] * vector[1] - ray[1] * vector[0]))
        return [radius * ray[0], radius * ray[1]]

    tip_radius = 5.8 if reference_exit else math.hypot(*xy) - .025
    tip = [tip_radius * math.cos(angle), tip_radius * math.sin(angle)]
    left[edge + 1:edge + 1] = [shoulder(angle - 1e-5), tip, shoulder(angle + 1e-5)]
    route = validate_route(payload)
    candidate = OrderedCurve(route, base.curve, base.q)
    poly = tuple(validator._point(p) for p in route.occurrences[0].polygon)
    # All affected nonportal solver knots, including both ends of the offending
    # cubic, remain inside. The new restriction lies strictly between them.
    for i, owner in enumerate(base.curve.owners):
        if owner[0] == 'o0' and .3 < base.q[i] < route.occurrences[0].length - .3:
            assert validator._inside(validator._point(base.curve.segments[i].evaluate(0.)), poly)
            coefficient = validator._coefficient_records(base.curve.coefficients[i])
            body, _ = validator._rectangle(
                coefficient, Fraction(0), BODY, interval_bounds(coefficient))
            assert validator._rectangle_clearance2(body, poly) is not None
    assert all(validator._inside(validator._point(segment.evaluate(t)), poly) for t in (0., 1.))
    assert validator._inside(validator._point(xy), poly) != reference_exit
    return candidate, segment_index, poly


@pytest.mark.parametrize('reference_exit', [True, False])
def test_full_validator_rejects_original_notch_between_legal_solver_knots(
        reference_exit, candidates):
    candidate, index, polygon = _between_node_notch(candidates['s0_route'], reference_exit)
    if not reference_exit:
        coefficient = validator._coefficient_records(candidate.curve.coefficients[index])
        bounds = interval_bounds(coefficient)
        rectangle, _ = validator._rectangle(coefficient, Fraction(1, 2), BODY, bounds)
        assert all(validator._inside(p, polygon) for p in rectangle)
        assert validator._rectangle_clearance2(rectangle, polygon) is None
    report = validate_geometry(candidate, candidate.route, BODY)
    assert report.status == 'FAIL', (report.status, report.reason, report.offending_interval)
    assert 'rectangle' in report.reason


def test_interior_curvature_peak_fails_even_when_every_coefficient_knot_passes(candidates):
    base = candidates['s0_route']
    limit = Fraction(.20915)

    def above(coefficient, t):
        a = validator._coefficient_records(coefficient)
        d = validator._position(a, t, 1)
        dd = tuple(validator._polyval(validator._derivative(validator._derivative(row)), t)
                   for row in a)
        return validator._cross(d, dd) ** 2 > limit ** 2 * validator._dot(d, d) ** 3

    assert not any(above(c, Fraction(t)) for c in base.curve.coefficients for t in (0, 1))
    assert above(base.curve.coefficients[69], Fraction(25, 32))
    report = validate_geometry(
        base, base.route, BODY, GeometryValidationPolicy(max_curvature=float(limit)))
    assert report.status == 'FAIL' and 'interior curvature' in report.reason


def test_actual_gate_phase_cannot_be_supplied_by_q_labels_alone(candidates):
    base = candidates['s0_route']
    rotated = tuple((tuple(-x for x in c[1]), c[0]) for c in base.curve.coefficients)
    curve = Curve(rotated, base.curve.owners)
    candidate = OrderedCurve(base.route, curve, base.q)
    report = validate_geometry(candidate, base.route, BODY)
    assert report.status == 'FAIL' and 'gate' in report.reason


def test_forged_tensor_count_cannot_bypass_preprocessing_resource_guard(candidates):
    base = candidates['s0_route']
    curve = SimpleNamespace(coefficients=base.curve.coefficients * 2,
                            owners=base.curve.owners, segments=base.curve.segments,
                            policy=base.curve.policy)
    report = validate_geometry(_fake(base, curve=curve), base.route, BODY)
    assert report.status == 'FAIL' and 'resource shape' in report.reason


def test_coincident_bridge_deck_cannot_be_legalized_by_optimizer_claims(candidates):
    base = candidates['s3_surfaces_route']
    ground = next(o for o in base.route.occurrences if o.id == 'o0')
    upper = next(o for o in base.route.occurrences if o.id == 'o2')
    polygons = tuple(tuple(validator._point(p) for p in o.polygon)
                     for o in (ground, upper))
    overlap = []
    for index, owner in enumerate(base.curve.owners):
        if owner != (ground.id, ground.surface_id):
            continue
        coefficient = validator._coefficient_records(base.curve.coefficients[index])
        for parameter in (Fraction(0), Fraction(1, 4), Fraction(1, 2), Fraction(3, 4)):
            point = validator._position(coefficient, parameter)
            if all(validator._inside(point, polygon) for polygon in polygons):
                overlap.append((index, parameter, point))
    assert overlap, 'fixture must contain the same legal projected XY on both decks'
    index, parameter, point = overlap[len(overlap) // 2]
    curve = copy.deepcopy(base.curve)
    owners = list(curve.owners)
    owners[index] = (upper.id, upper.surface_id)
    object.__setattr__(curve, 'owners', tuple(owners))
    assert curve.coefficients == base.curve.coefficients
    assert validator._position(validator._coefficient_records(
        curve.coefficients[index]), parameter) == point
    # The identical XY remains legal on both projected polygons. It supplies no
    # permission to replace the original q-conditioned occurrence or deck.
    forged = SimpleNamespace(
        route=base.route, curve=curve, q=base.q, success=True, solver_success=True,
        status='SUCCESS', clearance_m=1e6,
        corridors=(SimpleNamespace(lower=-1e6, upper=1e6),))
    report = validate_geometry(forged, base.route, BODY)
    assert report.status == 'FAIL' and 'owner' in report.reason
    Path('/work/a05-wrong-deck-coincident.json').write_text(json.dumps({
        'route_sha256': base.route.digest, 'segment': index,
        'original_route_payload': base.route.payload,
        'actual_coefficients': base.curve.coefficients, 'q': base.q,
        'owners_original': base.curve.owners, 'owners_forged': curve.owners,
        'footprint': asdict(BODY), 'policy': asdict(GeometryValidationPolicy()),
        'independent_report': asdict(report),
        'parameter': [parameter.numerator, parameter.denominator],
        'xy': [float(x) for x in point], 'same_xy_legal_on_both_decks': True,
        'original_owner': list(base.curve.owners[index]),
        'forged_owner': list(curve.owners[index]), 'optimizer_success_claim': True,
        'false_clearance_m': 1e6, 'status': report.status, 'reason': report.reason,
    }, indent=2))
