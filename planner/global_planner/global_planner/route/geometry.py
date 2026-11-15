"""
Small planar geometry helpers for walls and sections, built on shapely.

points:     (x, y) tuples in metres; polygons are tuples of points, not closed.
EPS:        tolerance in metres for "the same point"; coordinates stay within 1e5 m.
"""
from collections.abc import Iterator
import math

from shapely.geometry import LinearRing, LineString, Polygon

EPS = 1e-9

XY = tuple[float, float]
Chain = tuple[XY, ...]


def sub(a: XY, b: XY) -> XY:
    """Return the vector a - b."""
    return (a[0] - b[0], a[1] - b[1])


def cross(a: XY, b: XY) -> float:
    """Return the z component of a x b; positive when b turns left from a."""
    return a[0] * b[1] - a[1] * b[0]


def dot(a: XY, b: XY) -> float:
    """Return the dot product of a and b."""
    return a[0] * b[0] + a[1] * b[1]


def distance(a: XY, b: XY) -> float:
    """Return the distance between a and b."""
    return math.hypot(*sub(a, b))


def outline(left: Chain, right: Chain) -> Chain:
    """Return a section's outline from its walls: the right wall, then the left one backwards."""
    return right + left[::-1]


def edges(poly: Chain) -> Iterator[tuple[XY, XY]]:
    """Return the edges of a polygon, including the closing one."""
    return zip(poly, poly[1:] + poly[:1])


def chains_touch(a: Chain, b: Chain) -> bool:
    """Check that the polylines a and b come within EPS of each other."""
    return LineString(a).distance(LineString(b)) <= EPS


def covers(poly: Chain, chain: Chain) -> bool:
    """Check that the polyline chain lies inside poly, its boundary included, within EPS."""
    return Polygon(poly).buffer(EPS).covers(LineString(chain))


def counterclockwise(poly: Chain) -> bool:
    """Check that the polygon's points run counterclockwise."""
    return LinearRing(poly).is_ccw


def simple_polygon(poly: Chain) -> bool:
    """Check for a ring of 3+ points without zero-length edges, self-contact or zero area."""
    if len(poly) < 3 or any(distance(a, b) <= EPS for a, b in edges(poly)):
        return False

    return LinearRing(poly).is_simple and Polygon(poly).area > EPS
