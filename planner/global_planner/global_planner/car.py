"""
The car the planner plans for: its body, from the stack's car_model.yaml, plus a margin.

reference:  base_link, the rear axle centre on the ground; the planned line is its path.
body:       a rectangle from body_rear_m behind to body_front_m ahead of base_link,
            width_m wide and centred on it.
turning:    the smallest radius base_link can drive: wheelbase / tan(max_steering_angle),
            the rear axle of a bicycle model at full steering. The car file's own
            min_radius_curv_m is not read: its comment gives this formula, and its value
            does not always follow it.
margin:     extra clearance the planner keeps around the body, the same distance in every
            direction; a planning choice, so it comes from the planner's settings, not
            from the car file.
limits:     how fast the car can go, speed up, brake, corner and steer (CarLimits), for the
            speed profile. Every value comes from the car file.
"""
from collections.abc import Sequence
from dataclasses import dataclass, fields
import math
from pathlib import Path

from shapely.geometry import Polygon
import yaml

from .route.geometry import XY


def is_number(value: object) -> bool:
    """Check that value is a finite number, and not a bool."""
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def _read(car_model_yaml: str | Path, keys: Sequence[str], needed: str,
          source: str | None) -> tuple[str, dict]:
    """
    Return the car's name and the values of its car_model.yaml.

    keys:   the keys the file must hold.
    needed: what they are needed for, to say so if one is missing.
    """
    path = Path(car_model_yaml)
    values = yaml.safe_load(path.read_text(encoding='utf-8') if source is None else source) or {}
    if not isinstance(values, dict):
        raise ValueError(f'{path} is not a car file: it holds no keys')

    name = str(values.get('racecar_version', path.parent.name))
    missing = [key for key in keys if values.get(key) is None]
    if missing:
        raise ValueError(f'{name}: {path.name} lacks {", ".join(missing)}, needed for {needed}')

    return name, values


@dataclass(frozen=True)
class Car:
    """
    Body and clearance of one car, in metres.

    name:           the car, e.g. NUC5.
    width_m:        body width.
    body_front_m:   body extent ahead of base_link.
    body_rear_m:    body extent behind base_link.
    min_radius_m:   smallest turning radius of base_link.
    margin_m:       clearance kept around the body.
    """

    name: str
    width_m: float
    body_front_m: float
    body_rear_m: float
    min_radius_m: float
    margin_m: float

    def __post_init__(self) -> None:
        for field in ('width_m', 'body_front_m', 'body_rear_m', 'min_radius_m', 'margin_m'):
            value = getattr(self, field)
            if not is_number(value) or value < 0:
                raise ValueError(f'{self.name}: {field} must be a finite number, not negative')

        if self.width_m == 0 or self.body_front_m + self.body_rear_m == 0:
            raise ValueError(f'{self.name}: the body must have a width and a length')

        if self.min_radius_m == 0:
            raise ValueError(f'{self.name}: the turning radius must be positive')

    @property
    def corner_m(self) -> float:
        """Return how far the furthest corner of the body is from base_link."""
        return math.hypot(max(self.body_front_m, self.body_rear_m), self.width_m / 2)

    @property
    def reach_m(self) -> float:
        """Return how far the body plus margin can extend from base_link in any direction."""
        return self.corner_m + self.margin_m

    @property
    def corners(self) -> tuple[XY, ...]:
        """Return the body's corners as (ahead, left) of base_link, anticlockwise."""
        half = self.width_m / 2

        return ((self.body_front_m, half), (-self.body_rear_m, half),
                (-self.body_rear_m, -half), (self.body_front_m, -half))

    @property
    def edges(self) -> tuple[tuple[XY, float], ...]:
        """Return the body's edges: outward normal as (ahead, left), distance from base_link."""
        half = self.width_m / 2

        return (((1., 0.), self.body_front_m), ((0., 1.), half),
                ((-1., 0.), self.body_rear_m), ((0., -1.), half))

    def body(self, xy: XY, heading: XY) -> Polygon:
        """Return the body rectangle with base_link at xy facing the unit vector heading."""
        (x, y), (cos, sin) = xy, heading

        return Polygon([(x + a * cos - b * sin, y + a * sin + b * cos) for a, b in self.corners])

    @classmethod
    def load(cls, car_model_yaml: str | Path, margin_m: float, *,
             source: str | None = None) -> 'Car':
        """Read a car's body and steering, optionally from captured YAML text."""
        keys = ('width_m', 'body_front_m', 'body_rear_m', 'wheelbase', 'max_steering_angle')
        name, values = _read(car_model_yaml, keys, 'the body, whose extents are measured '
                             'from base_link (rear axle centre on the ground), and the steering',
                             source)
        wheelbase, steering = values['wheelbase'], values['max_steering_angle']
        numbers = is_number(wheelbase) and is_number(steering)
        if not numbers or wheelbase <= 0 or not 0 < steering < math.pi / 2:
            raise ValueError(f'{name}: wheelbase must be positive and max_steering_angle '
                             f'between 0 and pi / 2')

        return cls(name, values['width_m'], values['body_front_m'], values['body_rear_m'],
                   wheelbase / math.tan(steering), margin_m)


@dataclass(frozen=True)
class CarLimits:
    """
    How fast one car can go, speed up, brake, corner and steer.

    Every field but the name is a key of the car's car_model.yaml, under the same name.

    name:                   the car, e.g. NUC5.
    m:                      its mass, in kg.
    wheelbase:              the distance between its axles, in m.
    v_max:                  its top speed, in m/s.
    a_max:                  the most its tyres speed it up, driving straight, in m/s2.
    a_min:                  the most they slow it down, driving straight, in m/s2: negative.
    a_lat_max:              the most they hold it in a bend, at a steady speed, in m/s2.
    a_motor:                the most its motor speeds it up at a speed: (m/s, m/s2) points,
                            straight between them and level beyond the first and the last;
                            never rising with the speed, and more than nothing at the first.
    drag_coeff:             air drag force divided by the speed squared, in kg/m.
    max_steering_angle:     the furthest its front wheels turn, in rad.
    max_steering_velocity:  the fastest its steering angle changes, in rad/s.
    """

    name: str
    m: float
    wheelbase: float
    v_max: float
    a_max: float
    a_min: float
    a_lat_max: float
    a_motor: tuple[tuple[float, float], ...]
    drag_coeff: float
    max_steering_angle: float
    max_steering_velocity: float

    def __post_init__(self) -> None:
        listed = (list, tuple)
        if not isinstance(self.a_motor, listed) or not self.a_motor or not all(
                isinstance(point, listed) and len(point) == 2 for point in self.a_motor):
            raise ValueError(f'{self.name}: a_motor must be a list of [speed, acceleration] '
                             f'points')

        object.__setattr__(self, 'a_motor', tuple(tuple(point) for point in self.a_motor))
        positive = ('m', 'wheelbase', 'v_max', 'a_max', 'a_lat_max', 'max_steering_angle',
                    'max_steering_velocity')
        numbers = [(key, getattr(self, key)) for key in (*positive, 'a_min', 'drag_coeff')]
        numbers += [('every value in a_motor', v) for point in self.a_motor for v in point]
        for key, value in numbers:
            if not is_number(value):
                hint = '; the car file reads 1e-2 as text, so write 0.01'
                raise ValueError(f'{self.name}: {key} must be a finite number'
                                 + (hint if isinstance(value, str) else ''))

            if key in positive and value <= 0:
                raise ValueError(f'{self.name}: {key} must be more than zero')

        if self.a_min >= 0:
            raise ValueError(f'{self.name}: a_min, the hardest braking, must be negative')

        if self.max_steering_angle >= math.pi / 2:
            raise ValueError(f'{self.name}: max_steering_angle must be below pi / 2')

        if self.drag_coeff < 0:
            raise ValueError(f'{self.name}: drag_coeff must not be negative')

        """
        A motor that pulled harder at a higher speed would make the fastest speed ambiguous,
        and one that gives nothing at standstill never gets the car round the lap.
        """
        speeds, pulls = [p[0] for p in self.a_motor], [p[1] for p in self.a_motor]
        ordered = all(a < b for a, b in zip(speeds, speeds[1:]))
        falling = all(a >= b for a, b in zip(pulls, pulls[1:]))
        if not ordered or not falling or speeds[0] < 0 or pulls[0] <= 0 or pulls[-1] < 0:
            raise ValueError(f'{self.name}: a_motor needs points of rising speed, from zero '
                             f'or above, whose acceleration starts above zero, never rises '
                             f'and never goes negative')

    @classmethod
    def load(cls, car_model_yaml: str | Path, *, source: str | None = None) -> 'CarLimits':
        """Read a car's limits, optionally from captured YAML text."""
        keys = [field.name for field in fields(cls) if field.name != 'name']
        name, values = _read(car_model_yaml, keys, 'the speed profile', source)

        return cls(name, **{key: values[key] for key in keys})
