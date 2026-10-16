"""A06 retimer tests with independent metric/time and explicit table oracles."""
from dataclasses import FrozenInstanceError, asdict, replace
from fractions import Fraction
import gzip
import hashlib
import json
import math
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

import global_planner.cyclic_retime as timing
from global_planner.cyclic_retime import (
    DynamicsError, DynamicsModel, ModelRegion, RegionLimits, RetimePolicy,
    SteeringLimits, limits_from_tables, retime)
from global_planner.route_corridor import OrderedCurve, seed_curve
from global_planner.route_input import load_route, validate_route
from global_planner.route_reference import Curve

FIX = Path(__file__).parent / 'fixtures' / 'project_a'


def synthetic_model(route, **changes):
    values = dict(speed_min_mps=.05, speed_max_mps=4., ax_pos_mps2=2., ax_neg_mps2=3.,
                  ay_mps2=4., motor_mps2=2.5, drag_over_mass=.02,
                  provenance='A06 supplied synthetic planar software budgets')
    values.update(changes)
    limits = RegionLimits(**values)
    return DynamicsModel(tuple(ModelRegion(o.id, o.surface_id, limits) for o in route.occurrences),
                         'A06 synthetic model; no physical vehicle evidence')


def candidate(name='s0_route'):
    records = json.loads(gzip.decompress((FIX / 'w2_a04_candidates.json.gz').read_bytes()))
    value = records['candidates'][name]
    route = load_route(FIX / (name + '.json'))
    return OrderedCurve(route, Curve(value['coefficients'], value['owners']), value['q'])


def independent_arc(coeff, a, b):
    nodes, weights = np.polynomial.legendre.leggauss(96)
    t = (nodes + 1) * (b - a) / 2 + a
    c = np.asarray(coeff)
    d = c[:, 1, None] + 2 * c[:, 2, None] * t + 3 * c[:, 3, None] * t * t
    return float(weights @ np.sqrt(np.sum(d * d, axis=0)) * (b - a) / 2)


@pytest.mark.parametrize('name', ['s0_route', 's0_reverse_route', 's0_rotated_route',
                                  's2_upper_route', 's2_lower_route', 's3_surfaces_route',
                                  's3_notch_route'])
def test_actual_candidate_retiming_uses_true_cyclic_arc_and_metadata(name):
    ordered = candidate(name)
    model = synthetic_model(ordered.route)
    result = retime(ordered, model, spacing_m=.57)
    assert result.status == 'CANDIDATE', (name, result.message)
    assert result.max_lp_residual <= 1e-8
    knots = result.profile.knots
    independent_time = 0.
    for i, knot in enumerate(knots):
        following = knots[(i + 1) % len(knots)]
        end = following.t if following.segment == knot.segment else 1.
        ds = independent_arc(ordered.curve.coefficients[knot.segment], knot.t, end)
        acceleration = (following.u - knot.u) / (2 * ds)
        assert result.metadata.acceleration_mps2[i] == pytest.approx(acceleration, abs=2e-9)
        independent_time += 2 * ds / (math.sqrt(knot.u) + math.sqrt(following.u))
        assert knot.u > 0
    assert result.profile.lap_time_s == pytest.approx(independent_time, abs=1e-8)
    assert result.metadata.lap_time_s == result.profile.lap_time_s
    assert result.metadata.time_s[0] == 0
    assert all(a < b for a, b in zip(result.metadata.time_s, result.metadata.time_s[1:]))
    assert {k.segment for k in knots if k.t == 0} == set(range(len(ordered.curve.segments)))
    Path('/work/a06-retimer-' + name + '.json').write_text(json.dumps({
        'scope': 'synthetic planar software only', 'model': asdict(model),
        'policy': asdict(RetimePolicy()), 'result': asdict(result),
        'independent_gauss_lap_time_s': independent_time}, indent=2, allow_nan=False))


def test_seam_cap_is_applied_before_retiming_with_upstream_braking():
    raw = load_route(FIX / 's0_route.json').payload
    raw['occurrences'][0]['caps'][0]['max_speed_mps'] = .35
    route = validate_route(raw)
    ordered = seed_curve(route)
    model = synthetic_model(route, ax_neg_mps2=.3, drag_over_mass=0.)
    result = retime(ordered, model, spacing_m=.8)
    assert result.status == 'CANDIDATE', result.message
    assert result.metadata.velocity_mps[0] <= .35 + 1e-10
    assert result.metadata.acceleration_mps2[-1] >= -.3 - 1e-8
    assert max(result.metadata.velocity_mps) > 1.
    assert min(result.metadata.acceleration_mps2) < -.15


def test_weaker_portal_support_limits_both_adjacent_occurrences():
    ordered = candidate('s3_surfaces_route')
    model = synthetic_model(ordered.route)
    regions = tuple(replace(r, limits=replace(r.limits, speed_max_mps=.45))
                    if r.surface_id == 'upper-deck' else r for r in model.regions)
    model = replace(model, regions=regions)
    result = retime(ordered, model)
    assert result.status == 'CANDIDATE', result.message
    starts = [0.]
    for occurrence in ordered.route.occurrences:
        starts.append(starts[-1] + occurrence.length)
    for knot in result.profile.knots:
        q = ordered.progress(knot.segment, knot.t)
        # All of upper occurrence and both neighboring portal supports are slow.
        if starts[2] - ordered.route.portals[1].before <= q <= (
                starts[3] + ordered.route.portals[2].after):
            assert math.sqrt(knot.u) <= .45 + 1e-8


def test_optional_steering_rate_cap_and_required_model():
    ordered = candidate('s0_route')
    plain = synthetic_model(ordered.route, speed_min_mps=.0001)
    missing = retime(ordered, plain, policy=RetimePolicy(require_steering=True))
    assert missing.status == 'UNSUPPORTED' and missing.profile is None
    steering = SteeringLimits(.3, .7, .001)
    strict_floor = replace(synthetic_model(ordered.route), steering=steering)
    rejected = retime(ordered, strict_floor)
    assert rejected.status == 'REJECT' and rejected.profile is None
    slowed = retime(ordered, replace(plain, steering=steering))
    assert slowed.status == 'CANDIDATE', slowed.message
    normal = retime(ordered, plain)
    assert normal.status == 'CANDIDATE'
    assert max(slowed.metadata.velocity_mps) < max(normal.metadata.velocity_mps)
    impossible = replace(plain, steering=SteeringLimits(.3, 1e-5, 1.))
    limited = retime(ordered, impossible, policy=RetimePolicy(bound_depth=2))
    assert limited.status == 'INCONCLUSIVE' and limited.profile is None


def test_model_and_resource_failures_never_return_candidate(monkeypatch):
    ordered = candidate()
    model = synthetic_model(ordered.route)
    assert retime(ordered, None).status == 'UNSUPPORTED'
    assert retime(ordered, replace(model, regions=model.regions[:-1])).status == 'UNSUPPORTED'
    budget = retime(ordered, model, policy=RetimePolicy(max_knots=2))
    assert budget.status == 'INCONCLUSIVE' and budget.profile is None
    budget = retime(ordered, model, policy=RetimePolicy(max_constraints=1))
    assert budget.status == 'INCONCLUSIVE' and budget.profile is None
    budget = retime(ordered, model, policy=RetimePolicy(time_limit_s=1e-12))
    assert budget.status == 'INCONCLUSIVE' and budget.profile is None
    monkeypatch.setattr(timing, 'linprog', lambda *a, **k: SimpleNamespace(
        success=False, status=2, message='injected infeasibility'))
    failed = retime(ordered, model)
    assert failed.status == 'REJECT' and failed.profile is None


def test_solver_exception_nonfinite_and_zero_motion_are_fail_closed(monkeypatch):
    ordered = candidate()
    model = synthetic_model(ordered.route)

    def broken(*args, **kwargs):
        raise RuntimeError('injected solver exception')
    monkeypatch.setattr(timing, 'linprog', broken)
    assert retime(ordered, model).status == 'INCONCLUSIVE'
    monkeypatch.setattr(timing, 'linprog', lambda objective, **kwargs: SimpleNamespace(
        success=True, x=np.full(len(objective), np.nan), nit=0))
    assert retime(ordered, model).status == 'INCONCLUSIVE'
    monkeypatch.undo()
    raw = ordered.route.payload
    raw['occurrences'][0]['caps'][0]['max_speed_mps'] = .001
    route = validate_route(raw)
    impossible = retime(seed_curve(route), synthetic_model(route))
    assert impossible.status == 'REJECT' and impossible.profile is None


def test_table_full_range_minima_hashes_and_no_extrapolation(tmp_path):
    ggv = FIX / 'dynamics' / 'ggv_dip.csv'
    motor = FIX / 'dynamics' / 'motor_dip.csv'
    limits = limits_from_tables(ggv, motor, speed_min_mps=.25, speed_max_mps=3.75,
                                braking_mps2=.7, drag_over_mass=.02,
                                provenance='supplied synthetic table control')
    assert limits.ax_pos_mps2 == .75 and limits.ay_mps2 == 1.5
    assert limits.motor_mps2 == .5 and limits.ax_neg_mps2 == .7
    source = json.loads(limits.provenance)
    assert source['ggv_sha256'] == hashlib.sha256(ggv.read_bytes()).hexdigest()
    assert source['motor_sha256'] == hashlib.sha256(motor.read_bytes()).hexdigest()
    assert source['rule'] == 'piecewise_linear_full_range_minimum'
    partial = limits_from_tables(ggv, motor, speed_min_mps=.25, speed_max_mps=.75,
                                 braking_mps2=.7, drag_over_mass=.02, provenance='partial cell')
    assert partial.ax_pos_mps2 == 3.25 and partial.ay_mps2 == 5.25
    with pytest.raises(DynamicsError, match='no extrapolation'):
        limits_from_tables(ggv, motor, speed_min_mps=0, speed_max_mps=5,
                           braking_mps2=.7, drag_over_mass=0, provenance='bad coverage')
    malformed = tmp_path / 'bad.csv'
    malformed.write_text('0,1,2\n0,2,3\n')
    with pytest.raises(DynamicsError, match='ordered'):
        limits_from_tables(malformed, motor, speed_min_mps=0, speed_max_mps=1,
                           braking_mps2=.7, drag_over_mass=0, provenance='bad order')


def test_interpolated_table_minimum_rounds_inward_exactly(tmp_path):
    path = tmp_path / 'rational.csv'
    path.write_text('0.1,1.3,2.7\n0.9,0.3,0.7\n')
    motor = tmp_path / 'motor.csv'
    motor.write_text('0,4\n1,4\n')
    low, high = .2, .7
    result = limits_from_tables(path, motor, speed_min_mps=low, speed_max_mps=high,
                                braking_mps2=1., drag_over_mass=0., provenance='rounding control')
    exact = Fraction(1.3) + (Fraction(high) - Fraction(.1)) * (
        Fraction(.3) - Fraction(1.3)) / (Fraction(.9) - Fraction(.1))
    assert Fraction(result.ax_pos_mps2) <= exact
    assert math.nextafter(result.ax_pos_mps2, math.inf) >= float(exact)


def test_models_are_explicit_frozen_and_reject_nonfinite_or_unknown_inputs():
    route = load_route(FIX / 's0_route.json')
    model = synthetic_model(route)
    with pytest.raises(FrozenInstanceError):
        model.provenance = 'changed'
    for value in (0., -1., math.inf, math.nan, True):
        with pytest.raises(DynamicsError):
            replace(model.regions[0].limits, ax_neg_mps2=value)
    with pytest.raises(DynamicsError, match='duplicate'):
        replace(model, regions=(model.regions[0], model.regions[0]))
    with pytest.raises(DynamicsError):
        SteeringLimits(.3, math.pi, 1.)


def test_explicit_pinned_legacy_table_import_preserves_provenance():
    source = (Path(__file__).parents[1] / 'global_planner' /
              'global_racetrajectory_optimization' / 'global_racetrajectory_optimization' /
              'inputs' / 'veh_dyn_info')
    ggv, motor = source / 'ggv.csv', source / 'ax_max_machines.csv'
    limits = limits_from_tables(ggv, motor, speed_min_mps=.1, speed_max_mps=15.,
                                braking_mps2=2., drag_over_mass=.03,
                                provenance='explicit archived files; no physical calibration')
    assert limits.ax_pos_mps2 == limits.ay_mps2 == 12.
    assert limits.motor_mps2 == 5.3
    assert limits.ax_neg_mps2 == 2. and limits.drag_over_mass == .03
    provenance = json.loads(limits.provenance)
    assert provenance['ggv_sha256'] == hashlib.sha256(ggv.read_bytes()).hexdigest()
    assert provenance['motor_sha256'] == hashlib.sha256(motor.read_bytes()).hexdigest()


def test_extreme_numerical_floor_and_mesh_preflight_are_bounded(monkeypatch):
    ordered = candidate()
    model = synthetic_model(ordered.route)
    extreme = retime(ordered, model, policy=RetimePolicy(moving_speed_mps=1e-300))
    assert extreme.status == 'UNSUPPORTED' and extreme.profile is None

    def prohibited(*args, **kwargs):
        raise AssertionError('resampling must not start before mesh preflight')
    monkeypatch.setattr(timing, 'resample_ordered', prohibited)
    result = retime(ordered, model, spacing_m=1e-20)
    assert result.status == 'INCONCLUSIVE' and result.profile is None


def test_table_hash_and_parse_share_one_bounded_snapshot(monkeypatch):
    original = np.loadtxt
    observed = []

    def snapshot_only(source, *args, **kwargs):
        assert hasattr(source, 'getvalue'), 'parser must consume the captured byte snapshot'
        observed.append(source.getvalue())
        return original(source, *args, **kwargs)

    def unbounded_read_prohibited(*args, **kwargs):
        raise AssertionError('table importer must not use an unbounded path read')
    monkeypatch.setattr(np, 'loadtxt', snapshot_only)
    monkeypatch.setattr(Path, 'read_bytes', unbounded_read_prohibited)
    ggv = FIX / 'dynamics' / 'ggv_dip.csv'
    motor = FIX / 'dynamics' / 'motor_dip.csv'
    limits = limits_from_tables(ggv, motor, speed_min_mps=0, speed_max_mps=4.,
                                braking_mps2=1., drag_over_mass=0., provenance='snapshot test')
    source = json.loads(limits.provenance)
    assert source['ggv_sha256'] == hashlib.sha256(observed[0]).hexdigest()
    assert source['motor_sha256'] == hashlib.sha256(observed[1]).hexdigest()


def test_underflow_steering_product_and_malformed_policy_are_structured(monkeypatch):
    ordered = candidate()
    model = synthetic_model(ordered.route)
    assert retime(ordered, model, policy=None).status == 'UNSUPPORTED'
    bound = SimpleNamespace(speed_lower=1., curvature_upper=0., curvature_rate_upper=1e-300)
    monkeypatch.setattr(timing, 'interval_bounds', lambda *a, **k: bound)
    tiny = replace(model, steering=SteeringLimits(1e-300, .7, 1.))
    result = retime(ordered, tiny)
    assert result.status == 'INCONCLUSIVE' and result.profile is None


def test_model_text_budget_rejects_before_expensive_reconstruction(monkeypatch):
    ordered = candidate()
    model = synthetic_model(ordered.route)

    def reconstruction_prohibited(*args, **kwargs):
        raise AssertionError('text preflight must precede route and coefficient reconstruction')
    monkeypatch.setattr(timing, 'validate_route', reconstruction_prohibited)
    monkeypatch.setattr(timing, 'Curve', reconstruction_prohibited)
    # The Unicode case fits in characters but exceeds the UTF-8 byte budget.
    for value, budget in (('ordinary provenance', 1), ('é' * 250, 500)):
        large = replace(model, provenance=value)
        result = retime(ordered, large, policy=RetimePolicy(max_text_bytes=budget))
        assert result.status == 'INCONCLUSIVE' and result.profile is None
        assert 'text budget' in result.message
