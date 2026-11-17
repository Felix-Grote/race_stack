"""
Lap time and the car's speed rules, written for the solver.

When the optimizer is asked for the fastest line it moves the points and the car's speed at
every point together. This file writes down, as expressions the solver can work with, the
time a lap takes and the rules the speeds keep. The rules are those of speed/points.py, so
that a line the solver finds fast is fast by the speed profile too.

unknowns:   the square of the speed at every point. The steady acceleration over a gap is
            then (next - this) / (2 gap), a straight line in the speeds.
rows:       every rule is a number that must not be negative. Cornering takes its share of
            the grip part for part (grip_exponent 1 in speed/), so each rule with the bend
            in it is written twice, once for a bend to the left and once to the right.
bend:       speed^2 |k| stays within a_lat_max.
speeding:   over a gap the car speeds up no harder than its tyres have left, or its motor
            gives, less the air drag, at both ends of the gap.
braking:    and brakes no harder than its tyres have left plus the air drag, at both ends.
steering:   both ends of a gap are held to the speed that takes it in the time the steering
            needs to turn from one angle to the other.
caps:       the track's limit and the car's top speed are plain bounds on the unknowns,
            set for each pass by problem.py.
same rules: speed/model.py and speed/points.py state these rules for numbers. A change to
            a rule there belongs here too, and the other way round.
"""
import casadi as ca

from ..car import CarLimits


def _next(column: ca.SX) -> ca.SX:
    """Return, for every point, the value at the next point around the lap."""
    return ca.vertcat(column[1:], column[0])


def _motor(limits: CarLimits, speed: ca.SX) -> ca.SX:
    """Return what the motor gives at a speed: straight between its points, level beyond."""
    points = limits.a_motor
    value = points[0][1]
    for (v0, a0), (v1, a1) in zip(points, points[1:]):
        value += (a1 - a0) / (v1 - v0) * (ca.fmin(ca.fmax(speed, v0), v1) - v0)

    return value


def lap_time(gap: ca.SX, speed_squared: ca.SX) -> ca.SX:
    """Return the time of a lap driven at these speeds, steadily from each point to the next."""
    speed = ca.sqrt(speed_squared)

    return ca.sum1(2 * gap / (speed + _next(speed)))


def speed_rows(limits: CarLimits, curvature: ca.SX, gap: ca.SX, speed_squared: ca.SX) -> ca.SX:
    """
    Return the car's speed rules as rows that must not be negative.

    curvature:      the curvature at each point.
    gap:            the distance from each point to the next.
    speed_squared:  the unknowns.
    """
    accel = (_next(speed_squared) - speed_squared) / (2 * gap)
    angle = ca.atan(limits.wheelbase * curvature)
    turned = _next(angle) - angle

    # The steering turns by `turned` over a gap in time if speed x |turned| stays under this.
    steerable = limits.max_steering_velocity * gap

    # The bend, to the left and to the right.
    rows = [limits.a_lat_max - speed_squared * curvature,
            limits.a_lat_max + speed_squared * curvature]

    # Each gap is held at its near end and at its far end.
    for squared, bend in ((speed_squared, curvature), (_next(speed_squared), _next(curvature))):
        speed, drag = ca.sqrt(squared), limits.drag_coeff * squared / limits.m
        rows.append(_motor(limits, speed) - drag - accel)
        for side in (1, -1):
            grip = 1 - side * squared * bend / limits.a_lat_max
            speeding_up = limits.a_max * grip - drag - accel
            braking = accel - limits.a_min * grip + drag
            steering = steerable - side * speed * turned
            rows += [speeding_up, braking, steering]

    return ca.vertcat(*rows)
