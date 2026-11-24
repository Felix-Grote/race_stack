"""
The checks a route manifest from the editor must pass, in order, the first failure refusing it.

legal:      every section covers no area off the kept road's cell squares (walls.py), measured
            against their exact union.
route:      the route package reads the manifest (validate_route), builds the lap
            (centre_curve), finds its gate crossings and samples it; and, given a car, works
            out the portal zones for the car's reach.
wide:       given a car, no section's walls come closer than the car's width plus its margin
            on both sides: there the car cannot pass, and the optimizer would only find out
            after a long run.
"""
import numpy as np
import shapely
from shapely.geometry import LineString, Polygon
from shapely.ops import nearest_points

from .track_map import AnnotationError, TrackMap
from .walls import AREA_EPS_M2, legal_union
from ..car import Car
from ..route.errors import GeometryError, LapError, RouteError
from ..route.lap import centre_curve, LapCurve
from ..route.manifest import validate_route
from ..route.portals import portal_crossings
from ..route.sampling import sample_lap
from ..route.track import Route
from ..route.zones import portal_zones, reach_boundaries


def check(payload: dict, track_map: TrackMap, kept: np.ndarray,
          car: Car | None = None) -> tuple[Route, LapCurve]:
    """Return the route and its lap, or refuse the manifest at the first failed check."""
    legal = legal_union(track_map, kept)
    for section in payload['sections']:
        outside = Polygon(list(section['right']) + list(reversed(section['left']))) \
            .difference(legal)
        if outside.area > AREA_EPS_M2:
            worst = max(shapely.get_parts(outside), key=lambda g: g.area)
            x, y = shapely.centroid(worst).coords[0]
            raise AnnotationError(f'section {section["uid"]} covers {outside.area:.6f} m2 off '
                                  f'the kept road (marked red)',
                                  at_px=[track_map.world_to_pixel((x, y))])

    try:
        route = validate_route(payload)
        lap = centre_curve(route)
        portal_crossings(lap)
        sample_lap(lap, 0.25)
        if car is not None:
            anchors = [q for zone in portal_zones(route, car.reach_m)
                       for q in reach_boundaries(lap, zone)]
            sample_lap(lap, 0.25, extra_anchors=anchors)
    except (RouteError, LapError, GeometryError) as exc:
        raise AnnotationError(f'the route package refuses the route: {exc}') from exc

    if car is not None:
        _check_width(route, track_map, car)

    return route, lap


def _check_width(route: Route, track_map: TrackMap, car: Car) -> None:
    """Refuse the route where a section is narrower than the car plus its margin."""
    needed = car.width_m + 2 * car.margin_m
    for section in route.sections:
        left, right = LineString(section.left), LineString(section.right)
        gap = left.distance(right)
        if gap < needed:
            a, b = nearest_points(left, right)
            middle = ((a.x + b.x) / 2, (a.y + b.y) / 2)
            raise AnnotationError(
                f'section {section.uid} narrows to {gap:.2f} m, and {car.name} needs '
                f'{needed:.2f} m: its {car.width_m:.2f} m plus {car.margin_m:.2f} m of margin '
                f'on each side (marked red). Widen the road there or cut it off',
                at_px=[track_map.world_to_pixel(middle)])
