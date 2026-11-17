"""
The points of a lap for one car: what each allows, and the fastest speeds the car can drive.

caps:       what each point allows by itself: the track limit it is given, the car's top
            speed, the speed its tyres hold the bend at, and the speed its steering keeps
            up with.
turning:    a lap that turns tighter anywhere than the car can steer is refused: no speed
            makes it drivable. The optimizer holds its line to the same limit.
steering:   between two points the steering angle changes no faster than the car steers.
            Both points are capped at the speed that takes the gap in just that time. That
            is on the safe side: it would be enough for the two speeds to average it.
between:    from one point to the next the car speeds up or brakes steadily. That
            acceleration must lie between the lowest and the highest the car can make, at
            both points (model.py).
passes:     starting from the caps, speeds are lowered backwards around the lap until the
            car can brake for every point, then forwards until it can speed up to every
            point, and so on until a round lowers no speed by more than resolved_mps.
            Speeds are only ever lowered.
gaps:       two points must be close enough for the bend between them:
            2 gap (a |k| / a_lat_max + drag_coeff / m) below 1, with a the larger of a_max
            and |a_min| and k the sharper of the two bends; a lap with a longer gap is
            refused. Lowering the speed at one end of a gap then never makes a higher
            speed possible at the other, speeding up or braking, so with grip_exponent 1
            the passes find the fastest profile; no faster one was found on any lap
            tried. Above 1 they need not: there a slightly faster profile can exist. The
            halving needs the drag part of the same rule whatever the exponent.
checked:    the settled speeds can be checked against the car's limits: its top speed, the
            bend, the steering, and both ends of what it can speed up and brake by, with
            the car's answers for all points at once and not the halving the passes use.
            Speeds that break one are refused. The track limit is not among them: it comes
            in as a cap, and the speeds never rise above their caps.
fixed:      the arrays are the lap's own copies and cannot be written to; the speeds
            cannot either, once settled.
"""
import math

import numpy as np

from .errors import SpeedError
from .model import Bound, CarModel

# How much tighter than the car can steer a lap may turn and still be taken. Copied from
# _RESOLVED in optimizer/solve.py, which is how closely the optimizer holds its line to the
# car's turning limit: keep the two the same.
_TURNING_SLACK = 1e-3


def _next(values: np.ndarray) -> np.ndarray:
    """Return, for every point, the value at the next point around the lap."""
    return np.roll(values, -1)


def _to_next(values: np.ndarray) -> np.ndarray:
    """Return how much values change from each point to the next around the lap."""
    return _next(values) - values


class LapPoints:
    """
    The points of one closed lap for one car: what each allows, and the speeds found for them.

    car:        the car with its grip setting.
    gap_m:      the distance from each point to the next; the last one back to the first.
    curvature:  the curvature at each point.
    angle:      the steering angle at each point.
    cap_mps:    the most each point allows by itself: the track limit it is given, the
                car's top speed, the bend, and the steering on the gaps before and after.
    speed_mps:  the speed at each point: the caps to begin with, lowered by settle().
    accel_mps2: the steady acceleration from each point to the next.
    took_s:     the time from each point to the next.

    Everything but the speeds, and what follows from them, is worked out once, here.
    """

    def __init__(self, car: CarModel, gap_m: np.ndarray, curvature: np.ndarray,
                 track_cap_mps: np.ndarray) -> None:
        limits = car.limits
        gap_m, curvature, track_cap_mps = (
            np.array(values, dtype=float) for values in (gap_m, curvature, track_cap_mps))
        count = track_cap_mps.size
        given = (('gap_m', gap_m), ('curvature', curvature), ('track_cap_mps', track_cap_mps))
        if not count or any(values.shape != (count,) for _, values in given):
            raise SpeedError('gap_m, curvature and track_cap_mps need one value for each point')

        for name, values in given:
            if not np.all(np.isfinite(values)):
                raise SpeedError(f'{name} must be finite at every point')

        if np.min(gap_m) <= 0 or np.min(track_cap_mps) <= 0:
            raise SpeedError('gap_m and track_cap_mps must be positive at every point')

        # Two points must be close enough for the bend between them; see `gaps` above.
        sharper = np.maximum(np.abs(curvature), np.abs(_next(curvature)))
        with np.errstate(divide='ignore'):
            grip = max(limits.a_max, abs(limits.a_min))
            furthest = 1 / (2 * (grip * sharper / limits.a_lat_max
                                 + limits.drag_coeff / limits.m))

        widest = int(np.argmax(gap_m - furthest))
        if gap_m[widest] >= furthest[widest]:
            raise SpeedError(f'points {widest} and {(widest + 1) % count} are '
                             f'{gap_m[widest]:.3f} m apart; where the line bends as it does '
                             f'there, this car needs them closer than '
                             f'{furthest[widest]:.3f} m (lower spacing_m)')

        tightest = math.tan(limits.max_steering_angle) / limits.wheelbase
        sharpest = int(np.argmax(np.abs(curvature)))
        if abs(curvature[sharpest]) > tightest * (1 + _TURNING_SLACK):
            raise SpeedError(f'point {sharpest} turns on a radius of '
                             f'{1 / abs(curvature[sharpest]):.3f} m; the car turns no tighter '
                             f'than wheelbase / tan(max_steering_angle), {1 / tightest:.3f} m')

        self.car, self.gap_m, self.curvature = car, gap_m, curvature
        self.angle = car.steering_angle(curvature)
        self._turn = np.abs(_to_next(self.angle))
        self._bend_mps = car.bend_speed(curvature)

        # No faster over a gap than the steering can follow, which caps both of its ends.
        with np.errstate(divide='ignore'):
            steering = limits.max_steering_velocity * gap_m / self._turn

        self.cap_mps = np.minimum(limits.v_max, np.minimum.reduce((
            track_cap_mps, self._bend_mps, steering, np.roll(steering, 1))))
        self.speed_mps = self.cap_mps.copy()
        for fixed in (self.gap_m, self.curvature, self.angle, self.cap_mps):
            fixed.flags.writeable = False

    @property
    def accel_mps2(self) -> np.ndarray:
        """Return the steady acceleration from each point to the next."""
        return _to_next(self.speed_mps ** 2) / (2 * self.gap_m)

    @property
    def took_s(self) -> np.ndarray:
        """Return the time from each point to the next."""
        return 2 * self.gap_m / (self.speed_mps + _next(self.speed_mps))

    def _fastest(self, here: int, other: int, bound: Bound) -> float:
        """
        Return the fastest speed at point `here`, given the speed at its neighbour `other`.

        bound:  HIGHEST if the car comes from `other` and can speed up only so hard;
                LOWEST if it goes on to `other` and can brake only so hard.

        The steady acceleration between the two must keep within that bound at both. The
        faster `here`, the nearer the bound, so the speeds that work are all those up to
        one speed. It is found by halving, down to two neighbouring numbers, and the one
        that works is returned.
        """
        towards = 1 if bound is Bound.HIGHEST else -1
        gap = self.gap_m[other if towards > 0 else here]
        bend, speed_there = self.curvature[here], self.speed_mps[other]
        at_other = float(self.car.accel(speed_there, self.curvature[other], bound))
        top = min(self.speed_mps[here],
                  math.sqrt(speed_there ** 2 + 2 * gap * towards * at_other))

        def over(speed: float) -> float:
            change = (speed ** 2 - speed_there ** 2) / (2 * gap)

            return change - towards * float(self.car.accel(speed, bend, bound))

        if over(top) <= 0:
            return top

        low, middle = 0., top / 2
        while low < middle < top:
            if over(middle) <= 0:
                low = middle
            else:
                top = middle

            middle = (low + top) / 2

        return low

    def settle(self, resolved_mps: float, max_rounds: int) -> int:
        """
        Lower the speeds until the car can drive them; return the rounds it took.

        resolved_mps:   the speeds have settled once a round lowers none by more than this.
        max_rounds:     rounds allowed before giving up.
        """
        count = len(self.speed_mps)

        # Once around each way in a round; what crosses the lap's seam is felt in the next.
        for rounds in range(1, max_rounds + 1):
            before = self.speed_mps.copy()
            for i in reversed(range(count)):
                self.speed_mps[i] = self._fastest(i, (i + 1) % count, Bound.LOWEST)

            for i in range(count):
                j = (i + 1) % count
                self.speed_mps[j] = self._fastest(j, i, Bound.HIGHEST)

            if np.max(before - self.speed_mps) <= resolved_mps:
                self.speed_mps.flags.writeable = False

                return rounds

        raise SpeedError(f'the speeds did not settle in {max_rounds} rounds; a car '
                         f'that can hardly hold its speed against the air drag settles slowly '
                         f'and needs more (max_rounds)')

    def check(self, resolved_mps: float) -> None:
        """
        Raise SpeedError unless the speeds keep every limit of the car.

        Each limit is a number per point that must not be positive: how far over it the
        point is, or the way from it to the next point.
        """
        car, speed, accel = self.car, self.speed_mps, self.accel_mps2
        if not np.all(np.isfinite(speed)) or np.min(speed) <= 0:
            raise SpeedError('the speed profile holds a speed that is not above zero')

        highest = car.accel(speed, self.curvature, Bound.HIGHEST)
        lowest = car.accel(speed, self.curvature, Bound.LOWEST)

        # A speed off by resolved_mps puts the acceleration over a gap off by this much.
        slack = resolved_mps * np.maximum(speed, _next(speed)) / self.gap_m
        over = {
            'the top speed': (speed - car.limits.v_max, 'm/s'),
            'what the tyres hold in the bend': (speed - self._bend_mps, 'm/s'),
            'what the steering can follow': (
                self._turn - car.limits.max_steering_velocity * self.took_s, 'rad'),
            'how hard the car can speed up': (
                accel - slack - np.minimum(highest, _next(highest)), 'm/s2'),
            'how hard the car can brake': (
                np.maximum(lowest, _next(lowest)) - accel - slack, 'm/s2'),
        }

        # Each is over in its own unit; resolved_mps is next to nothing in any of them.
        for limit, (by, unit) in over.items():
            worst = int(np.argmax(by))
            if not by[worst] <= resolved_mps:
                raise SpeedError(f'the speed profile is over {limit} at point {worst}, '
                                 f'by {by[worst]:.3g} {unit}')
