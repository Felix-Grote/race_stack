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

**Hyperparameters** applies one worksheet across all maps. Its γ value refers to Balanced. Gentle uses twice that value and Aggressive uses half. The chosen γ weights curvature energy in the native lap-time objective. The presets are provisional. Changing the weight can change convergence and the relative lap times.

## Compare and inspect

- Check profiles in **Driving profiles** to show them on the map and graph. The comparison displays predicted flying-lap times and the signed difference from the current Balanced result.
- **Active Constraints** colours one visible profile by the speed constraints it reaches at either end of each sampled interval. The categories are road speed, vehicle speed, cornering, tyre drive, motor drive, tyre braking and the conservative steering-rate cap. Multiple limits get a shared colour and the inspector lists each one. Grey marks intervals with no local bound reached. The map describes the returned speed solve on its final geometry. A bound elsewhere can affect speed on an interval that has local slack.
- The inspector compares physical demand with the effective profile limit and the original model limit at the same endpoint. For tyre drive and braking, both limits account for the lateral demand at that endpoint. The combined grip percentage uses the native grip exponent and both tyre demands, including drag in the longitudinal demand. It reports the highest value over the interval for each envelope. Road speed has its own cap and percentage.
- **Vehicle utilisation (base)** is the highest base-model usage of top speed, combined grip, motor drive, steering angle or mean steering rate over the interval. The graph offers each component and road speed limit use as separate quantities. Motor ratios are omitted where the available drive is zero.
- **Wall clearance** is sampled from the oriented, uninflated vehicle rectangle to physical side walls of the owning section and its immediate neighbours. Gates and artificial portal support edges are excluded. A footprint outside its legal road is reported with zero clearance. The legend relates this measurement to the required clearance. The optimizer's own geometry checks determine validity.
- The graph and map use the planner's shared route progress `q` in metres. Longitudinal acceleration, steering rate and limit usage describe the outgoing sample interval. The graph's steering rate is the mean over that interval. The map uses the native conservative endpoint speed cap. Use the graph's arrow keys to move the inspection cursor and Home or End to jump to either end of the lap.

### High-speed-cap demonstration

On a scratch copy of `test/test`, set **Speed limit** to 20 m/s in Annotator and export the route. Generate Balanced and Aggressive with the NUC5 car model. In Tracks, select **Active Constraints** and inspect Balanced. With the road cap above the planning top speed, the map shows where cornering grip, tyre drive and braking grip limit the lap. At about 45 m of route progress the inspector shows the cornering demand alongside both lateral limits.

## Export to the car

**Export to car** in Tracks writes `global_waypoints.json` next to the map, replacing the one there. The stack reads it as before. Choose what goes in the two lines the car is launched with:

| Slot | Topic | Launched with |
|---|---|---|
| Raceline | `/global_waypoints` | `raceline:=mincurv` (the default) |
| Shortest path | `/global_waypoints/shortest_path` | `raceline:=shortest_path`; also the line overtaking sectors are tuned on |

Each slot takes Gentle, Balanced, Aggressive or Centreline. Only profiles with a current result are offered, so a stale line never reaches the car. Results generated before export existed must be generated again. The file's third slot, `/centerline_waypoints`, always holds the centreline; where the car cannot steer it, the raceline's choice stands in.

The centreline is the route's centre curve timed for the car's unscaled limits. Unlike the profiles it is not optimized, and nothing checks that the body stays clear of the walls along it. Retune `ot_sectors.yaml` and `speed_scaling.yaml` after exporting a new raceline, since they index its waypoints.

## Data and limits

The existing [annotation workflow](global_planner/annotation/README.md) validates and exports the route and its source receipt. The Centre detects changes to the saved route or its map calibration. An export without a receipt can be used after operator review if its image hash matches. An open draft can differ from the saved export used by Tracks.

One isolated worker runs the requested profiles in sequence. Each completed profile is saved atomically with its effective settings, body, profile and original model limits, calibration and route digests, worksheet revision and a planner source fingerprint. Changing an effective input removes stale results from the plots. Bounds-only edits do not invalidate results. Results saved before Active Constraints require regeneration to populate the new diagnostics.

The Centre is for offline, single-operator planning. Times, dynamics and clearances come from the model and sampled trajectories. They require offline evaluation and vehicle testing before the presets can be calibrated for operational use.
