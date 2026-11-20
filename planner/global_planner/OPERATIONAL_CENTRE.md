# ForzaETH Operational Centre

The local workspace includes the Windows 95 Paint annotator, an optimizer worksheet and a workbench for comparing driving profiles.

## Run

From a checkout with the stack's Python dependencies installed, use the ROS package entry point `ros2 run global_planner operational_centre` or launch it from source without ROS.

```sh
PYTHONPATH=planner/global_planner python -m global_planner.operational_centre.server \
  --maps stack_master/maps \
  --car stack_master/config/NUC5/car_model.yaml
```

Open the address printed by the server. Use a writable copy of the map directory to keep your checkout clean. With `test/test`, open the map and use **Set start** on the suggested guide along the upper straight, around image pixel (206, 39). Export the route, switch to **Tracks** and choose **Generate…**.

The `--workspace` directory defaults to `.forzaeth/operational-centre` relative to the working directory. It stores the worksheet and the latest successful result for each profile. A car model with body and speed limits is required for generation. Annotation can run without a car.

## Driving profiles

| Profile | Performance fraction α | Extra clearance above `--margin` | Smoothness γ with defaults |
|---|---:|---:|---:|
| Gentle | 80% | 0.050 m | 0.20 |
| Balanced | 90% | 0.025 m | 0.10 |
| Aggressive | 95% | 0 m | 0.05 |

Each profile runs the native geometry and flying-lap optimizer independently. The performance fraction scales vehicle top speed, lateral and longitudinal tyre limits, braking, motor acceleration at the calibrated speed breakpoints and steering-rate limits. Mass, drag, steering geometry and the source calibration stay fixed. The clearance baseline defaults to 0.05 m and the added clearance is in metres.

**Hyperparameters** applies one worksheet across all maps. Its value and working bounds for γ refer to Balanced. Gentle uses twice that value and Aggressive uses half. The chosen γ weights curvature energy in the native lap-time objective. The presets are provisional. Changing the weight can change convergence and the relative lap times.

## Compare and inspect

- Check profiles in **Driving profiles** to show them on the map and graph. The comparison displays predicted flying-lap times and the signed difference from the current Balanced result.
- Use **Display** to switch the map to a heatmap of a single visible profile. Constraint utilisation is the maximum of the road and vehicle speed ratios, combined tyre grip, drive-motor demand, steering angle and the planner's steering-rate cap. Combined grip uses the native grip exponent and the worse endpoint of each gap. The tyre demand includes drag and uses the acceleration or braking limit according to its sign. Inspection reports the dominant constraint, the other ratios and the two grip contributions.
- Wall clearance is sampled from the oriented, uninflated vehicle rectangle to physical side walls of the owning section and its immediate neighbours. Gates and artificial portal support edges are excluded. A footprint outside its legal road is reported with zero clearance. The legend relates this measurement to the required clearance. The optimizer's own geometry checks determine validity.
- Select a telemetry quantity and point at the graph to inspect the same route location across profiles. The horizontal coordinate is the planner's shared route progress `q` in metres. Longitudinal acceleration, steering rate and constraint utilisation are shown over the outgoing sample interval. Steering rate in the graph is the mean for that interval. The utilisation overlay uses the native conservative endpoint speed cap. Use the graph's arrow keys to move the inspection cursor and Home or End to jump to either end of the lap.

## Data and limits

The existing [annotation workflow](global_planner/annotation/README.md) validates and exports the route and its source receipt. The Centre detects changes to the saved route or its map calibration. An export without a receipt can be used after operator review if its image hash matches. An open draft can differ from the saved export used by Tracks.

One isolated worker runs the requested profiles in sequence. Each completed profile is saved atomically with its effective settings, body, limits, calibration and route digests, worksheet revision and a planner source fingerprint. Changing an effective input removes stale results from the plots. Bounds-only edits do not invalidate results. Older trajectory files remain in the workspace under their original names.

The Centre is for offline, single-operator planning. Times, dynamics and clearances come from the model and sampled trajectories. They require offline evaluation and vehicle testing before the presets can be calibrated for operational use.
