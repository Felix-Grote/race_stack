"""
The fastest speed at every point of a lap that the track's limits and the car allow.

points:     the lap is sampled on a grid of spacing_m, and at every knot of its curve,
            where the curvature peaks, at every section start and wherever the line enters
            or leaves a portal's reach.
lap:        a flying lap: the car passes the first point at the speed it reaches at the
            end. Starting from standstill is not planned here.
track:      one limit per section. Within a portal's reach the car's body may be on both
            sections, so the lower of the two limits applies there.
speeds:     the points with their track limits go to LapPoints (points.py), which adds the
            car's own caps, lowers the speeds until the car can drive them, and checks them.
"""
from dataclasses import dataclass

import numpy as np

from .errors import SpeedError
from .model import CarModel
from .points import LapPoints
from ..car import CarLimits, is_number
from ..route.lap import LapCurve
from ..route.sampling import LapSample, sample_at_station, sample_lap
from ..route.zones import PortalZone, reach_boundaries


@dataclass(frozen=True)
class SpeedSettings:
    """
    How the speed profile is worked out; planning choices, not car values.

    spacing_m:      the distance between neighbouring points of the grid. Grid points
                    next to a knot, a section start or the edge of a portal's reach are
                    left out, so two points can be up to twice this apart.
    grip_exponent:  how cornering shares the tyres' grip with speeding up and braking, from
                    1 (what is used sideways comes off the grip along the car part for part)
                    to 2 (an ellipse, which leaves more); see model.py. 1 is the more
                    careful, and what the stack's planner used.
    resolved_mps:   the speeds have settled once a round lowers none by more than this.
                    The result is only as settled, and its limits only as closely kept, as
                    this is small.
    max_rounds:     rounds allowed before giving up. A few do for a car that can hold its
                    speed; one that can hardly beat its air drag takes many more.
    """

    spacing_m: float = 0.1
    resolved_mps: float = 1e-6
    max_rounds: int = 200
    # If you change this, rework the gap rule in points.py: it is worked out for 1.
    grip_exponent: float = 1.

    def __post_init__(self) -> None:
        for name in ('spacing_m', 'grip_exponent', 'resolved_mps', 'max_rounds'):
            value = getattr(self, name)
            if not is_number(value) or value <= 0:
                raise SpeedError(f'{name} must be a positive, finite number')

        if not isinstance(self.max_rounds, int):
            raise SpeedError('max_rounds must be a whole number')

        if not 1 <= self.grip_exponent <= 2:
            raise SpeedError('grip_exponent must be between 1 and 2')


@dataclass(frozen=True)
class SpeedProfile:
    """
    The speeds of one flying lap.

    samples:    where each point is on the lap, in lap order. A sample's speed_limit_mps
                is its section's own limit; the limit applied at the point, the lower of
                two near a gate, is in points.cap_mps.
    points:     what each point allows and the speed found for it (LapPoints): gap_m,
                cap_mps, speed_mps, accel_mps2 and took_s.
    rounds:     rounds of passes it took for the speeds to settle.
    """

    samples: tuple[LapSample, ...]
    points: LapPoints
    rounds: int

    @property
    def time_s(self) -> np.ndarray:
        """Return when the car passes each point, counted from the first."""
        took = self.points.took_s

        return np.cumsum(took) - took

    @property
    def lap_time_s(self) -> float:
        """Return how long the lap takes."""
        return float(self.points.took_s.sum())


def _track_limits(lap: LapCurve, zones: tuple[PortalZone, ...],
                  samples: tuple[LapSample, ...]) -> np.ndarray:
    """
    Return the track's speed limit between each sample and the next.

    The stretch lies in one section, and a portal applies on all of it or on none, since
    the samples include where the line enters and leaves each portal's reach. So it is
    judged halfway along: a sample on the edge of a reach falls to either side by rounding.
    One case escapes: a line that clips a reach for less than an eighth of a curve piece is
    not seen to enter it (zones.reach_boundaries), and keeps the higher limit there.
    """
    limit = {s.uid: s.max_speed_mps for s in lap.route.sections}
    length = lap.curve.length
    limits = []
    for here, following in zip(samples, samples[1:] + samples[:1]):
        halfway = sample_at_station(lap, (here.s + (following.s - here.s) % length / 2) % length)
        allowed = limit[halfway.section_uid]
        for zone in zones:
            if zone.applies(halfway.xy, halfway.section_uid):
                allowed = min(allowed, limit[zone.portal.source], limit[zone.portal.target])

        limits.append(allowed)

    return np.array(limits)


def speed_profile(lap: LapCurve, zones: tuple[PortalZone, ...], limits: CarLimits,
                  settings: SpeedSettings = SpeedSettings()) -> SpeedProfile:
    """
    Return the fastest speeds around lap for a car of these limits.

    zones:  the car's portal zones on the lap's route (zones.portal_zones): where the lower
            of two sections' speed limits applies.
    """
    if tuple(zone.portal for zone in zones) != lap.route.portals:
        raise SpeedError("zones must be the portal zones of the lap's route, one for each "
                         'portal in lap order (zones.portal_zones)')

    anchors = [q for zone in zones for q in reach_boundaries(lap, zone)]
    samples = sample_lap(lap, settings.spacing_m, extra_anchors=(*anchors, *lap.q[:-1]))
    stations = np.array([v.s for v in samples])
    gap = (np.roll(stations, -1) - stations) % lap.curve.length

    # A point keeps to the limits of the stretch before it and of the one after.
    track = _track_limits(lap, zones, samples)
    points = LapPoints(CarModel(limits, settings.grip_exponent), gap,
                       np.array([v.curvature for v in samples]),
                       np.minimum(track, np.roll(track, 1)))
    rounds = points.settle(settings.resolved_mps, settings.max_rounds)
    points.check(settings.resolved_mps)

    return SpeedProfile(samples, points, rounds)
