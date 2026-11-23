"""Optimize the driving profiles independently using captured planning inputs."""
from dataclasses import asdict, replace
from functools import cache
from pathlib import Path
import traceback

from .inputs import Track, Vehicle
from .storage import digest, write_json
from .telemetry import measure
from ..car import Car, CarLimits
from ..optimizer.solve import optimize, OptimizerSettings
from ..speed.speeds import SpeedSettings

# Provisional performance fractions, added clearance in metres, and multipliers on Balanced γ.
PROFILES = {
    'gentle': (0.80, 0.050, 2.0),
    'balanced': (0.90, 0.025, 1.0),
    'aggressive': (0.95, 0.000, 0.5),
}
RESULT_VERSION = 3


@cache
def _planner_revision() -> str:
    """Fingerprint the planner sources shipped with the installed package."""
    root = Path(__file__).resolve().parents[1]
    sources = [root / 'car.py']
    for package in ('optimizer', 'route', 'speed'):
        sources.extend(sorted((root / package).glob('*.py')))
    sources.append(root / 'route' / 'manifest.schema.json')
    return digest(''.join(digest(path.read_bytes()) for path in sources).encode())


def profile_info(kind: str, margin: float, settings: OptimizerSettings | None) -> dict:
    """Return the effective policy shown to the operator and saved with the result."""
    alpha, extra, multiplier = PROFILES[kind]
    return {'alpha': alpha, 'margin_m': margin + extra,
            'gamma': None if settings is None else settings.smoothness * multiplier}


def _effective(kind: str, vehicle: Vehicle, settings: OptimizerSettings
               ) -> tuple[Car, CarLimits, OptimizerSettings]:
    policy = profile_info(kind, vehicle.car.margin_m, settings)
    limits = vehicle.limits
    alpha = policy['alpha']
    reduced = replace(
        limits,
        v_max=limits.v_max * alpha,
        a_max=limits.a_max * alpha,
        a_min=limits.a_min * alpha,
        a_lat_max=limits.a_lat_max * alpha,
        a_motor=tuple((speed, acceleration * alpha) for speed, acceleration in limits.a_motor),
        max_steering_velocity=limits.max_steering_velocity * alpha,
    )
    return (replace(vehicle.car, margin_m=policy['margin_m']), reduced,
            replace(settings, smoothness=policy['gamma']))


def provenance(kind: str, track: Track, vehicle: Vehicle,
               settings: OptimizerSettings | None) -> dict:
    """Identify the captured sources and all effective settings of one profile."""
    inputs = {'route': track.route.digest if track.route else None,
              'map': track.source, 'car': vehicle.revision,
              'profile': None, 'body': None, 'base_limits': None, 'limits': None,
              'optimizer': None, 'speed_model': asdict(SpeedSettings()),
              'planner': _planner_revision()}
    if vehicle.car is not None and vehicle.limits is not None and settings is not None:
        car, limits, optimizer = _effective(kind, vehicle, settings)
        inputs.update(profile=profile_info(kind, vehicle.car.margin_m, settings),
                      body=asdict(car), base_limits=asdict(vehicle.limits),
                      limits=asdict(limits), optimizer=asdict(optimizer))
        for key in ('base_limits', 'limits'):
            inputs[key]['a_motor'] = [list(point) for point in inputs[key]['a_motor']]
    return inputs


def generate(kind: str, track: Track, vehicle: Vehicle, settings: OptimizerSettings) -> dict:
    """Run a full geometry and speed solve and sample its validated result."""
    car, limits, optimizer = _effective(kind, vehicle, settings)
    result = optimize(track.route, car, optimizer, limits=limits)
    telemetry = measure(result.lap, car, result.profile, vehicle.limits)
    return {
        'metrics': {'length_m': result.lap.curve.length,
                    'lap_time_s': result.profile.lap_time_s,
                    'min_clearance_m': min(telemetry['values']['clearance'])},
        'telemetry': telemetry,
    }


def run_job(directory: Path, progress: Path, job: dict, track: Track, vehicle: Vehicle,
            settings: OptimizerSettings) -> None:
    """Publish each completed profile independently in the worker process."""
    for kind, attempt in job['attempts'].items():
        attempt['status'] = 'running'
        write_json(progress, job)
        try:
            result = generate(kind, track, vehicle, settings)
            write_json(directory / f'{kind}.json',
                       dict(result, version=RESULT_VERSION, id=job['id'],
                            inputs=provenance(kind, track, vehicle, settings)))
        except (ValueError, OSError) as exc:
            attempt.update(status='failed', message=str(exc))
        except Exception as exc:  # noqa: BLE001 - report unexpected worker failures to the UI
            traceback.print_exc()
            attempt.update(status='failed', message=f'{type(exc).__name__}: {exc}')
        else:
            attempt['status'] = 'complete'
        write_json(progress, job)
