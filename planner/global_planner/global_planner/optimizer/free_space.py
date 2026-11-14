"""
Where the car may be, as the walls the optimizer keeps it from.

base_link:  stays inside the section that owns its point.
body:       stays on its section's road: the section plus the supports of the two portals at
            its ends. A body whose base_link is in its section can only reach a neighbour
            through the gate, and then that portal applies, so this is the portal rule.
walls:      the boundary of an area, except the rounded edge of a support: that edge only
            marks how far a body can reach across a gate, and no body gets to it.
plane:      where a corner of the body is what comes nearest a wall, every corner of the
            body stays beyond the wall's line.
vertex:     where an edge of the body is what comes nearest a wall, the wall's two ends stay
            beyond that edge. The edge turns with the body, so the body can turn along a
            wall corner without backing off.
passing:    a wall corner that passes the front or the rear of the body between two poses is
            nearest a corner of the body at that moment, so it gets a vertex there: beside
            the body, beyond its side edge. Only wall corners that poke into the area need
            it; one the area wraps around is held by its two walls.
wrong side: a wall the pose touches, or lies beyond, asks the body back to its road side;
            the optimizer recovers from what such a wall is short of (problem.py).
"""
from dataclasses import dataclass
from functools import cached_property
import math

import numpy as np
import shapely
from shapely.geometry import Point, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

from ..car import Car
from ..route.geometry import EPS, XY
from ..route.track import Route
from ..route.zones import PortalZone


@dataclass(frozen=True)
class Plane:
    """
    A wall's line that every corner p of a pose stays beyond: normal . (p - anchor) >= clearance.

    normal:     unit vector pointing to the side the pose keeps to.
    anchor:     a point on the wall.
    """

    normal: XY
    anchor: XY


@dataclass(frozen=True)
class Vertex:
    """
    A wall point that stays beyond one edge of the body by the clearance.

    edge:   index of the edge in Car.edges.
    xy:     the wall point.
    """

    edge: int
    xy: XY


@dataclass(frozen=True)
class _Walls:
    """
    The wall segments on the boundary of an area.

    lines, tree:    the segments, and an index of them.
    starts, ends:   their two points.
    inward:         their unit normals into the area.
    pokes:          whether the boundary turns away from the area at their start, so that
                    the wall corner there pokes into it.
    """

    lines: np.ndarray
    tree: shapely.STRtree
    starts: np.ndarray
    ends: np.ndarray
    inward: np.ndarray
    pokes: np.ndarray


@dataclass(frozen=True)
class _Contacts:
    """
    The walls within reach of a shape, and how the shape stands to each.

    near:       the walls' indices; the nearest wall alone for a shape off the area with none
                in reach.
    on_wall:    each wall's point nearest the shape.
    on_shape:   the shape's point nearest each wall.
    gap:        the distance between the two.
    wrong:      whether the shape touches the wall or lies beyond it.
    """

    near: np.ndarray
    on_wall: np.ndarray
    on_shape: np.ndarray
    gap: np.ndarray
    wrong: np.ndarray


def _framed(points: np.ndarray, xy: XY, heading: XY) -> np.ndarray:
    """Return points in the frame of a pose: ahead and to the left of base_link."""
    return (points - np.asarray(xy)) @ np.array([heading, (-heading[1], heading[0])]).T


@dataclass(frozen=True)
class Area:
    """
    A polygon and the walls on its boundary.

    polygon:    the area.
    wall_lines: lines the wall segments of the boundary lie on; the whole boundary if None.
    """

    polygon: BaseGeometry
    wall_lines: BaseGeometry | None = None

    @cached_property
    def _tolerant(self) -> BaseGeometry:
        tolerant = self.polygon.buffer(EPS)
        shapely.prepare(tolerant)

        return tolerant

    @cached_property
    def _walls(self) -> _Walls:
        starts, ends, pokes = [], [], []
        for part in shapely.get_parts(self.polygon):
            # Oriented, the area lies left of every ring: the outline and the holes.
            part = orient(part, sign=1.)
            for ring in (part.exterior, *part.interiors):
                xy = np.asarray(ring.coords)
                along = xy[1:] - xy[:-1]
                before = np.roll(along, 1, axis=0)
                starts.append(xy[:-1])
                ends.append(xy[1:])
                pokes.append(before[:, 0] * along[:, 1] - before[:, 1] * along[:, 0] < 0)

        starts, ends, pokes = np.vstack(starts), np.vstack(ends), np.concatenate(pokes)
        if self.wall_lines is not None:
            middles = shapely.points((starts + ends) / 2)
            on_wall = shapely.distance(self.wall_lines, middles) <= EPS
            starts, ends, pokes = starts[on_wall], ends[on_wall], pokes[on_wall]

        along = ends - starts
        inward = np.column_stack((-along[:, 1], along[:, 0]))
        inward /= np.linalg.norm(along, axis=1)[:, None]
        lines = shapely.linestrings(np.stack((starts, ends), axis=1))

        return _Walls(lines, shapely.STRtree(lines), starts, ends, inward, pokes)

    def covers(self, shape: BaseGeometry) -> bool:
        """Check that shape lies in the area, within EPS of it counting as in it."""
        return bool(self._tolerant.covers(shape))

    def _contacts(self, shape: BaseGeometry, reach: float) -> _Contacts:
        """Return the walls within reach of shape and how shape stands to each."""
        walls = self._walls
        x0, y0, x1, y1 = shape.bounds
        near = walls.tree.query(shapely.box(x0 - reach, y0 - reach, x1 + reach, y1 + reach))
        covered = self.covers(shape)
        if not len(near) and not covered:
            near = walls.tree.query_nearest(shape)

        nearest = shapely.get_coordinates(shapely.shortest_line(walls.lines[near], shape))
        on_wall, on_shape = nearest[0::2], nearest[1::2]
        gap = np.linalg.norm(on_shape - on_wall, axis=1)
        wrong = gap <= EPS
        if not covered:
            wrong |= ~shapely.covers(self._tolerant, shapely.points(on_shape))

        return _Contacts(near, on_wall, on_shape, gap, wrong)

    def _planes(self, contacts: _Contacts) -> list[Plane]:
        """Return each wall in contacts as a plane: through its nearest point, or its own line."""
        walls = self._walls
        towards = contacts.on_shape - contacts.on_wall
        towards /= np.where(contacts.wrong, 1., contacts.gap)[:, None]

        return [Plane(tuple(walls.inward[k]), tuple(walls.starts[k])) if contacts.wrong[j]
                else Plane(tuple(towards[j]), tuple(contacts.on_wall[j]))
                for j, k in enumerate(contacts.near)]

    def point_planes(self, xy: XY, reach: float) -> list[Plane]:
        """Return the walls within reach of a point, as planes it stays beyond."""
        return self._planes(self._contacts(Point(xy), reach))

    def body_walls(self, car: Car, xy: XY, heading: XY,
                   reach: float) -> tuple[list[Plane], list[Vertex]]:
        """Return the walls within reach of the body at a pose, as planes and vertices."""
        walls = self._walls
        contacts = self._contacts(car.body(xy, heading), reach)
        planes = self._planes(contacts)

        """
        A wall both of whose ends lie as far beyond one edge of the body as the wall is from
        the body has that edge nearest it. The ends are taken in the body's frame.
        """
        wall_ends = np.stack((walls.starts[contacts.near], walls.ends[contacts.near]), axis=1)
        normals = np.array([normal for normal, _ in car.edges])
        distance = np.array([distance for _, distance in car.edges])
        beyond = (_framed(wall_ends, xy, heading) @ normals.T).min(axis=1) - distance
        nearest_edge = beyond.argmax(axis=1)

        kept, vertices = [], {}
        for j, k in enumerate(contacts.near):
            edge = int(nearest_edge[j])
            if contacts.wrong[j] or beyond[j, edge] < contacts.gap[j] - EPS:
                kept.append(planes[j])
                continue

            for end in (walls.starts[k], walls.ends[k]):
                vertices[(edge, *end)] = Vertex(edge, tuple(end))

        return kept, list(vertices.values())

    def passing(self, car: Car, before: tuple[XY, XY], after: tuple[XY, XY],
                reach: float) -> list[tuple[float, Vertex]]:
        """
        Return the wall corners that pass the front or the rear of the body between two poses.

        before, after:  the two poses, each as base_link and unit heading.

        Each wall corner comes with how far on the way from one pose to the other it passes,
        from 0 to 1, and the side edge of the body it is beside at that moment.
        """
        walls = self._walls
        around = reach + car.corner_m
        x, y = np.transpose((before[0], after[0]))
        near = walls.tree.query(shapely.box(x.min() - around, y.min() - around,
                                            x.max() + around, y.max() + around))
        corners = walls.starts[near[walls.pokes[near]]]
        first, second = _framed(corners, *before), _framed(corners, *after)
        side = {normal[1]: edge for edge, (normal, _) in enumerate(car.edges) if normal[1]}
        found = []
        for (ahead, aside), distance in car.edges:
            if aside:
                continue

            # How far beyond the front, or the rear, each wall corner lies at either pose.
            a, b = ahead * first[:, 0] - distance, ahead * second[:, 0] - distance
            for j in np.flatnonzero(a * b < 0):
                moment = a[j] / (a[j] - b[j])
                left = first[j, 1] + moment * (second[j, 1] - first[j, 1])
                if abs(left) - car.width_m / 2 <= reach:
                    found.append((float(moment), Vertex(side[math.copysign(1., left)],
                                                        tuple(corners[j]))))

        return found


class FreeSpace:
    """The areas the points of a lap and their bodies keep to, for one route and its zones."""

    def __init__(self, route: Route, zones: tuple[PortalZone, ...]) -> None:
        self.zones = zones
        sections = [Polygon(s.polygon) for s in route.sections]
        supports = [Polygon(z.support) for z in zones]
        self._sections = {s.uid: Area(p) for s, p in zip(route.sections, sections)}
        self._supports = {z.portal.uid: p for z, p in zip(zones, supports)}
        self._roads, self._roads_at = {}, {}
        for i, section in enumerate(route.sections):
            # Portal i - 1 leads into section i and portal i out of it.
            around = (i - 1, i, (i + 1) % len(sections))
            wall_lines = unary_union([sections[j].exterior for j in around])
            road = unary_union([sections[i], supports[i - 1], supports[i]])
            self._roads[section.uid] = Area(road, wall_lines)

    def section(self, section_uid: str) -> Area:
        """Return the area base_link of a point of section_uid keeps to."""
        return self._sections[section_uid]

    def road(self, section_uid: str) -> Area:
        """Return the area the body of a point of section_uid keeps to."""
        return self._roads[section_uid]

    def road_at(self, xy: XY, section_uid: str) -> Area:
        """Return the legal road with base_link at xy: its section and the supports applying."""
        applying = tuple(z.portal.uid for z in self.zones if z.applies(xy, section_uid))
        key = (section_uid, applying)
        if key not in self._roads_at:
            parts = [self._sections[section_uid].polygon] + [self._supports[k] for k in applying]
            self._roads_at[key] = Area(unary_union(parts))

        return self._roads_at[key]
