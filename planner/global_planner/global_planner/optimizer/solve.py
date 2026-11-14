"""
The minimum-curvature line of a route for one car.

points:     the line is a ring of points, the first of each section on the gate into it and
            the others at equal gaps from there. They keep that spacing while they move.
passes:     each pass picks the walls near the current poses, then IPOPT moves the points as
            far as one step allows (problem.LapProblem).
step:       a pass counts only if the true rows bear out what its straight rows said. If
            they do not, even corrected, it is tried again with half the step; the step
            doubles again after a pass that counted without a correction.
settled:    when a pass that could have moved twice as far moves no point more than
            settle_m, or cannot lower the energy by more than settle_gain of it.
legal:      a line that settles while a row still falls short, or a full step that cannot
            bring the rows closer, has no legal way to go on: the road is narrower, or turns
            tighter, than the car can drive.
result:     the points become a lap curve again (refit_lap). The car follows that curve, so
            it is checked every check_m and at its knots: where the body plus margin pokes
            off its road, the poses around keep that much more clearance; where it turns
            tighter than the car can, the limit at the points drops by that factor; where the
            start pose faces outside its range, the range its point is held to turns back by
            that much. Then the passes go on, up to max_refinements times.
"""
from dataclasses import dataclass, replace
import math
import time

import numpy as np
import shapely
from shapely.geometry import Point, Polygon

from .free_space import Area, FreeSpace
from .problem import BodyWalls, GateRow, IpoptRun, LapProblem, PointWalls
from ..car import Car
from ..route.lap import centre_curve, LapCurve
from ..route.portals import portal_crossings
from ..route.sampling import (LapSample, refit_lap, sample_at_progress, sample_at_station,
                              sample_lap)
from ..route.track import Route
from ..route.zones import portal_zones

# What the turning limit and the start heading range are held to on the checked curve: this
# fraction of the limit, and as many radians. Below it the points say nothing about the curve.
_RESOLVED = 1e-3


class OptimizerError(ValueError):
    """The optimizer found no line, or none it can vouch for."""


@dataclass(frozen=True)
class OptimizerSettings:
    """
    How the optimizer works; planning choices, not car values.

    spacing_m:          the most two neighbouring points are apart at the start.
    step_m:             the most a coordinate may move in one pass; at most spacing_m, so
                        that neighbouring points cannot swap sides.
    settle_m:           the line has settled once no point moves more than this in a pass.
    settle_gain:        it has also settled once a pass cannot lower the energy by more than
                        this fraction of it, which is about what IPOPT resolves; at least
                        its tolerance.
    met_m:              how far short of met a row may be and still count as met; at most
                        settle_m, to which the line is resolved.
    check_m:            how finely the refitted curve is checked between its knots.
    elastic:            cost per metre a row falls short while the line recovers.
    max_passes:         passes allowed in each refinement before giving up.
    max_refinements:    rounds of tighter rows where the checked curve asks for them.
    tolerance:          IPOPT's convergence tolerance.
    max_iterations:     IPOPT iterations allowed in one pass.
    """

    spacing_m: float = 0.25
    step_m: float = 0.1
    settle_m: float = 1e-3
    settle_gain: float = 1e-6
    met_m: float = 1e-4
    check_m: float = 0.05
    elastic: float = 1e3
    max_passes: int = 100
    max_refinements: int = 5
    tolerance: float = 1e-8
    max_iterations: int = 500

    def __post_init__(self) -> None:
        positive = (self.spacing_m, self.step_m, self.settle_m, self.settle_gain, self.met_m,
                    self.check_m, self.elastic, self.tolerance, self.max_passes,
                    self.max_iterations)
        if not all(math.isfinite(v) and v > 0 for v in positive) or self.max_refinements < 0:
            raise OptimizerError('optimizer settings must be positive and finite')

        if (not 2 * self.settle_m <= self.step_m <= self.spacing_m
                or self.met_m > self.settle_m or self.tolerance > self.settle_gain):
            raise OptimizerError('step_m must be at most spacing_m and at least twice settle_m, '
                                 'met_m at most settle_m, and tolerance at most settle_gain')


@dataclass(frozen=True)
class Pass:
    """
    The record of one pass that counted.

    refinement:     the refinement round the pass belongs to, from 0.
    energy:         curvature energy after the pass, sum of k^2 ds.
    move_m:         the largest move of any point.
    step_m:         the most a coordinate was allowed to move.
    short_before:   what the rows fell short in total when the pass began; 0 for a legal line.
    short_after:    what they still fell short when it ended.
    seconds:        wall time of the pass.
    ipopt:          what IPOPT did.
    """

    refinement: int
    energy: float
    move_m: float
    step_m: float
    short_before: float
    short_after: float
    seconds: float
    ipopt: IpoptRun


@dataclass(frozen=True)
class OptimizedLap:
    """
    The optimized lap and how it was found.

    lap:            the optimized lap curve.
    start_q:        lap progress of the pose the car launches from, in the start box.
    start_energy:   the curvature energy of the points before the first pass.
    passes:         every pass that counted, in order, across all refinements.
    refinements:    rounds of tighter rows the checked curve needed.
    """

    lap: LapCurve
    start_q: float
    start_energy: float
    passes: tuple[Pass, ...]
    refinements: int


@dataclass(frozen=True)
class _Tightening:
    """
    What the checked curve asked for beyond the car's own limits.

    clearance:  extra clearance per piece of the curve, for the poses on it, in metres.
    curvature:  factor on the car's turning limit, at most 1.
    heading:    how far the range the start point is held to is turned, in radians, to the
                left if positive.
    """

    clearance: np.ndarray
    curvature: float = 1.
    heading: float = 0.


@dataclass(frozen=True)
class _Excess:
    """
    Where the checked curve goes beyond what the points were held to.

    off_road:       per piece of the curve, how far the body plus margin pokes off its road.
    too_tight:      how many times tighter than the car can the curve turns at most; 1 if not.
    heading_off:    how far outside its range the start pose faces, in radians: positive
                    to the left of it, negative to the right.
    """

    off_road: dict[int, float]
    too_tight: float
    heading_off: float

    def __bool__(self) -> bool:
        return bool(self.off_road) or self.too_tight > 1 or self.heading_off != 0


def _points(lap: LapCurve, spacing: float) -> tuple[list[LapSample], list[GateRow]]:
    """Return samples evenly spaced along lap within each section, and each section's gate."""
    bounds = lap.route.section_bounds
    samples, gates = [], []
    for j, (q0, q1) in enumerate(zip(bounds, bounds[1:])):
        s0, s1 = lap.station_at_progress(q0), lap.station_at_progress(min(q1, lap.period))
        count = max(1, math.ceil((s1 - s0) / spacing))
        gates.append(GateRow(len(samples), lap.route.portals[j - 1].gate))
        samples.append(sample_at_progress(lap, q0))
        samples += [sample_at_station(lap, s0 + (s1 - s0) * k / count) for k in range(1, count)]

    return samples, gates


def _heading_off(tangent: tuple[float, float], heading_range: tuple[float, float]) -> float:
    """
    Return how far tangent faces outside heading_range, in radians; 0 inside it.

    Positive to the left of the range, negative to the right.
    """
    first, last = heading_range
    middle, width = (first + last) / 2, (last - first) / 2
    angle = (math.atan2(tangent[1], tangent[0]) - middle + math.pi) % (2 * math.pi) - math.pi

    return math.copysign(max(0., abs(angle) - width), angle)


def _start_point(route: Route, centre: LapCurve, samples: list[LapSample]) -> int:
    """
    Return the point the car launches from.

    Of the samples whose place on the centre curve lies in the start box, those facing within
    the start heading range if there are any, which tells two passes of a track through one
    box apart; of these, the one nearest the middle of the box.
    """
    box = Polygon(route.start.zone)
    middle = np.asarray(box.centroid.coords[0])
    places = [sample_at_progress(centre, v.q) for v in samples]
    inside = [i for i, v in enumerate(places) if box.covers(Point(v.xy))]
    if not inside:
        raise OptimizerError('no point of the line lies in the start box: the box is shorter '
                             'than the spacing, or off the centre curve')

    facing = [i for i in inside
              if _heading_off(places[i].tangent, route.start.heading_range) == 0]

    return min(facing or inside, key=lambda i: np.linalg.norm(np.asarray(places[i].xy) - middle))


def _reserve(car: Car, spacing: float) -> float:
    """
    Return the clearance to keep for the curve between two neighbouring poses.

    Between two poses a body corner at distance r from base_link runs on an arc that lies
    d^2 k (1 + r k) / 8 off the straight line between its two places, for poses d apart on a
    curve of curvature k. Taken for poses half a spacing apart at the car's turning limit,
    it spares most lines a refinement; what it misses, where gaps have grown, the checked
    curve finds.
    """
    d, k = spacing / 2, 1 / car.min_radius_m

    return d ** 2 * k * (1 + car.corner_m * k) / 8


def _tightened(tightening: _Tightening, excess: _Excess, settle_m: float) -> _Tightening:
    """
    Return tightening with what excess asks for added.

    Every limit moves by what the curve is over it plus what the line is resolved to:
    settle_m of clearance, _RESOLVED of the turning limit and of the heading range.
    """
    clearance = tightening.clearance.copy()
    for piece, depth in excess.off_road.items():
        clearance[piece] += depth + settle_m

    curvature, heading = tightening.curvature, tightening.heading
    if excess.too_tight > 1:
        curvature /= excess.too_tight * (1 + _RESOLVED)

    if excess.heading_off:
        heading -= excess.heading_off + math.copysign(_RESOLVED, excess.heading_off)

    return replace(tightening, clearance=clearance, curvature=curvature, heading=heading)


class _Optimization:
    """
    One optimization: what stays the same through its passes, and the passes themselves.

    samples:        the starting points on the initial curve, with their q and section.
    gate_points:    the first point of every section.
    start_point:    the point the car launches from.
    start_width:    half the start heading range; None when it is a full turn.
    box:            the start box.
    clearance:      what the body keeps from every wall: the margin and the reserve.
    move, reach:    the most a point, and a body corner, can move in one pass.
    """

    def __init__(self, route: Route, car: Car, settings: OptimizerSettings,
                 initial: LapCurve | None) -> None:
        self.route, self.car, self.settings = route, car, settings
        centre = centre_curve(route)
        self.initial = centre if initial is None else initial
        self.samples, gates = _points(self.initial, settings.spacing_m)
        self.gate_points = frozenset(row.point for row in gates)
        self.start_point = _start_point(route, centre, self.samples)
        self.box = Area(Polygon(route.start.zone))
        self.space = FreeSpace(route, portal_zones(route, car.reach_m))
        self.clearance = car.margin_m + _reserve(car, settings.spacing_m)

        first, last = route.start.heading_range
        full_turn = last - first >= 2 * math.pi
        middle = (first + last) / 2
        self.start_width = None if full_turn else (last - first) / 2

        """
        In one pass a point moves at most a step along each axis, and a pose turns at most
        `turn`; a pose between two points also shifts with the two headings it hangs on.
        That bounds how far a body corner can get.
        """
        count = len(self.samples)
        turn = settings.step_m / settings.spacing_m
        self.move = math.sqrt(2) * settings.step_m
        self.reach = self.move + (car.corner_m + settings.spacing_m / 4) * turn
        self.problem = LapProblem(
            count, car, settings.spacing_m, [i for i in range(count) if i not in self.gate_points],
            gates, None if full_turn else (self.start_point, (math.cos(middle), math.sin(middle))),
            turn, settings.elastic, settings.met_m, settings.settle_gain, settings.tolerance,
            settings.max_iterations)
        self.passes = []

    def _walls(self, xy: np.ndarray,
               extra: np.ndarray) -> tuple[list[BodyWalls], list[PointWalls]]:
        """
        Return the walls of every body pose and of every base_link for one pass.

        poses:  the body at every point and halfway to the next one, and wherever on the way
                a wall corner passes its front or its rear (free_space).
        extra:  the clearance each piece of the curve keeps on top of the usual.
        """
        car, n = self.car, len(xy)
        owners = [v.section_uid for v in self.samples]
        heading = self.problem.evaluate(xy)[2]
        middle, middle_heading = self.problem.poses(xy, heading, range(n), np.full(n, 0.5))
        bodies, points = [], []
        for i, owner in enumerate(owners):
            road, following = self.space.road(owner), (i + 1) % n
            here = (tuple(xy[i]), tuple(heading[i]))
            halfway = (tuple(middle[i]), tuple(middle_heading[i]))
            there = (tuple(xy[following]), tuple(heading[following]))

            # A pose at a point lies on the pieces before and after it, the others on its own.
            on_piece = self.clearance + extra[i]
            at_point = self.clearance + max(extra[i - 1], extra[i])
            for along, pose, clearance in ((0., here, at_point), (0.5, halfway, on_piece)):
                walls = road.body_walls(car, *pose, self.reach + clearance)
                bodies.append(BodyWalls(i, along, clearance, *walls))

            for along, before, after in ((0., here, halfway), (0.5, halfway, there)):
                for moment, vertex in road.passing(car, before, after, self.reach + on_piece):
                    bodies.append(BodyWalls(i, along + moment / 2, on_piece, (), (vertex,)))

            # The first point of a section is held on its gate; the bodies keep it between walls.
            if i not in self.gate_points:
                planes = self.space.section(owner).point_planes(tuple(xy[i]), self.move)
                points.append(PointWalls(i, planes))

        planes = self.box.point_planes(tuple(xy[self.start_point]), self.move)
        points.append(PointWalls(self.start_point, planes))

        return bodies, points

    def _settle(self, xy: np.ndarray, tightening: _Tightening, refinement: int) -> np.ndarray:
        """Run passes from xy until the line has settled; return its points."""
        settings = self.settings
        limit = tightening.curvature / self.car.min_radius_m
        facing = None
        if self.start_width is not None:
            facing = (tightening.heading - self.start_width, tightening.heading + self.start_width)

        step, walls = settings.step_m, None
        for _ in range(settings.max_passes):
            began = time.monotonic()

            # The walls depend on the points alone: a pass tried again keeps them.
            walls = walls or self._walls(xy, tightening.clearance)
            result = self.problem.solve(xy, *walls, limit, facing, step)
            if not result.accepted:
                step /= 2
                if step < settings.settle_m:
                    raise OptimizerError(f'pass {len(self.passes) + 1} found no step that its '
                                         f'rows bear out (IPOPT: {result.ipopt.status})')

                continue

            move = float(np.max(np.linalg.norm(result.xy - xy, axis=1)))
            xy, walls = result.xy, None
            self.passes.append(Pass(
                refinement, self.problem.evaluate(xy)[0], move, step,
                result.short_before, result.short_after, time.monotonic() - began, result.ipopt))

            # A full step that cannot bring the rows settle_m closer, or halfway if nearer.
            closer = result.short_before - result.short_promised
            stuck = (step == settings.step_m and result.short_before > 0
                     and closer < min(settings.settle_m, result.short_before / 2))
            settled = move <= settings.settle_m and step >= 2 * settings.settle_m
            if stuck or (settled and result.short_after > 0):
                raise OptimizerError('the line cannot get legal: the road is narrower, or turns '
                                     'tighter, than the car can drive at this spacing')

            if settled:
                return xy

            if result.trusted:
                step = min(2 * step, settings.step_m)

        raise OptimizerError(f'the line did not settle in {settings.max_passes} passes')

    def _check(self, lap: LapCurve, start_q: float) -> _Excess:
        """
        Return where the refitted curve goes beyond what its points were held to.

        It is sampled every check_m and at its knots, where its curvature peaks.
        """
        car, off_road, too_tight = self.car, {}, 1.
        for v in sample_lap(lap, self.settings.check_m, lap.q[:-1]):
            if not self.space.section(v.section_uid).covers(Point(v.xy)):
                raise OptimizerError(f'base_link leaves its section near ({v.xy[0]:.2f}, '
                                     f'{v.xy[1]:.2f}) in section {v.section_uid}')

            too_tight = max(too_tight, abs(v.curvature) * car.min_radius_m)
            road = self.space.road_at(v.xy, v.section_uid)
            body = car.body(v.xy, v.tangent).buffer(car.margin_m)
            if not road.covers(body):
                outside = shapely.get_coordinates(body.difference(road.polygon))
                depth = float(np.max(shapely.distance(road.polygon, shapely.points(outside))))
                off_road[v.segment] = max(off_road.get(v.segment, 0.), depth)

        pose = sample_at_progress(lap, start_q)
        if not self.box.covers(Point(pose.xy)):
            raise OptimizerError('the line does not pass through the start box')

        heading_off = 0.
        if self.start_width is not None:
            heading_off = _heading_off(pose.tangent, self.route.start.heading_range)

        return _Excess(off_road, too_tight if too_tight > 1 + _RESOLVED else 1.,
                       heading_off if abs(heading_off) > _RESOLVED else 0.)

    def run(self) -> OptimizedLap:
        """Return the optimized lap."""
        settings, samples = self.settings, self.samples

        # The samples are evenly spaced along the curve; the points keep equal gaps, on gates.
        xy = self.problem.evened(np.array([v.xy for v in samples]))
        if xy is None:
            raise OptimizerError('the starting line cannot be spaced evenly between its gates')

        start_energy = self.problem.evaluate(xy)[0]
        start_q = samples[self.start_point].q
        tightening = _Tightening(np.zeros(len(xy)))
        for refinement in range(settings.max_refinements + 1):
            xy = self._settle(xy, tightening, refinement)
            lap = refit_lap(self.initial, samples, [tuple(p) for p in xy])
            excess = self._check(lap, start_q)
            if not excess:
                break

            tightening = _tightened(tightening, excess, settings.settle_m)

        else:
            raise OptimizerError(f'the curve still leaves the road, turns too tight or starts '
                                 f'off its heading after {settings.max_refinements} refinements')

        # Raises unless the curve crosses every gate once, forwards and in lap order.
        portal_crossings(lap)

        return OptimizedLap(lap, start_q, start_energy, tuple(self.passes), refinement)


def optimize(route: Route, car: Car, settings: OptimizerSettings = OptimizerSettings(),
             initial: LapCurve | None = None) -> OptimizedLap:
    """Return the minimum-curvature lap for car, starting from the centre curve or initial."""
    return _Optimization(route, car, settings, initial).run()
