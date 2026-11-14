"""Where a car on a lap is legal, written apart from the optimizer's own check of its result."""
from global_planner.car import Car
from global_planner.route.lap import LapCurve
from global_planner.route.sampling import sample_lap
from global_planner.route.track import Route
from global_planner.route.zones import portal_zones
from shapely.geometry import Point, Polygon


def off_road(route: Route, car: Car, lap: LapCurve, spacing: float = 0.01) -> list[float]:
    """
    Return the q of every sample of lap, every `spacing` metres, where the car is not legal.

    Legal: base_link lies in the section that owns it, and every piece of the body plus
    margin outside that section lies in the support of one portal that applies there. The
    optimizer checks one union of areas instead; the body, the supports and where a portal
    applies are the route's and the car's, the same for both.
    """
    zones = portal_zones(route, car.reach_m)
    sections = {s.uid: Polygon(s.polygon).buffer(1e-9) for s in route.sections}
    supports = [Polygon(z.support).buffer(1e-9) for z in zones]
    off = []
    for v in sample_lap(lap, spacing):
        own = sections[v.section_uid]
        applying = [s for z, s in zip(zones, supports) if z.applies(v.xy, v.section_uid)]
        outside = car.body(v.xy, v.tangent).buffer(car.margin_m).difference(own)
        pieces = [g for g in getattr(outside, 'geoms', [outside]) if not g.is_empty]
        legal = all(any(s.covers(g) for s in applying) for g in pieces)
        if not legal or not own.covers(Point(v.xy)):
            off.append(v.q)

    return off
