"""
One pass of the optimizer as a nonlinear program, solved by IPOPT through CasADi.

points:     the x, y of every lap point, in lap order; the lap is closed.
objective:  curvature squared along the lap, the sum of k^2 ds, with k the curvature of the
            circle through a point and its two neighbours.
spacing:    within a section every point stays as far from the next point as from the one
            before. Points then cannot slide along the line: only its shape is free.
gates:      the first point of every section stays on the line of the gate into it, so the
            curve crosses each gate exactly where the section begins in q.
poses:      at a point the body faces along the parabola through the point and its
            neighbours. Between two points it follows the cubic that leaves both along their
            headings; that cubic stays close to the spline the points are refitted with,
            where the chord between them does not.
rows:       what the line must keep, each a value that must not be negative, in metres
            unless said otherwise:
            walls       the planes and vertices of free_space, for the body at the poses
                        they were picked at and for base_link at the points;
            turning     the curvature at every point within the limit, times the spacing
                        squared: about how far the point is from where it would meet it.
recovery:   a row that is not met yet is elastic: it may fall short, at a cost of `elastic`
            per metre. A pass can then always be solved, IPOPT pulls the line back as fast as
            the other rows allow, and once the line is legal the cost is zero. A row within
            `met` of met counts as met: it is not pulled back, and it may not get worse. It
            gets no slack: a slack starts on its bound, IPOPT moves every start off its
            bounds, and from a start shaken that way it can end on a line worse than the
            one it was given.
straight:   within a pass every row above is taken as a straight line: its value at the
            start and how it changes with the first move. The energy, the spacing and the
            gates keep their bends, and so do the lap time and the speed rules when the
            lap time is aimed at.
trust:      no coordinate moves more than one step and no pose turns more than `turn` in a
            pass, so no wall beyond the reach its rows were picked with can be crossed.
counts:     a pass counts only if the true rows bear its straight rows out. From a legal
            line, every true row must still be met after it: the line stays legal, and
            since the energy is not straightened the pass lowers it. From a line that is
            not legal yet, the true rows must come at least half as much closer in total as
            the straight rows said.
again:      the walls are picked anew for every pass, and a wall corner then passes the
            body at another moment than before. There the line can be a few millimetres
            short again; that pass brings it back before the energy falls further.
corrected:  where the body turns around a wall corner its row bends, and the straight row
            says too much. Every row is then shifted to where it truly ended and the pass
            is solved again from the same start, which leaves the rows off by far less. If
            the pass still does not count after _CORRECTIONS of these, the step was too
            long for straight rows and the caller tries a shorter one.
trusted:    a pass that counted without a correction; the caller lets the next step grow.
gain:       the cost of a pass is what it lowers, the energy or its mix with the lap time,
            plus what the rows fall short. A pass that cannot lower it by more than `gain`
            of it leaves the line where it is: IPOPT does not resolve less, and lines that
            close in cost are equally good. With the lap time in it the cost is resolved
            less finely (_TIME_GAIN).
time:       given the car's speed limits, a pass can aim at lap time as well (aim). The
            speed at every point then joins the points as unknowns, with the car's speed
            rules as rows that keep their bends (timing.py), and the cost is a share of
            the lap time plus a share of the energy. The lap time that counts is the one
            of the points driven as fast as the car can (speed/points.py), worked out
            before the pass and again after it, both with the track's limits looked up
            where the points were when the pass began. If the moved points cannot be
            timed at all, the pass does not count.
length:     a pass can aim at length instead (shorten): the cost is then a share of the
            length of the polyline through the points plus a share of the energy. The
            turning row still holds, so the line is the shortest the car can steer.
left out:   most speed rows cannot bind in a pass; on a lap driven at the track's limit
            none can. A gap's speed rows are given to the solver only if one of them is
            within _NEAR of binding where the solve starts, as a share of its limit. The
            answer is then held against every gap's rows. If it breaks rows that were
            left out, their gaps are kept as well and the pass is solved again, until an
            answer breaks none; every such solve keeps more gaps, so that ends.
agreed:     the solver and that lap time must tell the same story. After a solve the lap
            time by the solver's own speeds is held against the one worked out for the
            same points and limits; if they are apart, timing.py and speed/ no longer
            state the same rules, and the pass raises.
"""
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import count
import math

import casadi as ca
import numpy as np
from scipy import sparse

from .free_space import Plane, Vertex
from .timing import gap_rows, gap_time
from ..car import Car, CarLimits
from ..route.geometry import EPS, XY
from ..speed.errors import SpeedError
from ..speed.model import CarModel
from ..speed.points import LapPoints
from ..speed.speeds import SpeedSettings

# How often a pass that does not count is solved again with its rows corrected, before the
# step is given up as too long. One correction is nearly always enough, and a second leaves
# the rows off by far less again; after that the step is halved instead.
_CORRECTIONS = 2

# The speed package's own settings: the lap time that judges a pass is worked out with
# them, as the speed profile of the finished curve is.
_SPEED = SpeedSettings()

"""
The slowest speed the solver may give a point, in m/s. The speed rules take the square root
of the unknowns, which has no slope at zero; a centimetre a second is far below any speed
a lap is driven at.
"""
_SLOWEST = 0.01

"""
The fraction of its cost a pass that aims at lap time must lower it by. IPOPT stops with
its speeds a few hundred-thousandths of a m/s inside their rules, so its own lap time is
good to about a hundred-thousandth, and so is its idea of whether a move pays.
"""
_TIME_GAIN = 1e-5

"""
How far apart, as a fraction, the lap time by the solver's own speeds and the one worked out
by speed/ for the same points may be. They agree to a hundred-thousandth when both state
the same rules; a thousandth is far outside that and well inside what a wrong rule gives.
"""
_TIMES_AGREE = 1e-3

"""
A gap's speed rows are given to the solver if one of them is within this share of its limit
of binding where the solve starts. Half is generous: on the tracks it was tried on, no
answer broke a row left out with it.
"""
_NEAR = 0.5

# A row that was left out is broken once the answer is this share of its limit beyond it.
_BROKEN = 1e-7

# A column of numbers or of symbols, and the x and y columns of some points or headings.
Column = np.ndarray | ca.SX | ca.DM
Pair = tuple[Column, Column]


@dataclass(frozen=True)
class BodyWalls:
    """
    The walls the body keeps to at one pose.

    point:      the lap point the pose is at, or leaves from.
    along:      how far the pose is on the way to the next point, from 0 to 1.
    clearance:  the distance the body keeps from these walls.
    planes:     walls every corner of the body stays beyond.
    vertices:   wall points that stay beyond one edge of the body.
    """

    point: int
    along: float
    clearance: float
    planes: Sequence[Plane]
    vertices: Sequence[Vertex]


@dataclass(frozen=True)
class PointWalls:
    """The walls base_link keeps to at one lap point, as planes it stays beyond."""

    point: int
    planes: Sequence[Plane]


@dataclass(frozen=True)
class GateRow:
    """Keep one point, the first of a section, on the line of the gate into it."""

    point: int
    gate: tuple[XY, XY]


@dataclass(frozen=True)
class IpoptRun:
    """
    What IPOPT did in one pass.

    status:     its verdict on the last solve.
    iterations: its iterations over all solves of the pass.
    rows:       the rows of its last program.
    solves:     how often the pass was solved: once, once more for every correction, and
                once more every time speed rows that were left out were put back.
    """

    status: str
    iterations: int
    rows: int
    solves: int = 1


@dataclass(frozen=True)
class PassResult:
    """
    The points after one pass.

    xy:             the points; unchanged when the pass does not count.
    accepted:       whether the pass counts.
    trusted:        whether it counted without a correction, so that the step may grow.
    short_before:   what the true rows fell short in total before the pass, in metres.
    short_promised: what the straight rows said they would still fall short after it.
    short_after:    what the true rows fall short after it; 0 once the line is legal.
    """

    xy: np.ndarray
    accepted: bool
    trusted: bool
    short_before: float
    short_promised: float
    short_after: float
    ipopt: IpoptRun


@dataclass(frozen=True)
class _Picked:
    """
    The walls picked for one pass, one entry per row.

    plane_*:    a body corner beyond a wall's line: the pose (point, along), the corner as
                (ahead, left) of base_link, the line's normal, and what the row must exceed.
    vertex_*:   a wall point beyond a body edge: the pose, the edge's normal in the body's
                frame, the wall point, and what the row must exceed.
    base_*:     base_link beyond a wall's line: the point, the normal, what it must exceed.
    """

    plane_point: np.ndarray
    plane_along: np.ndarray
    plane_corner: np.ndarray
    plane_normal: np.ndarray
    plane_offset: np.ndarray
    vertex_point: np.ndarray
    vertex_along: np.ndarray
    vertex_edge: np.ndarray
    vertex_wall: np.ndarray
    vertex_offset: np.ndarray
    base_point: np.ndarray
    base_normal: np.ndarray
    base_offset: np.ndarray


def _columns(m: np.ndarray | ca.SX, rows: Sequence[int] | slice = slice(None)) -> Pair:
    """Return the x and the y column of the given rows of m."""
    return m[rows, 0], m[rows, 1]


def _length(v: Pair) -> Column:
    """Return the length of every vector of v."""
    return (v[0] ** 2 + v[1] ** 2) ** 0.5


def _curvature(before: Pair, at: Pair, after: Pair) -> Column:
    """Return the curvature of the circle through three points."""
    back, ahead = (at[0] - before[0], at[1] - before[1]), (after[0] - at[0], after[1] - at[1])
    across = _length((after[0] - before[0], after[1] - before[1]))

    return (2 * (back[0] * ahead[1] - back[1] * ahead[0])
            / (_length(back) * _length(ahead) * across))


def _heading(before: Pair, at: Pair, after: Pair) -> Pair:
    """
    Return the unit heading at `at` of the parabola through three points.

    The parabola weights the step from each side by the gap on the other. Written once for
    numbers and for symbols of the points alike, like _cubic.
    """
    back, ahead = (at[0] - before[0], at[1] - before[1]), (after[0] - at[0], after[1] - at[1])
    ratio = _length(ahead) / _length(back)
    along = (back[0] * ratio + ahead[0] / ratio, back[1] * ratio + ahead[1] / ratio)
    speed = _length(along)

    return along[0] / speed, along[1] / speed


def _cubic(p0: Pair, p1: Pair, t0: Pair, t1: Pair, u: Column | float) -> tuple[Pair, Pair]:
    """
    Return the position and the unit heading at u along the cubic from p0 to p1.

    The cubic leaves p0 along t0 and reaches p1 along t1, at the speed of the chord between
    them.
    """
    gap = _length((p1[0] - p0[0], p1[1] - p0[1]))
    at, along = [], []
    for k in (0, 1):
        at.append((2 * u ** 3 - 3 * u ** 2 + 1) * p0[k] + (3 * u ** 2 - 2 * u ** 3) * p1[k]
                  + gap * ((u ** 3 - 2 * u ** 2 + u) * t0[k] + (u ** 3 - u ** 2) * t1[k]))
        along.append(6 * (u - u ** 2) * (p1[k] - p0[k])
                     + gap * ((3 * u ** 2 - 4 * u + 1) * t0[k] + (3 * u ** 2 - 2 * u) * t1[k]))

    speed = _length(along)

    return (at[0], at[1]), (along[0] / speed, along[1] / speed)


def _neighbour(m: ca.SX | ca.MX, k: int) -> ca.SX | ca.MX:
    """Return, for every row i of m, the row i + k around the closed lap."""
    return ca.vertcat(m[k:, :], m[:k, :])


def _weighted(weights: np.ndarray, matrix: sparse.spmatrix) -> sparse.spmatrix:
    """Return matrix with every row multiplied by its weight."""
    return sparse.diags(weights) @ matrix


def _lines(start: np.ndarray, change: sparse.spmatrix, move: ca.MX) -> ca.MX:
    """Return straight rows: their values at the start plus how they change with the move."""
    if not len(start):
        return ca.MX(0, 1)

    return ca.DM(start) + ca.mtimes(ca.DM(change.tocsc()), move)


def _short(values: np.ndarray, met: float) -> float:
    """Return what rows of these values fall short in total, those within met left out."""
    return float(-values[values < -met].sum())


class LapProblem:
    """
    The program of a closed lap of n points; everything but the walls is built once.

    car:            the car, for the corners and edges of its body.
    spacing:        the gap between neighbouring points the line starts with, in metres.
    equal_gaps:     the points that keep their two gaps equal: all but the first of a section.
    gates:          the first point of every section and the gate it stays on.
    turn:           the most a pose may turn in one pass, in radians.
    elastic:        cost per metre a row falls short while it recovers.
    met:            how far short of met a row may be and still count as met, in metres.
    gain:           the fraction of its cost a pass must lower it by to be worth making.
    limits:         the car's limits, for a pass that aims at lap time; None if the
                    problem is only ever asked for the least curvature.
    """

    def __init__(self, n: int, car: Car, spacing: float, equal_gaps: Sequence[int],
                 gates: Sequence[GateRow], turn: float,
                 elastic: float, met: float, gain: float, tolerance: float,
                 max_iterations: int, limits: CarLimits | None = None) -> None:
        self.n = n
        self.limits = limits
        self.goal = self.shorter = None
        self._timed_at = {}
        if limits is not None and _SPEED.grip_exponent != 1:
            raise ValueError('the speed rules of timing.py are written for grip_exponent 1')
        self.corners = np.array(car.corners)
        self.edges = car.edges
        self.spacing = spacing
        self.turn = turn
        self.elastic = elastic
        self.met = met
        self.gain = gain

        x = ca.SX.sym('x', 2 * n)
        points = ca.reshape(x, 2, n).T
        before, here, after = (_columns(_neighbour(points, k)) for k in (-1, 0, 1))
        back = (here[0] - before[0], here[1] - before[1])
        ahead = (after[0] - here[0], after[1] - here[1])
        curvature = _curvature(before, here, after)
        energy = ca.sum1(curvature ** 2 * (_length(back) + _length(ahead)) / 2)
        heading = _heading(before, here, after)
        following = (_neighbour(heading[0], 1), _neighbour(heading[1], 1))
        _, halfway = _cubic(here, after, heading, following, 0.5)

        """
        What keeps its bends in a pass: the energy, and the gaps and gates that stay zero.
        Kept as one function, whose derivatives IPOPT works out once: they last for as long
        as a solver built on it is alive, so the solver of the last pass is held on to.
        """
        gaps = (_length(ahead) ** 2 - _length(back) ** 2)[list(equal_gaps)]
        on_gate = [self._across(points, row) for row in gates]
        self._bent = ca.Function('bent', [x], [energy, ca.vertcat(gaps, *on_gate)])
        self._lap_length = ca.Function('lap_length', [x], [ca.sum1(_length(ahead))])
        self._solver = None

        # What the turning and trust rows need at the start of a pass, and how each changes.
        turning = [*heading, *halfway]
        self._derived = ca.Function('derived', [x], [energy, curvature, ca.horzcat(*heading)])
        self._changes = ca.Function('changes', [x], [
            ca.horzcat(*halfway), *[ca.jacobian(c, x) for c in (curvature, *turning)]])

        """
        A pose and its rows as functions of the four points around it: the one before, the
        one it leaves from, the next and the one after. Built once and evaluated for every
        row of a pass; each returns the row's value and how it changes with those points.
        """
        around, along = ca.SX.sym('around', 8), ca.SX.sym('along')
        four = [(around[2 * k], around[2 * k + 1]) for k in range(4)]
        at, facing = _cubic(four[1], four[2], _heading(*four[:3]), _heading(*four[1:]), along)
        left = (-facing[1], facing[0])

        corner, normal = ca.SX.sym('corner', 2), ca.SX.sym('normal', 2)
        beyond = sum(normal[k] * (at[k] + corner[0] * facing[k] + corner[1] * left[k])
                     for k in (0, 1))
        self._plane = ca.Function('plane', [around, along, corner, normal],
                                  [beyond, ca.jacobian(beyond, around)])

        edge, wall = ca.SX.sym('edge', 2), ca.SX.sym('wall', 2)
        apart = (wall[0] - at[0], wall[1] - at[1])
        beyond = (edge[0] * (apart[0] * facing[0] + apart[1] * facing[1])
                  + edge[1] * (apart[0] * left[0] + apart[1] * left[1]))
        self._vertex = ca.Function('vertex', [around, along, edge, wall],
                                   [beyond, ca.jacobian(beyond, around)])

        """
        The lap time and the speed rules, for a pass that aims at lap time. A gap's time and
        its rows are small functions of the four points around it and of the squared speeds
        at its two ends, applied to every gap: the solver then works out the derivatives of
        one gap, not of the whole lap at once. `_timed` gives the lap time of some points
        and speeds, and for every gap how near its nearest row is to binding, as a share
        of that row's limit; below zero the row is broken.
        """
        if limits is not None:
            ends = ca.SX.sym('ends', 2)
            length = _length((four[2][0] - four[1][0], four[2][1] - four[1][1]))
            rows, against = gap_rows(
                limits, length, (_curvature(*four[:3]), _curvature(*four[1:])), ends)
            self._gaps = ca.Function('gaps', [x], [_length(ahead)])
            self._gap_time = ca.Function('gap_time', [around, ends], [gap_time(length, ends)])
            self._gap_rows = ca.Function('gap_rows', [around, ends], [rows])
            nearest = ca.Function('nearest', [around, ends], [ca.mmin(rows / against)])
            lap, squared = ca.MX.sym('x', 2 * n), ca.MX.sym('squared', n)
            wide = self._wide(lap, squared)
            self._timed = ca.Function('timed', [lap, squared], [
                ca.sum2(self._gap_time.map(n)(*wide)), nearest.map(n)(*wide)])

        """
        IPOPT ends well inside EPS of every row, so that what it calls met also passes the
        checks made with EPS afterwards. While only the curvature is aimed at, every row
        with two different bounds is a straight line, which jac_d_constant tells it. A pass
        starts from a line close to its answer; there IPOPT's adaptive strategy, which
        sets how hard it keeps away from the rows by the progress of each iteration and
        not on a fixed schedule, needs fewer iterations than its default.
        """
        self.options = {'ipopt.print_level': 0, 'ipopt.sb': 'yes', 'print_time': 0,
                        'ipopt.tol': tolerance, 'ipopt.max_iter': max_iterations,
                        'ipopt.constr_viol_tol': EPS / 10,
                        'ipopt.bound_relax_factor': EPS / 10,
                        'ipopt.mu_strategy': 'adaptive'}

    def _wide(self, x: ca.MX, squared: ca.MX) -> tuple[ca.MX, ca.MX]:
        """
        Return what the gap functions take for every gap of the lap, a column a gap.

        The four points around the gap, x and y in turn, and the squared speeds at its two
        ends.
        """
        points = ca.reshape(x, 2, self.n).T
        around = ca.horzcat(*[_neighbour(points, k) for k in (-1, 0, 1, 2)]).T
        ends = ca.horzcat(squared, _neighbour(squared, 1)).T

        return around, ends

    def _rules(self, wide: tuple[ca.MX, ca.MX] | None, kept: np.ndarray | None) -> ca.MX:
        """Return the speed rows of the gaps that are kept, out of all the gaps of `wide`."""
        gaps = [] if kept is None else [int(i) for i in np.flatnonzero(kept)]
        if not gaps:
            return ca.MX(0, 1)

        around, ends = wide

        return ca.vec(self._gap_rows.map(len(gaps))(around[:, gaps], ends[:, gaps]))

    @staticmethod
    def _across(points: ca.SX, row: GateRow) -> ca.SX:
        """Return how far a point lies across the line of its gate."""
        a, b = np.asarray(row.gate)
        across = np.array([a[1] - b[1], b[0] - a[0]]) / np.linalg.norm(b - a)
        p = points[row.point, :]

        return across[0] * (p[0] - a[0]) + across[1] * (p[1] - a[1])

    def aim(self, time_share: float, energy_share: float) -> None:
        """
        Aim the timed passes at lap time as well as curvature.

        Their cost becomes time_share times the lap time plus energy_share times the energy.
        """
        self.goal = (time_share, energy_share)

    def shorten(self, length_share: float, energy_share: float) -> None:
        """
        Aim the untimed passes at length as well as curvature.

        Their cost becomes length_share times the length of the lap plus energy_share times
        the energy. The turning row still holds, so the line is the shortest the car can
        steer, not the shortest there is.
        """
        self.shorter = (length_share, energy_share)

    def length(self, xy: np.ndarray) -> float:
        """Return the length of the closed polyline through the points."""
        return float(self._lap_length(xy.ravel()))

    def fastest(self, xy: np.ndarray, cap: np.ndarray) -> tuple[float, np.ndarray]:
        """
        Return the lap time of the points driven as fast as the car can, and those speeds.

        cap:    the track's speed limit at every point.
        """
        if self.limits is None:
            raise ValueError("a lap is timed only for a problem built with the car's limits")

        # A pass asks for the same laps more than once: the answers of the last pass are kept.
        key = (xy.tobytes(), cap.tobytes())
        if key in self._timed_at:
            return self._timed_at[key]

        tightest = math.tan(self.limits.max_steering_angle) / self.limits.wheelbase
        gap = np.asarray(self._gaps(xy.ravel())).ravel()

        # A point may sit a hair past the turning limit, which the speeds need not refuse.
        curvature = np.clip(self.evaluate(xy)[1], -tightest, tightest)
        points = LapPoints(CarModel(self.limits, _SPEED.grip_exponent), gap, curvature, cap)
        points.settle(_SPEED.resolved_mps, _SPEED.max_rounds)
        self._timed_at[key] = (float(points.took_s.sum()), points.speed_mps)

        return self._timed_at[key]

    @staticmethod
    def _agree(believed: float, worked_out: float) -> None:
        """Raise unless the solver's lap time and the one worked out by speed/ agree."""
        if abs(believed - worked_out) > _TIMES_AGREE * worked_out:
            raise ValueError(
                f'the solver takes a lap for {believed:.3f} s where speed/ works out '
                f'{worked_out:.3f} s for the same points: optimizer/timing.py and speed/ '
                f'no longer state the same rules')

    def cost(self, xy: np.ndarray, cap: np.ndarray | None) -> float:
        """Return what a pass lowers: the energy, or its mix with the length or the lap time."""
        energy = self.evaluate(xy)[0]
        if cap is None:
            if self.shorter is None:
                return energy

            return self.shorter[0] * self.length(xy) + self.shorter[1] * energy

        if self.goal is None:
            raise ValueError('a pass aims at lap time only after aim() has said how much')

        return self.goal[0] * self.fastest(xy, cap)[0] + self.goal[1] * energy

    def evaluate(self, xy: np.ndarray) -> tuple[float, np.ndarray, np.ndarray]:
        """Return the curvature energy, and the curvature and unit heading at every point."""
        energy, curvature, heading = self._derived(xy.ravel())

        return float(energy), np.asarray(curvature).ravel(), np.asarray(heading)

    def poses(self, xy: np.ndarray, heading: np.ndarray, point: Sequence[int],
              along: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Return base_link and unit heading of the poses `along` the way from each point."""
        following = [(i + 1) % self.n for i in point]
        at, facing = _cubic(_columns(xy, point), _columns(xy, following),
                            _columns(heading, point), _columns(heading, following), along)

        return np.column_stack(at), np.column_stack(facing)

    def evened(self, xy: np.ndarray) -> np.ndarray | None:
        """Return the points nearest xy with equal gaps, on their gates; None if IPOPT fails."""
        x0 = xy.ravel()
        x = ca.MX.sym('x', len(x0))
        solver = ca.nlpsol('evened', 'ipopt', {
            'x': x, 'f': ca.sumsqr(x - x0), 'g': self._bent(x)[1]}, self.options)
        out = solver(x0=x0, lbg=0., ubg=0.)
        if float(ca.mmax(ca.fabs(out['g']))) > EPS:
            return None

        return np.asarray(out['x']).reshape(-1, 2)

    def _picked(self, bodies: Sequence[BodyWalls], points: Sequence[PointWalls]) -> _Picked:
        """Return the walls of a pass as arrays; every plane of a body once per corner."""
        planes = [(r, p) for r in bodies for p in r.planes]
        vertices = [(r, v) for r in bodies for v in r.vertices]
        base = [(r.point, p) for r in points for p in r.planes]
        corners = len(self.corners)

        def array(values: list, width: int = 0) -> np.ndarray:
            return np.array(values, dtype=float).reshape((-1, width) if width else -1)

        normal = array([p.normal for _, p in planes], 2)
        offset = array([np.dot(p.normal, p.anchor) + r.clearance for r, p in planes])
        edge = [self.edges[v.edge] for _, v in vertices]
        base_normal = array([p.normal for _, p in base], 2)

        return _Picked(
            plane_point=np.tile(array([r.point for r, _ in planes]).astype(int), corners),
            plane_along=np.tile(array([r.along for r, _ in planes]), corners),
            plane_corner=np.repeat(self.corners, len(planes), axis=0),
            plane_normal=np.tile(normal, (corners, 1)),
            plane_offset=np.tile(offset, corners),
            vertex_point=array([r.point for r, _ in vertices]).astype(int),
            vertex_along=array([r.along for r, _ in vertices]),
            vertex_edge=array([normal for normal, _ in edge], 2),
            vertex_wall=array([v.xy for _, v in vertices], 2),
            vertex_offset=array([d + r.clearance for (_, d), (r, _) in zip(edge, vertices)]),
            base_point=array([i for i, _ in base]).astype(int),
            base_normal=base_normal,
            base_offset=array([np.dot(p.normal, p.anchor) for _, p in base]))

    def _posed(self, row: ca.Function, xy: np.ndarray, point: np.ndarray, along: np.ndarray,
               *parameters: np.ndarray) -> tuple[np.ndarray, sparse.csr_matrix]:
        """Return one kind of pose row at many poses: its values and how they change with xy."""
        count = len(point)
        if not count:
            return np.zeros(0), sparse.csr_matrix((0, 2 * self.n))

        around = (point[:, None] + np.arange(-1, 3)) % self.n
        value, change = row.map(count)(xy[around].reshape(count, 8).T, along[None, :],
                                       *[p.T for p in parameters])
        columns = (2 * around[:, :, None] + np.arange(2)).reshape(count, 8)
        change = sparse.csr_matrix(
            (np.asarray(change).ravel(), (np.repeat(np.arange(count), 8), columns.ravel())),
            shape=(count, 2 * self.n))

        return np.asarray(value).ravel(), change

    def _kept(self, xy: np.ndarray, picked: _Picked,
              curvature_limit: float) -> tuple[np.ndarray, sparse.csr_matrix]:
        """
        Return every row the line must keep, at xy: its value in metres and how it changes.

        In order: the body's planes, its vertices, base_link's planes, and the turning limit
        to either side.
        """
        x = xy.ravel()
        curvature = self.evaluate(xy)[1]
        bending = sparse.csr_matrix(self._changes(x)[1].sparse())
        values, slopes = [], []

        value, change = self._posed(self._plane, xy, picked.plane_point, picked.plane_along,
                                    picked.plane_corner, picked.plane_normal)
        values.append(value - picked.plane_offset)
        slopes.append(change)
        value, change = self._posed(self._vertex, xy, picked.vertex_point, picked.vertex_along,
                                    picked.vertex_edge, picked.vertex_wall)
        values.append(value - picked.vertex_offset)
        slopes.append(change)

        count = len(picked.base_point)
        values.append(np.einsum('ij,ij->i', xy[picked.base_point], picked.base_normal)
                      - picked.base_offset)
        columns = 2 * picked.base_point[:, None] + np.arange(2)
        slopes.append(sparse.csr_matrix(
            (picked.base_normal.ravel(), (np.repeat(np.arange(count), 2), columns.ravel())),
            shape=(count, len(x))))

        for sign in (1, -1):
            values.append((curvature_limit - sign * curvature) * self.spacing ** 2)
            slopes.append(-sign * self.spacing ** 2 * bending)

        return np.concatenate(values), sparse.vstack(slopes).tocsr()

    def _turned(self, xy: np.ndarray) -> sparse.csr_matrix:
        """Return how the sideways part of every heading, at a point and halfway, changes."""
        heading = self.evaluate(xy)[2]
        halfway, _, to_x, to_y, half_to_x, half_to_y = (
            sparse.csr_matrix(c.sparse()) for c in self._changes(xy.ravel()))
        halfway = halfway.toarray()

        return sparse.vstack((
            _weighted(-heading[:, 1], to_x) + _weighted(heading[:, 0], to_y),
            _weighted(-halfway[:, 1], half_to_x) + _weighted(halfway[:, 0], half_to_y))).tocsr()

    def _straight(self, x0: np.ndarray, guess: np.ndarray, current: np.ndarray,
                  values: np.ndarray, slope: sparse.csr_matrix, turned: sparse.csr_matrix,
                  step: float, speeds: tuple[np.ndarray, np.ndarray] | None
                  ) -> tuple[np.ndarray | None, float, IpoptRun, float | None]:
        """
        Solve a pass from x0 with every row a straight line.

        guess:      where IPOPT starts looking.
        current:    the true rows at x0. One that is not met there gets a slack, back to
                    zero; one within `met` of met stays at least where it is now.
        values:     the rows at x0 as this solve takes them: current, plus any correction.
                    A row that stays positive wherever the step lets the points go cannot
                    hold the line back, and is left out.
        slope:      how the rows change with the points.
        turned:     how the headings turn with the points.
        speeds:     for a pass that aims at lap time: the speeds the car can drive at x0,
                    and the most the solver may give each point; None otherwise. The
                    speed rows of gaps far from binding are left out, and put back if the
                    answer breaks them (left out, above).

        Returns the points, what the rows that fall short were charged, what IPOPT did, and
        the lap time by its own speeds if it has any; no points if it did not keep its rows.
        """
        able = np.flatnonzero(values - step * np.asarray(abs(slope).sum(axis=1)).ravel() <= 0)
        negative = np.flatnonzero(current[able] < -self.met)
        lower = np.where(current[able] < -self.met, 0., np.minimum(0., current[able]))
        lift = sparse.csc_matrix((np.ones(len(negative)), (negative, np.arange(len(negative)))),
                                 shape=(len(able), len(negative)))

        x, slack = ca.MX.sym('x', len(x0)), ca.MX.sym('slack', len(negative))
        cost, bent = self._bent(x)
        straight = [_lines(values[able], slope[able], x - x0),
                    _lines(np.zeros(turned.shape[0]), turned, x - x0)]
        if len(negative):
            straight[0] += ca.mtimes(ca.DM(lift), slack)

        most = np.full(turned.shape[0], math.sin(self.turn))
        zeros = np.zeros(bent.shape[0])
        lbg = [lower, -most, zeros]
        ubg = [np.full(len(able), np.inf), most, zeros]
        unknowns, rows, options = [x, slack], [*straight, bent], dict(self.options)
        at_guess = values[able] + slope[able] @ (guess - x0)
        start = [guess, np.maximum(0., lower - at_guess)[negative]]
        lbx = [x0 - step, np.zeros(len(negative))]
        ubx = [x0 + step, np.full(len(negative), np.inf)]
        wide, kept = None, None
        if speeds is None:
            options['ipopt.jac_d_constant'] = 'yes'
            if self.shorter is not None:
                cost = self.shorter[0] * self._lap_length(x) + self.shorter[1] * cost
        else:
            # The speeds join the unknowns, squared, each between a crawl and its cap.
            driven, cap = speeds
            squared = ca.MX.sym('squared', self.n)
            wide = self._wide(x, squared)
            time = ca.sum2(self._gap_time.map(self.n)(*wide))
            cost = self.goal[0] * time + self.goal[1] * cost
            unknowns.append(squared)
            slowest = np.minimum(_SLOWEST, cap / 2)
            start.append(np.clip(driven, slowest, cap) ** 2)
            lbx.append(slowest ** 2)
            ubx.append(cap ** 2)
            kept = np.asarray(self._timed(guess, start[-1])[1]).ravel() <= _NEAR

        iterations = 0
        for solves in count(1):
            rules = self._rules(wide, kept)
            low = np.concatenate((*lbg, np.zeros(rules.shape[0])))
            high = np.concatenate((*ubg, np.full(rules.shape[0], np.inf)))
            solver = ca.nlpsol('pass', 'ipopt', {
                'x': ca.vertcat(*unknowns), 'f': cost + self.elastic * ca.sum1(slack),
                'g': ca.vertcat(*rows, rules)}, options)
            out = solver(x0=np.concatenate(start), lbg=low, ubg=high,
                         lbx=np.concatenate(lbx), ubx=np.concatenate(ubx))
            iterations += int(solver.stats()['iter_count'])
            found, held = np.asarray(out['x']).ravel(), np.asarray(out['g']).ravel()
            result, believed = found[:len(x0)], None

            # IPOPT must have kept its own rows, whatever it calls its result.
            if np.max(np.concatenate((low - held, held - high))) > EPS:
                result = None

            if result is None or speeds is None:
                break

            # The answer is held against the rows of every gap, those left out too.
            believed, nearest = self._timed(result, found[len(x0) + len(negative):])
            believed = float(believed)
            broken = (np.asarray(nearest).ravel() < -_BROKEN) & ~kept
            if not broken.any():
                break

            kept |= broken

        ipopt = IpoptRun(solver.stats()['return_status'], iterations, len(low), solves)
        self._solver = solver
        paid = found[len(x0):len(x0) + len(negative)]

        # IPOPT may end a slack a hair below zero, which must not count as a gain.
        return result, float(self.elastic * np.maximum(0., paid).sum()), ipopt, believed

    def solve(self, xy: np.ndarray, bodies: Sequence[BodyWalls], points: Sequence[PointWalls],
              curvature_limit: float, step: float, cap: np.ndarray | None = None) -> PassResult:
        """
        Run one pass from xy.

        bodies, points:     the walls of the body poses and of the base_links, from free_space.
        curvature_limit:    the most the line may curve at a point.
        step:               the most a coordinate may move.
        cap:                the track's speed limit at every point, for a pass that aims
                            at lap time as well (aim); None for an untimed pass.
        """
        x0 = xy.ravel()
        picked = self._picked(bodies, points)
        current, slope = self._kept(xy, picked, curvature_limit)
        short = _short(current, self.met)
        cost_before = self.cost(xy, cap) + self.elastic * short
        turned = self._turned(xy)
        resolved = self.gain * cost_before
        speeds = None
        if cap is not None:
            # The solver is held to the track's limits and to the car's top speed.
            speeds = (self.fastest(xy, cap)[1], np.minimum(cap, self.limits.v_max))
            resolved = max(self.gain, _TIME_GAIN) * cost_before
            self._timed_at = {(xy.tobytes(), cap.tobytes()): self.fastest(xy, cap)}

        guess, correction, runs = x0, np.zeros(len(current)), []
        for solves in range(1, _CORRECTIONS + 2):
            result, charged, run, believed = self._straight(
                x0, guess, current, current + correction, slope, turned, step, speeds)
            runs.append(run)
            ipopt = IpoptRun(run.status, sum(r.iterations for r in runs), run.rows,
                             sum(r.solves for r in runs))
            if result is None:
                break

            # Moved points that cannot be timed at all are a move that does not count.
            moved = result.reshape(-1, 2)
            try:
                if believed is not None and run.status == 'Solve_Succeeded':
                    self._agree(believed, self.fastest(moved, cap)[0])

                cost = self.cost(moved, cap) + charged
            except SpeedError:
                break

            """
            IPOPT resolves the cost to about `resolved`. With no more than that to gain,
            the line stays where it is; a solve that ends worse by more than that went
            astray, and the step is too long.
            """
            gained = cost_before - cost
            if gained < -resolved:
                break

            if gained <= resolved:
                return PassResult(xy, True, True, short, short, short, ipopt)

            straight = current + slope @ (result - x0)
            said = straight + correction
            true = self._kept(moved, picked, curvature_limit)[0]
            promised, after = _short(said, self.met), _short(true, self.met)

            # A legal line stays legal; one that is not comes half as much closer as promised.
            if after == 0 or (short > 0 and short - after >= (short - promised) / 2):
                return PassResult(moved, True, solves == 1, short, promised, after, ipopt)

            # Solve again with every row shifted to where it truly ended at this move.
            guess, correction = result, true - straight

        return PassResult(xy, False, False, short, short, short, ipopt)
