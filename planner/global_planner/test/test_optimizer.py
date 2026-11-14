"""The optimizer settles on one legal line from any start, and refuses what no car can drive."""
from dataclasses import replace
import math

from global_planner.car import Car
from global_planner.optimizer.solve import optimize, OptimizedLap, OptimizerError
from global_planner.optimizer.solve import OptimizerSettings
from global_planner.route.lap import centre_curve, LapCurve
from global_planner.route.sampling import sample_at_progress, sample_lap
from global_planner.route.track import Route
from legal import off_road
import pytest
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union
from tracks import SHORT, stadium, wobbled

BINDING = (0.1, 0.5)


@pytest.fixture(scope='module')
def route() -> Route:
    return stadium(straight=6., radius=1.5, width=1.4)


@pytest.fixture(scope='module')
def from_centre(route: Route, car: Car) -> OptimizedLap:
    return optimize(route, car)


def _peak_curvature(lap: LapCurve) -> float:
    """Return the largest curvature of lap, sampled every centimetre and at its knots."""
    return max(abs(v.curvature) for v in sample_lap(lap, 0.01, lap.q[:-1]))


def _legal_line_stays_legal_and_gets_gentler(result: OptimizedLap) -> bool:
    """Check that no pass from a legal line left it short of a row or raised its energy."""
    energy = [result.start_energy] + [p.energy for p in result.passes]

    return all(done.short_after == 0 and after <= before
               for before, after, done in zip(energy, energy[1:], result.passes)
               if done.short_before == 0)


def _start_heading(result: OptimizedLap) -> float:
    """Return the heading of the pose the car launches from."""
    tangent = sample_at_progress(result.lap, result.start_q).tangent

    return math.atan2(tangent[1], tangent[0])


def test_car_stays_on_legal_road(route: Route, car: Car, from_centre: OptimizedLap) -> None:
    assert off_road(route, car, from_centre.lap) == []
    assert from_centre.passes[-1].energy < from_centre.start_energy
    assert _legal_line_stays_legal_and_gets_gentler(from_centre)


def test_start_pose_is_in_the_box_within_its_heading(route: Route, car: Car,
                                                     from_centre: OptimizedLap) -> None:
    """The heading range is loose on the fixture's route and binds on a second one."""
    bound = stadium(straight=6., radius=1.5, width=1.4, heading_range=BINDING)
    result = optimize(bound, car)
    pose = sample_at_progress(result.lap, result.start_q)

    assert not BINDING[0] <= _start_heading(from_centre) <= BINDING[1]
    assert BINDING[0] - 1e-3 <= _start_heading(result) <= BINDING[1] + 1e-3
    assert Polygon(bound.start.zone).buffer(1e-9).covers(Point(pose.xy))
    assert off_road(bound, car, result.lap) == []


def test_short_sections_where_a_body_reaches_two_gates(car: Car) -> None:
    route = stadium(straight=6., radius=1.5, width=1.4, cuts_m=SHORT)

    assert off_road(route, car, optimize(route, car).lap) == []


@pytest.mark.parametrize('amplitude, waves, on_road', (
    (0.2, 5, True), (0.9, 3, False), (0.9, 4, False)),
    ids=('from the road', 'from off the road', 'from off the road, another way'))
def test_line_from_any_start_is_legal_and_as_gentle(route: Route, car: Car,
                                                    from_centre: OptimizedLap, amplitude: float,
                                                    waves: int, on_road: bool) -> None:
    """
    From a start on the road or well off it: a legal line, its energy within 0.5 %.

    The lines themselves may lie apart. Sliding a U-turn along its straights hardly changes
    the energy, and which of those lines comes out depends on the start (optimizer README).
    """
    initial = wobbled(centre_curve(route), amplitude, waves)
    road = unary_union([Polygon(s.polygon) for s in route.sections])
    other = optimize(route, car, initial=initial)
    energy = from_centre.passes[-1].energy

    assert all(road.covers(Point(v.xy)) for v in sample_lap(initial, 0.05)) == on_road
    assert off_road(route, car, other.lap) == []
    assert abs(other.passes[-1].energy - energy) <= 5e-3 * energy
    assert _legal_line_stays_legal_and_gets_gentler(other)


def test_turning_limit_holds_where_it_binds(route: Route, car: Car,
                                            from_centre: OptimizedLap) -> None:
    limited = replace(car, min_radius_m=1.8)
    result = optimize(route, limited)

    assert _peak_curvature(from_centre.lap) * limited.min_radius_m > 1.05
    assert _peak_curvature(result.lap) * limited.min_radius_m <= 1 + 1e-3
    assert off_road(route, limited, result.lap) == []


def test_tight_bend_settles_at_a_fine_spacing(car: Car) -> None:
    """A step as long as the spacing once sent this bend back and forth without end."""
    hairpin = stadium(straight=3., radius=0.8, width=0.7, cuts_m=(0., 2., 5., 8.))
    result = optimize(hairpin, car, OptimizerSettings(spacing_m=0.1))

    assert off_road(hairpin, car, result.lap) == []


def test_road_too_tight_for_the_car_is_refused(car: Car) -> None:
    hairpin = stadium(straight=3., radius=0.45, width=0.7, cuts_m=(0., 2., 4., 6.))

    with pytest.raises(OptimizerError, match='cannot get legal'):
        optimize(hairpin, car)


def test_start_box_without_a_point_is_refused(route: Route, car: Car) -> None:
    with pytest.raises(OptimizerError, match='start box'):
        optimize(route, car, OptimizerSettings(spacing_m=2.))


@pytest.mark.parametrize('settings', (
    {'step_m': 0.3}, {'settle_m': 0.06}, {'met_m': 0.01}, {'spacing_m': 0.}, {'max_passes': 0}),
    ids=('step over spacing', 'settle over half a step', 'met over settle', 'no spacing',
         'no passes'))
def test_settings_that_cannot_work_are_refused(settings: dict) -> None:
    with pytest.raises(OptimizerError, match='must be'):
        OptimizerSettings(**settings)
