# Global Planner

The Global Planner package generates a global trajectory around a race track. Its ROS 2 node
processes map and car pose information and publishes global waypoints and track bounds. The
package uses the [TUM Global Race Trajectory Optimization](https://github.com/TUMFTM/global_racetrajectory_optimization)
package, modified to integrate with this race stack. The main node is launched with the
`mapping_launch.xml` file from the `stack_master` package or when the `map_editor` is used; the
global trajectory publisher publishes calculated waypoints and markers while the base system
runs.

The package also contains a route geometry library and a local map annotation editor:

- [Route library](global_planner/route/README.md): validated route manifests, lap geometry,
  portal crossings, and sampling.
- [Annotation editor](global_planner/annotation/README.md): create and validate route manifests
  from occupancy maps.

Older planner details follow.

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
