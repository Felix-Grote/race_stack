"""Sample the native flying lap for inspection in Tracks."""
import numpy as np
from shapely.geometry import MultiLineString

from ..car import Car, CarLimits
from ..optimizer.free_space import FreeSpace
from ..route.lap import LapCurve
from ..route.zones import portal_zones
from ..speed.model import CarModel
from ..speed.speeds import SpeedProfile, SpeedSettings


def _clearances(lap: LapCurve, car: Car, profile: SpeedProfile) -> list[float]:
    """Measure from the uninflated rectangle to the local corridor's physical side walls."""
    sections = lap.route.sections
    space = FreeSpace(lap.route, portal_zones(lap.route, car.reach_m))
    # Internal gates and the curved limits of portal supports are not physical walls.
    walls = {
        section.uid: MultiLineString([
            wall for offset in (-1, 0, 1)
            for wall in (sections[(i + offset) % len(sections)].left,
                         sections[(i + offset) % len(sections)].right)
        ])
        for i, section in enumerate(sections)
    }
    distances = []
    for sample in profile.samples:
        body = car.body(sample.xy, sample.tangent)
        road = space.road_at(sample.xy, sample.section_uid)
        distances.append(walls[sample.section_uid].distance(body) if road.covers(body) else 0.)
    return distances


def _ends(values: np.ndarray) -> np.ndarray:
    """Put each sampled gap's start and end values in separate rows."""
    return np.stack((values, np.roll(values, -1)))


def _constraint(demand: np.ndarray, planning, baseline, active: np.ndarray) -> dict:
    """Describe the tightest endpoint, preferring an endpoint with an active bound."""
    slack = np.where(active.any(axis=0) & ~active, np.inf, planning - demand)
    end = slack.argmin(axis=0)
    index = end, np.arange(end.size)

    return {
        'actual': demand[index].tolist(),
        'profile': np.broadcast_to(planning, demand.shape)[index].tolist(),
        'base': None if baseline is None else np.broadcast_to(baseline, demand.shape)[index].tolist(),
        'end': end.tolist(),
        'active': (active[0].astype(int) + 2 * active[1]).tolist(),
    }


def _grip(lateral: np.ndarray, tyre: np.ndarray, model: CarModel) -> np.ndarray:
    """Gauge combined tyre demand with the same exponent as the speed solver."""
    limits, exponent = model.limits, model.grip_exponent
    longitudinal_limit = np.where(tyre < 0, -limits.a_min, limits.a_max)
    return ((lateral / limits.a_lat_max) ** exponent
            + (abs(tyre) / longitudinal_limit) ** exponent) ** (1 / exponent)


def measure(lap: LapCurve, car: Car, profile: SpeedProfile, base_limits: CarLimits) -> dict:
    """Report local speed bounds separately from usage of the calibrated vehicle."""
    points = profile.points
    model, speed = points.car, points.speed_mps
    limits = model.limits
    base = CarModel(base_limits, model.grip_exponent)
    longitudinal = points.accel_mps2
    lateral = speed ** 2 * points.curvature
    angle_step = np.roll(points.angle, -1) - points.angle
    steering_rate = angle_step / points.took_s

    end_speed, end_curvature = _ends(speed), _ends(points.curvature)
    end_lateral = _ends(abs(lateral))
    road = _ends(points.track_cap_mps)
    # The profile scales limits while keeping drag, mass and steering geometry fixed.
    tyre = longitudinal + limits.drag_coeff * end_speed ** 2 / limits.m
    grip_left = model.grip_left(end_speed, end_curvature)
    base_grip_left = base.grip_left(end_speed, end_curvature)
    drive, brake = limits.a_max * grip_left, -limits.a_min * grip_left
    motor, base_motor = model.motor_accel(end_speed), base.motor_accel(end_speed)
    steering_per_speed = abs(angle_step) / points.gap_m
    steering_cap_demand = end_speed * steering_per_speed

    speed_slack = SpeedSettings().resolved_mps
    # Adjacent samples can be very close. Keep their speed-to-acceleration slack bounded.
    accel_slack = np.minimum(speed_slack * (1 + end_speed.max(axis=0) / points.gap_m), 0.005)
    constraints = {
        'road': _constraint(end_speed, road, None, end_speed >= road - speed_slack),
        'vehicle_speed': _constraint(end_speed, limits.v_max, base_limits.v_max,
                                     end_speed >= limits.v_max - speed_slack),
        'cornering': _constraint(end_lateral, limits.a_lat_max, base_limits.a_lat_max,
                                 end_speed >= model.bend_speed(end_curvature) - speed_slack),
        'drive': _constraint(np.maximum(tyre, 0), drive, base_limits.a_max * base_grip_left,
                             (tyre > accel_slack) & (tyre >= drive - accel_slack)),
        'motor': _constraint(np.maximum(tyre, 0), motor, base_motor, tyre >= motor - accel_slack),
        'braking': _constraint(np.maximum(-tyre, 0), brake, -base_limits.a_min * base_grip_left,
                               (-tyre > accel_slack) & (-tyre >= brake - accel_slack)),
        'steering_cap': _constraint(steering_cap_demand, limits.max_steering_velocity,
                                    base_limits.max_steering_velocity,
                                    steering_cap_demand >= limits.max_steering_velocity
                                    - speed_slack * steering_per_speed),
    }

    grip = _grip(end_lateral, tyre, model).max(axis=0)
    base_grip = _grip(end_lateral, tyre, base).max(axis=0)
    vehicle_speed = end_speed.max(axis=0) / base_limits.v_max
    steering_angle = _ends(abs(points.angle)).max(axis=0) / base_limits.max_steering_angle
    steering = abs(steering_rate) / base_limits.max_steering_velocity
    with np.errstate(over='ignore'):
        motor_ratio = np.divide(np.maximum(tyre, 0), base_motor,
                               out=np.full_like(base_motor, np.nan), where=base_motor > 0)
    motor_ratio[~np.isfinite(motor_ratio)] = np.nan
    base_motor_usage = np.fmax(motor_ratio[0], motor_ratio[1])
    vehicle_usage = np.maximum.reduce(
        [vehicle_speed, base_grip, steering_angle, steering, np.nan_to_num(base_motor_usage)])

    return {
        'q': [sample.q for sample in profile.samples],
        'points': [sample.xy for sample in profile.samples],
        'values': {
            'speed': speed.tolist(),
            'longitudinal': longitudinal.tolist(),
            'lateral': lateral.tolist(),
            'curvature': points.curvature.tolist(),
            'angle': points.angle.tolist(),
            'steering_rate': steering_rate.tolist(),
            'clearance': _clearances(lap, car, profile),
            'vehicle_usage': vehicle_usage.tolist(),
            'road_usage': (end_speed / road).max(axis=0).tolist(),
            'speed_usage': vehicle_speed.tolist(),
            'grip_usage': base_grip.tolist(),
            'motor_usage': [float(value) if np.isfinite(value) else None for value in base_motor_usage],
            'angle_usage': steering_angle.tolist(),
            'steering_usage': steering.tolist(),
        },
        'constraints': constraints,
        'profile_grip': grip.tolist(),
        'steering_limits': [limits.max_steering_angle, base_limits.max_steering_angle,
                            limits.max_steering_velocity, base_limits.max_steering_velocity],
    }
