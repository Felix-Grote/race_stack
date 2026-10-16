"""Explicit closed-ellipse A06 retiming and independent metric control.

Run in the pinned Python 3.10 test environment. All model values and annotations
are synthetic software inputs.
"""
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pytest
from scipy.special import ellipe

from global_planner.cyclic_retime import (DynamicsModel, ModelRegion, RegionLimits,
                                          RetimePolicy, curve_digest, retime)
from global_planner.route_corridor import seed_curve
from global_planner.route_input import load_route, validate_route
from global_planner.route_validate_dynamics import validate_dynamics

_ROOTS_96, _WEIGHTS_96 = np.polynomial.legendre.leggauss(96)
_ROOTS_48, _WEIGHTS_48 = np.polynomial.legendre.leggauss(48)
_BASE_FIXTURE = Path('/src/planner/global_planner/test/fixtures/project_a/s0_route.json')


def _gaussian_arc(coefficients, a=0., b=1., *, order=96):
    roots, weights = ((_ROOTS_96, _WEIGHTS_96) if order == 96 else
                      (_ROOTS_48, _WEIGHTS_48))
    t = a + (b - a) * (roots + 1) / 2
    c = np.asarray(coefficients)
    d = c[:, 1, None] + 2 * c[:, 2, None] * t + 3 * c[:, 3, None] * t * t
    return float((b - a) / 2 * (weights @ np.hypot(d[0], d[1])))


def _curvature(coefficients, t):
    c = np.asarray(coefficients)
    d = c[:, 1] + 2 * c[:, 2] * t + 3 * c[:, 3] * t * t
    dd = 2 * c[:, 2] + 6 * c[:, 3] * t
    return float((d[0] * dd[1] - d[1] * dd[0]) / math.hypot(*d) ** 3)


def _ellipse_route():
    # The fixture is an independently approved synthetic circle ribbon. An
    # invertible positive-determinant affine map preserves its selected topology,
    # ownership, shared caps and side orientation. Seed q must be recomputed.
    payload = load_route(_BASE_FIXTURE).payload

    def affine(points):
        return [[4 * x / 3, 5 * y / 6] for x, y in points]

    for occurrence in payload['occurrences']:
        for key in ('seed', 'left', 'right'):
            occurrence[key] = affine(occurrence[key])
        occurrence['caps'] = [{'at_m': 0., 'max_speed_mps': 8.}]
        occurrence['provenance']['source'] = 'synthetic affine ellipse from S0 circle'
    for portal in payload['transitions']:
        portal['gate'] = affine(portal['gate'])
        portal['support'] = affine(portal['support'])
    payload['initialization']['zone'] = affine(payload['initialization']['zone'])
    payload['course_id'] = 'a06-ellipse-oracle'
    payload['provenance']['source'] = 'analytic ellipse axes8m/5m; synthetic only'
    return validate_route(payload)


def test_simple_closed_ellipse_retimes_with_independent_metric_and_lateral_oracles():
    route = _ellipse_route()
    ordered = seed_curve(route)
    limits = RegionLimits(.1, 6., 20., 20., 2., 20., 0.,
                          'explicit synthetic ellipse lateral-binding control')
    model = DynamicsModel(tuple(ModelRegion(o.id, o.surface_id, limits)
                                for o in route.occurrences),
                          'ellipse software acceptance; no physical vehicle calibration')
    policy = RetimePolicy()
    result = retime(ordered, model, spacing_m=.47, policy=policy)
    assert result.status == 'CANDIDATE', result.message
    report = validate_dynamics(
        ordered, result.profile, model, metadata=result.metadata,
        expected_curve_digest=curve_digest(ordered))
    assert report.status == 'PASS', report.reason
    knots = result.profile.knots
    assert report.edges[-1].closing and len(report.edges) == len(knots)
    assert result.max_lp_residual <= 1e-8

    # Coefficient geometry is the authority. The analytic elliptic integral
    # additionally checks the intended generating shape, with its separately
    # declared cubic-approximation allowance (never a metric-kernel relaxation).
    full_arcs = [_gaussian_arc(s.coefficients) for s in ordered.curve.segments]
    independent_length = math.fsum(full_arcs)
    analytic_length = 4 * 8 * float(ellipe(1 - (5 / 8) ** 2))
    assert ordered.curve.length == pytest.approx(independent_length, abs=1e-9)
    assert independent_length == pytest.approx(analytic_length, abs=1e-5)
    assert max(abs(_gaussian_arc(s.coefficients, order=48) - arc)
               for s, arc in zip(ordered.curve.segments, full_arcs)) < 1e-13

    axis_nodes = {}
    distances, times, acceleration = [], [], []
    lateral_max = positive_max = negative_max = 0.
    for i, first in enumerate(knots):
        following = knots[(i + 1) % len(knots)]
        end = following.t if following.segment == first.segment else 1.
        coefficients = ordered.curve.segments[first.segment].coefficients
        distance = _gaussian_arc(coefficients, first.t, end)
        assert distance > 0
        assert report.edges[i].distance_lower_m <= distance <= report.edges[i].distance_upper_m
        distances.append(distance)
        a = (following.u - first.u) / (2 * distance)
        acceleration.append(a)
        times.append(2 * distance / (math.sqrt(first.u) + math.sqrt(following.u)))
        if first.t == 0.:
            point = np.asarray(coefficients)[:, 0]
            if abs(point[1]) < 1e-10 and abs(abs(point[0]) - 8) < 1e-10:
                axis_nodes['high' + str(first.segment)] = (
                    first.u, abs(_curvature(coefficients, 0.)))
            if abs(point[0]) < 1e-10 and abs(abs(point[1]) - 5) < 1e-10:
                axis_nodes['low' + str(first.segment)] = (
                    first.u, abs(_curvature(coefficients, 0.)))
        # Independent samples are regression diagnostics; the PASS above still
        # depends on whole-edge interval bounds, not this sample density.
        for fraction in np.linspace(0., 1., 9):
            t = first.t + float(fraction) * (end - first.t)
            progress = _gaussian_arc(coefficients, first.t, t) / distance
            u = first.u + (following.u - first.u) * progress
            lateral = abs(_curvature(coefficients, t)) * u / 2
            lateral_max = max(lateral_max, lateral)
            positive_max = max(positive_max, a / 20 + lateral)
            negative_max = max(negative_max, -a / 20 + lateral)
    assert max(distances) > 2 * min(distances)
    assert math.fsum(distances) == pytest.approx(independent_length, abs=1e-10)
    time = math.fsum(times)
    assert result.profile.lap_time_s == pytest.approx(time, abs=1e-8)
    assert report.lap_time_lower_s <= time <= report.lap_time_upper_s
    np.testing.assert_allclose(result.metadata.acceleration_mps2, acceleration,
                               rtol=0, atol=1e-8)
    assert lateral_max <= 1 + 1e-8
    assert positive_max <= 1 + 1e-8 and negative_max <= 1 + 1e-8

    high = [value for key, value in axis_nodes.items() if key.startswith('high')]
    low = [value for key, value in axis_nodes.items() if key.startswith('low')]
    assert len(high) == len(low) == 2
    assert min(k for _, k in high) > .30 and max(k for _, k in low) < .09
    assert min(u for u, _ in low) > 2 * max(u for u, _ in high)
    assert min(k * u / 2 for u, k in high) > .80

    Path('/work/a06-ellipse-route.json').write_bytes(route.encoded)
    Path('/work/a06-ellipse-profile.json').write_text(json.dumps(
        asdict(result.profile), indent=2, allow_nan=False))
    Path('/work/a06-ellipse.json').write_text(json.dumps({
        'base_fixture_file_sha256': hashlib.sha256(_BASE_FIXTURE.read_bytes()).hexdigest(),
        'base_fixture_canonical_route_sha256': load_route(_BASE_FIXTURE).digest,
        'transform': {'coordinate_operations': ['(4*x)/3', '(5*y)/6'],
                      'ellipse_semiaxes_m': [8., 5.],
                      'static_speed_caps_mps': 8.},
        'route_sha256': route.digest, 'curve_digest': result.profile.curve_digest,
        'model_digest': result.profile.model_digest, 'model': asdict(model),
        'derived_route_payload': route.payload,
        'actual_coefficients': ordered.curve.coefficients,
        'actual_q': ordered.q, 'actual_owners': ordered.curve.owners,
        'profile': asdict(result.profile), 'metadata': asdict(result.metadata),
        'independent_validation': asdict(report),
        'solver_policy': asdict(policy), 'requested_spacing_m': .47,
        'status': report.status, 'knots': len(knots),
        'coefficient_length_m': ordered.curve.length,
        'gauss96_length_m': independent_length, 'analytic_ellipse_length_m': analytic_length,
        'analytic_shape_approximation_tolerance_m': 1e-5,
        'minimum_metric_edge_m': min(distances), 'maximum_metric_edge_m': max(distances),
        'high_curvature_axis_u_kappa': high, 'low_curvature_axis_u_kappa': low,
        'independent_time_s': time, 'certified_time_lower_s': report.lap_time_lower_s,
        'certified_time_upper_s': report.lap_time_upper_s,
        'closing_acceleration_mps2': acceleration[-1],
        'sampled_lateral_utilization_max': lateral_max,
        'sampled_diamond_positive_max': positive_max,
        'sampled_diamond_negative_max': negative_max,
        'oracle_errors': {
            'metric_length_m': ordered.curve.length - independent_length,
            'analytic_shape_length_m': independent_length - analytic_length,
            'time_s': result.profile.lap_time_s - time,
            'maximum_metric_edge_m': max(abs(edge.distance_m - distance)
                                         for edge, distance in zip(report.edges, distances)),
            'maximum_acceleration_mps2': max(
                abs(a - b) for a, b in zip(result.metadata.acceleration_mps2, acceleration)),
        },
        'scope': 'synthetic offline model; sampling is a regression oracle only',
    }, indent=2, allow_nan=False))
