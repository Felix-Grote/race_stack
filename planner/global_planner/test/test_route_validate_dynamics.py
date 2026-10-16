"""Independent A06 cyclic/interior/model/metadata rejection regressions."""
from dataclasses import asdict, replace
from fractions import Fraction
import copy
import gzip
import hashlib
import json
import math
from pathlib import Path

import pytest

from global_planner.cyclic_retime import (
    DynamicsModel, ModelRegion, RegionLimits, SpeedKnot, SpeedProfile,
    SteeringLimits, curve_digest, model_digest, retime)
from global_planner.route_corridor import OrderedCurve
from global_planner.route_input import load_route, validate_route
from global_planner.route_reference import Curve
import global_planner.route_validate_dynamics as checker
from global_planner.route_validate_dynamics import DynamicsValidationPolicy, validate_dynamics

FIX = Path(__file__).parent / 'fixtures' / 'project_a'
NAMES = ('s0_route', 's2_upper_route', 's2_lower_route', 's3_surfaces_route', 's3_notch_route')


def load_candidate(name='s0_route'):
    frozen = (FIX / 'w2_a04_candidates.json.gz').read_bytes()
    assert hashlib.sha256(frozen).hexdigest() == (
        '2a506953026b75fc5be4defb1b018577faa46cebdbdfcd767c0103e733b2279b')
    value = json.loads(gzip.decompress(frozen))['candidates'][name]
    route = load_route(FIX / (name + '.json'))
    return OrderedCurve(route, Curve(value['coefficients'], value['owners']), value['q'])


def model_for(route, **changes):
    values = dict(speed_min_mps=.05, speed_max_mps=4., ax_pos_mps2=2.,
                  ax_neg_mps2=3., ay_mps2=4., motor_mps2=3., drag_over_mass=.02,
                  provenance='explicit synthetic planar limits; no car calibration')
    values.update(changes)
    limits = RegionLimits(**values)
    return DynamicsModel(tuple(ModelRegion(o.id, o.surface_id, limits)
                               for o in route.occurrences), 'synthetic test model')


@pytest.fixture(scope='module')
def timed_candidates():
    result, evidence = {}, {}
    for name in NAMES:
        ordered = load_candidate(name)
        model = model_for(ordered.route)
        timed = retime(ordered, model)
        assert timed.status == 'CANDIDATE', (name, timed.message)
        report = validate_dynamics(
            ordered, timed.profile, model, metadata=timed.metadata,
            expected_curve_digest=curve_digest(ordered))
        assert report.status == 'PASS', (name, report.reason, report.offending_edge)
        result[name] = ordered, model, timed, report
        evidence[name] = asdict(report)
    Path('/work/a06-independent-dynamics.json').write_text(json.dumps({
        'scope': 'synthetic planar continuous software only', 'reports': evidence,
        'policy': asdict(DynamicsValidationPolicy())}, indent=2, allow_nan=False))
    return result


@pytest.mark.parametrize('name', NAMES)
def test_same_actual_curves_have_complete_independent_cyclic_certificates(name, timed_candidates):
    ordered, _, timed, report = timed_candidates[name]
    assert len(report.edges) == len(timed.profile.knots)
    assert sum(edge.closing for edge in report.edges) == 1 and report.edges[-1].closing
    assert {edge.segment for edge in report.edges} == set(range(len(ordered.curve.segments)))
    assert report.lap_time_lower_s <= report.lap_time_s <= report.lap_time_upper_s
    assert report.lap_time_error_s >= report.lap_time_upper_s - report.lap_time_s
    assert all(edge.distance_lower_m > 0 and
               edge.normalized_residual_upper <= 1e-8 for edge in report.edges)
    assert max(dict(report.worst_residuals).values()) <= 1e-8
    if name.startswith('s3'):
        assert any(len(edge.support_occurrences) > 1 for edge in report.edges)


@pytest.mark.parametrize('field', [
    'stations_m', 'velocity_mps', 'acceleration_mps2', 'curvature_per_m', 'time_s',
    'lap_time_s', 'curve_digest'])
def test_stale_exported_fields_are_rejected(field, timed_candidates):
    ordered, model, timed, _ = timed_candidates['s0_route']
    if field == 'curve_digest':
        value = '0' * 64
    elif field == 'lap_time_s':
        value = timed.metadata.lap_time_s + .1
    else:
        original = getattr(timed.metadata, field)
        value = (original[0] + .1,) + original[1:]
    report = validate_dynamics(
        ordered, timed.profile, model, metadata=replace(timed.metadata, **{field: value}),
        expected_curve_digest=curve_digest(ordered))
    assert report.status == 'FAIL' and 'metadata' in report.reason or (
        report.status == 'FAIL' and 'exported' in report.reason)


def profile_for(ordered, model, values):
    knots = tuple(SpeedKnot(i, 0., float(u)) for i, u in enumerate(values))
    times = []
    for i, segment in enumerate(ordered.curve.segments):
        j = (i + 1) % len(knots)
        times.append(2 * segment.length / (math.sqrt(knots[i].u) + math.sqrt(knots[j].u)))
    return SpeedProfile(knots, curve_digest(ordered), model_digest(model), math.fsum(times))


def fast_cap_route(ordered):
    payload = ordered.route.payload
    for occurrence in payload['occurrences']:
        for cap in occurrence['caps']:
            cap['max_speed_mps'] = 100.
    return OrderedCurve(validate_route(payload), ordered.curve, ordered.q)


def test_complete_closing_edge_rejects_an_open_lap_acceleration_solution():
    ordered = fast_cap_route(load_candidate())
    model = model_for(ordered.route, speed_max_mps=100., ax_pos_mps2=2.,
                      ax_neg_mps2=2., ay_mps2=1e6, motor_mps2=2., drag_over_mass=0.)
    values = [1 + 2 * station for station in ordered.curve.cumulative[:-1]]
    profile = profile_for(ordered, model, values)
    # Every open edge has a=1; the last-to-first edge requires excessive braking.
    for i, segment in enumerate(ordered.curve.segments[:-1]):
        assert (values[i + 1] - values[i]) / (2 * segment.length) == pytest.approx(1.)
    report = validate_dynamics(
        ordered, profile, model,
        expected_curve_digest=curve_digest(ordered))
    assert report.status == 'FAIL' and report.offending_edge == len(values) - 1
    assert 'dynamic constraint' in report.reason


def test_actual_interior_lateral_violation_despite_valid_knot_curvature():
    ordered = load_candidate()
    model = model_for(ordered.route, ax_pos_mps2=1000., ax_neg_mps2=1000.,
                      ay_mps2=.20915 * 4, motor_mps2=1000., drag_over_mass=0.)
    profile = profile_for(ordered, model, [4.] * len(ordered.curve.segments))
    for coefficient in ordered.curve.coefficients:
        squared, _, _, _ = checker._point_curvature(coefficient, Fraction(0))
        assert squared * 16 < Fraction(model.regions[0].limits.ay_mps2) ** 2
    report = validate_dynamics(
        ordered, profile, model,
        expected_curve_digest=curve_digest(ordered))
    assert report.status == 'FAIL' and 'continuous dynamic' in report.reason


@pytest.mark.parametrize('value', [0., -1., math.nan, math.inf])
def test_zero_negative_nonfinite_speed_cannot_be_accepted(value, timed_candidates):
    ordered, model, timed, _ = timed_candidates['s0_route']
    knots = list(timed.profile.knots)
    knots[0] = replace(knots[0], u=value)
    report = validate_dynamics(
        ordered, replace(timed.profile, knots=knots), model,
        expected_curve_digest=curve_digest(ordered))
    assert report.status == 'FAIL'


def test_stale_profile_identity_time_and_missing_coefficient_boundary_fail(timed_candidates):
    ordered, model, timed, _ = timed_candidates['s0_route']
    profiles = [replace(timed.profile, curve_digest='0' * 64),
                replace(timed.profile, model_digest='0' * 64),
                replace(timed.profile, lap_time_s=timed.profile.lap_time_s + 1.),
                replace(timed.profile, knots=timed.profile.knots[1:])]
    for profile in profiles:
        assert validate_dynamics(
            ordered, profile, model,
            expected_curve_digest=curve_digest(ordered)).status == 'FAIL'


def test_absent_wrong_surface_and_tampered_model_provenance_fail_closed(timed_candidates):
    ordered, model, timed, _ = timed_candidates['s0_route']
    assert validate_dynamics(
        ordered, timed.profile, None,
        expected_curve_digest=curve_digest(ordered)).status == 'UNSUPPORTED'
    wrong = replace(model, regions=(replace(model.regions[0], surface_id='wrong-deck'),) +
                    model.regions[1:])
    assert validate_dynamics(
        ordered, timed.profile, wrong,
        expected_curve_digest=curve_digest(ordered)).status == 'UNSUPPORTED'
    changed = replace(model, provenance='changed declared model')
    assert validate_dynamics(
        ordered, timed.profile, changed,
        expected_curve_digest=curve_digest(ordered)).status == 'FAIL'
    missing = validate_dynamics(
        ordered, timed.profile, model, DynamicsValidationPolicy(require_steering=True),
        expected_curve_digest=curve_digest(ordered))
    assert missing.status == 'UNSUPPORTED'


def test_actual_steering_model_is_checked_including_between_nodes(timed_candidates):
    ordered, model, _, _ = timed_candidates['s0_route']
    supplied = replace(model, steering=SteeringLimits(.3, .7, 3.))
    timed = retime(ordered, supplied)
    assert timed.status == 'CANDIDATE', timed.message
    assert validate_dynamics(
        ordered, timed.profile, supplied, metadata=timed.metadata,
        expected_curve_digest=curve_digest(ordered)).status == 'PASS'
    constrained = replace(model, steering=SteeringLimits(.3, .001, 3.))
    profile = profile_for(ordered, constrained, [1.] * len(ordered.curve.segments))
    report = validate_dynamics(
        ordered, profile, constrained,
        expected_curve_digest=curve_digest(ordered))
    assert report.status == 'FAIL' and 'dynamic constraint' in report.reason


def test_steering_rate_rejects_when_every_steering_angle_is_legal():
    ordered = load_candidate()
    model = replace(model_for(ordered.route), steering=SteeringLimits(.3, .7, 1e-5))
    for coefficient in ordered.curve.coefficients:
        squared, _, _, _ = checker._point_curvature(coefficient, Fraction(0))
        assert math.atan(.3 * math.sqrt(float(squared))) < .7
    profile = profile_for(ordered, model, [1.] * len(ordered.curve.segments))
    report = validate_dynamics(
        ordered, profile, model,
        expected_curve_digest=curve_digest(ordered))
    assert report.status == 'FAIL' and 'dynamic constraint' in report.reason


def test_upper_deck_model_restriction_cannot_be_borrowed_from_other_surface():
    ordered = load_candidate('s3_surfaces_route')
    original = model_for(ordered.route)
    regions = tuple(replace(region, limits=replace(region.limits, speed_max_mps=.45))
                    if region.surface_id == 'upper-deck' else region
                    for region in original.regions)
    model = replace(original, regions=regions)
    profile = profile_for(ordered, model, [1.] * len(ordered.curve.segments))
    report = validate_dynamics(
        ordered, profile, model,
        expected_curve_digest=curve_digest(ordered))
    assert report.status == 'FAIL' and 'model speed' in report.reason


@pytest.mark.parametrize('term', ['motor_drag', 'combined_diamond'])
def test_motor_drag_and_combined_envelope_are_independently_rejected(term):
    ordered = load_candidate()
    if term == 'motor_drag':
        model = model_for(ordered.route, motor_mps2=.01, drag_over_mass=.1)
        assert 4 * .1 > .01
    else:
        model = model_for(ordered.route, ax_pos_mps2=1., ax_neg_mps2=10.,
                          ay_mps2=1., motor_mps2=1., drag_over_mass=.125)
        assert 4 * .125 < 1.  # Separate longitudinal and motor terms pass.
        assert max(math.sqrt(float(checker._point_curvature(c, Fraction(0))[0])) * 4
                   for c in ordered.curve.coefficients) < 1.  # Lateral term passes.
    profile = profile_for(ordered, model, [4.] * len(ordered.curve.segments))
    report = validate_dynamics(
        ordered, profile, model,
        expected_curve_digest=curve_digest(ordered))
    assert report.status == 'FAIL' and 'dynamic constraint' in report.reason


@pytest.mark.parametrize('policy', [
    DynamicsValidationPolicy(max_knots=0), DynamicsValidationPolicy(max_segments=0),
    DynamicsValidationPolicy(max_intervals=0), DynamicsValidationPolicy(max_route_bytes=0),
    DynamicsValidationPolicy(max_text_bytes=0), DynamicsValidationPolicy(wall_seconds=1e-12)])
def test_independent_resource_limits_return_inconclusive(policy, timed_candidates):
    ordered, model, timed, _ = timed_candidates['s0_route']
    assert validate_dynamics(
        ordered, timed.profile, model, policy,
        expected_curve_digest=curve_digest(ordered)).status == 'INCONCLUSIVE'


def test_fraction_external_anchor_and_forged_metric_records_are_rejected(timed_candidates):
    ordered, model, timed, _ = timed_candidates['s0_route']
    knots = (replace(timed.profile.knots[0], t=Fraction(0)),) + timed.profile.knots[1:]
    assert validate_dynamics(
        ordered, replace(timed.profile, knots=knots), model,
        expected_curve_digest=curve_digest(ordered)).status == 'FAIL'
    corrupt = copy.deepcopy(ordered.curve)
    object.__setattr__(corrupt, 'cumulative', tuple(x * 2 for x in corrupt.cumulative))
    forged = copy.copy(ordered)
    object.__setattr__(forged, 'curve', corrupt)
    assert validate_dynamics(
        forged, timed.profile, model,
        expected_curve_digest=curve_digest(ordered)).status == 'FAIL'


def test_unrepresentable_bounds_are_uncertainty_and_subnormal_sqrt_is_enclosed():
    for function in (checker._up, checker._down):
        with pytest.raises(checker._Stop) as stop:
            function(Fraction(10) ** 1000)
        assert stop.value.status == 'INCONCLUSIVE'
    value = Fraction(1, 10 ** 400)
    assert Fraction(checker._sqrt(value, False)) ** 2 <= value
    assert Fraction(checker._sqrt(value)) ** 2 >= value


def test_policy_rejects_boolean_and_nonfinite_terms():
    for changes in ({'residual_abs': True}, {'max_knots': True},
                    {'metadata_abs': math.inf}, {'require_steering': 1}):
        with pytest.raises(ValueError):
            DynamicsValidationPolicy(**changes)


def test_final_curve_handoff_digest_is_required_and_checked_independently():
    ordered = load_candidate()
    expected = curve_digest(ordered)  # Capture trusted fixture before the handoff.
    model = model_for(ordered.route)
    profile = profile_for(ordered, model, [1.] * len(ordered.curve.segments))
    missing = validate_dynamics(ordered, profile, model)
    assert missing.status == 'INCONCLUSIVE' and 'independently expected' in missing.reason
    mismatched = validate_dynamics(
        ordered, profile, model, expected_curve_digest='0' * 64)
    assert mismatched.status == 'FAIL' and 'digest mismatch' in mismatched.reason
    accepted = validate_dynamics(
        ordered, profile, model, expected_curve_digest=expected)
    assert accepted.status == 'PASS', accepted.reason


@pytest.mark.parametrize('expected', [True, 1, '', '0' * 63, 'g' * 64, 'A' * 64])
def test_malformed_expected_identity_fails_before_reconstructing_candidate(expected):
    report = validate_dynamics(None, None, None, expected_curve_digest=expected)
    assert report.status == 'FAIL' and 'malformed independently expected' in report.reason
