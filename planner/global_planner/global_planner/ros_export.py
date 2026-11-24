"""
Write an optimized lap as the stack's global_waypoints.json, the file the car reads.

file:       the one the old planner wrote (readwrite_global_waypoints.py), so that
            global_trajectory_publisher and every node behind it stay as they are. It is
            written as plain JSON, without ROS, so that it runs wherever the planner does.
waypoints:  every 0.1 m along the curve, as the stack's nodes assume, counted from the start
            line. The last one repeats the first.
speeds:     from the lap's speed profile. Between two of its points the car speeds up
            steadily, so the speed squared is straight in s.
widths:     d_left and d_right are the distance to the nearest point of the left and of the
            right wall, as the old planner measured them, among the walls on the waypoint's
            surface and those of its two neighbouring sections.
slots:      the file holds three lines the car can drive: the raceline, the "shortest path"
            and the centreline. Any line may be put in any slot (write_lines).
"""
import argparse
import json
import math
import os
from pathlib import Path

import numpy as np
from shapely.geometry import LineString, MultiLineString, Point
from shapely.ops import unary_union

from .car import Car, CarLimits
from .optimizer.solve import optimize
from .route.lap import centre_curve, LapCurve
from .route.manifest import load_route
from .route.sampling import sample_at_station
from .route.track import Route
from .route.zones import portal_zones
from .speed.speeds import speed_profile, SpeedProfile

# What state_machine, the local planners, the controllers and frenet_conversion index by.
_SPACING_M = 0.1
_SPHERE, _CYLINDER = 2, 3   # visualization_msgs/Marker types


def _walls(route: Route, index: int) -> tuple[MultiLineString, MultiLineString]:
    """Return the left and the right walls near section index: its surface's and neighbours'."""
    sections = route.sections
    near = {sections[index - 1].uid, sections[(index + 1) % len(sections)].uid}
    return tuple(unary_union([LineString(getattr(s, side)) for s in sections
                              if s.surface == sections[index].surface or s.uid in near])
                 for side in ('left', 'right'))


def waypoints(lap: LapCurve, profile: SpeedProfile, start_q: float) -> list[dict]:
    """
    Return the lap as f110_msgs/Wpnt fields, closed: the last waypoint repeats the first.

    start_q:    lap progress of the first waypoint (OptimizedLap.start_q).
    """
    length = lap.curve.length
    count = round(length / _SPACING_M)
    start = lap.station_at_progress(start_q)
    station = np.array([v.s for v in profile.samples])
    square = np.interp((start + length * np.arange(count) / count) % length, station,
                       profile.points.speed_mps ** 2, period=length)
    accel = profile.points.accel_mps2

    walls = {}
    wpnts = []
    for i in range(count):
        at = sample_at_station(lap, (start + length * i / count) % length)
        (x, y), (cos, sin) = at.xy, at.tangent
        left, right = walls.setdefault(at.section_uid,
                                       _walls(lap.route, lap.section_index(at.q)))
        here = Point(at.xy)
        wpnts.append({
            'id': i, 's_m': length * i / count, 'd_m': 0., 'x_m': x, 'y_m': y,
            'd_right': here.distance(right), 'd_left': here.distance(left),
            'psi_rad': math.atan2(sin, cos), 'kappa_radpm': at.curvature,
            'vx_mps': math.sqrt(square[i]),
            # Before the profile's first point the car is on its last gap: index -1.
            'ax_mps2': float(accel[np.searchsorted(station, at.s, side='right') - 1])})

    return wpnts + [dict(wpnts[0], id=count, s_m=length)]


def _marker(i: int, kind: int, xyz: tuple[float, float, float], height: float,
            rgb: tuple[float, float, float], width: float = 0.05) -> dict:
    """Return the fields of one visualization_msgs/Marker in the map frame."""
    return {'header': {'frame_id': 'map'}, 'type': kind, 'id': i,
            'scale': {'x': width, 'y': width, 'z': height},
            'color': dict(zip('rgb', rgb), a=1.),
            'pose': {'position': dict(zip('xyz', xyz)), 'orientation': {'w': 1.}}}


def centreline_waypoints(route: Route, car: Car, limits: CarLimits) -> list[dict]:
    """
    Return the route's centre line as waypoints, driven as fast as the car can.

    The centre line is timed, not optimized: nothing checks that the car's body stays on
    the road along it. Raises SpeedError if the car cannot steer it.
    """
    lap = centre_curve(route)
    profile = speed_profile(lap, portal_zones(route, car.reach_m), limits)

    return waypoints(lap, profile, 0.)   # from the start line, like the optimized lines


def lap_time_s(wpnts: list[dict]) -> float:
    """Return the time of one lap of waypoints, sped up steadily over each gap."""
    return sum(2 * (b['s_m'] - a['s_m']) / (a['vx_mps'] + b['vx_mps'])
               for a, b in zip(wpnts, wpnts[1:]))


def write_lines(map_dir: str | Path, route: Route, raceline: list[dict],
                shortest_path: list[dict], centreline: list[dict], info: str = '') -> Path:
    """
    Write map_dir/global_waypoints.json with a line of waypoints in each of its three slots.

    raceline:       what the car drives (/global_waypoints).
    shortest_path:  the line the overtaking sectors are tuned on, and the car's second choice
                    (/global_waypoints/shortest_path).
    centreline:     its third choice (/centerline_waypoints).
    info:           what was put where, for /map_infos.
    """
    def slot(wpnts: list[dict], rgb: tuple[float, float, float]) -> tuple[dict, dict]:
        top = max(w['vx_mps'] for w in wpnts)
        return {'wpnts': wpnts}, {'markers': [
            _marker(w['id'], _CYLINDER, (w['x_m'], w['y_m'], w['vx_mps'] / top / 2),
                    w['vx_mps'] / top, rgb, 0.1) for w in wpnts]}

    # Raceline red, shortest path yellow, centreline blue, right walls purple, left walls
    # green, as the old planner drew them.
    race, race_markers = slot(raceline, (1., 0., 0.))
    short, short_markers = slot(shortest_path, (1., 1., 0.))
    centre, centre_markers = slot(centreline, (0., 0., 1.))
    bounds = [(xy, rgb) for side, rgb in (('right', (.5, 0., .5)), ('left', (.5, 1., 0.)))
              for s in route.sections
              for xy in LineString(getattr(s, side)).segmentize(_SPACING_M).coords]
    time_s = lap_time_s(raceline)
    payload = {
        'map_info_str': {'data': f'{info}estimated lap time: {time_s:.4f}s; maximum speed: '
                                 f'{max(w["vx_mps"] for w in raceline):.4f}m/s; '
                                 f'route: {route.digest[:12]}; '},
        'est_lap_time': {'data': time_s},
        'centerline_markers': centre_markers, 'centerline_waypoints': centre,
        'global_traj_markers_iqp': race_markers, 'global_traj_wpnts_iqp': race,
        'global_traj_markers_sp': short_markers, 'global_traj_wpnts_sp': short,
        'trackbounds_markers': {'markers': [
            _marker(i, _SPHERE, (*xy, 0.), 0.05, rgb) for i, (xy, rgb) in enumerate(bounds)]},
    }

    # Written aside and moved into place: the car never reads half a file.
    path = Path(map_dir) / 'global_waypoints.json'
    aside = path.with_suffix('.json.tmp')
    aside.write_text(json.dumps(payload, allow_nan=False), encoding='utf-8')
    os.replace(aside, path)

    return path


def main(argv: list[str] | None = None) -> None:
    """Optimize a route for a car and write it in all three slots of the car's file."""
    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument('route', help='the track manifest, e.g. track.json')
    parser.add_argument('car', help="the car's car_model.yaml")
    parser.add_argument('map_dir', help='the map folder, e.g. stack_master/maps/test; its '
                                        'global_waypoints.json is replaced')
    parser.add_argument('--margin', type=float, default=0.05,
                        help='clearance kept around the body, in metres (default 0.05)')
    args = parser.parse_args(argv)

    route = load_route(args.route)
    result = optimize(route, Car.load(args.car, args.margin), limits=CarLimits.load(args.car))
    line = waypoints(result.lap, result.profile, result.start_q)
    path = write_lines(args.map_dir, route, line, line, line)
    print(f'{path}: {result.lap.curve.length:.2f} m, {result.profile.lap_time_s:.3f} s')


if __name__ == '__main__':
    main()
