"""A02 independent analytic, Gauss-Legendre and differential geometry oracles."""
from dataclasses import FrozenInstanceError
import math
import json
from pathlib import Path

import numpy as np
import pytest
from scipy.special import ellipe

from global_planner.route_reference import CubicSegment, Curve, GeometryError, NumericPolicy


def circle(n=64, reverse=False):
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    if reverse:
        t = -t
    return Curve.interpolate(np.c_[6 * np.cos(t), 6 * np.sin(t)])


def gauss_arc(c, t=1., n=160):
    # Independent fixed-order Gaussian quadrature; no production arc/eval calls.
    x, w = np.polynomial.legendre.leggauss(n)
    u = (x + 1) * t / 2
    a = np.asarray(c)
    d = a[:, 1, None] + 2 * a[:, 2, None] * u + 3 * a[:, 3, None] * u ** 2
    return float(np.dot(w, np.sqrt(np.sum(d * d, axis=0))) * t / 2)


def test_nonuniform_parameter_analytic_parabola():
    seg = CubicSegment(((0, 1, 0, 0), (0, 0, 1, 0)))

    def exact(t):
        return .5 * t * math.sqrt(1 + 4 * t * t) + .25 * math.asinh(2 * t)
    assert seg.length == pytest.approx(exact(1), abs=1e-12)
    worst_old = 0.
    residual = 0.
    for s in np.linspace(0, seg.length, 51):
        t = seg.parameter(s)
        residual = max(residual, abs(exact(t) - s))
        worst_old = max(worst_old, abs(exact(s / seg.length) - s))
        assert seg.arc(t) == pytest.approx(s, abs=1e-8)
    assert residual < 1e-8
    Path('/work/a02-parabola.json').write_text(json.dumps({
        'exact_length_m': exact(1), 'integrated_length_m': seg.length,
        'max_inverse_station_residual_m': residual,
        'max_linear_fraction_station_error_m': worst_old,
        'station_acceptance_m': 1e-8, 'quad_estimated_error_m': seg.arc_error,
    }, indent=2))
    assert worst_old > .16  # would fail if inverse merely used s/L


@pytest.mark.parametrize('reverse', [False, True])
def test_circle_metric_sign_and_periodicity(reverse):
    c = circle(reverse=reverse)
    assert c.length == pytest.approx(12 * np.pi, abs=5e-6)
    sign = -1 if reverse else 1
    for s in np.linspace(0, c.length, 23, endpoint=False):
        v = c.sample(s)
        assert np.linalg.norm(v.xy) == pytest.approx(6, abs=2e-6)
        assert v.curvature == pytest.approx(sign / 6, abs=1.4e-4)
        assert np.linalg.norm(v.tangent) == pytest.approx(1, abs=1e-14)
        assert np.dot(v.tangent, v.left_normal) == pytest.approx(0, abs=1e-14)
        assert c.sample(s - 3 * c.length).xy == pytest.approx(v.xy, abs=1e-8)
        assert c.sample(s + 7 * c.length).xy == pytest.approx(v.xy, abs=1e-8)
    assert c.locate(c.length) == (0, 0.)
    for i, s in enumerate(c.cumulative[:-1]):
        assert c.locate(s) == (i, 0.)


def test_nonuniform_ellipse_independent_coefficients_and_arc():
    # Nonuniform parameter mesh: enough density for ellipse length convergence.
    t = 2 * np.pi * (np.arange(300) / 300) ** 1.3
    c = Curve.interpolate(np.c_[8 * np.cos(t), 4 * np.sin(t)], q=np.r_[t, 2 * np.pi])
    assert c.length == pytest.approx(32 * ellipe(.75), abs=1e-6)
    oracle = [gauss_arc(a) for a in c.coefficients]
    assert sum(oracle) == pytest.approx(c.length, abs=1e-10)
    for i in range(0, len(c.segments), 7):
        for t0 in (.03, .4, .93):
            s = sum(oracle[:i]) + gauss_arc(c.coefficients[i], t0)
            j, t1 = c.locate(s)
            assert j == i
            assert c.station(j, t1) == pytest.approx(s, abs=1e-8)
            # Independent Horner derivatives from NumPy polynomial routines.
            a = np.asarray(c.coefficients[i])
            d = np.array([np.polynomial.polynomial.polyval(t0,
                          np.polynomial.polynomial.polyder(row)) for row in a])
            dd = np.array([np.polynomial.polynomial.polyval(t0,
                           np.polynomial.polynomial.polyder(row, 2)) for row in a])
            k = (d[0] * dd[1] - d[1] * dd[0]) / np.linalg.norm(d) ** 3
            assert c.sample(s).curvature == pytest.approx(k, abs=2e-8)


def test_coefficients_immutable_reconstruction_and_window():
    c = circle()
    d = Curve(c.coefficients)
    assert d.coefficients == c.coefficients
    assert d.length == c.length
    with pytest.raises(FrozenInstanceError):
        c.cumulative = ()
    with pytest.raises(TypeError):
        c.coefficients[0][0][0] = 1
    w = c.window(-.2, .3, .1)
    assert len(w) == 6
    assert w[-1].xy == pytest.approx(c.sample(.3).xy, abs=1e-8)
    with pytest.raises(GeometryError):
        c.window(0, 1e6, 1e-6)


@pytest.mark.parametrize('kind', ['position', 'tangent', 'curvature', 'nan', 'zero', 'cusp'])
def test_invalid_curve(kind):
    coeff = np.array(circle(8).coefficients)
    if kind == 'position':
        coeff[0, 0, 0] += .1
    if kind == 'tangent':
        coeff[0, 0, 1] += .1
    if kind == 'curvature':
        coeff[0, 0, 2] += .1
    if kind == 'nan':
        coeff[0, 0, 0] = np.nan
    if kind == 'zero':
        coeff[0, :, 1:] = 0
    if kind == 'cusp':
        # derivative zero at t=.5 in interior, endpoints remain nonzero.
        coeff[0] = [[0, -.5, .5, 0], [0, 0, 0, 0]]
    with pytest.raises(GeometryError):
        Curve(coeff)


def test_budgets_owners_and_bad_queries():
    c = circle(8)
    owners = [('o' + str(i), 'surface') for i in range(8)]
    d = Curve(c.coefficients, owners)
    assert d.sample(.1, occurrence_id='o0').surface_id == 'surface'
    with pytest.raises(GeometryError):
        d.sample(.1, occurrence_id='o4')
    for s in (float('nan'), float('inf'), 1e30):
        with pytest.raises(GeometryError):
            c.sample(s)
    with pytest.raises(GeometryError):
        CubicSegment(((0, 1, 0, 0), (0, 0, 20, 0)), NumericPolicy(quad_limit=1))
    with pytest.raises(GeometryError):
        CubicSegment(((0, 1, -1, 0), (0, 1.2, -2, 4 / 3)),
                     NumericPolicy(regularity_budget=1, regularity_depth=1))
    with pytest.raises(GeometryError):
        NumericPolicy(arc_abs=1e-3)
    with pytest.raises(GeometryError):
        Curve.interpolate([[0, 0], [0, 0], [1, 1]])


def feature_arc(coeff, center, width, transverse, scale, t=1.):
    """Independent Gaussian oracle with the narrow feature explicitly resolved."""
    anchors = {0., t}
    for root in (center - width, center, center + width):
        local = transverse / max(2 * scale * width, math.sqrt(scale * transverse))
        for factor in (-1000, -100, -10, -1, -.1, 0, .1, 1, 10, 100, 1000):
            value = root + factor * local
            if 0 < value < t:
                anchors.add(value)
    x, w = np.polynomial.legendre.leggauss(96)
    values = []
    a = np.asarray(coeff)
    anchors = sorted(anchors)
    for lo, hi in zip(anchors, anchors[1:]):
        u = lo + (x + 1) * (hi - lo) / 2
        d = a[:, 1, None] + 2 * a[:, 2, None] * u + 3 * a[:, 3, None] * u ** 2
        values.append(float(np.dot(w, np.hypot(*d)) * (hi - lo) / 2))
    return math.fsum(values)


@pytest.mark.parametrize('center', [.2, .37, .53, .8])
@pytest.mark.parametrize('width', [.001, .01])
@pytest.mark.parametrize('scale', [.1, 1., 10.])
def test_regular_narrow_speed_features(center, width, scale):
    transverse = max(2e-7, scale * 2e-7)
    coeff = ((0., scale * (center ** 2 - width ** 2), -scale * center, scale / 3),
             (0., transverse, 0., 0.))
    # This stress matrix explicitly grants more panels, never looser accuracy.
    seg = CubicSegment(coeff, NumericPolicy(quad_limit=256))
    oracle = feature_arc(coeff, center, width, transverse, scale)
    assert abs(seg.length - oracle) <= seg.policy.arc_abs
    assert abs(seg.length - oracle) <= seg.arc_error + 2e-14 * scale
    projected = scale * (1 / 3 - center + center ** 2 - width ** 2 + 8 * width ** 3 / 3)
    assert seg.length + seg.arc_error >= projected - 1e-14 * scale
    for fraction in (.25, .6, .75, .93):
        target = fraction * seg.length
        t = seg.parameter(target)
        actual = feature_arc(coeff, center, width, transverse, scale, t)
        assert abs(actual - target) <= seg.policy.station_abs


def test_regular_monotone_speed_minimum():
    scale, center, transverse = .75, 17 / 32, 4e-6
    coeff = ((0., .211669921876, -.3984375, .25), (0., transverse, 0., 0.))
    seg = CubicSegment(coeff)
    oracle = feature_arc(coeff, center, 0., transverse, scale)
    assert abs(seg.length - oracle) <= seg.policy.arc_abs
    target = .75 * seg.length
    actual = feature_arc(coeff, center, 0., transverse, scale, seg.parameter(target))
    assert abs(actual - target) <= seg.policy.station_abs


def test_original_speed_feature_and_explicit_budget_exhaustion():
    coeff = ((0., .0899, -.3, 1 / 3), (0., 2e-7, 0., 0.))
    segment = CubicSegment(coeff)
    oracle = feature_arc(coeff, .3, .01, 2e-7, 1.)
    assert abs(segment.length - oracle) <= segment.policy.arc_abs
    # The larger-scale stress above is resolvable, but cannot silently spend
    # beyond the caller's default 100-panel numerical resource allowance.
    hard = ((0., 10 * (.53 ** 2 - .01 ** 2), -5.3, 10 / 3),
            (0., 2e-6, 0., 0.))
    with pytest.raises(GeometryError, match='budget exhausted'):
        CubicSegment(hard)


def test_periodic_narrow_speed_feature():
    points = [
        [-1.5024623491492127e-15, -7.957616698076442e-22],
        [.12323333333333301, 1.9999999999986714e-7],
        [.2867959417586583, -.4813887455929313],
        [-1.4997593897109303, -1.6151633169617934],
        [-.647436223972624, .9494314068337777],
        [-.20927157109936093, .9423388372100486],
        [1.4381127571538583, -.3109547412709052],
        [.23234307397572523, -.12505112468113805],
    ]
    curve = Curve.interpolate(points, q=np.arange(9, dtype=float))
    segment = curve.segments[0]
    oracle = feature_arc(segment.coefficients, .3, .01, 2e-7, 1.)
    assert abs(segment.length - oracle) <= segment.policy.arc_abs
    target = .75 * segment.length
    sample = curve.sample(target)
    actual = feature_arc(segment.coefficients, .3, .01, 2e-7, 1., sample.t)
    assert abs(actual - target) <= curve.policy.station_abs


@pytest.mark.parametrize('count', [5, 8, 17, 64])
def test_canonical_endpoint_owners_and_adjacent_floats(count):
    theta = 2 * np.pi * (np.arange(count) / count) ** 1.2
    owners = tuple(('o' + str(i), 's' + str(i)) for i in range(count))
    curve = Curve.interpolate(np.c_[6 * np.cos(theta), 4 * np.sin(theta)], owners=owners)
    for i in range(count):
        assert curve.station(i, 0.) == curve.cumulative[i]
        assert curve.station(i, 1.) == curve.cumulative[i + 1]
        next_i = (i + 1) % count
        assert curve.locate(curve.station(i, 1.)) == (next_i, 0.)
        endpoint = curve.sample(curve.station(i, 1.))
        assert (endpoint.occurrence_id, endpoint.surface_id) == owners[next_i]
        left = curve.sample(float(np.nextafter(curve.cumulative[i + 1], -np.inf)))
        right = curve.sample(float(np.nextafter(curve.cumulative[i], np.inf)))
        assert (left.occurrence_id, left.surface_id) == owners[i]
        assert (right.occurrence_id, right.surface_id) == owners[i]


def test_negative_seam_progress_retains_preceding_side():
    theta = np.linspace(0, 2 * np.pi, 64, endpoint=False)
    owners = tuple(('o' + str(i), 's' + str(i)) for i in range(64))
    curve = Curve.interpolate(np.c_[6 * np.cos(theta), 6 * np.sin(theta)], owners=owners)
    for progress in (-1e-20, -float(np.nextafter(0., 1.)), -math.ulp(curve.length)):
        assert 0 <= curve.wrap(progress) < curve.length
        sample = curve.sample(progress)
        assert sample.s < curve.length
        assert (sample.occurrence_id, sample.surface_id) == owners[-1]
        assert sample.xy == pytest.approx(curve.sample(0.).xy, abs=1e-8)
    for progress in (0., curve.length, -curve.length, 2 * curve.length, -2 * curve.length):
        assert curve.locate(progress) == (0, 0.)
        assert curve.sample(progress).occurrence_id == 'o0'
