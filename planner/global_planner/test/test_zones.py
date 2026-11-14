"""Wherever the real body reaches across a gate, that portal applies and its support covers it."""
from global_planner.car import Car
from global_planner.route.errors import RouteError
from global_planner.route.lap import centre_curve
from global_planner.route.sampling import sample_lap
from global_planner.route.zones import portal_zones
import pytest
from shapely.geometry import LineString, Polygon
from tracks import LONG, SHORT, stadium, wobbled


@pytest.mark.parametrize('cuts_m', (LONG, SHORT), ids=('long sections', 'short sections'))
@pytest.mark.parametrize('wobble', (0., 0.3))
def test_portal_applies_wherever_the_body_crosses_its_gate(car: Car, cuts_m: tuple[float, ...],
                                                           wobble: float) -> None:
    route = stadium(straight=6., radius=1.5, width=1.4, cuts_m=cuts_m)
    lap = wobbled(centre_curve(route), wobble, waves=3) if wobble else centre_curve(route)
    zones = portal_zones(route, car.reach_m)
    sections = {s.uid: Polygon(s.polygon) for s in route.sections}
    for v in sample_lap(lap, 0.05):
        body = car.body(v.xy, v.tangent).buffer(car.margin_m)
        for zone in zones:
            if not zone.portal.joins(v.section_uid) or not body.intersects(
                    LineString(zone.portal.gate)):
                continue

            neighbour = ({zone.portal.source, zone.portal.target} - {v.section_uid}).pop()
            spill = body.intersection(sections[neighbour])

            assert zone.applies(v.xy, v.section_uid), (zone.portal.uid, v.q)
            assert spill.difference(Polygon(zone.support).buffer(1e-7)).area <= 1e-9


def test_section_too_short_for_the_car_is_rejected(car: Car) -> None:
    """On the inside of a bend the gates of a 0.8 m section come closer than the car reaches."""
    route = stadium(straight=6., radius=1.5, width=1.4, cuts_m=(0., 7., 7.8, 13., 20.))

    with pytest.raises(RouteError, match='too short for this car'):
        portal_zones(route, car.reach_m)
