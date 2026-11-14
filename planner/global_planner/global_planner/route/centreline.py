"""
The centreline of a section, derived from its two walls.

bisector:   the points equally far from the left and the right wall: the Voronoi
            edges between one left-wall point and one right-wall point, clipped to the
            section.
path:       the shortest way along those edges between the points nearest the two cap
            midpoints, which skips side branches; straight pieces join it to the midpoints.
spacing:    the result is resampled evenly; walls are densified ten times finer.
limit:      past the end of the shorter wall, "equally far" no longer means the middle
            of the road, so caps far from square to the walls bend the centreline.
"""
import math

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
from scipy.spatial import Voronoi
import shapely
from shapely.geometry import LineString, Polygon

from .geometry import Chain, EPS, outline


def _bisector(left: Chain, right: Chain, spacing: float) -> np.ndarray:
    """Return the bisector inside the section as an (n, 2, 2) array of edges."""
    section = Polygon(outline(left, right)).buffer(EPS)
    shapely.prepare(section)
    left_points = np.asarray(shapely.segmentize(LineString(left), spacing / 10).coords)
    right_points = np.asarray(shapely.segmentize(LineString(right), spacing / 10).coords)
    on_left = np.arange(len(left_points) + len(right_points)) < len(left_points)
    voronoi = Voronoi(np.vstack((left_points, right_points)))

    edges = []
    for (site_a, site_b), (i, j) in zip(voronoi.ridge_points, voronoi.ridge_vertices):
        if i < 0 or j < 0 or on_left[site_a] == on_left[site_b]:
            continue

        ends = voronoi.vertices[[i, j]]
        ridge = LineString(ends)
        if section.covers(ridge):
            edges.append(ends)
        elif section.intersects(ridge):
            for part in shapely.get_parts(ridge.intersection(section)):
                if part.geom_type == 'LineString':
                    xy = shapely.get_coordinates(part)
                    edges += zip(xy, xy[1:])

    edges = np.asarray(edges, dtype=float).reshape(-1, 2, 2)

    return edges[(edges[:, 0] != edges[:, 1]).any(axis=1)]


def centreline(left: Chain, right: Chain, spacing: float = 0.5) -> Chain:
    """Return the section's centreline from start-cap midpoint to end-cap midpoint."""
    edges = _bisector(left, right, spacing)
    if not len(edges):
        raise ValueError('no point is equally far from both walls inside the section')

    nodes, index = np.unique(edges.reshape(-1, 2), axis=0, return_inverse=True)
    lengths = np.linalg.norm(edges[:, 0] - edges[:, 1], axis=1)
    graph = csr_matrix((lengths, index.reshape(-1, 2).T), shape=(len(nodes), len(nodes)))

    start = (np.asarray(right[0]) + np.asarray(left[0])) / 2
    end = (np.asarray(right[-1]) + np.asarray(left[-1])) / 2
    first = int(np.argmin(np.linalg.norm(nodes - start, axis=1)))
    last = int(np.argmin(np.linalg.norm(nodes - end, axis=1)))

    _, previous = dijkstra(graph, directed=False, indices=first, return_predecessors=True)
    path, k = [], last
    while k != first:
        if k < 0:
            raise ValueError('the walls do not leave a connected way between the caps')

        path.append(nodes[k])
        k = previous[k]

    line = LineString([start, nodes[first]] + path[::-1] + [end])
    count = max(2, math.ceil(line.length / spacing)) + 1
    points = shapely.line_interpolate_point(line, np.linspace(0., 1., count), normalized=True)

    return tuple(map(tuple, shapely.get_coordinates(points).tolist()))
