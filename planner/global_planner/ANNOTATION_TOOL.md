# Minimal Project A map-annotation tool (MVP1)

Two pencils, no GIS: open a map, close missing legal boundaries with the
boundary pencil, draw one directed lap with the route pencil, approve,
and export a strict Project A `legal_route.json`.

## Run

```bash
PYTHONPATH=planner/global_planner python3.12 -m global_planner.annotation_server \
  --maps stack_master/maps --out /tmp/annotation_out --port 8766
# open http://127.0.0.1:8766/
```

Headless (same core): `annotation_tool extract|export --map <yaml> --session <json> --out <dir>`.
ROS: `annotation_node` exposes the same operations as std_msgs/String JSON
on `/planner_annotation/command` → `/planner_annotation/state`, with
`maps_dir`/`out_dir` ROS params (fail-fast when unset). Run it only
in an isolated namespace/`ROS_DOMAIN_ID`, never in the driving launch.
Foxglove Bridge can forward those two topics to Lichtblick/Foxglove; no
custom WebSocket transport is built or needed. No live ROS/Foxglove
roundtrip has been demonstrated in this environment (no rclpy, no
`/opt/ros`, no ROS images) — see Limitations.

## How it works (and why not the legacy chain)

- Source PNG/YAML are read-only; strokes patch an in-memory copy
  (black = occupied, `negate: 1` supported by inversion), preserving
  the legacy flip/resolution/origin convention
  (`y = origin_y + (H-1-v)·res`, zero-yaw only). Non-binary images
  (gray/unknown levels) are rejected instead of being read as free.
- Extraction = the two loops of the free-space region (outer + one hole).
  This replaces skeleton→centerline→watershed for this tool: no guessed
  centerline length, no initial pose, and any non-annulus topology
  (split, extra island) is rejected instead of guessed. Small outer-wall
  damage is accepted as a visible detour (fail-open is impossible here),
  so the operator must compare the candidate overlay with the map.
- The directed loop is split into 4 occurrences at locally straight
  points; left/right chains are arcs of the extracted loops, so shared
  end-caps are exact by construction. Strict `validate_route` +
  `prepare_route` must pass (adaptive seed smoothing 0–6 passes; failure
  at every level = rejected route, reported as such). The export receipt
  reports the maximum lateral seed correction in metres, so the operator
  sees how far their line was moved.
- Approval is explicit and digest-bound: every edit (strokes, route,
  width, undo) bumps the session revision and revokes approval; export
  binds the approval to a digest of the exact geometry, and the headless
  CLI re-checks that digest. A stale approval can never authorize edited
  geometry. Sessions are bound to the full map identity (PNG hash, size,
  resolution, origin, negate), not just the hash. v1 drafts reopen with
  approval revoked. Validation levels are never conflated: CANDIDATE
  (extraction) ≠ VALIDATED (strict input + corridor preparation) ≠
  optimizer PASS ≠ on-car qualification.

## Verified (2026-11-09, this branch)

- `test_annotation_core.py`: 21 passed — end-to-end strict PASS on the
  real `test` and `baku` maps, pixel↔world roundtrip, session
  save/reopen + full map-identity rejection (hash, size, resolution,
  origin, negate), outer-wall bay detour + tangent-stroke repair with
  geometry fidelity, isolated-speck and infield-chord rejection,
  reversed direction, outside-track rejection, non-binary rejection,
  negate:1 equivalence, v1 migration with revoked approval,
  digest-bound approval lifecycle, undo revokes approval, CLI refuses
  stale approvals, headless ROS-adapter configuration.
- Live loopback roundtrip: open → route → extract (CANDIDATE) → export
  (VALIDATED, digest `58a86373da78…`, correction 0.189 m, 341 samples,
  4 validated route chains) → save → undo (revokes approval) on
  `http://127.0.0.1:8766/` with the `test` map.
- Full compile attempt (Milestone B): `route_compile compile` with
  `synthetic_model.json`/`synthetic_policy.json` on the
  annotation-generated manifest reaches the optimizer and returns
  `SOLVER_FAILURE: OptimizationError: unrecognized pinned kernel:
  numpy` in this environment (numpy 2.5.4 vs pinned 1.26.4). No
  optimizer math was changed; the pinned gate works as designed. Full
  optimizer PASS remains **not demonstrated** — it needs the canonical
  pinned kernel environment (numpy 1.26.4 / scipy 1.11.4 / quadprog
  0.1.7 / trajectory-planning-helpers 0.79, per
  `iqp_route_adapter._helpers`). Note the repo inconsistency: the
  devcontainer installs `quadprog~=0.1.11`, which the pin gate rejects;
  the pin was deliberately not weakened — resolving which side is
  canonical needs an owner decision with a pinned-environment build.

## Limitations / unsupported (fail-closed)

- Planar single enclosed loop only; splits, bridges, decks, nonzero map
  yaw, non-binary encodings, and multi-region free space are rejected
  as UNSUPPORTED.
- On `spa`, `zuri`, `hangar_1905_v0`, `GLC_smile_small` the crude
  programmatic seed used in testing was rejected by the strict
  validator; an operator-drawn centreline may do better, but this is
  **not tested** and must not be assumed. (`glc_ot_ez` has two separate
  free-space regions and is rejected at extraction.)
- ROS/Foxglove roundtrip not demonstrated here (no rclpy, `/opt/ros`,
  or ROS container images in this environment). The adapter is
  unit-tested headless; bridge wiring needs a ROS Humble host. Isolate
  from the driving network when running it.
- `ament_flake8`/`pep257`/`copyright` harness tests error at collection
  here (ament packages not installed); changed files pass `py_compile`
  and a 99-column scan instead.
- The synthetic vehicle model/policy are software budgets only — no car
  calibration, no on-car qualification is claimed.
