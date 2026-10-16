"""Independent minimal shared-cap cancellation and strict F1 preservation."""
from dataclasses import replace
from fractions import Fraction as F
import math

import pytest

from global_planner import _route_geometry as geometry
from global_planner.route_corridor import _merge, _normal_geometry
from global_planner.route_input import Occurrence


P = (10.346273849151595, -10.953427375385925)
N = (.9350684075601509, .3544673090468617)
A = (9.693644707538146, -11.20655817764086)
B = (10.765821154985087, -10.790700430881152)
SOURCE = ((9.339177398491284, -10.27148977008071), A, B,
          (10.411353845938224, -9.855632023321002))
TARGET = (A, (10.048112016585009, -12.14162658520101),
          (11.12028846403195, -11.725768838441303), B)


def exact_root(p, n, a, b):
    x, y = F(a[0]) - F(p[0]), F(a[1]) - F(p[1])
    vx, vy = F(b[0]) - F(a[0]), F(b[1]) - F(a[1])
    return (x * vy - y * vx) / (F(n[0]) * vy - F(n[1]) * vx)


def test_exact_shared_cap_two_quadrilaterals_have_identical_cuts():
    assert exact_root(P, N, A, B) == exact_root(P, N, B, A)
    assert exact_root(P, N, A, B) == F(-6493513456432416, 89282567569951896214720469081)
    first = geometry.line_intervals(P, N, SOURCE, ((A, B),))
    second = geometry.line_intervals(P, N, TARGET, ((A, B),))
    assert len(first) == len(second) == 1
    assert first[0][1] == second[0][0], (first, second)
    assert len(_merge(first + second, lambda _: True)) == 1


@pytest.mark.parametrize('angle', (0., .37, 1.1, math.pi / 2))
@pytest.mark.parametrize('translation', ((0., 0.), (19.25, -7.5), (10000., -20000.)))
def test_shared_cap_and_polygon_orientation_invariance(angle, translation):
    c, s = math.cos(angle), math.sin(angle)

    def point(p):
        return (c * p[0] - s * p[1] + translation[0],
                s * p[0] + c * p[1] + translation[1])

    p, a, b = point(P), point(A), point(B)
    n = (c * N[0] - s * N[1], s * N[0] + c * N[1])
    source, target = tuple(map(point, SOURCE)), tuple(map(point, TARGET))
    first = geometry.line_intervals(p, n, source, ((a, b),))
    second = geometry.line_intervals(p, n, target, ((a, b),))
    assert first[0][1] == second[0][0], (angle, translation, first, second)
    assert geometry.line_intervals(p, n, source[::-1], ((a, b),)) == first
    assert geometry.line_intervals(p, n, target[::-1], ((a, b),)) == second


@pytest.mark.parametrize('gap', (1e-10, .4e-9, 5e-9, 1e-6))
@pytest.mark.parametrize('angle', (0., .37, 1.1))
@pytest.mark.parametrize('translation', ((0., 0.), (10000., -20000.)))
def test_distinct_actual_gaps_are_never_merged(gap, angle, translation):
    c, s = math.cos(angle), math.sin(angle)

    def point(p):
        return (c * p[0] - s * p[1] + translation[0],
                s * p[0] + c * p[1] + translation[1])

    below = Occurrence('below', 'ground', tuple(map(point, ((-2, -.5), (2, -.5)))),
                       tuple(map(point, ((-2, 0), (2, 0)))),
                       tuple(map(point, ((-2, -1), (2, -1)))), ((0, 4),))
    above = replace(below, id='above', seed=tuple(map(point, ((-2, .5), (2, .5)))),
                    left=tuple(map(point, ((-2, 1), (2, 1)))),
                    right=tuple(map(point, ((-2, gap), (2, gap)))))
    support = tuple(map(point, ((-3, -2), (3, -2), (3, 2), (-3, 2))))
    unrelated_cap = tuple(map(point, ((0, -1), (0, 1))))
    lo, hi = _normal_geometry((below, above), point((0, -.5)), (c, s),
                              support, (unrelated_cap,))
    assert -.500001 < lo < -.499999
    assert .499999 < hi < .500001
    # A positive gap remains disjoint even below EPS; no approximate touching.
    assert len(_merge(((-1., 0.), (gap, 1.)), lambda _: True)) == 2


@pytest.mark.parametrize('angle,translation', ((0., (0., 0.)), (.37, (0., 0.)),
                                               (1.1, (10000., -20000.))))
@pytest.mark.parametrize('tip_dx', (-1e-6, -5e-9, 0., 1e-6))
def test_original_f1_tangent_side_contact_stays_a_cut(angle, translation, tip_dx):
    c, s = math.cos(angle), math.sin(angle)

    def point(p):
        return (c * p[0] - s * p[1] + translation[0],
                s * p[0] + c * p[1] + translation[1])

    occurrence = Occurrence(
        'strip', 'ground', tuple(map(point, ((0, 0), (10, 0)))),
        tuple(map(point, ((0, 2), (10, 2), (10, 1), (5 + tip_dx, .75),
                          (10, .5), (10, .1)))),
        tuple(map(point, ((0, -1), (10, -1)))), ((0, 4),))
    lo, hi = _normal_geometry((occurrence,), point((5, 0)), (c, s))
    assert lo == pytest.approx(-1, abs=2e-9)
    if tip_dx <= 0:
        assert .7499998 < hi <= .75
    else:
        assert hi == pytest.approx(2, abs=2e-9)
