"""
The smoothest line of a route for one car and, given its speed limits, the fastest one.

points:     the line is a ring of points, the first of each section on the gate into it and
            the others at equal gaps from there. They keep that spacing while they move.
passes:     each pass picks the walls near the current poses, then IPOPT moves the points as
            far as one step allows (problem.LapProblem).
step:       a pass counts only if the true rows bear out what its straight rows said. If
            they do not, even corrected, it is tried again with half the step; the step
            doubles again after a pass that counted without a correction.
settled:    when a pass that could have moved twice as far moves no point more than
            settle_m, or cannot lower its cost by more than settle_gain of it. The cost
            is the energy, or its mix with the lap time once that is aimed at.
legal:      a line that settles while a row still falls short, or a full step that cannot
            bring the rows closer, has no legal way to go on: the road is narrower, or turns
            tighter, than the car can drive.
result:     the points become a lap curve again (refit_lap). The car follows that curve, so
            it is checked every check_m and at its knots: where the body plus margin pokes
            off its road, the poses around keep that much more clearance; where it turns
            tighter than the car can, the limit at the points drops by that factor. Then
            the passes go on, up to max_refinements times.
start:      the lap starts on the route's start line, the gate into the first section. The
            first point is held on it like every section's first point on its gate, free
            from wall to wall, so the start pins nothing about the line across the road.
fastest:    given the car's speed limits, the passes go on from that smoothest line with a
            second aim: the lap time, with a share of the curvature kept so that the line
            does not turn harsh. Both are measured against the smoothest line, which makes
            `smoothness` a plain number: 0.1 gives up ten per cent of smoothness for one
            per cent of lap time. The lap time the passes go by is that of the points,
            driven as fast as the car can (speed/points.py). The one reported is the speed
            profile's of the finished curve, which can differ from it by a per cent or two.
            Each of the two aims may tighten the rows up to max_refinements times. If the
            finished line is still slower than the smoothest one, which the passes can end
            on when smoothness is low and they get stuck, the smoothest line is kept: what
            is asked for the lap time never makes it longer.
shortest:   asked for instead, the passes go on from the smoothest line to lower its length,
            with the same share of the curvature kept. The car still has to steer it: the
            line turns no tighter than the car can, and its body keeps the margin. It is
            the line the overtaking sectors are tuned on (ros_export).
"""
from dataclasses import dataclass, replace
import logging
import math
import time

import numpy as np
import shapely
from shapely.geometry import Point

from .free_space import FreeSpace
from .problem import BodyWalls, GateRow, IpoptRun, LapProblem, PointWalls
from ..car import Car, CarLimits, is_number
from ..route.lap import centre_curve, LapCurve
from ..route.portals import portal_crossings
from ..route.sampling import (LapSample, refit_lap, sample_at_progress, sample_at_station,
                              sample_lap)
from ..route.track import Route
from ..route.zones import portal_zones
from ..speed.errors import SpeedError
from ..speed.speeds import speed_profile, SpeedProfile

# Where a run says how far it is. A library does not print: whoever calls it listens here, or
# not at all (the Operational Centre shows it, export_route prints it). INFO is one short
# line a step, fit for a status line; DEBUG is every figure a pass was judged by.
_LOG = logging.getLogger(__name__)

# What the turning limit is held to on the checked curve: this fraction of it. Below it the
# points say nothing about the curve.
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
    settle_gain:        it has also settled once a pass cannot lower its cost by more than
                        this fraction of it, which is about what IPOPT resolves; at least
                        its tolerance.
    smoothness:         when the fastest line is asked for: the share of the curvature
                        kept in what the passes lower, next to the lap time, each measured
                        against the smoothest line. A large value is the smoothest line
                        again. 0 asks for the fastest line whatever it does to the steering,
                        and often fails: the passes get stuck (optimizer README).
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

    # Provisional. To be chosen from laps driven on the real car, not from made-up tracks.
    smoothness: float = 0.1
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

        if not is_number(self.smoothness) or self.smoothness < 0:
            raise OptimizerError('smoothness must be a finite number, not negative')

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
    time_s:         lap time of the points after the pass, driven as fast as the car can;
                    None for a pass that aimed at curvature alone.
    """

    refinement: int
    energy: float
    move_m: float
    step_m: float
    short_before: float
    short_after: float
    seconds: float
    ipopt: IpoptRun
    time_s: float | None = None


@dataclass(frozen=True)
class OptimizedLap:
    """
    The optimized lap and how it was found.

    lap:            the optimized lap curve.
    start_q:        lap progress where the lap starts: 0, where the line crosses the start
                    line (Route.start_line).
    start_energy:   the curvature energy of the points before the first pass.
    passes:         every pass that counted, in order, across all refinements.
    refinements:    rounds of tighter rows the checked curve needed.
    profile:        the speeds of the lap, if the car's limits were given; None otherwise.
    smoothest_time_s:   the lap time of the smoothest line's points, which the lap times of
                    the passes are measured against; None unless the fastest was asked for.
    """

    lap: LapCurve
    start_q: float
    start_energy: float
    passes: tuple[Pass, ...]
    refinements: int
    profile: SpeedProfile | None = None
    smoothest_time_s: float | None = None


@dataclass(frozen=True)
class _Tightening:
    """
    What the checked curve asked for beyond the car's own limits.

    clearance:  extra clearance per piece of the curve, for the poses on it, in metres.
    curvature:  factor on the car's turning limit, at most 1.
    """

    clearance: np.ndarray
    curvature: float = 1.


@dataclass(frozen=True)
class _Excess:
    """
    Where the checked curve goes beyond what the points were held to.

    off_road:       per piece of the curve, how far the body plus margin pokes off its road.
    too_tight:      how many times tighter than the car can the curve turns at most; 1 if not.
    """

    off_road: dict[int, float]
    too_tight: float

    def __bool__(self) -> bool:
        return bool(self.off_road) or self.too_tight > 1


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
    settle_m of clearance, _RESOLVED of the turning limit.
    """
    clearance = tightening.clearance.copy()
    for piece, depth in excess.off_road.items():
        clearance[piece] += depth + settle_m

    curvature = tightening.curvature
    if excess.too_tight > 1:
        curvature /= excess.too_tight * (1 + _RESOLVED)

    return replace(tightening, clearance=clearance, curvature=curvature)


class _Optimization:
    """
    One optimization: what stays the same through its passes, and the passes themselves.

    samples:        the starting points on the initial curve, with their q and section.
    gate_points:    the first point of every section; the very first is on the start line.
    clearance:      what the body keeps from every wall: the margin and the reserve.
    move, reach:    the most a point, and a body corner, can move in one pass.
    """

    def __init__(self, route: Route, car: Car, settings: OptimizerSettings,
                 initial: LapCurve | None, limits: CarLimits | None, shortest: bool) -> None:
        self.route, self.car, self.settings, self.limits = route, car, settings, limits
        self.shortest, self.aim = shortest, 'Smoothest'
        if limits is not None:
            turning = limits.wheelbase / math.tan(limits.max_steering_angle)
            if limits.name != car.name or not math.isclose(turning, car.min_radius_m):
                raise OptimizerError(
                    f'the body is of {car.name}, turning on {car.min_radius_m:.3f} m, and '
                    f'the limits of {limits.name}, turning on {turning:.3f} m: both must '
                    f'come from one car file')

        centre = centre_curve(route)
        self.initial = centre if initial is None else initial
        self.samples, gates = _points(self.initial, settings.spacing_m)
        self.gate_points = frozenset(row.point for row in gates)
        self.space = FreeSpace(route, portal_zones(route, car.reach_m))
        self.clearance = car.margin_m + _reserve(car, settings.spacing_m)

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
            gates, turn, settings.elastic, settings.met_m, settings.settle_gain,
            settings.tolerance, settings.max_iterations, limits)
        self.passes = []
        self.refinements = 0
        _LOG.debug('route %s: %d sections, centre curve %.2f m; %s, body %.3f x %.3f m, margin '
                   '%.3f m, turning radius %.3f m', route.digest[:12], len(route.sections),
                   centre.curve.length, car.name, car.body_front_m + car.body_rear_m,
                   car.width_m, car.margin_m, car.min_radius_m)
        _LOG.debug('%d points, %d of them on gates, the first on the start line; clearance '
                   'held %.4f m; %s', count, len(gates), self.clearance, settings)
        _LOG.debug('aim: %s', f'shortest line with smoothness {settings.smoothness:g}'
                   if shortest else 'smoothest line only' if limits is None
                   else f'fastest line with smoothness {settings.smoothness:g}; {limits}')

    def _caps(self, xy: np.ndarray) -> np.ndarray:
        """
        Return the track's speed limit at every point.

        Within a portal's reach it is the lower of the two sections' limits. A point also
        keeps to its two neighbours' limits, so that a gap is driven at the lower of its ends.
        """
        limit = {s.uid: s.max_speed_mps for s in self.route.sections}
        owners = np.array([v.section_uid for v in self.samples])
        caps = np.array([limit[uid] for uid in owners])
        for zone in self.space.zones:
            for faster, slower in ((zone.portal.source, zone.portal.target),
                                   (zone.portal.target, zone.portal.source)):
                at = np.flatnonzero(owners == faster)
                if limit[slower] < limit[faster] and len(at):
                    within = at[np.asarray(zone.gap(xy[at])) <= 0]
                    caps[within] = np.minimum(caps[within], limit[slower])

        return np.minimum.reduce((caps, np.roll(caps, 1), np.roll(caps, -1)))

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

        return bodies, points

    def _settle(self, xy: np.ndarray, tightening: _Tightening, timed: bool) -> np.ndarray:
        """
        Run passes from xy until the line has settled; return its points.

        timed:  whether the passes aim at lap time as well as curvature.
        """
        settings = self.settings
        limit = tightening.curvature / self.car.min_radius_m
        step, walls, cap = settings.step_m, None, None
        for _ in range(settings.max_passes):
            began = time.monotonic()

            # Walls and speed limits depend on the points alone: a pass tried again keeps them.
            if walls is None:
                walls = self._walls(xy, tightening.clearance)
                cap = self._caps(xy) if timed else None

            result = self.problem.solve(xy, *walls, limit, step, cap)
            if not result.accepted:
                _LOG.debug('pass %d not counted at step %.4f m (IPOPT %s, %d iterations, %d '
                           'solves): trying half the step', len(self.passes) + 1, step,
                           result.ipopt.status, result.ipopt.iterations, result.ipopt.solves)
                step /= 2
                if step < settings.settle_m:
                    raise OptimizerError(f'pass {len(self.passes) + 1} found no step that '
                                         f'counts: none kept its rows and lowered its cost '
                                         f'(IPOPT: {result.ipopt.status})')

                continue

            move = float(np.max(np.linalg.norm(result.xy - xy, axis=1)))
            xy, walls = result.xy, None
            lap_time = self.problem.fastest(xy, self._caps(xy))[0] if timed else None
            self.passes.append(Pass(
                self.refinements, self.problem.evaluate(xy)[0], move, step, result.short_before,
                result.short_after, time.monotonic() - began, result.ipopt, lap_time))
            _LOG.info('%s line, pass %d%s', self.aim, len(self.passes),
                      f', lap {lap_time:.2f} s' if timed else '')
            done = self.passes[-1]
            _LOG.debug('pass %d: energy %.6g, moved %.2f mm at step %.1f mm, short %.3g -> '
                       '%.3g m, %s, %.2f s (IPOPT %s, %d iterations, %d rows, %d solves)',
                       len(self.passes), done.energy, move * 1e3, step * 1e3,
                       done.short_before + 0., done.short_after + 0.,   # no -0
                       'trusted' if result.trusted else 'corrected', done.seconds,
                       done.ipopt.status, done.ipopt.iterations, done.ipopt.rows,
                       done.ipopt.solves)

            # A full step that cannot bring the rows settle_m closer, or halfway if nearer.
            closer = result.short_before - result.short_promised
            stuck = (step == settings.step_m and result.short_before > 0
                     and closer < min(settings.settle_m, result.short_before / 2))
            settled = move <= settings.settle_m and step >= 2 * settings.settle_m
            if stuck or (settled and result.short_after > 0):
                raise OptimizerError('the line cannot get legal: the road is narrower, or turns '
                                     'tighter, than the car can drive at this spacing')

            if settled:
                _LOG.debug('settled after pass %d: no point moved more than %.1f mm',
                           len(self.passes), settings.settle_m * 1e3)
                return xy

            if result.trusted:
                step = min(2 * step, settings.step_m)

        raise OptimizerError(f'the line did not settle in {settings.max_passes} passes')

    def _check(self, lap: LapCurve) -> _Excess:
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

        return _Excess(off_road, too_tight if too_tight > 1 + _RESOLVED else 1.)

    def run(self) -> OptimizedLap:
        """Return the optimized lap."""
        settings, samples = self.settings, self.samples

        # The samples are evenly spaced along the curve; the points keep equal gaps, on gates.
        xy = self.problem.evened(np.array([v.xy for v in samples]))
        if xy is None:
            raise OptimizerError('the starting line cannot be spaced evenly between its gates')

        start_energy = self.problem.evaluate(xy)[0]
        tightening = _Tightening(np.zeros(len(xy)))
        xy, lap, tightening = self._legal(xy, tightening, timed=False)
        profile = smoothest_time = None
        if self.shortest:
            # Measured against the smoothest line, as the lap time is (fastest, above).
            self.aim = 'Shortest'
            self.problem.shorten(self.problem.evaluate(xy)[0] / self.problem.length(xy),
                                 settings.smoothness)
            xy, lap, tightening = self._legal(xy, tightening, timed=False)
            if self.limits is not None:
                profile = self._timed(lap)
        elif self.limits is not None:
            try:
                """
                From the smoothest line on, the passes lower lap time / its lap time +
                smoothness x energy / its energy. The mix is given to the problem times
                that energy, so that it stays on the scale of an energy, which the cost
                of a row that falls short and the settle rule are set for.
                """
                smoothest_time = self.problem.fastest(xy, self._caps(xy))[0]
                _LOG.debug('smoothest line: %.2f m, energy %.6g, lap %.3f s; now the fastest',
                           lap.curve.length, self.problem.evaluate(xy)[0], smoothest_time)
                self.problem.aim(self.problem.evaluate(xy)[0] / smoothest_time,
                                 settings.smoothness)
                smoothest, self.aim = lap, 'Fastest'
                xy, lap, tightening = self._legal(xy, tightening, timed=True)
                profile, kept = self._timed(lap), self._timed(smoothest)
                if kept.lap_time_s < profile.lap_time_s:
                    _LOG.info('Smoothest line is faster, %.2f s against %.2f s: kept',
                              kept.lap_time_s, profile.lap_time_s)
                    lap, profile = smoothest, kept
            except SpeedError as error:
                raise OptimizerError(f'the lap cannot be timed for this car: {error}') from error

        # Raises unless the curve crosses every gate once, forwards and in lap order.
        portal_crossings(lap)
        _LOG.debug('done: %d passes, %d refinements, %.1f s in passes', len(self.passes),
                   self.refinements, sum(done.seconds for done in self.passes))

        # The lap starts where the line crosses the start line: its first point, at q 0.
        return OptimizedLap(lap, 0., start_energy, tuple(self.passes), self.refinements,
                            profile, smoothest_time)

    def _timed(self, lap: LapCurve) -> SpeedProfile:
        """Return the speed profile of a finished curve; raises SpeedError."""
        _LOG.info('Timing the finished line')
        profile = speed_profile(lap, self.space.zones, self.limits)
        _LOG.debug('finished line: %.2f m, lap %.3f s over %d points, speeds settled in %d '
                   'rounds, %.2f to %.2f m/s', lap.curve.length, profile.lap_time_s,
                   len(profile.samples), profile.rounds, profile.points.speed_mps.min(),
                   profile.points.speed_mps.max())
        return profile

    def _legal(self, xy: np.ndarray, tightening: _Tightening,
               timed: bool) -> tuple[np.ndarray, LapCurve, _Tightening]:
        """
        Settle the line and check its curve, tightening the rows until the curve is legal.

        timed:  whether the passes aim at lap time as well as curvature.

        Returns the points, their curve and the tightening it took.
        """
        settings = self.settings
        for _ in range(settings.max_refinements + 1):
            xy = self._settle(xy, tightening, timed)
            lap = refit_lap(self.initial, self.samples, [tuple(p) for p in xy])
            excess = self._check(lap)
            _LOG.debug('checked curve of %.2f m: %d pieces off the road (worst %.2f mm), '
                       'turning %.4f times the limit', lap.curve.length, len(excess.off_road),
                       max(excess.off_road.values(), default=0.) * 1e3, excess.too_tight)
            if not excess:
                return xy, lap, tightening

            tightening = _tightened(tightening, excess, settings.settle_m)
            self.refinements += 1
            _LOG.info('Curve off its limits, refinement %d', self.refinements)

        raise OptimizerError(f'the curve still leaves the road or turns too tight after '
                             f'{settings.max_refinements} refinements')


def optimize(route: Route, car: Car, settings: OptimizerSettings = OptimizerSettings(),
             initial: LapCurve | None = None, limits: CarLimits | None = None,
             shortest: bool = False) -> OptimizedLap:
    """
    Return the optimized lap for car, starting from the centre curve or from initial.

    limits:     the car's speed limits. With them the lap is the fastest one, with a share
                of smoothness kept (settings.smoothness), and comes with its speeds;
                without them it is the smoothest one.
    shortest:   the shortest line the car can steer instead of the fastest, with the same
                share of smoothness kept; timed if limits are given.
    """
    return _Optimization(route, car, settings, initial, limits, shortest).run()
