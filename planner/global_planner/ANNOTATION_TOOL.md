# Minimal Project A map-annotation tool (MVP1)

Two pencils, no GIS: open a map, close missing legal boundaries with the
boundary pencil, draw a rough directed lap with the route pencil (or take
the computed centerline suggestion), preview the candidate, approve exactly
that candidate, and export a strict Project A manifest. Draft and export
filenames are namespaced per source map —
`{parentdir}__{stem}__{bytesha8}__{ctxsha8}_annotation.json` /
`{parentdir}__{stem}__{bytesha8}__{ctxsha8}_legal_route.json` — PNG
content hash plus a context hash over the enforced session identity
(resolved directory, resolution, origin, negate, image size), so two
maps sharing one PNG stem, and identical pixels under different YAML
interpretations, can never silently share a slot. A legacy bare-stem
draft is adopted in place on open and written forward on save.
Preview → approve → export is enforced: the operator always sees the
transformed geometry (smoothed seed, lateral correction, validated route)
before approving, and approval binds to the previewed digest. Any edit
clears the candidate and revokes approval.

## Run

```bash
PYTHONPATH=planner/global_planner python3.12 -m global_planner.annotation_server \
  --maps stack_master/maps --out /tmp/annotation_out --port 8766
# open http://127.0.0.1:8766/
```

Headless (same core):
`annotation_tool extract|preview|approve|export --map <yaml> --session <json> --out <dir>`
(`approve` quotes `--candidate <digest>` from `preview`).
ROS: `annotation_node` exposes the same operations plus `suggest` and a
read-only `state` op as std_msgs/String JSON on the relative topics
`planner_annotation/command` → `planner_annotation/state` (no custom
messages), with `maps_dir`/`out_dir` ROS params (fail-fast when unset).
Every reply carries the `request_id` (when given) and the authoritative
session `revision`; a repeated id is acknowledged `DUPLICATE` without
re-applying, while a failed command stays retryable under the same id.
Run it only in an isolated namespace and `ROS_DOMAIN_ID`, never in the
driving launch. Topics are relative so a namespace push moves them:

```bash
ROS_DOMAIN_ID=169 ros2 run global_planner annotation_node --ros-args \
  -r __ns:=/annot -p maps_dir:=stack_master/maps -p out_dir:=/tmp/annotation_out
# topics: /annot/planner_annotation/command, /annot/planner_annotation/state
```

With the default namespace the wire names stay
`/planner_annotation/command` and `/planner_annotation/state`.
Foxglove Bridge can forward those two topics to Lichtblick/Foxglove; no
custom WebSocket transport is built or needed. A live ROS Humble +
Foxglove Bridge roundtrip passed against this code — see Verified.

## How it works (and why not the legacy chain)

- Source PNG/YAML/pbstream and localization assets are read-only; strokes
  patch an in-memory copy (black = occupied, `negate: 1` supported by
  inversion), preserving the legacy flip/resolution/origin convention
  (`y = origin_y + (H-1-v)·res`, zero-yaw only). Non-binary images
  (gray/unknown levels) are rejected instead of being read as free.
- Extraction = the two loops of the free-space region (outer + one hole).
  This replaces skeleton→centerline→watershed for this tool: no guessed
  centerline length, no initial pose, and any non-annulus topology
  (split, extra island) is rejected instead of guessed. Small outer-wall
  damage is accepted as a visible detour (fail-open is impossible here),
  so the operator must compare the candidate overlay with the map.
- The route pencil captures the operator's rough directed loop. `suggest`
  fills it with a computed centerline instead, trying the seed methods in
  a fixed deterministic order (suggest, then ridge) and keeping the first
  seed the strict validator accepts — the operator never names a seed
  algorithm. The reply states which method won. It is a starting point,
  not an approval: the operator inspects it in preview, may redraw it,
  and only an explicit approve authorizes export.
- The directed loop is split into 4 occurrences at locally straight
  points; left/right chains are arcs of the extracted loops, so shared
  end-caps are exact by construction. Walls are thinned with a
  shape-preserving RDP decimation (2 cm, end-caps re-pinned exact):
  raster extraction yields a vertex per pixel, which exhausts the
  independent checker's polygon budgets without adding geometry, while
  uniform coarsening folds the optimizer's charts at bends. Strict
  `validate_route` + `prepare_route` must pass (adaptive seed smoothing
  0–6 passes; failure at every level = rejected route, reported as such).
  The preview and export receipts report the maximum lateral seed
  correction in metres, so the operator sees how far their line was moved
  before approving.
- The initialization zone is a 2.0 m × 1.6 m box at the seed start: a
  1.0 × 0.8 m box demonstrably rejects optimizer start poses (~0.3 m from
  the seed start) that the independent checker otherwise fully accepts,
  while 2.0 × 1.6 m remains a precise start declaration on a ~3 m wide
  track. Input-convention change, not a checker change: the checker still
  verifies the reference starts inside the box.
- Approval is explicit, digest-bound and preview-gated: preview builds the
  exact candidate (bit-identical receipt to export) without writing or
  approving; approve binds the quoted preview digest to the current
  geometry; export re-validates and writes only the approved candidate.
  Every edit (strokes, route, suggest, width, undo) bumps the session
  revision, clears the candidate and revokes approval. The headless CLI
  enforces the same digest binding. A stale approval can never authorize
  edited geometry. Sessions are bound to the full map identity (PNG hash,
  size, resolution, origin, negate), not just the hash. v1 drafts reopen
  with approval revoked. Validation levels are never conflated: CANDIDATE
  (extraction) ≠ VALIDATED (strict input + corridor preparation) ≠
  optimizer PASS ≠ on-car qualification.
- Explicit offline validation (`Validate`, server op and CLI): tries the
  bounded thinning settings (0.02, then the 0.03 envelope edge) with the
  full optimizer and independent checkers, and records the first full
  PASS as the session's `chain_dp_epsilon_m`. The setting is part of the
  approval digest, so preview/approve/export all use the winner and any
  prior approval is revoked. Selection runs the optimizer, so it is an
  explicit operator action, never part of drawing or preview. Rejected
  settings report why they failed.
- `ridge_seed` offers a deterministic distance-transform centerline seed
  (relaxation confined to free space) as an alternative starting point;
  strict `build_and_validate` remains the acceptance gate for any seed.

## Verified (this branch)

- `test_annotation_core.py`: 57 tests, 56 passed + 1 ROS-only skipped
  headless (thinning now binds the approval digest) — end-to-end strict PASS on the real `test` and `baku` maps
  (crude, ridge and suggested seeds), pixel↔world roundtrip, session
  save/reopen + full map-identity rejection, outer-wall bay detour +
  tangent-stroke repair, isolated-speck and infield-chord rejection,
  reversed direction, outside-track rejection, non-binary rejection,
  negate:1 equivalence, v1 migration, ridge-seed confinement/determinism,
  spa/zuri annulus topology, suggestion direction/closure, digest-bound
  preview→approve→export lifecycle, undo/state semantics, CLI
  preview/approve/export cycle, ROS retry/ack correlation incl.
  `suggest`, pipeline defaults (thinned walls, 2.0×1.6 m zone),
  headless ROS-adapter configuration, relative-topic pin. Under
  ROS 2 Humble the 3 headless-only adapter tests skip instead and a
  real namespaced pub/sub roundtrip (`__ns:=/annot`, correlated
  open) runs.
- `test_annotation_ui.py`: 15 tests, 13 passed + 2 pinned-only skipped
  headless — exact-corridor receipt, stale-display clearing,
  remove-selected and rerun-revised flows, aspect-fit cursor mapping,
  digest-bound approve/export, double-click endpoint preservation,
  digest-keyed map refresh, suggest seed fallback + direction guard,
  thinning lock via explicit validation.
- Full trajectory compilation, pinned environment
  (`/mnt/storage/forza-annot/venvs/pinned`, CPython 3.10.12,
  numpy 1.26.4 / scipy 1.11.4 / quadprog 0.1.7 / trajectory-planning-helpers
  0.79 — no pin weakened):
  - **test map** (suggested seed via the repo pipeline, default walls and
    zone): strict PASS (345 samples) → compile PASS (`H=e80c49b6…`,
    deterministic across runs: identical-provenance recompile is
    bit-identical, including in a from-scratch rebuilt env) → independent
    validate PASS (geometry + dynamics) → query PASS. Manifest:
    `repro/manifests/manifest_test_current.json`;
    artifact: `test_current_out/<H>/reference.json` (+ validate/query
    reports beside it). NOTE: the previously documented `H=b06017f7…`
    came from pre-fix geometry (unconstrained RDP, unseparated joints)
    and is superseded; hashes change when the geometry changes, which is
    expected — provenance, not the prefix, is the identity.
  - **baku map** (ordinary flow: `suggest` falls back to the ridge seed,
    `Validate` selects 0.03, preview → approve → export; same zone):
    strict PASS (479 samples) → compile PASS (`H=82f9b533…`,
    deterministic recompile verified) → independent validate PASS →
    query PASS. Manifest: `repro/manifests/manifest_baku_bal003.json`;
    artifact: `baku_bal_003_out/<H>/reference.json`. Baku needs 0.03
    rather than the 0.02 default: its longer track otherwise exceeds the
    independent checker's polygon budgets, and 0.035+ fails optimizer
    convergence. The ordinary export at the locked 0.03 setting is
    canonically identical to the committed manifest. NOTE: the previously
    documented `H=fe61f4f9…` was a strict-only result that never completed
    compilation and is withdrawn.
    Three fixes were required for full PASS: raster-gated RDP (chord
    containment gate), a minimum joint separation (unconstrained
    straight-snapping piled two joints 5 seed-samples apart, leaving a
    sliver occurrence whose coincident portals folded optimizer charts
    at iteration 5), and a gated radial pre-filter (the ungated
    pre-filter silently dropped sub-spacing notches taller than
    epsilon before RDP's deviation bound applied; measured 3x-eps gain
    on a 1-cell-wide x 1.2-cell notch fixture). Geometry contract
    (enforced in code): the pre-filter only removes deviations below
    the envelope's quantization floor (0.6 raster cells: pixel
    staircase peaks at ~0.5 px) with gate-checked chords, then RDP
    bounds the remainder within epsilon, also gated. End-to-end gain
    vs the extracted dense wall is bounded by floor + epsilon
    (<= ~1.2 cells inside the envelope); `build_manifest` rejects
    `chain_dp_epsilon_m / resolution > 0.6`. The method is
    raster-constrained bounded approximation, not strictly inward: a
    narrow sub-epsilon feature IS annexed (e.g. a 2-cell-wide 8 mm
    peninsula at 2 mm raster with eps 0.02: above the 1.2 mm floor,
    so the prefilter reinstates it, then RDP drops it within its
    epsilon bound), which is why the envelope — not the gate
    alone — carries the guarantee.
    The ordinary operator flow selects it automatically (explicit
    `Validate`, bounded to 0.02 then 0.03); a headless equivalent lives in
    the repro scripts. Generation is recorded on system python3.12
    (opencv 5.0): `ridge_seed` follows cv2 distance-transform numerics,
    which differ from opencv 4.8.1 by up to ~2.5 m; the manifest digest
    is the env-independent handoff and compiles bit-identically.
  - The s0 fixture compiles to full PASS plus independent
    geometry/dynamics validation PASS and query PASS in the same env
    (toolchain sanity, unchanged).
- Browser flow, headless Chromium, real UI: open → draw boundary stroke
  (double-click endpoint kept) → extraction auto-refreshes → undo /
  select-remove → suggest (ridge fallback where needed) → preview (exact
  final corridor + centerline, read-only) → explicit Validate (locks the
  passing thinning into the session identity) → re-preview → approve →
  export → save → reload → edit revokes approval → stale export refused.
  Verified on `test` (suggest wins, 0.02) and `baku` (ridge wins,
  Validate locks 0.03; export canonically identical to the committed
  manifest and recompiles to full PASS). Same-name/same-size map
  replacement refreshes the view (no stale image). UI-exported manifests
  compile to full PASS (geometry + dynamics PASS).
- Live ROS Humble + Foxglove Bridge roundtrip (Docker
  `osrf/ros:humble-desktop`, isolated `ROS_DOMAIN_ID`, repo read-only,
  re-run against the current HEAD): open (PASS rev 1) → update (PASS
  rev 2) → duplicate (DUPLICATE, unchanged) → reconnect + resend
  (DUPLICATE) → bad op (FAIL correlated) → same-id retry (PASS) →
  `state` canonical fetch → save. PASS. The node runs namespaced
  (`-r __ns:=/annot`); only `/annot/planner_annotation/command` and
  `/annot/planner_annotation/state` appear on the wire — no absolute
  topics, nothing on the driving graph. Transcript and scripts in
  `/mnt/storage/forza-annot/evidence/ros/` and
  `/mnt/storage/forza-annot/ros/`.

## Map support matrix (fail-closed)

- SUPPORTED, full pipeline to independent validation PASS: `test`
  (suggested seed, defaults), `baku` (ordinary suggest with automatic
  ridge fallback, explicit Validate step locks thinning 0.03; defaults
  reach strict PASS but exceed polygon budgets, 0.035+ fails
  convergence).
- EXTRACTION OK, route needs an operator-drawn seed: `spa`, `zuri` —
  clean annulus extraction, but programmatic seeds are rejected by the
  strict validator (hairpin/S-bend correspondence flips; the chart
  folds). Fail-closed; not claimed.
- UNSUPPORTED as shipped (rejected at extraction, correct): non-binary
  occupancy encodings — `hangar_1905_v0`, `GLC_smile_small`
  (anti-aliased wall rims), `glc_ot_ez` (two free-space regions);
  re-export binary maps upstream instead of reinterpreting gray as free.

## Limitations and owner decisions

- `ament_flake8`/`pep257`/`copyright` harness tests error at collection
  here (ament packages not installed); changed files pass `py_compile`
  and a 99-column scan instead.
- Browser zoom/pan is deferred; the canvas fits the map without it.
- Strictly operator-drawn (non-suggested) seeds on `test` strict-pass but
  do not converge in the optimizer (chart fold at iteration 1 / end-cap
  exit, all seed rotations tried). The suggestion exists for exactly this
  reason; the operator still inspects and approves the result. Strokes
  placed on intact walls can likewise break optimizer convergence while
  strict-passing (fail-closed at the optimizer, reported, not hidden).
- The devcontainer installs `quadprog~=0.1.11`, which the pin gate
  rejects; the pin was deliberately not weakened. Canonical numerical
  environment still needs an owner decision. Meanwhile the exact
  optimizer env is reproducible without touching the devcontainer:
  `/mnt/storage/forza-annot/pinned_setup.sh` +
  `pinned_requirements.txt` rebuild it from scratch (verified:
  from-scratch rebuild compiles the test manifest to a bit-identical
  artifact). Build subtlety recorded in the script: quadprog 0.1.7's
  `setup.py` uses unconstrained `setup_requires`, so an isolated build
  silently cythonizes with Cython 3.x, whose extern-C `qpgen2_`
  declaration does not link against the C++-mangled `solve.QP.c`
  definition (undefined symbol at import); the script pre-installs
  Cython 0.29.37 and builds only quadprog without isolation.
- Raising the independent checker's polygon budgets or refinement depth,
  or changing the model region count, would be acceptance-contract
  changes: not made. The tool fits the budgets by construction instead.
- The synthetic vehicle model/policy are software budgets only — no car
  calibration, no on-car qualification is claimed.
