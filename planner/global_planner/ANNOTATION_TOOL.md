# Minimal Project A map-annotation tool (MVP1)

Two pencils, no GIS: open a map, close missing legal boundaries with the
boundary pencil, draw one directed lap with the route pencil, preview the
candidate, approve exactly that candidate, and export a strict Project A
`legal_route.json`. Preview → approve → export is enforced: the operator
always sees the transformed geometry (smoothed seed, lateral correction,
validated route) before approving, and approval binds to the previewed
digest. Any edit clears the candidate and revokes approval.

## Run

```bash
PYTHONPATH=planner/global_planner python3.12 -m global_planner.annotation_server \
  --maps stack_master/maps --out /tmp/annotation_out --port 8766
# open http://127.0.0.1:8766/
```

Headless (same core):
`annotation_tool extract|preview|approve|export --map <yaml> --session <json> --out <dir>`
(`approve` quotes `--candidate <digest>` from `preview`).
ROS: `annotation_node` exposes the same operations as std_msgs/String JSON
on `/planner_annotation/command` → `/planner_annotation/state`, plus a
read-only `state` op for canonical-state recovery after reconnect, with
`maps_dir`/`out_dir` ROS params (fail-fast when unset). Every reply carries
the `request_id` (when given) and the authoritative session `revision`;
a repeated id is acknowledged `DUPLICATE` without re-applying, while a
failed command stays retryable under the same id. Run it only
in an isolated namespace/`ROS_DOMAIN_ID`, never in the driving launch.
Foxglove Bridge can forward those two topics to Lichtblick/Foxglove; no
custom WebSocket transport is built or needed. A live ROS Humble +
Foxglove Bridge roundtrip (open → edit → duplicate/reconnect → save)
passed against this code — see Verified.

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
  at every level = rejected route, reported as such). The preview and
  export receipts report the maximum lateral seed correction in metres,
  so the operator sees how far their line was moved before approving.
- Approval is explicit, digest-bound and preview-gated: preview builds
  the exact candidate (bit-identical receipt to export) without writing
  or approving; approve binds the quoted preview digest to the current
  geometry; export re-validates and writes only the approved candidate.
  Every edit (strokes, route, width, undo) bumps the session revision,
  clears the candidate and revokes approval. The headless CLI enforces
  the same digest binding. A stale approval can never authorize edited
  geometry. Sessions are bound to the full map identity (PNG hash, size,
  resolution, origin, negate), not just the hash. v1 drafts reopen with
  approval revoked. Validation levels are never conflated: CANDIDATE
  (extraction) ≠ VALIDATED (strict input + corridor preparation) ≠
  optimizer PASS ≠ on-car qualification.
- `ridge_seed` offers a deterministic distance-transform centerline seed
  (relaxation confined to free space) as a starting point; strict
  `build_and_validate` remains the acceptance gate for any seed.

## Verified (this branch)

- `test_annotation_core.py`: 26 passed — end-to-end strict PASS on the
  real `test` and `baku` maps (crude and DT-ridge seeds), pixel↔world
  roundtrip, session save/reopen + full map-identity rejection (hash,
  size, resolution, origin, negate), outer-wall bay detour +
  tangent-stroke repair with geometry fidelity, isolated-speck and
  infield-chord rejection, reversed direction, outside-track rejection,
  non-binary rejection, negate:1 equivalence, v1 migration with revoked
  approval, ridge-seed confinement/determinism, spa/zuri annulus
  topology, digest-bound preview→approve→export lifecycle (preview
  read-only, approve binds the previewed digest, export refuses
  unapproved/stale), undo/state semantics, CLI preview/approve/export
  cycle (incl. wrong and missing candidate refusal), ROS retry/ack
  correlation (failed commands stay retryable, successes dedup, every
  reply carries request_id + revision), headless ROS-adapter
  configuration.
- Browser flow (manual): open → draw → extract → preview (green
  candidate + correction shown before any approval) → approve → export
  → save → reload → edit revokes approval → export refused without a
  fresh preview. Previewed and exported outputs are asserted identical
  (route digest + validated geometry) in tests.
- Live ROS Humble + Foxglove Bridge roundtrip (Docker
  `osrf/ros:humble-desktop`, `ros-humble-foxglove-bridge` 3.6.0,
  isolated `ROS_DOMAIN_ID`, repo read-only): open (PASS rev 1) →
  stroke-width update (PASS rev 2) → duplicate retry (DUPLICATE rev 2,
  unchanged) → disconnect/reconnect + resend (DUPLICATE, no lost or
  double edits) → save (PASS rev 2, canonical state). Transcript and
  setup scripts: `/mnt/storage/forza-annot/evidence/ros/` and
  `/mnt/storage/forza-annot/ros/`.
- Full trajectory compilation: pinned environment built
  (`/mnt/storage/forza-annot/venvs/pinned`, CPython 3.10.12,
  numpy 1.26.4 / scipy 1.11.4 / quadprog 0.1.7 /
  trajectory-planning-helpers 0.79 — no pin weakened). The optimizer
  converges to CANDIDATE on annotation geometry (4 solver iterations);
  the s0 fixture compiles to full PASS plus independent
  geometry/dynamics validation PASS and query PASS in the same env.
  Full PASS on an annotation-generated manifest is **blocked in the
  independent checker**: dense annotation walls exceed the geometry
  polygon budgets, while wall compression that fits the budgets trips
  later checker gates (initialization-zone applicability, refinement
  depth). Twelve pinned compile runs characterize the exact gate
  sequence; receipts in
  `/mnt/storage/forza-annot/evidence/numerical/`. Raising budgets/depths
  or the occurrence count changes the acceptance contract and needs an
  owner decision — the tool does not game the checker.

## Map support matrix (fail-closed)

- SUPPORTED (strict validation PASS): `test`, `baku` — crude and
  DT-ridge (`ridge_seed`) seeds validate end-to-end.
- EXTRACTION OK, route needs an operator-drawn seed: `spa`, `zuri` —
  clean annulus extraction, but programmatic seeds are rejected by the
  strict validator (hairpin/S-bend correspondence flips; the chart
  folds). The tool rejects these fail-closed; it does not claim them.
- UNSUPPORTED as shipped (rejected at extraction, correct): non-binary
  occupancy encodings — `hangar_1905_v0`, `GLC_smile_small`
  (anti-aliased wall rims), `glc_ot_ez` (two free-space regions);
  re-export binary maps upstream instead of reinterpreting gray as free.

## Limitations / unsupported (fail-closed)

- Planar single enclosed loop only; splits, bridges, decks, nonzero map
  yaw, non-binary encodings, and multi-region free space are rejected
  as UNSUPPORTED.
- `ament_flake8`/`pep257`/`copyright` harness tests error at collection
  here (ament packages not installed); changed files pass `py_compile`
  and a 99-column scan instead.
- Browser zoom/pan is deferred; the canvas fits the map without it.
  The synthetic vehicle model/policy are software budgets only — no car
  calibration, no on-car qualification is claimed.
- Note the repo inconsistency: the devcontainer installs
  `quadprog~=0.1.11`, which the pin gate rejects; the pin was
  deliberately not weakened — resolving which side is canonical needs an
  owner decision with a pinned-environment build.
