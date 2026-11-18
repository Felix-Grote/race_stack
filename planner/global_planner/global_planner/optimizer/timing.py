"""
Lap time and the car's speed rules, written for the solver.

When the optimizer is asked for the fastest line it moves the points and the car's speed at
every point together. This file writes down, as expressions the solver can work with, the
time a gap between two points takes and the rules the speeds keep over it. The rules are
those of speed/points.py, so that a line the solver finds fast is fast by the speed profile
too.

one gap:    everything here is for one gap: its length, the curvature at its two ends and
            the squared speeds at its two ends. problem.py makes small functions of it and
            applies them to every gap of the lap, so the solver works out the derivatives
            of one gap and not of the whole lap at once.
unknowns:   the square of the speed at every point. The steady acceleration over a gap is
            then (far - near) / (2 length), a straight line in the speeds.
rows:       every rule is a number that must not be negative. Cornering takes its share of
            the grip part for part (grip_exponent 1 in speed/), so each rule with the bend
            in it is written twice, once for a bend to the left and once to the right.
bend:       speed^2 |k| stays within a_lat_max, at the gap's near end; its far end is the
            near end of the next gap.
speeding:   over a gap the car speeds up no harder than its tyres have left, or its motor
            gives, less the air drag, at both ends of the gap.
braking:    and brakes no harder than its tyres have left plus the air drag, at both ends.
steering:   both ends of a gap are held to the speed that takes it in the time the steering
            needs to turn from one angle to the other.
against:    every row comes with the limit it is measured against, so that how near a row
            is to binding can be told as a share of that limit.
caps:       the track's limit and the car's top speed are plain bounds on the unknowns,
            set for each pass by problem.py.
same rules: speed/model.py and speed/points.py state these rules for numbers. A change to
            a rule there belongs here too, and the other way round.
"""
import casadi as ca

from ..car import CarLimits


def _motor(limits: CarLimits, speed: ca.SX) -> ca.SX:
    """Return what the motor gives at a speed: straight between its points, level beyond."""
    points = limits.a_motor
    value = points[0][1]
    for (v0, a0), (v1, a1) in zip(points, points[1:]):
        value += (a1 - a0) / (v1 - v0) * (ca.fmin(ca.fmax(speed, v0), v1) - v0)

    return value


def gap_time(length: ca.SX, squared: ca.SX) -> ca.SX:
    """
    Return the time a gap takes, driven steadily from the speed at one end to the other.

    length:     the length of the gap.
    squared:    the squared speeds at its near end and at its far end.
    """
    return 2 * length / (ca.sqrt(squared[0]) + ca.sqrt(squared[1]))


def gap_rows(limits: CarLimits, length: ca.SX, bends: tuple[ca.SX, ca.SX],
             squared: ca.SX) -> tuple[ca.SX, ca.SX]:
    """
    Return the car's speed rules over one gap as rows, and what each is measured against.

    length:     the length of the gap.
    bends:      the curvature at its near end and at its far end.
    squared:    the squared speeds at its near end and at its far end, the unknowns.
    """
    accel = (squared[1] - squared[0]) / (2 * length)
    angle = [ca.atan(limits.wheelbase * bend) for bend in bends]
    turned = angle[1] - angle[0]

    # The steering turns by `turned` over the gap in time if speed x |turned| stays under this.
    steerable = limits.max_steering_velocity * length

    # The bend at the near end, to the left and to the right.
    held = [(limits.a_lat_max - side * squared[0] * bends[0], limits.a_lat_max)
            for side in (1, -1)]

    # The gap is held at its near end and at its far end.
    for end in (0, 1):
        speed, drag = ca.sqrt(squared[end]), limits.drag_coeff * squared[end] / limits.m
        held.append((_motor(limits, speed) - drag - accel, limits.a_motor[0][1]))
        for side in (1, -1):
            grip = 1 - side * squared[end] * bends[end] / limits.a_lat_max
            speeding_up = limits.a_max * grip - drag - accel
            braking = accel - limits.a_min * grip + drag
            steering = steerable - side * speed * turned
            held += [(speeding_up, limits.a_max), (braking, abs(limits.a_min)),
                     (steering, steerable)]

    rows, against = zip(*held)

    return ca.vertcat(*rows), ca.vertcat(*against)
