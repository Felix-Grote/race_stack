"""Fresh A04 -> A05 -> A06 acceptance on the same final coefficient authority."""
from dataclasses import asdict
import json
from pathlib import Path

import numpy as np
import pytest

from global_planner.cyclic_retime import (
    DynamicsModel, ModelRegion, RegionLimits, RetimePolicy, SteeringLimits, retime)
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
        ordered = numerical.ordered
        geometry = validate_geometry(ordered, route, BODY)
        assert geometry.status == 'PASS', (name, geometry.reason)
        model = synthetic_model(route)
        timed = retime(ordered, model, spacing_m=.5)
        assert timed.status == 'CANDIDATE', (name, timed.status, timed.message)
        dynamics = validate_dynamics(ordered, timed.profile, model, metadata=timed.metadata)
        results[name] = numerical, geometry, model, timed, dynamics
        evidence['scenarios'][name] = {
            'route_sha256': route.digest, 'coefficients': ordered.curve.coefficients,
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
    numerical, geometry, model, timed, dynamics = pipelines[name]
    assert geometry.status == dynamics.status == 'PASS', (
        name, dynamics.status, dynamics.reason, dynamics.offending_edge)
    assert timed.profile.curve_digest == timed.metadata.curve_digest
    assert timed.profile.lap_time_s > 0
    assert len(timed.profile.knots) >= len(numerical.ordered.curve.segments)
    assert len(model.regions) == len(numerical.ordered.route.occurrences)
    assert geometry.coefficients_sha256


def test_fresh_optimizer_and_retimer_are_repeatable(pipelines):
    original, _, model, timed, _ = pipelines['s0_route']
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
                             metadata=retimed.metadata).status == 'PASS'
