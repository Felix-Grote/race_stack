# Global Planner 

## Operational Centre

The local Windows 95-style workspace uses the route, optimizer and speed packages to prepare tracks and compare predicted flying laps. Use **Annotator** to export a validated route, **Settings** to tune the optimizer and **Tracks** to generate Gentle, Balanced and Aggressive driving profiles.

Tracks includes a trajectory overlay, an Active Constraints map, a wall-clearance heatmap and telemetry linked by route progress. The inspector shows the effective profile limits alongside the original vehicle limits. Route, vehicle or optimizer changes mark affected results stale.

See the [Operational Centre guide](OPERATIONAL_CENTRE.md) for launch commands, profile settings and the high-speed-cap demonstration.

## Description
The Global Planner package is a ROS2 package designed to generate a global trajectory around a race track. It provides a node that subscribes to map and car pose information, processes this data, and publishes global waypoints, track boundaries and map informations and saves everything in a JSON file. The logic of the Global Planner is separated into three parts: ROS2 node, logic and utility functions. The logic of the Global Planner is implemented in the `global_planner_logic.py` module and the utility function are in the `global_planner_utils.py` module. This package is implemented in Python and uses the `rclpy` library for ROS interactions. For the calculation of the global trajectory, it uses the [TUM Global Race Trajectory Optimization](https://github.com/TUMFTM/global_racetrajectory_optimization) package, which was modified so that it was possible to integrate it in our race stack. The main node `global_planner_node.py` is launched with the `mapping_launch.xml` file from the `stack_master` package or if the `map_editor` is used. There is also a node `global_trajectory_publisher.py` for publishing the global waypoints and markers and track bounds markers frequently after they have been calculated which is launched every time the base system is launched.

## Exporting a route to the car
`ros_export.py` writes optimized lines as the map's `global_waypoints.json`, the file `global_trajectory_publisher` reads. Nothing on the car changes, and it needs no ROS. The file has three slots, one for each `raceline` the car can be launched with: the raceline (`mincurv`), the shortest path and the centreline.

- **Operational Centre:** in Tracks, **Export to car** puts Gentle, Balanced, Aggressive or the centreline in the raceline and shortest-path slots; see [OPERATIONAL_CENTRE.md](OPERATIONAL_CENTRE.md).
- **Command line:** `ros2 run global_planner export_route track.json stack_master/config/NUC5/car_model.yaml stack_master/maps/<map_name>` optimizes one line and writes it in all three slots.
- **Python:** `waypoints(lap, profile, start_q)` for each line, then `write_lines(map_dir, route, raceline, shortest_path, centreline)`.

The waypoints are 0.1 m apart and count from the start line. `ot_sectors.yaml` and `speed_scaling.yaml` index the waypoints, so retune them after exporting a new raceline.

## Parameters
 - `rate`: Sets the rate in hertz at which the ROS node is running.
 - `safety_width`: Sets the width of the car in meters including a safety margin for the calculation of the global trajectory.
 - `safety_width_sp`: Sets the width of the car in meters including a safety margin for the calculation of the shortest path trajectory.
 - `occupancy_grid_threshold`: Sets the threshold above which a cell in the occupancy grid is considered occupied and below it is considered free.
 - `filter_kernel_size`: The size of the kernel for the morphological filtering.
 - `show_plots`: Show additional plots for debugging during generation of the global trajectory.
 - `map_editor`: `True` if the map editor is used.
 - `map_name`: Sets the name of the map.
 - `create_map`: Create a map that can be used in the simulator and save a YAML file and a PNG of the map in the directory `stack_master/maps/map_name`.
 - `reverse_mapping`: Generate a global trajectory in the reverse direction.
 - `required_laps`: Number of laps required before the generation of the global trajectory can be started.

## Input/Output Topic Signature
This node subscribes to:
- `/map`: Subscribes to the occupancy grid of the map.
- TF `map -> base_link`: Reads the car's pose
    
The node publishes to:
- `/global_waypoints`: Publishes global waypoints.
- `/global_waypoints/markers`: Publishes global waypoint markers.
- `/global_waypoints/shortest_path`: Publishes waypoints of the shortest path trajectory (only used for visualization of the overtaking sectors).
- `/global_waypoints/shortest_path/markers`: Publishes waypoint markers of the shortest path trajectory (only used for visualization of the overtaking sectors).
- `/centerline_waypoints`: Publishes centerline waypoints.
- `/centerline_waypoints/markers`: Publishes centerline waypoint markers.
- `/trackbounds/markers`: Publishes markers for the track boundaries.
- `/map_infos`: Publishes map infos like estimated lap time and maximum speed.
- `/estimated_lap_time`: Publishes the estimated lap time.


