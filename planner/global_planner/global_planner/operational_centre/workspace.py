"""Coordinate the editor, worksheet, jobs and comparison state for one workspace."""
from dataclasses import asdict
from functools import lru_cache
import json
from multiprocessing import get_context
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from . import car_file
from .generation import profile_info, PROFILES, provenance, RESULT_VERSION, run_job
from .inputs import Track, Vehicle
from .settings import parameter_info, validate, Worksheet
from .storage import digest
from ..annotation.editor import Editor
from ..annotation.track_map import AnnotationError, read_source

_CHANGED = {'route': 'Route export changed', 'map': 'Map source changed',
            'car': 'Car model changed', 'optimizer': 'Optimizer values changed',
            'profile': 'Profile policy changed', 'speed_model': 'Speed model settings changed',
            'planner': 'Planner source changed'}
# The lines the car can be given.
EXPORT_LINES = (*PROFILES, 'centreline')


@lru_cache(maxsize=18)
def _artifact(data: bytes) -> dict:
    result = json.loads(data)
    if (not isinstance(result, dict) or result.get('version') not in (2, RESULT_VERSION)
            or not {'id', 'inputs', 'metrics', 'telemetry'} <= result.keys()
            or not isinstance(result['inputs'], dict)):
        raise ValueError('Unrecognized result format.')
    return result


class Workspace:
    """Own the local editor and one isolated generation worker."""

    def __init__(self, maps: Path, directory: Path, car: Path | None, margin: float) -> None:
        self.editor = Editor(maps)
        self.directory, self.car_path, self.margin = directory, car, margin
        self.worksheet_path = directory / 'optimizer.json'
        self.job = None
        # One worker for a job run in sequence; one for each profile when run side by side.
        self._workers, self._scratch = [], None

    def _map_path(self, name: str) -> Path:
        return self.editor.maps_dir / f'{name}.yaml'

    def _results(self, name: str) -> Path:
        # The map id came from Editor.maps(), and includes its directory and basename.
        return self.directory / 'results' / name

    def _inputs(self, name: str | None):
        track = Track.read(self._map_path(name)) if name else Track('missing', 'No map selected.')
        vehicle = Vehicle.read(self.car_path, self.margin)
        worksheet = Worksheet.read(self.worksheet_path)
        settings = None if worksheet.error else validate(worksheet.parameters)
        revision = digest(json.dumps([track.status, track.route.digest if track.route else None,
                                      track.source, vehicle.revision, self.margin,
                                      worksheet.revision]).encode())
        return track, vehicle, worksheet, settings, revision

    def prepare_annotation(self, action: str) -> None:
        """Keep the editor's optional car preflight aligned with the configured car."""
        vehicle = Vehicle.read(self.car_path, self.margin)
        if action == 'export' and self.car_path is not None and vehicle.car is None:
            raise AnnotationError(f'Configured car cannot be checked. {vehicle.message}')
        self.editor.set_car(vehicle.car)

    def _annotation(self, track_name: str | None, track: Track, vehicle: Vehicle) -> dict:
        editor = self.editor
        if editor.map_name is None:
            return {'map': None, 'message': 'Open a map to edit or export its route.'}

        try:
            source_changed = (editor.track_map.source_digest
                              != read_source(editor.track_map.yaml_path).digest)
        except (ValueError, OSError):
            source_changed = True

        if source_changed:
            message = 'Map source changed on disk. Reopen the map before saving or exporting.'
        elif self.car_path is not None and vehicle.car is None:
            message = f'Configured car cannot be checked. {vehicle.message}'
        elif editor.car != vehicle.car:
            message = 'Car model changed. The next editor action will recheck the route.'
        else:
            opened = (track if track_name == editor.map_name
                      else Track.read(editor.track_map.yaml_path))
            if editor.result and opened.route and editor.result['digest'] == opened.route.digest:
                message = opened.message
            elif opened.route:
                message = 'Open draft differs from the exported route used by Tracks.'
            else:
                message = opened.message

        return {'map': editor.map_name, 'message': message, 'source_changed': source_changed,
                'export_blocked': self.car_path is not None and vehicle.car is None,
                'draft_differs': not source_changed and track_name == editor.map_name
                and track.route is not None
                and (editor.result is None or editor.result['digest'] != track.route.digest)}

    def _comparison(self, name: str | None, track: Track, vehicle: Vehicle,
                    settings) -> tuple[dict, dict, dict]:
        """Return each profile's summary, the current results and the stale ones."""
        summaries, current, stale = {}, {}, {}
        for kind in PROFILES:
            if name is None:
                summaries[kind] = {'status': 'missing'}
                continue
            try:
                artifact = _artifact((self._results(name) / f'{kind}.json').read_bytes())
            except FileNotFoundError:
                summaries[kind] = {'status': 'missing'}
                continue
            except (OSError, ValueError) as exc:
                summaries[kind] = {'status': 'invalid', 'message': str(exc)}
                continue

            if artifact['version'] != RESULT_VERSION:
                summaries[kind] = {'status': 'stale',
                                   'message': 'Regenerate to calculate active constraints.'}
                continue

            expected = provenance(kind, track, vehicle, settings)
            changed = [label for key, label in _CHANGED.items()
                       if artifact['inputs'].get(key) != expected.get(key)]
            if not changed and artifact['inputs'] != expected:
                changed = ['Effective planning inputs changed']
            (stale if changed else current)[kind] = artifact
            summaries[kind] = {
                'status': 'stale' if changed else 'current',
                'message': ', '.join(changed) + '.' if changed else None,
                'metrics': artifact['metrics'],
            }
        return summaries, current, stale

    def state(self, name: str | None, seen_view: str | None) -> dict:
        """Describe current inputs and return plot data only when the plotted snapshot changes."""
        self.update_job()
        maps = self.editor.maps()
        if name not in maps:
            name = next((item for item in maps if self._map_path(item).with_name(
                f'{Path(item).name}_route.json').is_file()), maps[0] if maps else None)
        track, vehicle, worksheet, settings, revision = self._inputs(name)
        annotation = self._annotation(name, track, vehicle)
        summaries, current, stale = self._comparison(name, track, vehicle, settings)
        route = track.route
        ids = [{kind: item['id'] for kind, item in shown.items()} for shown in (current, stale)]
        view_id = digest(json.dumps([name, route.digest if route else None, ids]).encode())
        state = {
            'maps': maps, 'map': name, 'annotation': annotation, 'revision': revision,
            'track': {'status': track.status, 'name': track.name, 'message': track.message,
                      'digest': route.digest if route else None,
                      'sections': len(route.sections) if route else 0},
            'car': {'name': vehicle.car.name if vehicle.car else None,
                    'timing': vehicle.limits is not None, 'message': vehicle.message},
            'settings': asdict(worksheet), 'parameters': parameter_info(),
            'profiles': {kind: profile_info(kind, self.margin, settings) for kind in PROFILES},
            'summaries': summaries, 'job': self.job,
            'exportable': [kind for kind, item in current.items() if 'waypoints' in item],
            'car_file': dict(zip(('level', 'message'), car_file.status(
                self._map_path(name).parent, self._results(name), track, vehicle, current)
                if name else ('off', 'No map selected.'))),
        }
        if seen_view != view_id:
            state['view'] = {
                'id': view_id,
                'walls': [section.polygon for section in route.sections] if route else [],
                'gates': [portal.gate for portal in route.portals] if route else [],
                'start': route.start_line if route else [],
                'period_m': route.section_bounds[-1] if route else 0.,
                'lines': {kind: item['telemetry'] for kind, item in current.items()},
                # Shown greyed: a stale line is still a result, only not of these inputs.
                'stale': {kind: item['telemetry']['points'] for kind, item in stale.items()},
            }
        return state

    def save_settings(self, body: dict) -> None:
        """Save a worksheet against the revision shown to the operator."""
        Worksheet.save(self.worksheet_path, body.get('parameters'), body.get('revision'))

    def generate(self, body: dict) -> None:
        """Validate, snapshot and start the requested planner runs."""
        self.update_job()
        if self._workers:
            raise ValueError('A generation job is already running.')
        name, categories = body.get('map'), body.get('categories')
        if name not in self.editor.maps():
            raise ValueError('Select a map from the workspace.')
        if (not isinstance(categories, list) or not categories
                or not all(kind in PROFILES for kind in categories)
                or len(set(categories)) != len(categories)):
            raise ValueError('Select at least one driving profile.')

        track, vehicle, worksheet, settings, revision = self._inputs(name)
        if body.get('revision') != revision:
            raise ValueError('Planner inputs changed. Review the current inputs and try again.')
        if track.route is None or (track.status == 'unverified'
                                   and body.get('allow_unverified') is not True):
            raise ValueError(track.message)
        if worksheet.error:
            raise ValueError(worksheet.error)
        if vehicle.car is None or vehicle.limits is None:
            raise ValueError(vehicle.message)

        parallel = body.get('parallel') is True
        job = {'id': uuid4().hex, 'map': name, 'running': True, 'parallel': parallel,
               'attempts': {kind: {'status': 'queued'} for kind in PROFILES if kind in categories}}
        scratch = TemporaryDirectory(prefix='forzaeth-planner-')
        workers = []
        try:
            for kinds in ([[kind] for kind in job['attempts']] if parallel
                          else [list(job['attempts'])]):
                progress = Path(scratch.name) / f'progress-{kinds[0]}.json'
                part = dict(job, attempts={kind: job['attempts'][kind] for kind in kinds})
                worker = get_context('spawn').Process(
                    target=run_job, daemon=True,
                    args=(self._results(name), progress, part, track, vehicle, settings))
                worker.start()
                workers.append((worker, progress, kinds))
        except BaseException:
            for worker, _, _ in workers:
                worker.kill()
            scratch.cleanup()
            raise
        self.job, self._workers, self._scratch = job, workers, scratch

    def export(self, body: dict) -> str:
        """Write the chosen lines into the map's global_waypoints.json; return a note."""
        name = body.get('map')
        if name not in self.editor.maps():
            raise ValueError('Select a map from the workspace.')
        chosen = {slot: body.get(slot) for slot in car_file.SLOTS}
        if not all(kind in EXPORT_LINES for kind in chosen.values()):
            raise ValueError('Choose a line for the raceline and for the shortest path.')

        track, vehicle, _, settings, revision = self._inputs(name)
        if body.get('revision') != revision:
            raise ValueError('Planner inputs changed. Review the current inputs and try again.')
        if track.route is None or vehicle.car is None or vehicle.limits is None:
            raise ValueError(vehicle.message or track.message)

        # Only results of the inputs as they are now go to the car, never stale ones.
        current = self._comparison(name, track, vehicle, settings)[1]
        return car_file.export(self._map_path(name).parent, self._results(name), chosen,
                               current, track, vehicle)

    def log(self, name: str | None, kind: str | None) -> str:
        """Return what the planner logged in the last run of a profile on a map."""
        if name not in self.editor.maps() or kind not in PROFILES:
            raise ValueError('Select a map and a driving profile.')
        try:
            return (self._results(name) / f'{kind}.log').read_text(encoding='utf-8')
        except FileNotFoundError:
            return ''

    def stop(self, job_id: str) -> None:
        """Stop only the job shown when the operator pressed Stop."""
        self.update_job()
        if self._workers:
            if self.job['id'] != job_id:
                raise ValueError('The active job changed. Review it before stopping.')
            self.update_job(cancel=True)

    def update_job(self, cancel: bool = False) -> None:
        """Collect completed attempts and reap or stop the workers."""
        if not self._workers:
            return
        for worker, progress, _ in self._workers:
            if cancel and worker.is_alive():
                worker.terminate()
                worker.join(timeout=0.5)
                if worker.is_alive():
                    worker.kill()
                    worker.join()

            if progress.exists():
                self.job['attempts'].update(json.loads(progress.read_bytes())['attempts'])

        if any(worker.is_alive() for worker, _, _ in self._workers):
            return

        self.job['running'] = False
        for worker, _, kinds in self._workers:
            worker.join()
            for attempt in (self.job['attempts'][kind] for kind in kinds):
                attempt.pop('progress', None)
                if attempt['status'] in ('queued', 'running'):
                    if cancel:
                        attempt.update(status='cancelled', message='Generation stopped.')
                    else:
                        attempt.update(status='failed', message=f'Planner worker exited '
                                       f'(code {worker.exitcode}). See server output.')
            worker.close()
        self._scratch.cleanup()
        self._workers, self._scratch = [], None
