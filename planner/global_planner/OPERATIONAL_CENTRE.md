# ForzaETH Operational Centre

The Centre runs on the local machine. It provides the Windows 95 Paint annotator, a worksheet for optimizer settings and a trajectory comparison workbench.

## Run

From a checkout with the stack's Python dependencies installed, use the ROS package entry point `ros2 run global_planner operational_centre` or launch it from source without ROS.

```sh
PYTHONPATH=planner/global_planner python -m global_planner.operational_centre.server \
  --maps stack_master/maps \
  --car stack_master/config/NUC5/car_model.yaml
```

Open the address printed by the server. Use a writable copy of the map directory if you want to keep your checkout clean. With `test/test`, open the map and use **Set start** on the suggested guide along the upper straight, around image pixel (206, 39). Export the route, switch to **Tracks** and choose **Generate…**.

The `--workspace` directory defaults to `.forzaeth/operational-centre` relative to the working directory. It holds the applied settings and latest successful results. `--margin` defaults to 0.05 m. With no `--car`, annotation and the centreline remain available.

## Operator workflow

- **Annotator** uses the existing map editor and validation. Exports include a canonical route manifest, the saved draft and a source receipt recording the route digest and map calibration. An open map whose image or calibration changed must be reopened before writing. Track files use the existing `<map>/<map>.yaml` layout. See the [annotation guide](global_planner/annotation/README.md).
- **Hyperparameters** applies one worksheet across all maps. The operator can narrow the range for each exposed value within the input limits. The planner validates the values together. The curve verification settings use the native defaults.
- **Tracks** plots the latest current lines and shows estimated flying-lap times for the timed profiles. The speed graph aligns the curves by shared route progress `q`. Use the layer checkboxes to compare lines that overlap. The centreline provides a geometry reference. Both optimized lines use the planner's vehicle clearance and steering checks.
- An export lacking a receipt can be used for comparison after operator review if its image hash matches. An export whose recorded inputs disagree with the current map or manifest requires a new export. An open draft and a saved export can differ, which the Centre reports while using the saved export for generation.

## Architecture and limits

The Python service mounts the Paint annotator beside two buildless browser panels with shared window styles. Generation runs one local job at a time in a separate process. It snapshots validated planner inputs before starting. The worker calls `centre_curve` and `portal_crossings` for the reference, `optimize` followed by `speed_profile` for minimum curvature, and `optimize(..., limits=...)` for lap time. If timing the minimum-curvature line fails, the validated geometry remains available with the timing error.

Each completed category is saved atomically with the inputs it used. The Centre marks old results stale and removes their layers when those inputs change. Bounds-only changes do not affect generated results. The smoothness weight affects lap-time mode. The job progress bar counts completed categories.

The workspace is designed for one local server and one operator. Estimates depend on the supplied vehicle model. Results are comparison data stored in the workspace. The app does not publish a trajectory to ROS.

## Verify

```sh
PYTHONPATH=planner/global_planner OPENBLAS_NUM_THREADS=1 \
  python -m pytest -q planner/global_planner/test/test_operational_centre.py
```
