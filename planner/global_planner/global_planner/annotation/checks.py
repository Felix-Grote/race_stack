"""
The checks a route manifest from the editor must pass, in order, the first failure refusing it.

legal:      every section covers no area off the kept road's cell squares (walls.py), measured
            against their exact union.
route:      the route package reads the manifest (validate_route), builds the lap
            (centre_curve), finds its gate crossings and samples it; and, given a car, works
            out the portal zones for the car's reach.
"""
import numpy as np
import shapely
from shapely.geometry import Polygon

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

    return route, lap
