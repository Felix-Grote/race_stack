"""Independent new analytic, asymmetric route through the complete W2 pipeline."""
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from scipy.integrate import quad

from global_planner.cyclic_retime import (
    DynamicsModel, ModelRegion, RegionLimits, SteeringLimits, curve_digest, retime)
from global_planner.iqp_route_adapter import optimize
from global_planner.route_input import load_route
from global_planner.route_validate import Footprint, validate_geometry
from global_planner.route_validate_dynamics import validate_dynamics

FIXTURE = Path(__file__).parent / 'fixtures/project_a/novel_varying_ellipse_route.json'


def _arc(coefficient, low=0., high=1.):
    # Independent QUADPACK control, distinct from the production bounded Gauss32.
    values = np.asarray(coefficient)

    def speed(parameter):
        derivative = values[:, 1] + parameter * (
            2 * values[:, 2] + 3 * parameter * values[:, 3])
        return math.hypot(*derivative)
    result, error = quad(speed, low, high, epsabs=2e-13, epsrel=2e-13)
    assert error < 1e-10
    return result


def test_new_varying_width_ellipse_has_complete_consistent_w2_acceptance():
    assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == (
        '742b03fa77cef8bfab9f203787ac8dd5435e479a6fddf9449ac4138e83c5a0aa')
    route = load_route(FIXTURE)
    numerical = optimize(route)
    assert numerical.status == 'CANDIDATE', (numerical.status, numerical.reason)
    expected = curve_digest(numerical.ordered)
    ordered = numerical.ordered
    body = Footprint(.1, .1, .12, .01)
    geometry = validate_geometry(ordered, route, body, expected_curve_digest=expected)
    limits = RegionLimits(.05, 4., 2., 3., 4., 2.5, .02,
                          'independent explicit synthetic diamond/model budgets')
    model = DynamicsModel(tuple(ModelRegion(o.id, o.surface_id, limits)
                                for o in route.occurrences),
                          'independent novel analytic route; no physical calibration',
                          SteeringLimits(.3, .7, 3.))
    timed = retime(ordered, model, spacing_m=.5)
    assert timed.status == 'CANDIDATE', (timed.status, timed.message)
    dynamics = validate_dynamics(ordered, timed.profile, model, metadata=timed.metadata,
                                 expected_curve_digest=expected)
    assert geometry.status == dynamics.status == 'PASS', (
        geometry.status, geometry.reason, dynamics.status, dynamics.reason)
    assert geometry.curve_digest == dynamics.curve_digest == expected
    assert timed.profile.curve_digest == timed.metadata.curve_digest == expected
    distances, times = [], []
    acceleration_error = diamond = motor = lateral = 0.
    for index, first in enumerate(timed.profile.knots):
        following = timed.profile.knots[(index + 1) % len(timed.profile.knots)]
        high = following.t if following.segment == first.segment else 1.
        coefficient = ordered.curve.coefficients[first.segment]
        distance = _arc(coefficient, first.t, high)
        edge = dynamics.edges[index]
        assert edge.distance_lower_m <= distance <= edge.distance_upper_m
        acceleration = (following.u - first.u) / (2 * distance)
        acceleration_error = max(acceleration_error,
                                 abs(acceleration - timed.metadata.acceleration_mps2[index]))
        distances.append(distance)
        times.append(2 * distance / (math.sqrt(first.u) + math.sqrt(following.u)))
        values = np.asarray(coefficient)
        for parameter in np.linspace(first.t, high, 13):
            fraction = _arc(coefficient, first.t, float(parameter)) / distance
            u = first.u + fraction * (following.u - first.u)
            derivative = values[:, 1] + parameter * (
                2 * values[:, 2] + 3 * parameter * values[:, 3])
            second = 2 * values[:, 2] + 6 * parameter * values[:, 3]
            curvature = abs(derivative[0] * second[1] - derivative[1] * second[0])
            curvature /= math.hypot(*derivative) ** 3
            drive = acceleration + limits.drag_over_mass * u
            lat = curvature * u / limits.ay_mps2
            lateral = max(lateral, lat)
            diamond = max(diamond, drive / limits.ax_pos_mps2 + lat,
                          -drive / limits.ax_neg_mps2 + lat)
            motor = max(motor, drive / limits.motor_mps2)
    assert diamond <= 1 + 1e-8 and motor <= 1 + 1e-8
    assert dynamics.lap_time_lower_s <= math.fsum(times) <= dynamics.lap_time_upper_s
    assert acceleration_error < 1e-8
    from test_route_w2_trace_oracle import verify_trace_lineage
    lineage = verify_trace_lineage(route, [asdict(t) for t in numerical.traces],
                                   ordered.curve.coefficients, ordered.q, asdict(numerical.policy))
    Path('/work/w2-novel-pipeline.json').write_text(json.dumps({
        'scope': 'independent synthetic software only', 'route_digest': route.digest,
        'expected_curve_digest': expected, 'footprint': asdict(body), 'model': asdict(model),
        'actual_coefficients': ordered.curve.coefficients, 'q': ordered.q,
        'owners': ordered.curve.owners, 'solver_policy': asdict(numerical.policy),
        'solver_traces': [asdict(t) for t in numerical.traces],
        'geometry': asdict(geometry), 'retimer': asdict(timed), 'dynamics': asdict(dynamics),
        'independent_trace_replay': lineage,
        'independent_quad_length_m': math.fsum(distances),
        'independent_quad_time_s': math.fsum(times),
        'sampled_diamond_utilization_max': diamond, 'sampled_motor_utilization_max': motor,
        'sampled_lateral_utilization_max': lateral,
        'maximum_acceleration_metadata_error_mps2': acceleration_error,
    }, indent=2, allow_nan=False))
