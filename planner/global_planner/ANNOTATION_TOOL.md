# Map annotation tool

Open a map, close or cut legal boundaries with the boundary pencil,
pick the retained track with the bucket when a cut splits free space,
draw (or suggest) a directed guide loop, preview the candidate,
approve exactly that candidate, and export a `global_planner.route`
manifest (`{name, map, start, sections}`). Source maps are never
written. Draft and export filenames are namespaced per source map —
`{parentdir}__{stem}__{bytesha8}__{ctxsha8}_annotation.json` /
`..._legal_route.json` — PNG content hash plus a context hash over the
enforced session identity (resolved directory, resolution, origin,
negate, image size, `free_thresh`), so two maps sharing one PNG stem,
and identical pixels under different YAML interpretations (including
different `free_thresh` values), can never silently share a slot.
`free_thresh` joined the namespace after the scheme was introduced, so
a draft saved by an earlier revision of this unmerged branch keeps the
old filename and is not auto-discovered — the server opens a new
session and leaves the old file untouched. To recover it, rename the
old file to the current draft name (`python3 -c "from
global_planner.annotation_core import TrackMap, draft_name;
print(draft_name(TrackMap('<map>.yaml')))"` with
`PYTHONPATH=planner/global_planner`) and reopen; loading still
validates the full stored identity and fails closed on mismatch.
`--session` CLI users are unaffected (explicit path, no discovery).

Preview → approve → export is enforced on every transport. Approval
binds two digests: the editor-input digest (map identity, strokes,
bucket seed, guide loop, thinning, name/surface/speed, generator
version) and the previewed manifest's `Route.digest`. Any edit clears
the candidate and revokes approval. Export rebuilds, refuses unless
the rebuilt digest equals the approved one, writes atomically, then
reloads the file and checks the digest again. The manifest itself
carries no approval state; that lives in the session draft.

Source identity: an approved route represents the interpreted snapshot
(PNG bytes, size, resolution, origin, negate, `free_thresh`) the
operator previewed; that identity is bound into every approval digest
and checked when a draft is reopened, so a draft can never be rebound
to a differently interpreted map. The editor works on the snapshot
taken at open — the browser displays those exact retained PNG bytes —
and never writes the source files. There are no repeated source-drift
re-reads: a file changed on disk after open is only picked up on reopen.

## Run

```bash
# from the repo root, in an environment with the package's deps
# (numpy, opencv, scipy, shapely, jsonschema, pyyaml)
PYTHONPATH=planner/global_planner python3 -m global_planner.annotation_server \
  --maps stack_master/maps --out /tmp/annotation_out --port 8766
# open http://127.0.0.1:8766/
```

Add `--car stack_master/config/<CAR>/car_model.yaml --car-margin 0.05`
to also run the vehicle portal-zone stages for that car; without it
receipts report the car stages as NOT checked. There is no default car.

Headless (same core):
`annotation_tool extract|preview|approve|export|validate|select-region --map <yaml> --session <json> [--out <dir>] [--car <yaml> --car-margin <m>]`
(`approve` quotes `--candidate <digest>` from `preview`).

ROS: `annotation_node` exposes the same operations as std_msgs/String
JSON on the relative topics `planner_annotation/command` →
`planner_annotation/state`, with `maps_dir`/`out_dir`/`car_model`/
`car_margin_m` ROS params. Every reply carries the `request_id` (when
given) and the session `revision`; a repeated id is acknowledged
`DUPLICATE` without re-applying. Run it only in an isolated namespace
and `ROS_DOMAIN_ID`, never in the driving launch; startup refuses the
ambient graph unless explicitly acknowledged:

```bash
ROS_DOMAIN_ID=169 ros2 run global_planner annotation_node --ros-args \
  -r __ns:=/annot -p maps_dir:=stack_master/maps -p out_dir:=/tmp/annotation_out
# topics: /annot/planner_annotation/command, /annot/planner_annotation/state
```

## How it works

- Source PNG/YAML are read-only. Boundary strokes patch an in-memory
  copy by adding occupied cells only (`negate: 1` supported by
  inversion; `y = origin_y + (H-1-v)·res`, zero-yaw only). Grayscale
  images are binarized at ingestion with ROS occupancy semantics
  (`p = (255 - v) / 255`, inverted for `negate: 1`): a cell counts as
  free only when `p < free_thresh` proves it, so occupied and
  uncertain (gray) cells alike stay occupied and never become road.
  Binary maps reduce to exactly the strict binary reading. Map YAML
  is parsed with PyYAML (`yaml.safe_load`); only image, resolution,
  origin, negate, mode and the thresholds pair are read, extra keys are
  ignored. `mode` must be absent or `trinary`; `raw`/`scale` are
  rejected with a conversion hint.
- Corner cutting: a stroke across a corner splits free space; the
  bucket click selects the one 8-connected component that stays legal
  and the excluded pocket is shaded. Legal free space only ever
  shrinks: `Flegal ⊆ Fpatched ⊆ Foriginal`. Without a selection,
  extraction answers `NEEDS_REGION_SELECTION` — it never silently
  keeps the largest component.
- Extraction = the two loops of the legal region (outer boundary +
  exactly one hole). Any other topology (open gap, split, extra
  island, frame contact) is rejected instead of guessed at.
- The guide pencil is a direction & section-cut hint, not an exported
  centreline: joints are placed at locally straight guide points
  (4 sections), left/right walls are arcs of the extracted loops with
  exact shared end-caps, thinned by deviation-bounded simplification
  whose every chord is exact-ear-checked to annex zero area against
  the legal cell squares (shape deviation vs the dense wall stays
  ≤ ~1.2 raster cells). The
  route package derives each section's centreline from the walls;
  preview draws that derived centreline, the gates and the start zone.
  `Suggest guide loop` fills the pencil (dense-pairing spline, then
  distance-ridge fallback), keeping the first seed that passes every
  check, in the operator's drawn direction.
- The start zone is the middle half of the road over the first 1.2 m
  of section `s0`, following its walls — a starting suggestion, not a
  surveyed grid slot. Name, surface and per-section `max_speed_mps`
  (one value per section; all sections share the session value) are
  editable metadata and approval-bound.

## What a PASS means

Preview/validate/export run, in order, failing closed at the first
bad stage:

1. `vector_legal` — exact continuous containment: the emitted
   section polygons (after thinning and cap re-pinning) must annex
   zero area over the occupied cell squares of the selected legal
   raster (boundary contact allowed; see LEGALITY.md for the full
   contract, evidence and the one policy decision it rests on).
   The generator guarantees this by construction — every
   simplification chord cuts off an ear whose exact occupied area
   is zero — and this stage re-verifies it independently on the
   final coordinates.
2. `manifest` — route `validate_route`: schema, simple CCW ribbons,
   shared caps, forward portals, contact rules, wall-derived
   centrelines inside their sections, and the whole start zone
   within the union of the section polygons (hence, chained with
   stage 1, within the legal cell squares).
3. `lap` / `portals` / `samples` — `centre_curve`,
   `portal_crossings` (exactly one forward crossing per gate),
   `sample_lap` at 0.25 m.
4. `car_zones` (only with `--car`) — `portal_zones` +
   `reach_boundaries` + anchored samples for that car's reach.

Not checked by anything here, and named in every receipt: trajectory
optimization / speed profile and continuous vehicle-body or dynamics
certification. A green preview is a valid route manifest, not a
certified racing trajectory.

`Validate` tries the two supported thinnings (0.02 m, then the
0.03 m envelope edge) through the same checks and locks the first
passing setting into the session.

Sessions are versioned (current: 4). Only current-version drafts
reopen; older drafts are rejected with a clear error rather than
migrated, so an approval can never silently carry across formats.

## Map support (fail-closed)

One planar ring in a zero-yaw occupancy map (binary or grayscale;
grayscale is read conservatively as above; YAML `mode` absent or
`trinary` only). Bridges/split courses, multiple holes and nonzero yaw
are rejected with a reason. The
manifest's `surface` string does not make this a 3D or multi-layer
editor.

## Tests

```bash
PYTHONPATH=planner/global_planner python3 -m pytest \
  planner/global_planner/test/test_annotation_core.py \
  planner/global_planner/test/test_annotation_ui.py \
  planner/global_planner/test/test_annotation_route.py \
  planner/global_planner/test/test_annotation_legality.py -q
```

The deployment suite is deliberately compact: real binary and
grayscale ForzaETH maps loading and validating end to end, exact
zero-annexation legality against an independent oracle (including
Baku corner cuts with bucket selection), canonical start-zone and
manifest contracts, NUC5 car zones, preview -> approval -> export
integrity on the server, CLI and ROS transports, and fail-closed
topology. Exact cross-machine digests are not asserted: the float
pipeline legitimately lands on different last-ulp branches across
CPU/BLAS builds; within one environment it is deterministic, which
is what approval binds. CI: `.github/workflows/annotation-headless.yml`.
