"""Independent exact/110-digit controls for numerical certification primitives.

These are regression challenges, not a sampled replacement for the certificate.
Expected arc values use a closed antiderivative rather than another quadrature.
"""
from decimal import Decimal, localcontext
from fractions import Fraction
import math
import random

from global_planner.route_reference import CubicSegment, GeometryError, NumericPolicy
from global_planner.route_validate import (
    BoundUncertain, Footprint, _rectangle, _sqrt, interval_bounds,
)


def _decimal(value):
    if isinstance(value, Decimal):
        return value
    exact = Fraction(value)
    return Decimal(exact.numerator) / Decimal(exact.denominator)


def test_exact_outward_sqrt_bounds_across_representable_scales():
    rng = random.Random(0xC0FFEE27)
    supported = uncertain = 0
    for _ in range(1000):
        exponent = rng.randrange(-2500, 2300)
        value = Fraction(rng.randrange(1, 2 ** 53), rng.randrange(1, 2 ** 53))
        value *= Fraction(2 ** exponent) if exponent >= 0 else Fraction(1, 2 ** -exponent)
        try:
            lower, upper = _sqrt(value, False), _sqrt(value, True)
        except BoundUncertain:
            uncertain += 1
            continue
        # This compares exact rationals and never invokes an expected sqrt.
        assert Fraction(lower) ** 2 <= value <= Fraction(upper) ** 2
        supported += 1
    assert supported and uncertain


def test_midpoint_rectangle_normalization_encloses_independent_exact_frame():
    rng = random.Random(0xDEC1A127)
    with localcontext() as context:
        context.prec = 110
        for _ in range(256):
            speed, angle = 10. ** rng.uniform(-6, 7.3), rng.uniform(-math.pi, math.pi)
            dx, dy = speed * math.cos(angle), speed * math.sin(angle)
            coefficients = ((rng.uniform(-1e8, 1e8), dx, 0., 0.),
                            (rng.uniform(-1e8, 1e8), dy, 0., 0.))
            extent = 10. ** rng.uniform(-12, 6)
            body = Footprint(extent, extent * .37, extent * .71, 0.)
            bounds = interval_bounds(coefficients)
            exact = tuple(tuple(Fraction(x) for x in row) for row in coefficients)
            rectangle, allowance = _rectangle(exact, Fraction(1, 3), body, bounds)
            norm = (_decimal(dx) ** 2 + _decimal(dy) ** 2).sqrt()
            tx, ty = _decimal(dx) / norm, _decimal(dy) / norm
            px = _decimal(coefficients[0][0]) + _decimal(dx) / 3
            py = _decimal(coefficients[1][0]) + _decimal(dy) / 3
            half_width = _decimal(body.width_m) / 2
            corners = ((body.front_m, half_width), (-body.rear_m, half_width),
                       (-body.rear_m, -half_width), (body.front_m, -half_width))
            for actual, (x, y) in zip(rectangle, corners):
                expected_x = px + _decimal(x) * tx - _decimal(y) * ty
                expected_y = py + _decimal(x) * ty + _decimal(y) * tx
                error2 = ((_decimal(actual[0]) - expected_x) ** 2 +
                          (_decimal(actual[1]) - expected_y) ** 2)
                assert error2 <= _decimal(allowance) ** 2


def test_shared_arc_primitive_against_closed_near_stationary_antiderivative():
    supported = 0
    with localcontext() as context:
        context.prec = 110
        for center in (Fraction(1, 8), Fraction(19661, 65536), Fraction(1, 2)):
            for scale in (.25, 1., 32.):
                for epsilon in (2. ** -25, 2. ** -16, .5):
                    coefficients = ((0., -scale * float(center), scale / 2, 0.),
                                    (0., scale * epsilon, 0., 0.))
                    try:
                        segment = CubicSegment(coefficients, NumericPolicy(quad_limit=256))
                    except GeometryError:
                        continue  # Resource/regularity uncertainty cannot grant acceptance.
                    supported += 1
                    ss, ee, aa = _decimal(scale), _decimal(scale * epsilon), _decimal(center)

                    def primitive(parameter):
                        z = ss * (parameter - aa)
                        zz = abs(z / ee)
                        asinh = (zz + (zz * zz + 1).sqrt()).ln()
                        if z < 0:
                            asinh = -asinh
                        return (z * (z * z + ee * ee).sqrt() + ee * ee * asinh) / (2 * ss)

                    for parameter in (1., float(center), 1. / 3, 2. / 3):
                        observed, allowance = segment._integrate(parameter)
                        expected = primitive(_decimal(parameter)) - primitive(Decimal(0))
                        assert abs(_decimal(observed) - expected) <= _decimal(allowance)
        assert supported
