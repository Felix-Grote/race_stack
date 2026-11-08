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
on `/planner_annotation/command` → `/planner_annotation/state`. Run it only
in an isolated namespace/`ROS_DOMAIN_ID`, never in the driving launch.
Foxglove Bridge can forward those two topics to Lichtblick/Foxglove; no
custom WebSocket transport is built or needed.

## How it works (and why not the legacy chain)

- Source PNG/YAML are read-only; strokes patch an in-memory copy
  (black = occupied), preserving the legacy flip/resolution/origin
  convention (`y = origin_y + (H-1-v)·res`, zero-yaw only).
- Extraction = the two loops of the free-space region (outer + one hole).
  This replaces skeleton→centerline→watershed for this tool: no guessed
  centerline length, no initial pose, and any non-annulus topology (open
  gap, split, extra island) is rejected instead of guessed.
- The directed loop is split into 4 occurrences at locally straight
  points; left/right chains are arcs of the extracted loops, so shared
  end-caps are exact by construction. Strict `validate_route` +
  `prepare_route` must pass (adaptive seed smoothing 0–6 passes; failure
  at every level = rejected route, reported as such).
- Approval is explicit: edits revoke it, drafts record `approval: none`,
  and only `operator-approved` sessions export. Validation levels are
  never conflated: CANDIDATE (extraction) ≠ VALIDATED (strict input +
  corridor preparation) ≠ optimizer PASS ≠ on-car qualification.

## Verified (2026-11-08, this branch)

- `test_annotation_core.py`: 9 passed — end-to-end strict PASS on the
  real `test` and `baku` maps, pixel↔world roundtrip, session
  save/reopen + map-identity rejection, gap rejection/repair, reversed
  direction, outside-track rejection, source-map immutability.
- Full compile attempt (Milestone B): `route_compile compile` with
  `synthetic_model.json`/`synthetic_policy.json` reaches the optimizer
  and fails `SOLVER_FAILURE: unrecognized pinned kernel: numpy` in this
  environment; with pinned versions in a venv, `quadprog==0.1.7` itself
  fails to import (`undefined symbol: qpgen2_…`) via wheel, sdist, and
  the Dockerfile recipe. No optimizer math was changed. Full optimizer
  PASS remains **not demonstrated** — it needs the canonical pinned
  kernel environment (numpy 1.26.4 / scipy 1.11.4 / quadprog 0.1.7 /
  trajectory-planning-helpers 0.79, per `iqp_route_adapter._helpers`).

## Limitations / unsupported (fail-closed)

- Planar single enclosed loop only; splits, bridges, decks, nonzero map
  yaw, and multi-region free space are rejected as UNSUPPORTED.
- On `spa`, `zuri`, `hangar_1905_v0` the crude programmatic seed used in
  testing was rejected by the strict validator (seed intersects a legal
  side); an operator-drawn centreline may do better, but this is
  **not tested** and must not be assumed.
- The synthetic vehicle model/policy are software budgets only — no car
  calibration, no on-car qualification is claimed.
