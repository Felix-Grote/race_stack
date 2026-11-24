"""Editable optimizer values, one worksheet applied to every map."""
from dataclasses import dataclass, replace
import json
from pathlib import Path

from .storage import digest, write_json
from ..car import is_number
from ..optimizer.solve import OptimizerSettings

# The other optimizer settings control convergence precision or geometric checks.
# They use the planner defaults in every run.
DEFAULTS = OptimizerSettings()
# label, unit, smallest and largest value accepted, hint
PARAMETERS = {
    'spacing_m': ('Point spacing', 'm', 0.05, 1.0,
                  'Maximum initial distance between optimizer points.'),
    'step_m': ('Step limit', 'm', 0.002, 0.5,
               'Maximum movement per coordinate in one pass. At most point spacing.'),
    'smoothness': ('Smoothness γ', '', 0.0, 10.0,
                   'Curvature penalty for Balanced and Aggressive. Gentle uses 2× and '
                   'Shortest 0.3× this.'),
    'max_passes': ('Pass limit', '', 1, 500,
                   'Maximum passes per refinement.'),
    'max_refinements': ('Refinement limit', '', 0, 20,
                        'Maximum attempts to tighten the constraints after checking the curve.'),
    'max_iterations': ('Iteration limit', '', 1, 2000,
                       'Maximum IPOPT iterations in one pass.'),
}


def defaults() -> dict:
    """Return the default worksheet."""
    return {key: getattr(DEFAULTS, key) for key in PARAMETERS}


def parameter_info() -> dict:
    """Describe each value and the range the page accepts."""
    return {key: {'label': label, 'unit': unit, 'min': low, 'max': high, 'hint': hint,
                  'integer': isinstance(low, int), 'default': getattr(DEFAULTS, key)}
            for key, (label, unit, low, high, hint) in PARAMETERS.items()}


def validate(values: object) -> OptimizerSettings:
    """Check the worksheet and hand its values to the native settings validator."""
    if not isinstance(values, dict) or values.keys() != PARAMETERS.keys():
        raise ValueError('Supply a value for each optimizer parameter.')
    for key, (label, _, low, high, _) in PARAMETERS.items():
        value = values[key]
        if not is_number(value):
            raise ValueError(f'{label} needs a finite number.')
        if isinstance(low, int) and not isinstance(value, int):
            raise ValueError(f'{label} needs a whole number.')
        if not low <= value <= high:
            raise ValueError(f'{label} must lie within {low:g}–{high:g}.')
    return replace(DEFAULTS, **values)


@dataclass(frozen=True)
class Worksheet:
    """A persisted worksheet and the revision against which an edit is made."""

    parameters: dict
    revision: str
    error: str | None = None

    @classmethod
    def read(cls, path: Path) -> 'Worksheet':
        """Read the saved worksheet, or offer defaults with a visible error."""
        try:
            data = path.read_bytes()
        except FileNotFoundError:
            return cls(defaults(), 'defaults')
        except OSError as exc:
            return cls(defaults(), 'unreadable', str(exc))

        revision = digest(data)
        try:
            record = json.loads(data)
            validate(record)
            return cls(record, revision)
        except (ValueError, OverflowError) as exc:
            return cls(defaults(), revision, f'Saved worksheet is invalid. {exc}')

    @classmethod
    def save(cls, path: Path, parameters: object, revision: str) -> None:
        """Refuse to overwrite a worksheet that changed while it was being edited."""
        if cls.read(path).revision != revision:
            raise ValueError('Settings changed on disk. Reload the saved values and try again.')
        validate(parameters)
        write_json(path, parameters)
