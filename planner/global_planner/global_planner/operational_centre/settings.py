"""Editable optimizer values and their operator-defined working bounds."""
import json
from dataclasses import dataclass, replace
from pathlib import Path

from ..car import is_number
from ..optimizer.solve import OptimizerSettings
from .storage import digest, write_json

# The other optimizer settings control convergence precision or geometric checks.
# They use the planner defaults in every run.
DEFAULTS = OptimizerSettings()
PARAMETERS = {
    'spacing_m': ('Point spacing', 'm', 0.05, 1.0,
                  'Maximum initial distance between optimizer points.'),
    'step_m': ('Step limit', 'm', 0.002, 0.5,
               'Maximum movement per coordinate in one pass. At most point spacing.'),
    'smoothness': ('Smoothness weight', '', 0.0, 10.0,
                   'Curvature penalty in Lap time mode. Larger values favor a gentler line.'),
    'max_passes': ('Pass limit', '', 1, 500,
                   'Maximum passes per refinement.'),
    'max_refinements': ('Refinement limit', '', 0, 20,
                        'Maximum attempts to tighten the constraints after checking the curve.'),
    'max_iterations': ('Iteration limit', '', 1, 2000,
                       'Maximum IPOPT iterations in one pass.'),
}


def defaults() -> dict:
    """Provide a fresh default worksheet."""
    return {key: {'value': getattr(DEFAULTS, key), 'lower': lower, 'upper': upper}
            for key, (_, _, lower, upper, _) in PARAMETERS.items()}


def parameter_info() -> dict:
    """Describe the worksheet, including absolute input limits."""
    return {key: {'label': label, 'unit': unit, 'lower': lower, 'upper': upper, 'hint': hint,
                  'integer': isinstance(lower, int), 'default': getattr(DEFAULTS, key)}
            for key, (label, unit, lower, upper, hint) in PARAMETERS.items()}


def validate(parameters: object) -> OptimizerSettings:
    """Validate the worksheet and hand its values to the native settings validator."""
    if not isinstance(parameters, dict) or parameters.keys() != PARAMETERS.keys():
        raise ValueError('Supply a value and working bounds for each optimizer parameter.')
    for key, (label, _, floor, ceiling, _) in PARAMETERS.items():
        row = parameters[key]
        if not isinstance(row, dict) or row.keys() != {'value', 'lower', 'upper'}:
            raise ValueError(f'{label} needs a value, lower bound and upper bound.')
        values = row['lower'], row['value'], row['upper']
        if not all(is_number(value) for value in values):
            raise ValueError(f'{label} needs finite numbers.')
        if isinstance(floor, int) and not all(isinstance(value, int) for value in values):
            raise ValueError(f'{label} needs whole numbers.')
        lower, value, upper = values
        if not floor <= lower <= value <= upper <= ceiling:
            raise ValueError(f'{label}: keep lower ≤ value ≤ upper within {floor:g}–{ceiling:g}.')
    return replace(DEFAULTS, **{key: row['value'] for key, row in parameters.items()})


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
