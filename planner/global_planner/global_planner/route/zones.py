"""
Where each portal applies for a given car.

rule:       a portal applies where the car's reference point is within the car's reach
            of its gate, on a piece of one of the two sections it joins; there the body
            may overlap both sections. The owner test keeps a bridge deck passing near
            the gate from counting.
support:    the union of both section polygons, clipped to within reach of the gate;
            the connected part that contains the gate.
own road:   the section the car is on always counts as road for it; the support only
            adds where the body may spill into the neighbour.
boundaries: on a given lap, the q where the line enters and leaves a portal's reach;
            they depend on the line, so they are computed per lap. They need not come
            in pairs: a section that bends back can start within reach of its own end gate.
"""
from dataclasses import dataclass
from functools import cached_property
import math

import numpy as np
from numpy.polynomial.polynomial import polyval
from numpy.typing import ArrayLike
from scipy.optimize import brentq
import shapely
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

from .errors import require, RouteError
from .geometry import Chain, XY
from .lap import LapCurve
from .track import Portal, Route


@dataclass(frozen=True)
class PortalZone:
    """
    One portal's zone for one car.

    portal:     the portal, with its gate and the two sections it joins.
    reach_m:    the car's reach; see Car.reach_m.
    support:    polygon where both sections count as road for the body.
    """

    portal: Portal
    reach_m: float
    support: Chain

    @cached_property
    def _gate(self) -> LineString:
        return LineString(self.portal.gate)

    def gap(self, xy: ArrayLike) -> float | np.ndarray:
        """Return how far beyond reach of the gate each point lies; negative within reach."""
        return shapely.distance(self._gate, shapely.points(xy)) - self.reach_m

    def applies(self, xy: XY, section_uid: str) -> bool:
        """Check the portal applies at reference point xy on a piece of section_uid."""
        return self.portal.joins(section_uid) and bool(self.gap(xy) <= 0)


def portal_zones(route: Route, reach_m: float) -> tuple[PortalZone, ...]:
    """Return every portal's zone for a car of the given reach (Car.reach_m)."""
    require(math.isfinite(reach_m) and reach_m > 0, 'reach_m must be positive and finite')

    zones = []
    for i, portal in enumerate(route.portals):
        source, target = route.sections[i], route.sections[(i + 1) % len(route.sections)]
        gate = LineString(portal.gate)
        joined = unary_union([Polygon(source.polygon), Polygon(target.polygon)])
        near = joined.intersection(gate.buffer(reach_m))
        parts = [g for g in shapely.get_parts(near) if g.intersects(gate)]
        if len(parts) != 1 or not parts[0].covers(gate) or parts[0].interiors:
            raise RouteError(f'portal {portal.uid}: within {reach_m:.2f} m of the gate, the '
                             f'road is not one piece without holes')

        support = tuple(tuple(p) for p in parts[0].exterior.coords[:-1])
        zones.append(PortalZone(portal, reach_m, support))

    return tuple(zones)


def reach_boundaries(lap: LapCurve, zone: PortalZone, steps: int = 8) -> tuple[float, ...]:
    """
    Return the q where the line enters or leaves the zone's reach of its gate.

    steps:  brackets per cubic piece; an entry and exit closer together than 1 / steps
            of a piece cancel out and are missed.
    """
    found = []
    t = np.linspace(0., 1., steps + 1)
    for i, segment in enumerate(lap.curve.segments):
        if not zone.portal.joins(lap.curve.owners[i]):
            continue

        """
        polyval does the same Horner arithmetic as CubicSegment.evaluate, bit for bit, so
        the grid's signs match the gap brentq evaluates again at the bracket ends.
        """
        values = zone.gap(polyval(t, np.asarray(segment.coefficients).T).T)
        for a, b, fa, fb in zip(t, t[1:], values, values[1:]):
            if fa == 0:
                found.append(lap.progress(i, a))
            elif fa * fb < 0:
                root = brentq(lambda x: zone.gap(segment.evaluate(x)), a, b)
                found.append(lap.progress(i, root))

    return tuple(sorted({q % lap.period for q in found}))
