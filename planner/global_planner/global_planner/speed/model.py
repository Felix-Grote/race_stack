"""
What a car can do at a speed on a bend: hold it, speed up, brake, steer.

sideways:   holding a bend of curvature k at speed v takes v^2 |k| of sideways acceleration,
            which the tyres give up to the car's a_lat_max.
grip left:  what the tyres use sideways they do not have along the car. With u the part of
            the sideways grip in use, (1 - u^e)^(1/e) of the grip along the car is left.
            The exponent e is the planner's choice, from 1 (what is used sideways comes
            off the grip along the car part for part) to 2 (an ellipse, which leaves more).
highest:    the hardest the car can speed up: the lesser of what the tyres have left of
            a_max and what the motor gives at that speed, less the air drag. It can be
            negative: a car with no grip left along it slows down.
lowest:     the hardest it can brake, a negative acceleration: what the tyres have left of
            a_min, less the air drag.
steering:   the angle of the front wheels on a bend, for a car that does not slide:
            atan(wheelbase k).

Every question takes one speed and curvature or arrays of them.
"""
from dataclasses import dataclass
from enum import Enum
from functools import cached_property

import numpy as np

from ..car import CarLimits

# A number, or an array of them: the car answers for one point or for many at once.
Numbers = float | np.ndarray


class Bound(Enum):
    """Which end of the accelerations a car can make: speeding up hardest, or braking hardest."""

    HIGHEST = 'highest'
    LOWEST = 'lowest'


@dataclass(frozen=True)
class CarModel:
    """
    One car with the planner's grip setting, to ask what it can do.

    limits:         the car's limits, from its car file.
    grip_exponent:  how cornering shares the tyres' grip with speeding up and braking.
    """

    limits: CarLimits
    grip_exponent: float

    @cached_property
    def _motor(self) -> tuple[np.ndarray, np.ndarray]:
        """Return the speeds and the accelerations of the motor's points."""
        speeds, accelerations = zip(*self.limits.a_motor)

        return np.array(speeds), np.array(accelerations)

    def bend_speed(self, curvature: Numbers) -> Numbers:
        """Return the fastest steady speed on a bend; infinite on a straight."""
        with np.errstate(divide='ignore'):
            return np.sqrt(self.limits.a_lat_max / np.abs(curvature))

    def grip_left(self, speed: Numbers, curvature: Numbers) -> Numbers:
        """Return the part of the grip along the car left at a speed on a bend, 0 to 1."""
        used = np.minimum(1., speed ** 2 * np.abs(curvature) / self.limits.a_lat_max)

        return (1. - used ** self.grip_exponent) ** (1. / self.grip_exponent)

    def motor_accel(self, speed: Numbers) -> Numbers:
        """Return the motor's acceleration envelope before drag."""
        return np.interp(speed, *self._motor)

    def accel(self, speed: Numbers, curvature: Numbers, bound: Bound) -> Numbers:
        """Return the highest or the lowest acceleration the car can make at a speed on a bend."""
        left = self.grip_left(speed, curvature)
        drag = self.limits.drag_coeff * speed ** 2 / self.limits.m

        if bound is Bound.LOWEST:
            return self.limits.a_min * left - drag
        return np.minimum(self.limits.a_max * left, self.motor_accel(speed)) - drag

    def steering_angle(self, curvature: Numbers) -> Numbers:
        """Return the angle of the front wheels on a bend, in radians."""
        return np.arctan(self.limits.wheelbase * curvature)
