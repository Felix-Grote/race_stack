"""Independent analytic cyclic-LP and physical-arc controls for A06.

These oracles do not consume LP rows, retimer support helpers or validator
residuals. Gaussian integration is a regression control, not the certificate.
"""
from dataclasses import replace
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pytest

import global_planner.cyclic_retime as retimer
from global_planner.route_corridor import refit_ordered, resample_ordered, seed_curve
from global_planner.route_input import load_route, validate_route
from global_planner.route_reference import CubicSegment
from global_planner.route_validate_dynamics import validate_dynamics

FIX = Path(__file__).parent / 'fixtures' / 'project_a'


def route():
    return load_route(FIX / 's0_route.json')


def model(ordered, **overrides):
    values = dict(speed_min_mps=.1, speed_max_mps=3., ax_pos_mps2=2.,
                  ax_neg_mps2=1., ay_mps2=1e12, motor_mps2=100., drag_over_mass=0.,
                  provenance='independent synthetic mathematical control')
    values.update(overrides)
    limits = retimer.RegionLimits(**values)
    regions = tuple(retimer.ModelRegion(o.id, o.surface_id, limits)
                    for o in ordered.route.occurrences)
    return retimer.DynamicsModel(regions, 'synthetic oracle; no physical vehicle calibration')


def gaussian_arc(coefficient, a=0., b=1., order=96):
    roots, weights = np.polynomial.legendre.leggauss(order)
    t = a + (b - a) * (roots + 1) / 2
    c = np.asarray(coefficient)
    derivative = c[:, 1, None] + 2 * c[:, 2, None] * t + 3 * c[:, 3, None] * t * t
    return float((b - a) / 2 * (weights @ np.hypot(derivative[0], derivative[1])))


def physical_mesh(ordered, profile):
    lengths = [gaussian_arc(s.coefficients) for s in ordered.curve.segments]
    prefix = [0.]
    for i in range(len(lengths)):
        prefix.append(math.fsum(lengths[:i + 1]))
    stations = [prefix[k.segment] + gaussian_arc(
        ordered.curve.segments[k.segment].coefficients, 0., k.t) for k in profile.knots]
    ds = [b - a for a, b in zip(stations, stations[1:])]
    ds.append(prefix[-1] - stations[-1] + stations[0])
    assert all(d > 0 for d in ds)
    return np.array(stations), np.array(ds), prefix[-1]


def test_constant_model_speed_is_exact_global_lp_optimum_and_time():
    ordered = seed_curve(route())
    dynamics = model(ordered)
    result = retimer.retime(ordered, dynamics, spacing_m=.6)
    assert result.status == 'CANDIDATE', result.message
    u = np.array([k.u for k in result.profile.knots])
    # Every node has u<=9; u=9 is feasible at every edge, so this is the exact
    # componentwise maximum for any positive distance-weighted objective.
    np.testing.assert_allclose(u, 9., rtol=0, atol=1e-8)
    stations, ds, length = physical_mesh(ordered, result.profile)
    assert result.objective == pytest.approx(9 * length, abs=1e-7)
    assert result.profile.lap_time_s == pytest.approx(length / 3, abs=1e-8)
    assert result.max_lp_residual <= 1e-8
    np.testing.assert_allclose(result.metadata.stations_m, stations, rtol=0, atol=1e-9)
    np.testing.assert_allclose(result.metadata.acceleration_mps2, 0., rtol=0, atol=1e-8)
    assert math.fsum(ds) == pytest.approx(length, abs=1e-12)
    assert {(k.segment, k.t) for k in result.profile.knots}.issuperset(
        {(i, 0.) for i in range(len(ordered.curve.segments))})
    accepted = validate_dynamics(
        ordered, result.profile, dynamics, metadata=result.metadata,
        expected_curve_digest=retimer.curve_digest(ordered))
    assert accepted.status == 'PASS', accepted.reason


def test_drag_motor_cycle_has_known_integrated_optimum():
    ordered = seed_curve(route())
    dynamics = model(ordered, speed_max_mps=5., ax_pos_mps2=100., ax_neg_mps2=100.,
                     motor_mps2=1., drag_over_mass=.5)
    result = retimer.retime(ordered, dynamics, spacing_m=.6)
    assert result.status == 'CANDIDATE', result.message
    u = np.array([k.u for k in result.profile.knots])
    # Integrate a+c*u<=M around a complete lap: integral(a ds)=0, hence
    # integral(u ds)<=M*L/c=2L. Constantu=2 attains this global LP bound.
    np.testing.assert_allclose(u, 2., rtol=0, atol=1e-8)
    _, _, length = physical_mesh(ordered, result.profile)
    assert result.objective == pytest.approx(2 * length, abs=1e-6)
    assert result.profile.lap_time_s == pytest.approx(length / math.sqrt(2), abs=1e-7)
    accepted = validate_dynamics(
        ordered, result.profile, dynamics, metadata=result.metadata,
        expected_curve_digest=retimer.curve_digest(ordered))
    assert accepted.status == 'PASS', accepted.reason


def test_open_chain_feasible_profile_is_rejected_only_on_closing_edge():
    ordered = seed_curve(route())
    dynamics = model(ordered)
    solved = retimer.retime(ordered, dynamics, spacing_m=.6)
    assert solved.status == 'CANDIDATE', solved.message
    stations, ds, _ = physical_mesh(ordered, solved.profile)
    u = np.minimum(9., 1 + 4 * stations)
    acceleration = (np.roll(u, -1) - u) / (2 * ds)
    assert np.max(acceleration[:-1]) <= 2 + 1e-8
    assert np.min(acceleration[:-1]) >= -1e-8
    assert acceleration[-1] < -2
    knots = tuple(retimer.SpeedKnot(old.segment, old.t, float(value))
                  for old, value in zip(solved.profile.knots, u))
    time = math.fsum(2 * distance / (math.sqrt(a) + math.sqrt(b))
                     for distance, a, b in zip(ds, u, np.roll(u, -1)))
    profile = replace(solved.profile, knots=knots, lap_time_s=time)
    rejected = validate_dynamics(
        ordered, profile, dynamics,
        expected_curve_digest=retimer.curve_digest(ordered))
    assert rejected.status == 'FAIL', rejected.reason
    assert rejected.offending_edge == len(knots) - 1
    assert len(rejected.edges) == len(knots) - 1


def edge_static_cap(ordered, first, following):
    segment = first.segment
    t1 = following.t if following.segment == segment else 1.
    q0, q1 = Fraction(ordered.q[segment]), Fraction(ordered.q[segment + 1])
    lo = q0 + Fraction(first.t) * (q1 - q0)
    hi = q0 + Fraction(t1) * (q1 - q0)
    owner = ordered.curve.owners[segment][0]
    start = 0.
    for occurrence in ordered.route.occurrences:
        end = start + occurrence.length
        if occurrence.id == owner:
            break
        start = end
    eligible = []
    for i, (position, cap) in enumerate(occurrence.caps):
        a = Fraction(start) + Fraction(position)
        b = (Fraction(start) + Fraction(occurrence.caps[i + 1][0])
             if i + 1 < len(occurrence.caps) else Fraction(end))
        if a <= hi and lo <= b:
            eligible.append(cap)
    assert eligible
    return min(eligible)


def test_asymmetric_closed_cycle_matches_independent_distance_cone_envelope():
    raw = route().payload
    for occurrence in raw['occurrences']:
        occurrence['caps'] = [{'at_m': 0., 'max_speed_mps': 4.2}]
    raw['occurrences'][0]['caps'].extend([
        {'at_m': 1.2345, 'max_speed_mps': 1.},
        {'at_m': 1.3345, 'max_speed_mps': 4.2},
    ])
    selected = validate_route(raw)
    seed = seed_curve(selected)
    samples = resample_ordered(seed, .55)
    ordered = refit_ordered(seed, samples, [s.xy for s in samples])
    dynamics = model(ordered, speed_max_mps=5.)
    result = retimer.retime(ordered, dynamics, spacing_m=.6)
    assert result.status == 'CANDIDATE', result.message
    knots = result.profile.knots
    u = np.array([k.u for k in knots])
    stations, ds, length = physical_mesh(ordered, result.profile)
    edge_caps = np.array([edge_static_cap(ordered, first, knots[(i + 1) % len(knots)])
                          for i, first in enumerate(knots)])
    node_caps = np.minimum(edge_caps, np.roll(edge_caps, 1)) ** 2
    # u_j-u_i<=2*A*ds and u_i-u_j<=2*B*ds form a directed positive-cost
    # cycle. The exact maximum feasible u is the lower envelope of all caps'
    # forward acceleration and backward braking distance cones.
    envelope = []
    for station in stations:
        forward = np.mod(station - stations, length)
        backward = np.mod(stations - station, length)
        envelope.append(float(np.min(node_caps + np.minimum(4 * forward, 2 * backward))))
    # Ay=1e12 leaves a <1e-10 perturbation; declared LP margin and arc bounds
    # account for the remaining <1e-7 squared-speed oracle comparison budget.
    np.testing.assert_allclose(u, envelope, rtol=0, atol=1e-7)
    closing = (u[0] - u[-1]) / (2 * ds[-1])
    assert -1 - 1e-8 <= closing < -.9
    assert u[0] < 4.  # Braking must already occur across the closing seam.
    acceleration = (np.roll(u, -1) - u) / (2 * ds)
    np.testing.assert_allclose(result.metadata.acceleration_mps2, acceleration,
                               rtol=0, atol=1e-8)
    time = math.fsum(2 * d / (math.sqrt(a) + math.sqrt(b))
                     for d, a, b in zip(ds, u, np.roll(u, -1)))
    assert result.profile.lap_time_s == pytest.approx(time, abs=1e-8)
    Path('/work/a06-cycle-oracle.json').write_text(json.dumps({
        'route_sha256': selected.digest, 'knots': len(knots),
        'oracle': 'directed cycle acceleration/braking distance-cone envelope',
        'maximum_squared_speed_error': float(np.max(np.abs(u - envelope))),
        'closing_acceleration_mps2': closing, 'lap_time_s': time,
        'longitudinal_positive_mps2': 2., 'longitudinal_negative_mps2': 1.,
        'lateral_mps2': 1e12, 'comparison_tolerance_m2ps2': 1e-7,
    }, indent=2))


@pytest.mark.parametrize('coefficient', [
    ((0., 1., 0., 0.), (0., 0., 1., 0.)),
    ((.1, 1., -.7, .3), (.2, .2, .8, -.1)),
    ((100000., 1., 0., 0.), (-50000., 0., 1., 0.)),
])
def test_metric_distance_enclosures_agree_with_independent_polynomial_quadrature(coefficient):
    segment = CubicSegment(coefficient)
    for a, b in ((0., 1.), (.2, .8), (1 - 2. ** -18, 1.)):
        nominal, lower, upper = retimer._arc_interval(segment, a, b)
        oracle = gaussian_arc(coefficient, a, b, 96)
        check = gaussian_arc(coefficient, a, b, 48)
        assert abs(oracle - check) < 1e-13
        assert lower <= oracle <= upper
        assert lower <= nominal <= upper
    with pytest.raises(retimer._Abort):
        retimer._arc_interval(segment, 1 - 2. ** -42, 1.)


def test_table_dips_full_range_interpolation_and_explicit_provenance(tmp_path):
    ggv = tmp_path / 'ggv.csv'
    motor = tmp_path / 'motor.csv'
    ggv.write_text('# speed,ax,ay\n0,4,12\n2,1,2\n4,3,9\n6,4,12\n')
    motor.write_text('# speed,motor\n0,3\n2,.5\n4,2\n6,3\n')
    common = dict(braking_mps2=1.7, drag_over_mass=.03,
                  provenance='independent synthetic nonmonotone tables')
    limits = retimer.limits_from_tables(
        ggv, motor, speed_min_mps=1., speed_max_mps=5., **common)
    assert limits.ax_pos_mps2 == 1.
    assert limits.ay_mps2 == 2.
    assert limits.motor_mps2 == .5
    assert limits.ax_neg_mps2 == 1.7 and limits.drag_over_mass == .03
    provenance = json.loads(limits.provenance)
    assert provenance['ggv_sha256'] == hashlib.sha256(ggv.read_bytes()).hexdigest()
    assert provenance['motor_sha256'] == hashlib.sha256(motor.read_bytes()).hexdigest()
    # No tabulated knot lies in this subrange; minima come from exact linear
    # interpolation at speed3.0 on the rising2..4 segment.
    rising = retimer.limits_from_tables(
        ggv, motor, speed_min_mps=3., speed_max_mps=3.5, **common)
    assert rising.ax_pos_mps2 == 2.
    assert rising.ay_mps2 == 5.5
    assert rising.motor_mps2 == 1.25
    with pytest.raises(retimer.DynamicsError, match='no extrapolation'):
        retimer.limits_from_tables(ggv, motor, speed_min_mps=1., speed_max_mps=7., **common)
