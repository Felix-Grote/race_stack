"""
The annotation editor's state: the open map, the operator's draft and the route it gives.

files:      the draft, the route and its receipt, next to the map (files.py).
draft:      strokes, picked region, guide, start, route name, surface and speed limit.
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
from pathlib import Path

import cv2
import numpy as np

from . import checks, files, guide, sections
from .track_map import (AnnotationError, floating_strokes, free_mask, kept_mask, read_source,
                        TrackMap)
from .walls import is_track, keep_track, loops
from ..car import Car
from ..route.lap import LapCurve
from ..route.manifest import load_route
from ..route.track import Route


def _png_url(image: np.ndarray | bytes) -> str:
    """Return an image as a data URL the page can show."""
    data = image if isinstance(image, bytes) else cv2.imencode('.png', image)[1].tobytes()

    return 'data:image/png;base64,' + base64.b64encode(data).decode()


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
        self.map_name = None
        self._map_url = None

    def maps(self) -> list[str]:
        """Return the maps in maps_dir, as <folder>/<map>, those named after their folder."""
        return sorted(f'{p.parent.name}/{p.stem}' for p in self.maps_dir.glob('*/*.yaml')
                      if p.stem == p.parent.name)

    def open(self, name: str) -> str:
        """Open a map from maps(), with its saved draft when it was made for this map."""
        if name not in self.maps():
            raise AnnotationError(f'no map {name!r} in {self.maps_dir}')

        self.track_map = TrackMap(self.maps_dir / f'{name}.yaml')
        self.map_name = name
        self._map_url = _png_url(self.track_map.png)
        self.draft, message = files.load_draft(self.track_map)
        self.draft['region_px'] = keep_track(self._free(), self.draft['region_px'])
        self._follow()
        self._recheck()
        return message

    def _require_open(self) -> None:
        if self.track_map is None:
            raise AnnotationError('open a map first')

    def _require_current_source(self) -> None:
        self._require_open()
        if read_source(self.track_map.yaml_path).digest != self.track_map.source_digest:
            raise AnnotationError('the map changed on disk: reopen it before saving or exporting')

    def set_car(self, car: Car | None) -> None:
        """Refresh optional portal-zone checks when the configured car changes."""
        if car != self.car:
            self.car = car
            if self.track_map is not None:
                self._recheck()

    def edit(self, field: str, value: object) -> str:
        """Change one field of the draft, or refuse it, and check the route again."""
        self._require_open()
        if (field not in files.FIELDS or isinstance(value, bool)
                or not isinstance(value, files.FIELDS[field])):
            raise AnnotationError(f'cannot set {field!r} to {value!r}')

        draft = dict(self.draft, **{field: value})
        if field == 'start_px' and value is not None:
            # The two ends of the start line the operator drew, or one click from an older draft.
            try:
                ends = np.asarray(value, float).reshape(-1, 2)
            except (TypeError, ValueError) as exc:
                raise AnnotationError(f'cannot set {field!r} to {value!r}') from exc

            same_place = len(ends) == 2 and np.ptp(ends, axis=0).max() < 1
            if len(ends) > 2 or not np.all(np.isfinite(ends)) or same_place:
                raise AnnotationError('the start line needs two clicks apart: one on each side '
                                      'of the road')

            kept = kept_mask(free_mask(self.track_map, draft['strokes_px'],
                                       draft['stroke_width_px']), draft['region_px'])
            if len(guide.off_road(kept, [[float(v) for v in ends.mean(axis=0)]])):
                raise AnnotationError('the start line must cross the road: click on one side '
                                      'of the track, then on the other')

        if field == 'guide_px':
            # A drawn guide stays as drawn.
            draft['guide_auto'] = False

        if field in ('strokes_px', 'stroke_width_px', 'region_px'):
            # Refuse a wall or a click the map cannot take now, not at the next check.
            free = free_mask(self.track_map, draft['strokes_px'], draft['stroke_width_px'])
            if field == 'region_px' and value is not None:
                kept_mask(free, value)
            else:
                draft['region_px'] = keep_track(free, draft['region_px'])
                # Removing walls is always allowed, so a draft can lose a bad one.
                if len(draft['strokes_px']) >= len(self.draft['strokes_px']):
                    self._refuse_bad_walls(draft)

        self.draft = draft
        self._follow()
        self._recheck()
        return f'{field} changed'

    def _refuse_bad_walls(self, draft: dict) -> None:
        """Refuse walls that leave an island in the road, or that cut a closed track open."""
        floating = floating_strokes(self.track_map, draft['strokes_px'], draft['stroke_width_px'])
        if floating:
            names = ', '.join(str(i + 1) for i in floating)
            raise AnnotationError(f'wall {names} touches no wall of the map, so the track would '
                                  f'get an island a route cannot go round: start and end it on '
                                  f'a black wall')

        region = self.draft['region_px']
        if draft['region_px'] is None and region is not None \
                and is_track(kept_mask(self._free(), region)):
            try:
                loops(kept_mask(free_mask(self.track_map, draft['strokes_px'],
                                          draft['stroke_width_px']), region), True)
            except AnnotationError as exc:
                # Say where the ring breaks, when the walls can tell.
                if exc.at_px:
                    raise
            raise AnnotationError('this wall cuts the track, leaving no closed ring: walls may '
                                  'close gaps and cut off pockets, but not cross the whole road')

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
            self.route = ('no start yet: press Set start and click on each side of the road '
                          'to draw the start line')
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
                       # The start line: the gate into the first section, wall to wall.
                       'start_px': px((payload['sections'][0]['right'][0],
                                       payload['sections'][0]['left'][0])),
                       'payload': payload, 'digest': route.digest}
        car = f', portal zones checked for {self.car.name}' if self.car else ''
        self.route = (f'valid: {len(payload["sections"])} sections, lap {lap.period:.2f} m{car}. '
                      f'Not optimized yet: export it for the optimizer')

    def save(self) -> str:
        """Write the draft next to the map."""
        self._require_current_source()
        return f'draft saved to {files.save_draft(self.track_map, self.draft)}'

    def export(self) -> str:
        """Write the route last checked next to the map, and confirm it reads back the same."""
        self._require_current_source()
        if self.result is None:
            raise AnnotationError(f'nothing written, the route is {self.route}')

        path = files.path(self.track_map, 'route')
        files.write(path, json.dumps(self.result['payload'], indent=1))
        if load_route(path).digest != self.result['digest']:
            raise AnnotationError(f'{path} does not read back as the checked route')

        self.save()
        files.write_receipt(self.track_map, path, self.result['digest'])
        return f'route written to {path}'

    def view(self) -> dict:
        """Return what the page shows: the map, the draft, the walls and the last route."""
        if self.track_map is None:
            return {'maps': self.maps()}

        view = dict(self.draft, maps=self.maps(), map=self.map_name, route=self.route,
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
