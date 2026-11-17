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
rows:       what the line must keep, each a value in metres that must not be negative:
            walls       the planes and vertices of free_space, for the body at the poses
                        they were picked at and for base_link at the points;
            turning     the curvature at every point within the limit, times the spacing
                        squared: about how far the point is from where it would meet it;
            start       one point facing within the start heading range, as an angle times
                        the spacing.
recovery:   a row that is not met yet is elastic: it may fall short, at a cost of `elastic`
            per metre. A pass can then always be solved, IPOPT pulls the line back as fast as
            the other rows allow, and once the line is legal the cost is zero. A row within
            `met` of met counts as met: it is not pulled back, it only pays for getting worse.
straight:   within a pass every row is taken as a straight line: its value at the start and
            how it changes with the first move. Only the energy, the spacing and the gates
            keep their bends.
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
gain:       the cost of a pass is the energy plus what the rows fall short. A pass that
            cannot lower it by more than `gain` of it leaves the line where it is: IPOPT
            does not resolve less, and lines that close in cost are equally good.
"""
from collections.abc import Sequence
from dataclasses import dataclass
import math

import casadi as ca
import numpy as np
from scipy import sparse

from .free_space import Plane, Vertex
from ..car import Car
from ..route.geometry import EPS, XY

# How often a pass that does not count is solved again with its rows corrected, before the
# step is given up as too long. One correction is nearly always enough, and a second leaves
# the rows off by far less again; after that the step is halved instead.
_CORRECTIONS = 2

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
    solves:     how often the pass was solved: once, and once more for every correction.
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


def _neighbour(m: ca.SX, k: int) -> ca.SX:
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
    start:          the start point and the middle of the heading range it faces; None for
                    a range that is a full turn.
    turn:           the most a pose may turn in one pass, in radians.
    elastic:        cost per metre a row falls short while it recovers.
    met:            how far short of met a row may be and still count as met, in metres.
    gain:           the fraction of its cost a pass must lower it by to be worth making.
    """

    def __init__(self, n: int, car: Car, spacing: float, equal_gaps: Sequence[int],
                 gates: Sequence[GateRow], start: tuple[int, XY] | None, turn: float,
                 elastic: float, met: float, gain: float, tolerance: float,
                 max_iterations: int) -> None:
        self.n = n
        self.corners = np.array(car.corners)
        self.edges = car.edges
        self.spacing = spacing
        self.start = start
        self.turn = turn
        self.elastic = elastic
        self.met = met
        self.gain = gain

        x = ca.SX.sym('x', 2 * n)
        points = ca.reshape(x, 2, n).T
        before, here, after = (_columns(_neighbour(points, k)) for k in (-1, 0, 1))
        back = (here[0] - before[0], here[1] - before[1])
        ahead = (after[0] - here[0], after[1] - here[1])
        across = _length((after[0] - before[0], after[1] - before[1]))
        curvature = (2 * (back[0] * ahead[1] - back[1] * ahead[0])
                     / (_length(back) * _length(ahead) * across))
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
        IPOPT ends well inside EPS of every row, so that what it calls met also passes the
        checks made with EPS afterwards. Every row with two different bounds is a straight
        line, which jac_d_constant tells it.
        """
        self.options = {'ipopt.print_level': 0, 'ipopt.sb': 'yes', 'print_time': 0,
                        'ipopt.tol': tolerance, 'ipopt.max_iter': max_iterations,
                        'ipopt.constr_viol_tol': EPS / 10,
                        'ipopt.bound_relax_factor': EPS / 10,
                        'ipopt.jac_d_constant': 'yes'}

    @staticmethod
    def _across(points: ca.SX, row: GateRow) -> ca.SX:
        """Return how far a point lies across the line of its gate."""
        a, b = np.asarray(row.gate)
        across = np.array([a[1] - b[1], b[0] - a[0]]) / np.linalg.norm(b - a)
        p = points[row.point, :]

        return across[0] * (p[0] - a[0]) + across[1] * (p[1] - a[1])

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

    def _kept(self, xy: np.ndarray, picked: _Picked, curvature_limit: float,
              heading_range: tuple[float, float] | None) -> tuple[np.ndarray, sparse.csr_matrix]:
        """
        Return every row the line must keep, at xy: its value in metres and how it changes.

        In order: the body's planes, its vertices, base_link's planes, the turning limit to
        either side, and the start heading to either side.
        """
        x = xy.ravel()
        _, curvature, heading = self.evaluate(xy)
        changes = [sparse.csr_matrix(c.sparse()) for c in self._changes(x)[1:]]
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
            slopes.append(-sign * self.spacing ** 2 * changes[0])

        if self.start is not None and heading_range is not None:
            point, (ahead, left) = self.start
            facing = heading[point]

            # The angle of the heading from the middle of its range, and how it changes.
            sideways = ahead * facing[1] - left * facing[0]
            forward = ahead * facing[0] + left * facing[1]
            angle = math.atan2(sideways, forward)
            change = ((-forward * left - sideways * ahead) * changes[1][point]
                      + (forward * ahead - sideways * left) * changes[2][point])
            for sign, edge in zip((-1, 1), heading_range):
                values.append(np.array([sign * (edge - angle) * self.spacing]))
                slopes.append(-sign * self.spacing * change)

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
                  step: float) -> tuple[np.ndarray | None, float, IpoptRun]:
        """
        Solve a pass from x0 with every row a straight line.

        guess:      where IPOPT starts looking.
        current:    the true rows at x0. Every one that falls short there gets a slack: back
                    to zero if it is not met, to where it is now if it is within `met`.
        values:     the rows at x0 as this solve takes them: current, plus any correction.
                    A row that stays positive wherever the step lets the points go cannot
                    hold the line back, and is left out.
        slope:      how the rows change with the points.
        turned:     how the headings turn with the points.

        Returns the points, the cost they come at and what IPOPT did; no points if it did
        not keep its own rows.
        """
        able = np.flatnonzero(values - step * np.asarray(abs(slope).sum(axis=1)).ravel() <= 0)
        negative = np.flatnonzero(current[able] < 0)
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
        lbg = np.concatenate((lower, -most, zeros))
        ubg = np.concatenate((np.full(len(able), np.inf), most, zeros))
        solver = ca.nlpsol('pass', 'ipopt', {
            'x': ca.vertcat(x, slack), 'f': cost + self.elastic * ca.sum1(slack),
            'g': ca.vertcat(*straight, bent)}, self.options)
        at_guess = values[able] + slope[able] @ (guess - x0)
        out = solver(x0=np.concatenate((guess, np.maximum(0., lower - at_guess)[negative])),
                     lbg=lbg, ubg=ubg,
                     lbx=np.concatenate((x0 - step, np.zeros(len(negative)))),
                     ubx=np.concatenate((x0 + step, np.full(len(negative), np.inf))))
        ipopt = IpoptRun(solver.stats()['return_status'], int(solver.stats()['iter_count']),
                         len(lbg))
        self._solver = solver
        found, rows = np.asarray(out['x']).ravel(), np.asarray(out['g']).ravel()
        result, paid = found[:len(x0)], found[len(x0):]

        # IPOPT may end a slack a hair below zero, which the cost must not count as a gain.
        cost = self.evaluate(result.reshape(-1, 2))[0] + self.elastic * np.maximum(0., paid).sum()

        # IPOPT must have kept its own rows, whatever it calls its result.
        if np.max(np.concatenate((lbg - rows, rows - ubg))) > EPS:
            result = None

        return result, cost, ipopt

    def solve(self, xy: np.ndarray, bodies: Sequence[BodyWalls], points: Sequence[PointWalls],
              curvature_limit: float, heading_range: tuple[float, float] | None,
              step: float) -> PassResult:
        """
        Run one pass from xy.

        bodies, points:     the walls of the body poses and of the base_links, from free_space.
        curvature_limit:    the most the line may curve at a point.
        heading_range:      the angles the start point may face between, measured from the
                            direction given as `start`; None for no limit.
        step:               the most a coordinate may move.
        """
        x0 = xy.ravel()
        picked = self._picked(bodies, points)
        current, slope = self._kept(xy, picked, curvature_limit, heading_range)
        short = _short(current, self.met)
        cost_before = self.evaluate(xy)[0] + self.elastic * short
        turned = self._turned(xy)

        guess, correction, runs = x0, np.zeros(len(current)), []
        for solves in range(1, _CORRECTIONS + 2):
            result, cost, run = self._straight(x0, guess, current, current + correction, slope,
                                               turned, step)
            runs.append(run)
            ipopt = IpoptRun(run.status, sum(r.iterations for r in runs), run.rows, solves)
            if result is None:
                break

            """
            IPOPT resolves the cost to about `gain` of it. With no more than that to gain,
            the line stays where it is; a solve that ends worse by more than that went
            astray, and the step is too long.
            """
            gained = cost_before - cost
            if gained < -self.gain * cost_before:
                break

            if gained <= self.gain * cost_before:
                return PassResult(xy, True, True, short, short, short, ipopt)

            moved = result.reshape(-1, 2)
            straight = current + slope @ (result - x0)
            said = straight + correction
            true = self._kept(moved, picked, curvature_limit, heading_range)[0]
            promised, after = _short(said, self.met), _short(true, self.met)

            # A legal line stays legal; one that is not comes half as much closer as promised.
            if after == 0 or (short > 0 and short - after >= (short - promised) / 2):
                return PassResult(moved, True, solves == 1, short, promised, after, ipopt)

            # Solve again with every row shifted to where it truly ended at this move.
            guess, correction = result, true - straight

        return PassResult(xy, False, False, short, short, short, ipopt)
