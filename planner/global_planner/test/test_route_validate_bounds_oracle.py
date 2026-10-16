"""Independent high-precision controls of continuous A05 coefficient bounds.

Decimal derivative evaluations are regression oracles, never the production
certificate. The certificate must still enclose every parameter continuously.
"""
from decimal import Decimal, localcontext
from fractions import Fraction
import json
import math
from pathlib import Path

import numpy as np
import pytest

from global_planner.route_validate import BoundUncertain, interval_bounds


def decimal_values(coefficients, parameter):
    """Differentiate exact binary64 inputs at 100 digits, independently of A02/A05."""
    with localcontext() as context:
        context.prec = 100
        if isinstance(parameter, Fraction):
            t = Decimal(parameter.numerator) / Decimal(parameter.denominator)
        else:
            t = Decimal.from_float(float(parameter))
        a = [[Decimal.from_float(float(x)) for x in row] for row in coefficients]
        d = [row[1] + 2 * row[2] * t + 3 * row[3] * t * t for row in a]
        dd = [2 * row[2] + 6 * row[3] * t for row in a]
        j = [6 * row[3] for row in a]
        g = d[0] * d[0] + d[1] * d[1]
        speed = g.sqrt()
        c = d[0] * dd[1] - d[1] * dd[0]
        cp = d[0] * j[1] - d[1] * j[0]
        gp = 2 * (d[0] * dd[0] + d[1] * dd[1])
        curvature = abs(c) / (g * speed)
        rate = abs(2 * cp * g - 3 * c * gp) / (2 * g * g * g)
        return +speed, +curvature, +rate


def assert_enclosure(coefficients, lo=Fraction(0), hi=Fraction(1), count=65):
    bounds = interval_bounds(coefficients, lo, hi)
    values = (bounds.speed_lower, bounds.speed_upper, bounds.curvature_upper,
              bounds.curvature_rate_upper, bounds.numeric_error)
    assert all(math.isfinite(v) for v in values)
    assert bounds.speed_lower > 0 and bounds.numeric_error >= 0
    lower = Decimal.from_float(bounds.speed_lower)
    upper = Decimal.from_float(bounds.speed_upper)
    curvature = Decimal.from_float(bounds.curvature_upper)
    rate = Decimal.from_float(bounds.curvature_rate_upper)
    maximum = [Decimal(0), Decimal(0), Decimal(0)]
    for i in range(count):
        parameter = lo + (hi - lo) * Fraction(i, count - 1)
        actual = decimal_values(coefficients, parameter)
        assert lower <= actual[0] <= upper, (parameter, bounds, actual)
        assert actual[1] <= curvature, (parameter, bounds, actual)
        assert actual[2] <= rate, (parameter, bounds, actual)
        maximum = [max(a, b) for a, b in zip(maximum, actual)]
    return bounds, tuple(float(v) for v in maximum)


@pytest.mark.parametrize('coefficients', [
    ((0., 1., 0., 0.), (0., 0., 1., 0.)),
    ((0., 1., 0., 0.), (.25, -1., 1., 0.)),
    ((.25, 2., -.5, .125), (-.5, .25, 1., -.25)),
    ((-2., 3., .25, -.125), (4., -.5, -.75, .5)),
])
def test_hundred_digit_derivative_oracle_over_full_and_subintervals(coefficients):
    for lo, hi in ((Fraction(0), Fraction(1)), (Fraction(1, 8), Fraction(5, 8)),
                   (Fraction(17, 32), Fraction(9, 16))):
        assert_enclosure(coefficients, lo, hi)


def test_between_node_curvature_and_curvature_rate_peaks_are_enclosed():
    coefficients = ((0., 1., 0., 0.), (.25, -1., 1., 0.))
    bounds, _ = assert_enclosure(coefficients)
    endpoints = [decimal_values(coefficients, Fraction(t)) for t in (0, 1)]
    assert float(max(v[1] for v in endpoints)) < .71
    assert Decimal.from_float(bounds.curvature_upper) >= Decimal(2)
    with localcontext() as context:
        context.prec = 100
        displacement = Decimal(1) / Decimal(20).sqrt()
        rate_peak = 24 * displacement / (1 + 4 * displacement ** 2) ** 3
        assert Decimal.from_float(bounds.curvature_rate_upper) >= rate_peak
        assert rate_peak > 2 * max(v[2] for v in endpoints)


def test_nearly_parallel_large_derivatives_do_not_erase_small_curvature():
    large = 1e7
    separated = math.nextafter(large, math.inf)
    coefficients = ((10000., large, large, 0.),
                    (-10000., large, separated, 2. ** -30))
    bounds, maximum = assert_enclosure(coefficients)
    # Cross products subtract terms of order1e14; the actual numerator is
    # small but nonzero. A floating cancellation to zero must not grant PASS.
    assert 0 < maximum[1] < 1e-20
    assert bounds.curvature_upper > 0 and bounds.curvature_rate_upper > 0


def test_translation_rotation_reflection_and_scale_preserve_valid_bounds():
    original = np.array(((.25, 2., -.5, .125), (-.5, .25, 1., -.25)))
    ledger = []
    for scale in (2. ** -10, 1., 2. ** 10):
        for angle in (0., .37, math.pi / 2):
            rotation = np.array(((math.cos(angle), -math.sin(angle)),
                                 (math.sin(angle), math.cos(angle))))
            coefficient = scale * rotation @ original
            coefficient[:, 0] += (100000., -50000.)
            bounds, maximum = assert_enclosure(coefficient)
            ledger.append({'scale': scale, 'angle': angle,
                           'oracle_maximum': maximum,
                           'bound_speed_lower': bounds.speed_lower,
                           'bound_speed_upper': bounds.speed_upper,
                           'bound_curvature': bounds.curvature_upper,
                           'bound_curvature_rate': bounds.curvature_rate_upper})
    reflected = original.copy()
    reflected[1] *= -1
    first, _ = assert_enclosure(original)
    second, _ = assert_enclosure(reflected)
    assert second.speed_lower == first.speed_lower
    assert second.speed_upper == first.speed_upper
    assert second.curvature_upper == first.curvature_upper
    assert second.curvature_rate_upper == first.curvature_rate_upper
    translated = original.copy()
    translated[:, 0] += (100000., -50000.)
    translated_bounds, _ = assert_enclosure(translated)
    for attribute in ('speed_lower', 'speed_upper', 'curvature_upper', 'curvature_rate_upper'):
        assert getattr(translated_bounds, attribute) == getattr(first, attribute)
    Path('/work/a05-bounds-oracle.json').write_text(json.dumps({
        'oracle': '100-digit Decimal derivative arithmetic on exact binary64 inputs',
        'scope': 'sampled independent regression oracle; production interval certificate required',
        'controls': ledger,
    }, indent=2, allow_nan=False))


def test_dyadic_parameter_restriction_and_physical_scale_laws():
    coefficients = ((.25, 2., -.5, .125), (-.5, .25, 1., -.25))
    lo, hi = Fraction(1, 8), Fraction(3, 4)
    h = hi - lo
    restricted = []
    for row in coefficients:
        a, b, c, d = (Fraction.from_float(x) for x in row)
        restricted.append((a + b * lo + c * lo ** 2 + d * lo ** 3,
                           h * (b + 2 * c * lo + 3 * d * lo ** 2),
                           h * h * (c + 3 * d * lo), h ** 3 * d))
    restricted = tuple(tuple(float(x) for x in row) for row in restricted)
    full_bounds, _ = assert_enclosure(coefficients, lo, hi)
    local_bounds, _ = assert_enclosure(restricted)
    assert local_bounds.speed_lower == pytest.approx(float(h) * full_bounds.speed_lower,
                                                     rel=2e-14, abs=0)
    assert local_bounds.speed_upper == pytest.approx(float(h) * full_bounds.speed_upper,
                                                     rel=2e-14, abs=0)
    assert local_bounds.curvature_upper == pytest.approx(full_bounds.curvature_upper, rel=2e-14)
    assert local_bounds.curvature_rate_upper == pytest.approx(
        full_bounds.curvature_rate_upper, rel=2e-14)
    for scale in (2. ** -10, 2. ** 10):
        scaled, _ = assert_enclosure(np.asarray(coefficients) * scale, lo, hi)
        assert scaled.speed_lower == pytest.approx(scale * full_bounds.speed_lower, rel=2e-14)
        assert scaled.curvature_upper == pytest.approx(
            full_bounds.curvature_upper / scale, rel=2e-14)
        assert scaled.curvature_rate_upper == pytest.approx(
            full_bounds.curvature_rate_upper / scale ** 2, rel=2e-14)


def test_near_zero_derivative_requires_proof_and_retains_large_curvature():
    epsilon = 2. ** -16
    coefficients = ((-.125, .75 + epsilon, -1.5, 1.), (.25, -1., 1., 0.))
    # The derivative's full-interval Bernstein box contains the origin even
    # though the curve is regular. Unproved regularity cannot authorize a bound.
    with pytest.raises(BoundUncertain):
        interval_bounds(coefficients)
    lo, hi = Fraction(1, 2) - Fraction(1, 4096), Fraction(1, 2) + Fraction(1, 4096)
    bounds, _ = assert_enclosure(coefficients, lo, hi)
    assert Decimal.from_float(bounds.curvature_upper) >= Decimal(2) / Decimal(epsilon) ** 2
    assert bounds.curvature_upper > 1e9
    zero = ((-.125, .75, -1.5, 1.), (.25, -1., 1., 0.))
    with pytest.raises(BoundUncertain):
        interval_bounds(zero, lo, hi)


@pytest.mark.parametrize('coefficients', [
    ((0., 1., 0., 0.), (0., 0., 1e-200, 0.)),
    ((0., 1., 0., 0.), (0., 0., 1.3e-162, 0.)),
    ((0., 2.9e-162, 0., 0.), (0., 0., 0., 0.)),
])
def test_squared_underflow_or_subnormal_conversion_never_grants_false_bound(coefficients):
    # sqrt(float(exact_squared)) loses a relative bound when the squared value
    # is subnormal, even if its square root is a perfectly normal binary64.
    try:
        assert_enclosure(coefficients)
    except BoundUncertain:
        pass  # Explicit numerical uncertainty is a valid fail-closed outcome.


def test_unrepresentable_curvature_rate_is_explicit_numerical_uncertainty():
    scale = 1e-160
    coefficients = ((0., scale, 0., 0.), (0., 0., scale, 0.))
    with pytest.raises(BoundUncertain):
        interval_bounds(coefficients)
