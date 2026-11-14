"""
The car the planner plans for: its body, from the stack's car_model.yaml, plus a margin.

reference:  base_link, the rear axle centre on the ground; the planned line is its path.
body:       a rectangle from body_rear_m behind to body_front_m ahead of base_link,
            width_m wide and centred on it.
margin:     extra clearance the planner keeps around the body, the same distance in every
            direction; a planning choice, so it comes from the planner's settings, not
            from the car file.
"""
from dataclasses import dataclass
import math
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Car:
    """
    Body and clearance of one car, in metres.

    name:           the car, e.g. NUC5.
    width_m:        body width.
    body_front_m:   body extent ahead of base_link.
    body_rear_m:    body extent behind base_link.
    margin_m:       clearance kept around the body.
    """

    name: str
    width_m: float
    body_front_m: float
    body_rear_m: float
    margin_m: float

    def __post_init__(self) -> None:
        for field in ('width_m', 'body_front_m', 'body_rear_m', 'margin_m'):
            value = getattr(self, field)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f'{self.name}: {field} must be a number')

            if not math.isfinite(value) or value < 0:
                raise ValueError(f'{self.name}: {field} must be finite and not negative')

        if self.width_m == 0 or self.body_front_m + self.body_rear_m == 0:
            raise ValueError(f'{self.name}: the body must have a width and a length')

    @property
    def reach_m(self) -> float:
        """Return how far the body plus margin can extend from base_link in any direction."""
        corner = math.hypot(max(self.body_front_m, self.body_rear_m), self.width_m / 2)

        return corner + self.margin_m

    @classmethod
    def load(cls, car_model_yaml: str | Path, margin_m: float) -> 'Car':
        """Read a car's body from its car_model.yaml; margin_m comes from the planner settings."""
        path = Path(car_model_yaml)
        values = yaml.safe_load(path.read_text(encoding='utf-8')) or {}
        name = str(values.get('racecar_version', path.parent.name))

        missing = [k for k in ('width_m', 'body_front_m', 'body_rear_m') if k not in values]
        if missing:
            raise ValueError(f'{name}: {path.name} has no {", ".join(missing)}; measure them '
                             f'from base_link (rear axle centre on the ground)')

        return cls(name, values['width_m'], values['body_front_m'], values['body_rear_m'],
                   margin_m)
