"""Capture route and car inputs with their provenance."""
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from ..annotation.track_map import read_source
from ..car import Car, CarLimits
from ..route.manifest import decode_manifest, validate_route
from ..route.track import Route
from .storage import digest


@lru_cache(maxsize=12)
def _route(data: bytes) -> tuple[Route, str, str]:
    payload = decode_manifest(data)
    route = validate_route(payload)
    return route, payload['map']['sha256'], payload['name']


@dataclass(frozen=True)
class Track:
    """The checked route and its relation to the map source on disk."""

    status: str
    message: str
    route: Route | None = None
    source: str | None = None
    name: str | None = None

    @classmethod
    def read(cls, yaml_path: Path) -> 'Track':
        """Read the canonical export and match it to its map and optional receipt."""
        path = yaml_path.with_name(f'{yaml_path.stem}_route.json')
        try:
            source = read_source(yaml_path)
            route, png, name = _route(path.read_bytes())
        except FileNotFoundError:
            return cls('missing', 'Export a valid route in Annotator to begin.')
        except (OSError, ValueError, OverflowError) as exc:
            return cls('invalid', str(exc))

        if png != source.sha256:
            return cls('stale', 'Map image changed. Reopen the map and export a new route.')

        try:
            receipt = json.loads(path.with_suffix('.source.json').read_bytes())
        except FileNotFoundError:
            return cls('unverified', 'Map image matches. Calibration was never recorded for this '
                       'export. Review the route or re-export it in Annotator.',
                       route, source.digest, name)
        except (OSError, ValueError) as exc:
            return cls('invalid', f'Cannot read the route source receipt. {exc}')

        if receipt != {'route': route.digest, 'map': source.digest}:
            return cls('stale', 'Route or map calibration changed since export. Re-export in '
                       'Annotator.')
        return cls('ready', 'Route export matches the current map source.',
                   route, source.digest, name)


@dataclass(frozen=True)
class Vehicle:
    """Body and timing limits from the same captured car-model file."""

    car: Car | None
    limits: CarLimits | None
    revision: str | None
    message: str | None = None

    @classmethod
    def read(cls, path: Path | None, margin: float) -> 'Vehicle':
        """Read the configured car without blocking annotation."""
        if path is None:
            return cls(None, None, None, 'Set --car to enable optimization.')
        try:
            return _vehicle(path, path.read_bytes().decode('utf-8'), margin)
        except (OSError, ValueError, OverflowError, yaml.YAMLError) as exc:
            return cls(None, None, None, str(exc))


@lru_cache(maxsize=8)
def _vehicle(path: Path, source: str, margin: float) -> Vehicle:
    car = Car.load(path, margin_m=margin, source=source)
    revision = digest(source.encode('utf-8'))
    try:
        return Vehicle(car, CarLimits.load(path, source=source), revision)
    except (ValueError, OverflowError) as exc:
        return Vehicle(car, None, revision, str(exc))
