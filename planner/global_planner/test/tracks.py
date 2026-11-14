"""Small synthetic tracks and lines for the route and optimizer tests."""
import math
from pathlib import Path

from global_planner.route.lap import LapCurve
from global_planner.route.manifest import validate_route
from global_planner.route.sampling import refit_lap, sample_lap
from global_planner.route.track import Route
import numpy as np
from shapely.geometry import LineString

NUC5 = Path(__file__).resolve().parents[3] / 'stack_master' / 'config' / 'NUC5' / 'car_model.yaml'

# Where the stadium's sections start, in metres along its centre: four long ones, or four
# short ones on the straights between longer ones, each just long enough for the car, so that
# a body can be within reach of two gates at once.
LONG = (0., 7., 13., 20.)
SHORT = (0., 0.6, 3., 3.6, 11., 11.6, 14., 14.6)

# Distance between the centre points the stadium's walls are built from, in metres.
_POINT_M = 0.1


def _centre(straight: float, radius: float) -> np.ndarray:
    """Return the stadium's centre points, anticlockwise from the start of the bottom straight."""
    lines, arcs = round(straight / _POINT_M), round(math.pi * radius / _POINT_M)
    points = []
    for side in (1, -1):
        start = -side * straight / 2
        points += [(start + side * straight * i / lines, -side * radius) for i in range(lines)]
        turn = -side * math.pi / 2
        points += [(-start + radius * math.cos(turn + math.pi * i / arcs),
                    radius * math.sin(turn + math.pi * i / arcs)) for i in range(arcs)]

    return np.array(points)


def stadium(straight: float, radius: float, width: float, cuts_m: tuple[float, ...] = LONG,
            heading_range: tuple[float, float] = (-0.3, 0.3),
            wall_tolerance_m: float = 0.02) -> Route:
    """
    Return a stadium of two straights and two half circles, cut into sections.

    cuts_m:             where sections start, in metres along the centre from the start of
                        the bottom straight, driving anticlockwise.
    heading_range:      the start heading range; the start box sits a metre into the bottom
                        straight, as wide as the road.
    wall_tolerance_m:   how far the walls may be off the true ones: they are thinned to
                        corners, as an annotator's are.
    """
    centre = _centre(straight, radius)
    ahead = np.roll(centre, -1, axis=0) - np.roll(centre, 1, axis=0)
    left_normal = np.column_stack((-ahead[:, 1], ahead[:, 0]))
    left_normal /= np.linalg.norm(left_normal, axis=1)[:, None]
    walls = {'left': centre + left_normal * width / 2, 'right': centre - left_normal * width / 2}
    cuts = [round(m / _POINT_M) for m in cuts_m]
    sections = []
    for k, a in enumerate(cuts):
        b = cuts[(k + 1) % len(cuts)] + (len(centre) if k == len(cuts) - 1 else 0)
        index = [i % len(centre) for i in range(a, b + 1)]
        section = {'uid': f's{k}', 'surface': 'ground', 'max_speed_mps': 3.0}
        for side, wall in walls.items():
            thinned = LineString(wall[index]).simplify(wall_tolerance_m)
            section[side] = [list(p) for p in thinned.coords]

        sections.append(section)

    x, y = -straight / 2 + 1, -radius
    box = [[x - 0.3, y - width / 2], [x + 0.3, y - width / 2],
           [x + 0.3, y + width / 2], [x - 0.3, y + width / 2]]

    return validate_route({
        'name': 'stadium', 'map': {'frame_id': 'map', 'sha256': '0' * 64},
        'start': {'heading_range_rad': list(heading_range), 'zone': box},
        'sections': sections})


def wobbled(lap: LapCurve, amplitude: float, waves: int = 5) -> LapCurve:
    """Return lap moved sideways by a sine of amplitude metres, waves times around the lap."""
    samples = sample_lap(lap, 0.25)
    moved = []
    for v in samples:
        f = amplitude * math.sin(waves * 2 * math.pi * v.q / lap.period + 1.)
        moved.append((v.xy[0] - f * v.tangent[1], v.xy[1] + f * v.tangent[0]))

    return refit_lap(lap, samples, moved)
