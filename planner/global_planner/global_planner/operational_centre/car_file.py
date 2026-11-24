"""
The map's global_waypoints.json as the Centre writes it, and how it stands against the results.

stamp:      results/<map>/export.json records what an export put in which slot, for which
            route, car and results, and the file's time and size: the Centre can then say
            when the file falls behind its results, or was replaced outside it.
centreline: the file's third slot always holds the centreline. Where the car cannot steer
            it, the raceline's line stands in, and the export says so.
"""
import json
from pathlib import Path
import time

from .inputs import Track, Vehicle
from .storage import write_json
from ..ros_export import centreline_waypoints, write_lines

# The two slots of the car's file the operator fills.
SLOTS = ('raceline', 'shortest_path')


def export(map_dir: Path, results: Path, chosen: dict, current: dict, track: Track,
           vehicle: Vehicle) -> str:
    """
    Write the chosen lines into map_dir/global_waypoints.json; return a note for the operator.

    chosen:     the profile, or 'centreline', for each slot.
    current:    the results of the inputs as they are now; only these go to the car.
    """
    lines = {}
    for kind in set(chosen.values()) - {'centreline'}:
        if kind not in current:
            raise ValueError(f'{kind.capitalize()} has no current result. Generate it first.')
        if 'waypoints' not in current[kind]:
            raise ValueError(f'{kind.capitalize()} was generated before export existed. '
                             f'Generate it again.')
        lines[kind] = current[kind]['waypoints']

    note = ''
    try:
        lines['centreline'] = centreline_waypoints(track.route, vehicle.car, vehicle.limits)
    except ValueError as exc:
        if 'centreline' in chosen.values():
            raise ValueError(f'The centreline cannot be driven by this car. {exc}. Generate '
                             f'a driving profile and export that instead.') from exc
        lines['centreline'] = lines[chosen['raceline']]
        note = (f'The car cannot steer the centreline ({exc}): its slot, '
                f'/centerline_waypoints, holds the raceline instead.')

    info = ''.join(f'{slot}: {kind}; ' for slot, kind in chosen.items())
    path = write_lines(map_dir, track.route, lines[chosen['raceline']],
                       lines[chosen['shortest_path']], lines['centreline'], info)
    stat = path.stat()
    write_json(results / 'export.json', {
        'lines': chosen, 'route': track.route.digest, 'car': vehicle.revision,
        'ids': {kind: current[kind]['id'] for kind in lines if kind in current},
        'centreline_stand_in': bool(note),
        'time': time.strftime('%H:%M on %d %b'), 'stat': [stat.st_mtime_ns, stat.st_size]})

    return note


def status(map_dir: Path, results: Path, track: Track, vehicle: Vehicle,
           current: dict) -> tuple[str, str]:
    """Return how the map's global_waypoints.json relates to the results shown: level, text."""
    try:
        stat = (map_dir / 'global_waypoints.json').stat()
    except OSError:
        return 'off', 'Nothing exported for this map.'
    try:
        stamp = json.loads((results / 'export.json').read_bytes())
        lines = stamp['lines']
        stand_in = ' (raceline in the centreline slot)' if stamp.get('centreline_stand_in') else ''
        what = (f'{lines["raceline"].capitalize()} + {lines["shortest_path"].capitalize()}'
                f'{stand_in}, exported {stamp["time"]}')
        if stamp['stat'] != [stat.st_mtime_ns, stat.st_size]:
            return 'off', 'The file was replaced outside the Centre. Its lines are unknown.'
        if track.route is None or stamp['route'] != track.route.digest:
            return 'warn', f'Out of date: route changed. Holds {what}.'
        if stamp['car'] != vehicle.revision:
            return 'warn', f'Out of date: car model changed. Holds {what}.'
        changed = [kind.capitalize() for kind, made in stamp['ids'].items()
                   if current.get(kind, {}).get('id') != made]
        if changed:
            return 'warn', (f'Out of date: {", ".join(changed)} changed since export. '
                            f'Holds {what}.')
        return 'ok', f'Up to date: {what}.'
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return 'off', 'Not exported from the Centre. Its lines are unknown.'
