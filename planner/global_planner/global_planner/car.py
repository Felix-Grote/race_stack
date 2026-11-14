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
"""
from dataclasses import dataclass
import math
from pathlib import Path

from shapely.geometry import Polygon
import yaml

from .route.geometry import XY


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
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f'{self.name}: {field} must be a number')

            if not math.isfinite(value) or value < 0:
                raise ValueError(f'{self.name}: {field} must be finite and not negative')

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
    def load(cls, car_model_yaml: str | Path, margin_m: float) -> 'Car':
        """Read a car's body and steering from its car_model.yaml; margin_m is the planner's."""
        path = Path(car_model_yaml)
        values = yaml.safe_load(path.read_text(encoding='utf-8')) or {}
        name = str(values.get('racecar_version', path.parent.name))

        keys = ('width_m', 'body_front_m', 'body_rear_m', 'wheelbase', 'max_steering_angle')
        missing = [k for k in keys if k not in values]
        if missing:
            raise ValueError(f'{name}: {path.name} has no {", ".join(missing)}; body extents '
                             f'are measured from base_link (rear axle centre on the ground)')

        wheelbase, steering = values['wheelbase'], values['max_steering_angle']
        numbers = all(isinstance(v, (int, float)) and not isinstance(v, bool)
                      for v in (wheelbase, steering))
        if not numbers or wheelbase <= 0 or not 0 < steering < math.pi / 2:
            raise ValueError(f'{name}: wheelbase must be positive and max_steering_angle '
                             f'between 0 and pi / 2')

        return cls(name, values['width_m'], values['body_front_m'], values['body_rear_m'],
                   wheelbase / math.tan(steering), margin_m)
