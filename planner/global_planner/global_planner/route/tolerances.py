"""Numerical tolerances and work budgets for curve geometry."""
from dataclasses import dataclass
import math

from .errors import GeometryError


@dataclass(frozen=True)
class NumericPolicy:
    """
    Software tolerances in metres and radians; never physical clearance margins.

    station_abs:    how exactly a distance along the curve must be resolved.
    join_abs:       allowed mismatch of position, tangent and curvature at joins.
    min_speed:      smallest allowed |dr/dt| on any cubic piece.
    max_samples:    most samples or pieces on one lap.
    """

    station_abs: float = 1e-8
    join_abs: float = 1e-8
    min_speed: float = 1e-7
    max_samples: int = 100000

    def __post_init__(self) -> None:
        for x in (self.station_abs, self.join_abs, self.min_speed):
            if not math.isfinite(x) or x <= 0:
                raise GeometryError('invalid numerical tolerance')

        if type(self.max_samples) is not int or self.max_samples <= 0:
            raise GeometryError('invalid numerical resource budget')
