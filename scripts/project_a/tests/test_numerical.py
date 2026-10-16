"""Synthetic W0 dependency/ordered-QP smoke, NOT legal trajectory acceptance."""
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path

import numpy as np
import pytest
import quadprog
from scipy.integrate import quad
import trajectory_planning_helpers as tph


def test_kernel_versions_and_source_identity():
    for name, version in {'numpy': '1.26.4', 'scipy': '1.11.4',
                          'quadprog': '0.1.7', 'trajectory-planning-helpers': '0.79'}.items():
        assert metadata.version(name) == version
    root = Path(tph.__file__).parent
    hashes = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
              for name in ('opt_min_curv.py', 'iqp_handler.py', 'spline_approximation.py')}
    Path('/work/helper-hashes.json').write_text(json.dumps(hashes, indent=2))
    assert hashes['opt_min_curv.py'] == 'a2ce75c33498426a5276e5b3455f2059040e8c5e5e54734aee3dde0436bef46d'


def test_quadprog_analytic_active_constraint():
    # min (x-2)^2 + (y-3)^2, x+y <= 2, x,y >= 0 => (.5, 1.5).
    result = quadprog.solve_qp(2 * np.eye(2), np.array([4., 6.]),
                              np.array([[-1., 1., 0.], [-1., 0., 1.]]),
                              np.array([-2., 0., 0.]))[0]
    np.testing.assert_allclose(result, [.5, 1.5], rtol=0, atol=1e-10)


@pytest.mark.parametrize('scenario', ['ellipse', 'projected_crossing'])
def test_ordered_minimum_curvature_qp(scenario):
    # One actual QP on each ordered 64-knot synthetic curve. No prep/width transfer.
    t = np.linspace(0, 2 * np.pi, 64, endpoint=False)
    xy = np.column_stack((8 * np.cos(t), 5 * np.sin(t))) if scenario == 'ellipse' else np.column_stack((8 * np.sin(t), 5 * np.sin(2 * t)))
    track = np.column_stack((xy, np.full((64, 2), .75)))
    original = track.copy()
    _, _, matrix, normals = tph.calc_splines.calc_splines(np.vstack((xy, xy[0])))
    alpha, error = tph.opt_min_curv.opt_min_curv(track, normals, matrix, 1., .30)
    assert np.isfinite(alpha).all() and np.isfinite(error)
    assert np.max(np.abs(alpha)) <= .60 + 1e-8
    np.testing.assert_array_equal(track, original)
    # Dependency smoke only: error reported for later IQP, not convergence/containment.
    Path(f'/work/qp-{scenario}.json').write_text(json.dumps({
        'scenario': scenario, 'knots': 64, 'width_m': .75, 'vehicle_width_m': .30,
        'curvature_bound_per_m': 1., 'offset_tolerance_m': 1e-8,
        'max_abs_alpha_m': float(np.max(np.abs(alpha))),
        'curvature_linearization_error_per_m': float(error),
        'verdict': 'FINITE_NODALLY_BOUNDED_QP_ONLY',
        'legal_footprint_validation': 'NOT_IMPLEMENTED',
    }, indent=2))


def test_independent_analytic_arc_oracle():
    exact = .5 * np.sqrt(5) + .25 * np.arcsinh(2)
    measured, error = quad(lambda t: np.sqrt(1 + 4 * t * t), 0, 1, epsabs=1e-12, epsrel=1e-12)
    assert abs(measured - exact) <= 1e-12 and error < 1e-12


def test_characterize_unmodified_legacy_preparation_failure():
    t = np.linspace(0, 2 * np.pi, 80, endpoint=False)
    track = np.column_stack((8 * np.cos(t), 5 * np.sin(t), np.full((80, 2), .75)))
    with pytest.raises(ValueError, match='Input vector should be 1-D'):
        tph.spline_approximation.spline_approximation(track, s_reg=1, stepsize_prep=.05, stepsize_reg=.2)


def test_characterize_legacy_nonmetric_interpolation():
    length = .5 * np.sqrt(5) + .25 * np.arcsinh(2)
    _, _, ts, nominal = tph.interp_splines.interp_splines(
        np.array([[0., 1., 0., 0.]]), np.array([[0., 0., 1., 0.]]),
        spline_lengths=np.array([length]), incl_last_point=True, stepsize_approx=.1)
    actual = .5 * ts * np.sqrt(1 + 4 * ts**2) + .25 * np.arcsinh(2 * ts)
    discrepancy = float(np.max(np.abs(actual - nominal)))
    assert .16 < discrepancy < .17  # Characterization, not an acceptance tolerance.
    Path('/work/legacy-metric.json').write_text(json.dumps({'max_station_error_m': discrepancy}))
