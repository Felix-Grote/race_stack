"""Export lines of a ring road and check what the car's nodes rely on."""
import json
import math
from pathlib import Path

from global_planner.car import Car, CarLimits
from global_planner.ros_export import centreline_waypoints, lap_time_s, waypoints, write_lines
from global_planner.route.lap import centre_curve
from global_planner.route.manifest import validate_route
from global_planner.route.zones import portal_zones
from global_planner.speed.speeds import speed_profile

CAR = Path(__file__).parents[3] / 'stack_master' / 'config' / 'NUC5' / 'car_model.yaml'
INNER, OUTER, LIMIT = 2., 3., 3.


def _ring() -> dict:
    """Return a ring road driven anticlockwise, cut into four sections."""
    def arc(radius: float, quarter: int) -> list:
        angles = [(quarter + i / 16) * math.pi / 2 for i in range(17)]
        return [[radius * math.cos(a), radius * math.sin(a)] for a in angles]

    return {'name': 'ring', 'map': {'frame_id': 'map', 'sha256': '0' * 64},
            'sections': [{'uid': f'o{k}', 'surface': 'ground', 'max_speed_mps': LIMIT,
                          'left': arc(INNER, k), 'right': arc(OUTER, k)} for k in range(4)]}


def test_export(tmp_path):
    """The file holds a closed lap of 0.1 m waypoints with true widths and legal speeds."""
    lap = centre_curve(validate_route(_ring()))
    zones = portal_zones(lap.route, Car.load(CAR, 0.05).reach_m)
    profile = speed_profile(lap, zones, CarLimits.load(CAR))
    start_q = lap.period / 3
    line = waypoints(lap, profile, start_q)
    centre = centreline_waypoints(lap.route, Car.load(CAR, 0.05), CarLimits.load(CAR))
    path = write_lines(tmp_path, lap.route, line, centre, centre, 'raceline: balanced; ')

    # Each slot holds the line it was given; the centreline starts on the start line.
    data = json.loads(path.read_text())
    assert data['global_traj_wpnts_sp'] == data['centerline_waypoints'] == {'wpnts': centre}
    assert math.hypot(centre[0]['x_m'] - 2.5, centre[0]['y_m']) < 1e-6
    right, left = lap.route.start_line
    assert math.dist(right, (OUTER, 0.)) < 1e-9 and math.dist(left, (INNER, 0.)) < 1e-9
    assert data['map_info_str']['data'].startswith('raceline: balanced; ')
    assert set(data) == {
        'map_info_str', 'est_lap_time', 'centerline_markers', 'centerline_waypoints',
        'global_traj_markers_iqp', 'global_traj_wpnts_iqp', 'global_traj_markers_sp',
        'global_traj_wpnts_sp', 'trackbounds_markers'}
    wpnts = data['global_traj_wpnts_iqp']['wpnts']
    first, last = wpnts[0], wpnts[-1]

    # Closed, counted from where it was told to start, 0.1 m apart: what the nodes index by.
    assert dict(last, id=0, s_m=0.) == first and last['id'] == len(wpnts) - 1
    assert math.isclose(last['s_m'], lap.curve.length)
    assert all(abs(b['s_m'] - a['s_m'] - .1) < 1e-3 for a, b in zip(wpnts, wpnts[1:]))
    assert math.dist((first['x_m'], first['y_m']),
                     lap.curve.sample(lap.station_at_progress(start_q)).xy) < 1e-9

    for w in wpnts:
        radius = math.hypot(w['x_m'], w['y_m'])
        angle = math.atan2(w['y_m'], w['x_m'])

        # The walls are 16 chords a quarter, a hair inside their circles.
        assert abs(w['d_left'] - (radius - INNER)) < 5e-3
        assert abs(w['d_right'] - (OUTER - radius)) < 5e-3
        assert abs(math.remainder(w['psi_rad'] - angle - math.pi / 2, math.tau)) < .05
        assert .3 < w['kappa_radpm'] < .5 and 0 < w['vx_mps'] <= LIMIT + 1e-9

    assert math.isclose(data['est_lap_time']['data'], lap_time_s(line))
    assert math.isclose(lap_time_s(line), profile.lap_time_s, rel_tol=1e-3)
    assert len(data['trackbounds_markers']['markers']) > len(wpnts)
