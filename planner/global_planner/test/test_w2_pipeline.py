"""Fresh A04 -> A05 -> A06 acceptance on the same final coefficient authority."""
from dataclasses import asdict
import json
from pathlib import Path

import numpy as np
import pytest

from global_planner.cyclic_retime import (
    DynamicsModel, ModelRegion, RegionLimits, RetimePolicy, SteeringLimits, curve_digest, retime)
from global_planner.iqp_route_adapter import optimize
from global_planner.route_input import load_route
from global_planner.route_validate import Footprint, GeometryValidationPolicy, validate_geometry
from global_planner.route_validate_dynamics import DynamicsValidationPolicy, validate_dynamics

FIX = Path(__file__).parent / 'fixtures' / 'project_a'
NAMES = ('s0_route', 's0_reverse_route', 's0_rotated_route', 's2_upper_route',
         's2_lower_route', 's3_surfaces_route', 's3_notch_route')
BODY = Footprint(front_m=.10, rear_m=.10, width_m=.12, margin_m=.01)


def synthetic_model(route):
    """Declared test budgets, with a weaker upper deck; no car calibration."""
    regions = []
    for occurrence in route.occurrences:
        upper = occurrence.surface_id == 'upper-deck'
        limits = RegionLimits(
            speed_min_mps=.05, speed_max_mps=2.5 if upper else 4.,
            ax_pos_mps2=1.5 if upper else 2., ax_neg_mps2=2. if upper else 3.,
            ay_mps2=2. if upper else 4., motor_mps2=2.5,
            drag_over_mass=.02,
            provenance='W2 synthetic planar diamond; explicitly chosen test values')
        regions.append(ModelRegion(occurrence.id, occurrence.surface_id, limits))
    return DynamicsModel(
        regions=tuple(regions), provenance='W2 synthetic test model; no physical evidence',
        steering=SteeringLimits(wheelbase_m=.3, angle_max_rad=.7, rate_max_radps=3.))


@pytest.fixture(scope='module')
def pipelines():
    results = {}
    evidence = {'scope': 'SYNTHETIC PLANAR SOFTWARE ONLY; no physical certification',
                'execution': 'fresh optimizer -> geometry -> retimer -> dynamics',
                'footprint': asdict(BODY), 'retime_policy': asdict(RetimePolicy()),
                'geometry_policy': asdict(GeometryValidationPolicy()),
                'dynamics_policy': asdict(DynamicsValidationPolicy()), 'scenarios': {}}
    for name in NAMES:
        route = load_route(FIX / (name + '.json'))
        numerical = optimize(route)
        assert numerical.status == 'CANDIDATE', (name, numerical.status, numerical.reason)
        expected = curve_digest(numerical.ordered)
        ordered = numerical.ordered
        geometry = validate_geometry(ordered, route, BODY, expected_curve_digest=expected)
        assert geometry.status == 'PASS', (name, geometry.reason)
        model = synthetic_model(route)
        timed = retime(ordered, model, spacing_m=.5)
        assert timed.status == 'CANDIDATE', (name, timed.status, timed.message)
        dynamics = validate_dynamics(ordered, timed.profile, model, metadata=timed.metadata,
                                     expected_curve_digest=expected)
        results[name] = numerical, geometry, model, timed, dynamics, expected
        evidence['scenarios'][name] = {
            'route_sha256': route.digest, 'expected_curve_digest': expected,
            'coefficients': ordered.curve.coefficients,
            'owners': ordered.curve.owners, 'q': ordered.q,
            'numeric_policy': asdict(ordered.curve.policy),
            'solver_policy': asdict(numerical.policy),
            'solver_iterations': [asdict(trace) for trace in numerical.traces],
            'geometry': asdict(geometry), 'model': asdict(model),
            'retimer': asdict(timed), 'dynamics': asdict(dynamics)}
    Path('/work/w2-pipeline.json').write_text(json.dumps(evidence, indent=2, allow_nan=False))
    return results


@pytest.mark.parametrize('name', NAMES)
def test_fresh_final_candidate_passes_both_independent_validators(name, pipelines):
    numerical, geometry, model, timed, dynamics, expected = pipelines[name]
    assert geometry.status == dynamics.status == 'PASS', (
        name, dynamics.status, dynamics.reason, dynamics.offending_edge)
    assert geometry.curve_digest == dynamics.curve_digest == expected
    assert timed.profile.curve_digest == timed.metadata.curve_digest == expected
    assert timed.profile.lap_time_s > 0
    assert len(timed.profile.knots) >= len(numerical.ordered.curve.segments)
    assert len(model.regions) == len(numerical.ordered.route.occurrences)
    assert geometry.coefficients_sha256


def test_fresh_optimizer_and_retimer_are_repeatable(pipelines):
    original, _, model, timed, _, expected = pipelines['s0_route']
    repeated = optimize(original.ordered.route)
    assert repeated.status == 'CANDIDATE', repeated.reason
    assert repeated.ordered.q == original.ordered.q
    np.testing.assert_allclose(repeated.ordered.curve.coefficients,
                               original.ordered.curve.coefficients, rtol=0, atol=1e-10)
    retimed = retime(original.ordered, model, spacing_m=.5)
    assert retimed.status == 'CANDIDATE', retimed.message
    assert retimed.profile == timed.profile
    assert retimed.metadata == timed.metadata
    assert validate_dynamics(original.ordered, retimed.profile, model,
                             metadata=retimed.metadata,
                             expected_curve_digest=expected).status == 'PASS'


def test_fresh_a04_q_history_replays_independently(pipelines):
    from test_route_w2_trace_oracle import verify_trace_lineage

    evidence = {}
    for name in NAMES:
        numerical, _, _, _, _, expected = pipelines[name]
        ordered = numerical.ordered
        # The independent helper rejects ancestry, fit, normal, damping or final
        # authority inconsistencies by assertion; it does not solve another QP.
        evidence[name] = verify_trace_lineage(
            ordered.route, [asdict(trace) for trace in numerical.traces],
            ordered.curve.coefficients, ordered.q, asdict(numerical.policy))
        assert evidence[name]['iterations'] == len(numerical.traces)
        assert curve_digest(ordered) == expected
    Path('/work/w2-trace-lineage-oracle.json').write_text(
        json.dumps(evidence, indent=2, allow_nan=False))


def test_independent_a04_history_oracle_rejects_changed_final_q(pipelines):
    from test_route_w2_trace_oracle import verify_trace_lineage

    numerical, _, _, _, _, _ = pipelines['s0_route']
    ordered = numerical.ordered
    altered_q = list(ordered.q)
    altered_q[3] += .01 * (altered_q[4] - altered_q[3])
    with pytest.raises(AssertionError):
        verify_trace_lineage(
            ordered.route, [asdict(trace) for trace in numerical.traces],
            ordered.curve.coefficients, altered_q, asdict(numerical.policy))
