"""
Exceptions raised while reading a track and building its geometry.

RouteError:     the manifest is malformed or inconsistent or, for a car's reach, the road
                near a gate is not one piece.
GeometryError:  a curve is unsupported, numerically uncertain or over budget.
LapError:       a lap curve, sample or gate crossing is invalid or ambiguous.
"""


class RouteError(ValueError):
    """The manifest is malformed or inconsistent."""


class GeometryError(ValueError):
    """A curve is unsupported, numerically uncertain or over its budget."""


class LapError(ValueError):
    """A lap curve, sample or gate crossing is invalid or ambiguous."""


def require(condition: object, message: str) -> None:
    """Raise RouteError(message) unless condition holds."""
    if not condition:
        raise RouteError(message)
