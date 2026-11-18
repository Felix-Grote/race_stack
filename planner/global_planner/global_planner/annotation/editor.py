"""
The annotation editor's state: the open map, the operator's draft and the route it gives.

files:      next to each map's YAML: <map>_annotation.json, the operator's draft, and
            <map>_route.json, the exported manifest. The map's own files are never written.
draft:      strokes, picked region, guide, start, route name, surface and speed limit. A draft
            saved for other map bytes is not loaded.
edits:      refused when the map cannot take them: a wall that touches no wall of the map, a
            click off the road. With no region picked, or when a wall leaves the picked one no
            track, the largest region that is a track is kept. After every edit the route is
            built and checked again, so the page always shows whether it is valid, and where
            it fails.
guide:      the road's midline unless the operator draws one: a suggested guide follows the
            road as walls change, keeping its direction; a drawn one stays as drawn.
export:     writes exactly the route checked after the last edit, so only a valid one. It is
            read back through load_route to confirm it holds the same route.
"""
import base64
import json
import os
from pathlib import Path

import cv2
import numpy as np

from . import checks, guide, sections
from .track_map import AnnotationError, floating_strokes, free_mask, kept_mask, TrackMap
from .walls import find_track, loops
from ..car import Car
from ..route.lap import LapCurve
from ..route.manifest import load_route
from ..route.track import Route

_FIELDS = {'strokes_px': list, 'stroke_width_px': int, 'region_px': (list, type(None)),
           'guide_px': list, 'start_px': (list, type(None)), 'name': str, 'surface': str,
           'max_speed_mps': (int, float)}


def _png_url(image: np.ndarray | bytes) -> str:
    """Return an image as a data URL the page can show."""
    data = image if isinstance(image, bytes) else cv2.imencode('.png', image)[1].tobytes()

    return 'data:image/png;base64,' + base64.b64encode(data).decode()


def _write(path: Path, text: str) -> None:
    """Write a file whole: a reader sees the old file or the new one, never part of it."""
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(text, encoding='utf-8')
    os.replace(tmp, path)


class Editor:
    """The open map, the operator's draft and the last route checked for it."""

    def __init__(self, maps_dir: str | Path, car: Car | None = None) -> None:
        self.maps_dir = Path(maps_dir).resolve()
        if not self.maps_dir.is_dir():
            raise AnnotationError(f'{self.maps_dir} is not a directory')

        self.car = car
        self.track_map = None
        self.draft = {}
        self.result = None
        self.route = ''
        self.route_at = []
        self._map_name = None
        self._map_url = None

    def maps(self) -> list[str]:
        """Return the maps in maps_dir, as <folder>/<map>, those named after their folder."""
        return sorted(f'{p.parent.name}/{p.stem}' for p in self.maps_dir.glob('*/*.yaml')
                      if p.stem == p.parent.name)

    def _path(self, suffix: str) -> Path:
        return self.track_map.yaml_path.with_name(f'{self.track_map.name}_{suffix}.json')

    def open(self, name: str) -> str:
        """Open a map from maps(), with its saved draft when it was made for this map."""
        if name not in self.maps():
            raise AnnotationError(f'no map {name!r} in {self.maps_dir}')

        self.track_map = TrackMap(self.maps_dir / f'{name}.yaml')
        self._map_name = name
        self._map_url = _png_url(self.track_map.png)
        self.draft = {'strokes_px': [], 'stroke_width_px': 5, 'region_px': None,
                      'guide_px': [], 'guide_auto': True, 'start_px': None,
                      'name': self.track_map.name, 'surface': 'ground', 'max_speed_mps': 2.5}
        path = self._path('annotation')
        saved = json.loads(path.read_text(encoding='utf-8')) if path.exists() else None
        if saved is None:
            message = 'new draft'
        elif saved.get('map_sha256') != self.track_map.sha256:
            message = f'{path.name} was made for other map bytes: new draft'
        else:
            self.draft.update({k: saved[k] for k in _FIELDS if k in saved},
                              guide_auto=saved.get('guide_auto', False))
            message = f'draft loaded from {path.name}'

        self.draft['region_px'] = self._region(self._free(), self.draft['region_px'])
        self._follow()
        self._recheck()
        return message

    def _require_open(self) -> None:
        if self.track_map is None:
            raise AnnotationError('open a map first')

    def edit(self, field: str, value: object) -> str:
        """Change one field of the draft, or refuse it, and check the route again."""
        self._require_open()
        if (field not in _FIELDS or isinstance(value, bool)
                or not isinstance(value, _FIELDS[field])):
            raise AnnotationError(f'cannot set {field!r} to {value!r}')

        draft = dict(self.draft, **{field: value})
        if field == 'start_px' and value is not None:
            kept = kept_mask(free_mask(self.track_map, draft['strokes_px'],
                                       draft['stroke_width_px']), draft['region_px'])
            if len(guide.off_road(kept, [value])):
                raise AnnotationError('the start must be on the road: click inside the track')

        if field == 'guide_px':
            # A drawn guide stays as drawn.
            draft['guide_auto'] = False

        if field in ('strokes_px', 'stroke_width_px', 'region_px'):
            # Refuse a wall or a click the map cannot take now, not at the next check.
            free = free_mask(self.track_map, draft['strokes_px'], draft['stroke_width_px'])
            if field == 'region_px' and value is not None:
                kept_mask(free, value)
            else:
                if len(draft['strokes_px']) >= len(self.draft['strokes_px']):
                    # Removing walls is always allowed, so a draft with a floating wall can
                    # lose it.
                    floating = floating_strokes(self.track_map, draft['strokes_px'],
                                                draft['stroke_width_px'])
                    if floating:
                        names = ', '.join(str(i + 1) for i in floating)
                        raise AnnotationError(f'wall {names} touches no wall of the map, so the '
                                              f'track would get an island a route cannot go '
                                              f'round: start and end it on a black wall')

                draft['region_px'] = self._region(free, draft['region_px'])

        self.draft = draft
        self._follow()
        self._recheck()
        return f'{field} changed'

    @staticmethod
    def _region(free: np.ndarray, region_px: list | None) -> list | None:
        """Return the region to keep: the one given while it is still a track, else the track."""
        if region_px is not None:
            try:
                loops(kept_mask(free, region_px), True)
                return region_px
            except AnnotationError:
                pass

        return find_track(free)

    def _free(self) -> np.ndarray:
        """Return the free cells left by the draft's strokes."""
        return free_mask(self.track_map, self.draft['strokes_px'], self.draft['stroke_width_px'])

    def _road(self, free: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Return the kept free cells and the two wall loops, or refuse the draft."""
        region = self.draft['region_px']
        kept = kept_mask(free, region)

        return (kept, *loops(kept, region is not None))

    def _build(self, guide_px: list) -> tuple[dict, Route, LapCurve]:
        """Return the checked manifest, its route and its lap for a guide."""
        kept, outer, inner = self._road(self._free())
        d = self.draft
        payload = sections.build(self.track_map, outer, inner, guide_px, d['start_px'], kept,
                                 d['name'], d['surface'], d['max_speed_mps'])

        return (payload, *checks.check(payload, self.track_map, kept, self.car))

    def _follow(self) -> None:
        """Lay a suggested guide on the road's midline, the way it ran before, if any."""
        if not self.draft['guide_auto']:
            return

        try:
            kept, _, inner = self._road(self._free())
        except AnnotationError:
            # No track yet: the guide waits for one.
            return

        loop = guide.midline(kept, inner)
        before = self.draft['guide_px']
        if len(before) >= 3 and guide.signed_area(before) * guide.signed_area(loop) < 0:
            loop = loop[:1] + loop[:0:-1]

        self.draft['guide_px'] = loop + loop[:1]

    def suggest(self) -> str:
        """Make the guide the road's midline again, following the road from now on."""
        self._require_open()
        self._road(self._free())
        self.draft['guide_auto'] = True
        self._follow()
        self._recheck()
        return 'guide suggested: it follows the road until you draw one'

    def reverse(self) -> str:
        """Turn the guide round, from the same first point."""
        self._require_open()
        g = self.draft['guide_px']
        if len(g) < 3:
            raise AnnotationError('there is no guide to reverse')

        self.draft['guide_px'] = [g[0], *g[-2:0:-1], g[0]]
        self._recheck()
        return 'guide reversed'

    def _recheck(self) -> None:
        """Build and check the route for the draft, and keep it, or why it fails, to show."""
        self.result, self.route_at = None, []
        if len(self.draft['guide_px']) < 3:
            self.route = 'no guide yet: draw one, or press Suggest'
            return

        if self.draft['start_px'] is None:
            self.route = 'no start yet: press Set start and click where the car starts'
            return

        try:
            payload, route, lap = self._build(self.draft['guide_px'])
        except (AnnotationError, ValueError) as exc:
            self.route = f'not valid: {exc}'
            self.route_at = getattr(exc, 'at_px', [])
            return

        def px(chain) -> list[list[float]]:
            return [list(self.track_map.world_to_pixel(p)) for p in chain]

        self.result = {'left_px': [px(s['left']) for s in payload['sections']],
                       'right_px': [px(s['right']) for s in payload['sections']],
                       'gates_px': [px((s['right'][-1], s['left'][-1]))
                                    for s in payload['sections']],
                       'start_px': px(payload['start']['zone']),
                       'payload': payload, 'digest': route.digest}
        car = f', portal zones checked for {self.car.name}' if self.car else ''
        self.route = (f'valid: {len(payload["sections"])} sections, lap {lap.period:.2f} m{car}. '
                      f'Not optimized yet: export it for the optimizer')

    def save(self) -> str:
        """Write the draft next to the map."""
        self._require_open()
        path = self._path('annotation')
        _write(path, json.dumps(dict(self.draft, map_sha256=self.track_map.sha256), indent=1))
        return f'draft saved to {path}'

    def export(self) -> str:
        """Write the route last checked next to the map, and confirm it reads back the same."""
        self._require_open()
        if self.result is None:
            raise AnnotationError(f'nothing written, the route is {self.route}')

        path = self._path('route')
        _write(path, json.dumps(self.result['payload'], indent=1))
        if load_route(path).digest != self.result['digest']:
            raise AnnotationError(f'{path} does not read back as the checked route')

        self.save()
        return f'route written to {path}'

    def view(self) -> dict:
        """Return what the page shows: the map, the draft, the walls and the last route."""
        if self.track_map is None:
            return {'maps': self.maps()}

        view = dict(self.draft, maps=self.maps(), map=self._map_name, route=self.route,
                    problem_px=self.route_at,
                    size=[self.track_map.width, self.track_map.height], png=self._map_url,
                    result={k: v for k, v in self.result.items() if k not in ('payload', 'digest')}
                    if self.result else None)
        try:
            free = self._free()
            kept, outer, inner = self._road(free)
            view['walls_px'] = [outer.tolist(), inner.tolist()]
            if self.draft['region_px'] is not None:
                excluded = ((free > 0) & (kept == 0)).astype(np.uint8)
                overlay = np.zeros((*excluded.shape, 4), np.uint8)
                # --excluded in the page's palette, as BGRA.
                overlay[excluded > 0] = (60, 146, 251, 150)
                view['excluded_png'] = _png_url(overlay)
        except AnnotationError as exc:
            view['walls_error'] = str(exc)

        return view
