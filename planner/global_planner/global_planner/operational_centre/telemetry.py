"""Sample the native flying lap for inspection in Tracks."""
import numpy as np
from shapely.geometry import MultiLineString

from ..car import Car
from ..optimizer.free_space import FreeSpace
from ..route.lap import LapCurve
from ..route.zones import portal_zones
from ..speed.speeds import SpeedProfile


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


def measure(lap: LapCurve, car: Car, profile: SpeedProfile) -> dict:
    """Describe speed constraints and footprint clearance at the profile's route samples."""
    points = profile.points
    model, speed = points.car, points.speed_mps
    limits = model.limits
    longitudinal = points.accel_mps2
    lateral = speed ** 2 * points.curvature
    angle_step = np.roll(points.angle, -1) - points.angle
    steering_rate = angle_step / points.took_s

    # The native profile checks one steady longitudinal acceleration at both ends of a gap.
    end_speed = np.stack((speed, np.roll(speed, -1)))
    end_lateral = np.stack((lateral, np.roll(lateral, -1)))
    tyre_demand = longitudinal + limits.drag_coeff * end_speed ** 2 / limits.m
    tyre_limit = np.where(tyre_demand < 0, -limits.a_min, limits.a_max)
    exponent = model.grip_exponent
    grip = ((np.abs(end_lateral) / limits.a_lat_max) ** exponent
            + (np.abs(tyre_demand) / tyre_limit) ** exponent) ** (1. / exponent)
    sample_index = np.arange(speed.size)
    grip_end = (grip[1] > grip[0]).astype(int)
    grip_index = grip_end, sample_index

    motor_demand = np.maximum(tyre_demand, 0.)
    motor_limit = model.motor_accel(end_speed)
    motor_ratio = np.divide(motor_demand, motor_limit, out=np.zeros_like(motor_limit),
                           where=motor_limit > 0)
    motor_end = (motor_ratio[1] > motor_ratio[0]).astype(int)
    motor_index = motor_end, sample_index

    # The planner caps both endpoint speeds by the steering demand of the gap.
    steering_cap_demand = abs(angle_step) * end_speed.max(axis=0) / points.gap_m
    constraints = {
        'Road speed': [speed.tolist(), points.track_cap_mps.tolist()],
        'Vehicle speed': [speed.tolist(), limits.v_max],
        'Combined tyre grip': [grip[grip_index].tolist(), 1.],
        'Motor acceleration': [motor_demand[motor_index].tolist(), motor_limit[motor_index].tolist()],
        'Steering angle': [abs(points.angle).tolist(), limits.max_steering_angle],
        'Steering rate cap': [steering_cap_demand.tolist(), limits.max_steering_velocity],
    }
    utilization = np.maximum.reduce([
        speed / points.track_cap_mps, speed / limits.v_max, grip.max(axis=0),
        motor_ratio.max(axis=0), abs(points.angle) / limits.max_steering_angle,
        steering_cap_demand / limits.max_steering_velocity,
    ])
    clearance = _clearances(lap, car, profile)
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
            'clearance': clearance,
            'utilization': utilization.tolist(),
        },
        'constraints': constraints,
        'grip': {
            'end': grip_end.tolist(),
            'lateral': abs(end_lateral[grip_index]).tolist(),
            'lateral_limit': limits.a_lat_max,
            'longitudinal': tyre_demand[grip_index].tolist(),
            'longitudinal_limit': tyre_limit[grip_index].tolist(),
        },
    }
