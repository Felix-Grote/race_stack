"""The track as data: sections of road, the portals joining them, and the route."""
from dataclasses import dataclass
from functools import cached_property
from itertools import accumulate

from .geometry import Chain, distance, outline, XY


@dataclass(frozen=True)
class Section:
    """
    One stretch of road, driven from its start cap to its end cap.

    uid:            unique section name.
    surface:        the physical surface it lies on; sections on one surface share it.
    centreline:     derived from the walls, from start-cap to end-cap midpoint; every
                    distance along the section is measured on it.
    left, right:    the walls in driving direction; right + reversed left
                    closes the section polygon.
    max_speed_mps:  speed limit over the whole section; to change it, cut a new section.
    """

    uid: str
    surface: str
    centreline: Chain
    left: Chain
    right: Chain
    max_speed_mps: float

    @property
    def polygon(self) -> Chain:
        """Return the section outline, counterclockwise."""
        return outline(self.left, self.right)

    @cached_property
    def length(self) -> float:
        """Return the length of the centreline in metres."""
        return sum(distance(a, b) for a, b in zip(self.centreline, self.centreline[1:]))


@dataclass(frozen=True)
class Portal:
    """
    The join from section `source` to section `target`.

    uid:                unique portal name, source_to_target.
    source, target:     uids of the sections before and after the gate.
    gate:               the shared cap, from the right wall to the left wall,
                        so it points to the driver's left while crossing.

    Where the portal applies depends on the car; see zones.portal_zones.
    """

    uid: str
    source: str
    target: str
    gate: tuple[XY, XY]

    def joins(self, section_uid: str) -> bool:
        """Check that section_uid is one of the two sections the portal joins."""
        return section_uid in (self.source, self.target)


@dataclass(frozen=True)
class Start:
    """
    Where the car stands before the race.

    zone:           the start box: polygon base_link stands in.
    heading_range:  (from, to) directions the car may face there, in radians.
    """

    zone: Chain
    heading_range: tuple[float, float]


@dataclass(frozen=True)
class Route:
    """
    One closed lap.

    sections:   in driving order.
    portals:    portal i joins section i to section i + 1, the last one closes the lap.
    start:      where the car starts.
    digest:     SHA-256 of the manifest (keys sorted), to record which track was used.
    """

    sections: tuple[Section, ...]
    portals: tuple[Portal, ...]
    start: Start
    digest: str

    @cached_property
    def section_bounds(self) -> tuple[float, ...]:
        """Return the lap progress q where each section starts, plus the lap length."""
        return (0.,) + tuple(accumulate(s.length for s in self.sections))
