"""Run the native planner on captured inputs and serialize the comparison samples."""
import traceback
from dataclasses import asdict
from pathlib import Path

from ..optimizer.solve import OptimizerSettings, optimize
from ..route.lap import centre_curve
from ..route.portals import portal_crossings
from ..route.sampling import sample_lap
from ..route.zones import portal_zones
from ..speed.speeds import speed_profile
from .inputs import Track, Vehicle
from .storage import write_json

CATEGORIES = ('centreline', 'curvature', 'laptime')
RESULT_VERSION = 1


def provenance(kind: str, track: Track, vehicle: Vehicle,
               settings: OptimizerSettings | None) -> dict:
    """Identify just the inputs used by this trajectory category."""
    inputs = {'route': track.route.digest if track.route else None, 'map': track.source}
    if kind != 'centreline':
        values = asdict(settings) if settings is not None else None
        if values is not None and kind == 'curvature':
            values.pop('smoothness')
        inputs.update(car=vehicle.revision, optimizer=values)
    return inputs


def generate(kind: str, track: Track, vehicle: Vehicle, settings: OptimizerSettings | None) -> dict:
    """Generate one line, leaving certification and refusals to the native planner."""
    profile, timing_error, passes = None, None, None
    if kind == 'centreline':
        lap = centre_curve(track.route)
        portal_crossings(lap)
    else:
        by_time = kind == 'laptime'
        result = optimize(track.route, vehicle.car, settings,
                          limits=vehicle.limits if by_time else None)
        lap, profile, passes = result.lap, result.profile, len(result.passes)
        if not by_time:
            if vehicle.limits is None:
                timing_error = vehicle.message
            else:
                try:
                    zones = portal_zones(track.route, vehicle.car.reach_m)
                    profile = speed_profile(lap, zones, vehicle.limits)
                except ValueError as exc:
                    timing_error = str(exc)

    samples = profile.samples if profile is not None else sample_lap(lap, 0.1)
    return {
        'metrics': {'length_m': lap.curve.length,
                    'peak_curvature_inv_m': max(abs(sample.curvature) for sample in samples),
                    'lap_time_s': None if profile is None else profile.lap_time_s,
                    'passes': passes},
        'points': [sample.xy for sample in samples],
        'speed': [] if profile is None else [
            [sample.q / lap.period, float(speed)]
            for sample, speed in zip(samples, profile.points.speed_mps)
        ],
        'timing_error': timing_error,
    }


def run_job(directory: Path, progress: Path, job: dict, track: Track, vehicle: Vehicle,
            settings: OptimizerSettings | None) -> None:
    """Publish each completed result independently in the worker process."""
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
