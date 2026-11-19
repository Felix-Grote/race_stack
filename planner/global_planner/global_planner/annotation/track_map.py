"""
An occupancy map from mapping, and the free space the operator keeps on it.

map:        a map_server pair, a PNG and the YAML that places it in the map frame. It is read
            once and never written.
pixels:     (u, v) with v = 0 at the top row of the file. A pixel is the square of side
            resolution centred on x = origin_x + u resolution,
            y = origin_y + (height - 1 - v) resolution.
free:       a cell is free only when its occupancy is below free_thresh; unknown (grey) cells
            count as occupied, so they never become road.
strokes:    lines the operator draws to close gaps in the walls; they only add occupied cells.
region:     a free pixel the operator picks; only the free cells connected to it stay free.
            Strokes and region only ever shrink the free space.
"""
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path

import cv2
import numpy as np
import yaml

# The widest stroke, in pixels, and the furthest a stroke point may lie outside the image.
MAX_STROKE_WIDTH_PX = 31
_MAX_STROKE_COORD_PX = 1e6


class AnnotationError(ValueError):
    """The map or the operator's annotation cannot give a route; the message says why."""

    def __init__(self, message: str, at_px=()) -> None:
        super().__init__(message)
        # Where on the map it fails, in file pixels, for the page to mark.
        self.at_px = [[float(u), float(v)] for u, v in at_px]


def _read_yaml(path: Path) -> dict:
    """Return the map file's keys, checked for what this tool reads."""
    try:
        meta = yaml.safe_load(path.read_text(encoding='utf-8'))
    except (OSError, yaml.YAMLError) as exc:
        raise AnnotationError(f'cannot read {path}: {exc}') from exc

    if not isinstance(meta, dict) or not isinstance(meta.get('image'), str):
        raise AnnotationError(f'{path.name} is not a map file: it names no image')

    try:
        resolution = float(meta['resolution'])
        origin = [float(v) for v in meta['origin']]
        free_thresh = float(meta.get('free_thresh', 0.196))
    except (KeyError, TypeError, ValueError) as exc:
        raise AnnotationError(f'{path.name}: resolution, origin or free_thresh is malformed') \
            from exc

    if not (math.isfinite(resolution) and resolution > 0 and len(origin) == 3
            and all(math.isfinite(v) for v in origin) and 0 < free_thresh <= 1):
        raise AnnotationError(f'{path.name}: resolution, origin or free_thresh is out of range')

    if origin[2] != 0:
        raise AnnotationError(f'{path.name}: a rotated map (origin yaw {origin[2]}) is not '
                              f'supported')

    if meta.get('negate', 0) not in (0, 1) or meta.get('mode', 'trinary') != 'trinary':
        raise AnnotationError(f'{path.name}: only trinary maps with negate 0 or 1 are supported')

    return dict(meta, resolution=resolution, origin=origin, free_thresh=free_thresh)


@dataclass(frozen=True)
class MapSource:
    """The map bytes and the settings that affect their interpretation."""

    png: bytes
    sha256: str
    digest: str
    resolution: float
    origin: tuple[float, float]
    free_thresh: float
    negate: int


def read_source(yaml_path: Path) -> MapSource:
    """Read one map source without decoding the image."""
    meta = _read_yaml(yaml_path)
    png_path = yaml_path.parent / meta['image']
    try:
        png = png_path.read_bytes()
    except OSError as exc:
        raise AnnotationError(f'cannot read the map image {png_path}') from exc

    sha = hashlib.sha256(png).hexdigest()
    resolution, origin = meta['resolution'], tuple(meta['origin'][:2])
    threshold, negate = meta['free_thresh'], int(meta.get('negate', 0))
    identity = json.dumps([sha, resolution, origin, threshold, negate]).encode()
    return MapSource(png, sha, hashlib.sha256(identity).hexdigest(),
                     resolution, origin, threshold, negate)


class TrackMap:
    """
    One occupancy map, read once.

    name:       the map file's stem, e.g. test.
    yaml_path:  the map file.
    png:        the image file's bytes, as read; sha256 is their hash.
    occupied:   per pixel, whether the cell is occupied or unknown.
    """

    def __init__(self, yaml_path: str | Path) -> None:
        self.yaml_path = Path(yaml_path)
        source = read_source(self.yaml_path)
        image = cv2.imdecode(np.frombuffer(source.png, np.uint8), cv2.IMREAD_GRAYSCALE)
        if image is None:
            raise AnnotationError(f'{self.yaml_path.name} does not point to a readable image')

        self.name = self.yaml_path.stem
        self.png, self.sha256, self.source_digest = source.png, source.sha256, source.digest
        self.resolution, self.origin = source.resolution, source.origin
        self.height, self.width = image.shape
        gray = image.astype(np.float64)
        occupancy = (255. - gray) / 255. if source.negate == 0 else gray / 255.
        self.occupied = occupancy >= source.free_thresh

    def pixel_to_world(self, uv) -> tuple[float, float]:
        """Return the map-frame point, in metres, at file pixel (u, v)."""
        return (self.origin[0] + float(uv[0]) * self.resolution,
                self.origin[1] + (self.height - 1 - float(uv[1])) * self.resolution)

    def world_to_pixel(self, xy) -> tuple[float, float]:
        """Return the file pixel (u, v) at a map-frame point; the inverse of pixel_to_world."""
        return ((float(xy[0]) - self.origin[0]) / self.resolution,
                (self.height - 1) - (float(xy[1]) - self.origin[1]) / self.resolution)


def _points(stroke) -> np.ndarray:
    """Return a stroke as an (n, 2) array of finite pixel coordinates, or refuse it."""
    try:
        points = np.asarray(stroke, dtype=float).reshape(-1, 2)
    except (TypeError, ValueError) as exc:
        raise AnnotationError('a stroke must be a list of [u, v] pixels') from exc

    if not np.isfinite(points).all() or np.abs(points).max(initial=0) > _MAX_STROKE_COORD_PX:
        raise AnnotationError('a stroke point is not a finite pixel near the map')

    return points


def _check_width(stroke_width_px: int) -> None:
    """Refuse a stroke width that is not a whole number of pixels in range."""
    if (isinstance(stroke_width_px, bool) or not isinstance(stroke_width_px, int)
            or not 1 <= stroke_width_px <= MAX_STROKE_WIDTH_PX):
        raise AnnotationError(f'the stroke width must be a whole number of pixels from 1 to '
                              f'{MAX_STROKE_WIDTH_PX}')


def _draw(cells: np.ndarray, stroke, stroke_width_px: int) -> None:
    """Mark the cells a stroke covers, in place."""
    # Truncated to whole pixels, as the drawing calls take them.
    points = _points(stroke).astype(np.int32)
    if len(points) >= 2:
        cv2.polylines(cells.view(np.uint8), [points.reshape(-1, 1, 2)], False, 1,
                      thickness=stroke_width_px, lineType=cv2.LINE_8)
    elif len(points) == 1:
        cv2.circle(cells.view(np.uint8), tuple(int(c) for c in points[0]),
                   max(1, stroke_width_px // 2), 1, -1)


def free_mask(track_map: TrackMap, strokes_px: list, stroke_width_px: int) -> np.ndarray:
    """Return the free cells left once the strokes are drawn, as 255 (free) or 0."""
    _check_width(stroke_width_px)
    occupied = track_map.occupied.copy()
    for stroke in strokes_px:
        _draw(occupied, stroke, stroke_width_px)

    # A cell in no 2x2 block of free cells is a sliver no car fits in, and a wall traced
    # round it would run out and back over itself; dropping it only shrinks the road.
    free = np.where(occupied, 0, 255).astype(np.uint8)
    block = np.ones((2, 2), np.uint8)
    # The two anchors must complement each other, or the even kernel shifts the road.
    corners = cv2.erode(free, block, anchor=(0, 0), borderType=cv2.BORDER_CONSTANT, borderValue=0)
    return cv2.dilate(corners, block, anchor=(1, 1),
                      borderType=cv2.BORDER_CONSTANT, borderValue=0)


def floating_strokes(track_map: TrackMap, strokes_px: list, stroke_width_px: int) -> list[int]:
    """
    Return the indices of the strokes that touch no occupied cell of the map.

    A stroke may reach the map's walls through other strokes. One that does not stands
    alone in the free space: an island, which a route round a single ring cannot go round.
    """
    _check_width(stroke_width_px)
    drawn = []
    for stroke in strokes_px:
        cells = np.zeros_like(track_map.occupied)
        _draw(cells, stroke, stroke_width_px)
        drawn.append(cells)

    occupied = track_map.occupied | np.logical_or.reduce(drawn, initial=False)
    _, labels = cv2.connectedComponents(occupied.astype(np.uint8), connectivity=8)
    anchored = np.unique(labels[track_map.occupied])

    return [i for i, cells in enumerate(drawn)
            if cells.any() and not np.isin(labels[cells], anchored).any()]


def kept_mask(free: np.ndarray, region_px: list | None) -> np.ndarray:
    """Return the free cells 8-connected to the picked pixel, or all of them when none is."""
    if region_px is None:
        return free

    try:
        u, v = (int(c) for c in region_px)
    except (TypeError, ValueError) as exc:
        raise AnnotationError('the picked region must be a [u, v] pixel') from exc

    if not (0 <= v < free.shape[0] and 0 <= u < free.shape[1]) or free[v, u] == 0:
        raise AnnotationError('the picked pixel is not free road; click inside the track')

    _, labels = cv2.connectedComponents((free > 0).astype(np.uint8), connectivity=8)

    return np.where(labels == labels[v, u], 255, 0).astype(np.uint8)
