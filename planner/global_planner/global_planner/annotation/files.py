"""
The files the editor writes next to a map's YAML; the map's own files are never written.

<map>_annotation.json:      the operator's draft, with the map source it was made for. A draft
                            saved for another map source is not loaded.
<map>_route.json:           the exported route manifest.
<map>_route.source.json:    its receipt: the route digest and the map source it was checked on.
"""
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from .track_map import TrackMap

# The draft's fields the page may set, and their types.
FIELDS = {'strokes_px': list, 'stroke_width_px': int, 'region_px': (list, type(None)),
          'guide_px': list, 'start_px': (list, type(None)), 'name': str, 'surface': str,
          'max_speed_mps': (int, float)}

# A new draft's speed limit: above any car's top speed, so that it is the car's own v_max
# that bounds the line. A lower one is for a track that asks for it, set by the operator.
UNLIMITED_MPS = 20.


def path(track_map: TrackMap, suffix: str) -> Path:
    """Return the path of one of the map's files, e.g. suffix 'route'."""
    return track_map.yaml_path.with_name(f'{track_map.name}_{suffix}.json')


def write(target: Path, text: str) -> None:
    """Write a file whole: a reader sees the old file or the new one, never part of it."""
    with NamedTemporaryFile(mode='w', encoding='utf-8', dir=target.parent,
                            delete=False) as stream:
        tmp = Path(stream.name)
        try:
            stream.write(text)
            stream.close()
            os.replace(tmp, target)
        finally:
            tmp.unlink(missing_ok=True)


def load_draft(track_map: TrackMap) -> tuple[dict, str]:
    """Return the map's saved draft, or a new one, and which it is."""
    draft = {'strokes_px': [], 'stroke_width_px': 5, 'region_px': None, 'guide_px': [],
             'guide_auto': True, 'start_px': None, 'name': track_map.name,
             'surface': 'ground', 'max_speed_mps': UNLIMITED_MPS}
    file = path(track_map, 'annotation')
    try:
        saved = json.loads(file.read_text(encoding='utf-8')) if file.exists() else None
    except (ValueError, OSError):
        saved = {}

    if saved == {}:
        return draft, f'{file.name} is unreadable or empty: new draft'
    if saved is None:
        return draft, 'new draft'
    if (not isinstance(saved, dict) or saved.get('map_sha256') != track_map.sha256
            or saved.get('map_source_digest', track_map.source_digest)
            != track_map.source_digest):
        return draft, f'{file.name} was made for a different map source: new draft'

    draft.update({k: saved[k] for k in FIELDS if k in saved},
                 guide_auto=saved.get('guide_auto', False))
    return draft, f'draft loaded from {file.name}'


def save_draft(track_map: TrackMap, draft: dict) -> Path:
    """Write the draft next to the map, with the map source it was made for."""
    file = path(track_map, 'annotation')
    write(file, json.dumps(dict(draft, map_sha256=track_map.sha256,
                                map_source_digest=track_map.source_digest), indent=1))
    return file


def write_receipt(track_map: TrackMap, route: Path, digest: str) -> None:
    """Record which route and map source an export was checked on."""
    write(route.with_suffix('.source.json'),
          json.dumps({'route': digest, 'map': track_map.source_digest}, indent=1))


def exported(track_map: TrackMap, result: dict | None) -> str:
    """Return how the route file on disk relates to the draft's result: none, current, changed."""
    try:
        written = json.loads(path(track_map, 'route').read_bytes())
    except FileNotFoundError:
        return 'none'
    except (OSError, ValueError):
        return 'changed'

    return 'current' if result and written == result['payload'] else 'changed'
