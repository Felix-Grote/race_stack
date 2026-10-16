# W3 reconnaissance and execution package — A07–A09

Prepared 16 October 2026. This is source-grounded execution preparation, **not W3 implementation or final W2 acceptance**.

## 1. Provenance, concurrency and launch gate

The scouting branch `project-a/w3-scout` starts at frozen W2
`e852641849b2497efea51dfca5ead38ad4476235`. Only this document and
`docs/project_a/W3_HANDOFF.md` are scouting deliverables. Production Python,
production tests, maps, message definitions, lockfiles and gitlinks are unchanged.
Experiments used read-only source mounts and writable scratch under
`/workspace/work/`; no W2 branch checkout, push, rebase, merge or PR edit occurred.

Evidence labels used below:

- **F**: verified source fact at the frozen SHA; source references use that SHA unless stated.
- **R**: recorded W0–W2 evidence, inspected but not rerun as full acceptance here.
- **E**: experiment executed during scouting; its exact scope/runtime/budget is stated.
- **I**: engineering inference, including asymptotic estimates.
- **P**: proposed W3 work; names, schemas and commands below are not installed interfaces today.

Authoritative inputs read: `EXECUTION_PLAN.md`, `STATUS.md`, `RESULTS.md`,
`DECISIONS.md`, `W2_NUMERICS.md`, `RUNBOOK.md`,
`references/GLOBAL_PLANNER_PROJECT_A_ARCHITECTURE.md`,
`references/GLOBAL_PLANNER_PROJECT_A_ROADMAP.md`, and
`planner/global_planner/AGENTS.md`. Actual A01–A06 code/tests and installed
interfaces take precedence over older proposed module boundaries. The user fixes
this scouting base and forbids production changes; the execution plan's old
rebase/continuation wording does not override that instruction.

**Mutable W2 dependency:** a read-only PR #2 snapshot observed reviewer head
`6b778519de74b09a7b66be2ac89e12d687226c9d`, after the frozen base. Its
`W2_INDEPENDENT_ADVERSARIAL_FINDINGS.md` records a real handoff gap: changing
monotone within-occurrence q, then regenerating a profile and hashes, moved an
original seed-local cap while the frozen checkers both returned PASS. Original
q checking rejected the same profile. This did not demonstrate faulty A04 q;
it demonstrated that a self-consistent supplied q is not independently approved
q. The repair adds keyword-only `expected_curve_digest` to both checkers and
`ValidationReport.curve_digest`; missing approval is INCONCLUSIVE, malformed or
mismatched approval FAIL. The expectation must be retained immediately at the
trusted A04 return, before downstream operations. This snapshot explicitly said
final verification was pending. **Do not use its existence as ACCEPT.**

**Full W3 may begin only after an independent adversarial reviewer explicitly
ACCEPTs an exact final W2 SHA with its required full local/installed and exact-head
hosted checks. Create a new W3 implementation branch from that SHA, compare its
API/contracts/tests to this scout, and reconcile every delta before coding.**
Do not implement from this scout commit or the frozen base automatically. The
scout documentation may be copied/cherry-picked as documentation only after that
base is fixed; do not merge a frozen W2 history over the accepted branch.

## 2. Verified prerequisites and acceptance authority

**F/R:** W2 provides numerical candidates, continuous planar geometry acceptance,
and cyclic declared-model dynamics acceptance. A04 convergence alone is not a
certificate. W2's seven fresh source pipelines cover S0 forward/reverse/rotated,
S2 upper/lower and S3 surfaces/notch on the same final coefficients. Committed
`evidence/w2-full` records 296 functional tests at `e3f94dc`, including a fresh
installed pipeline; supplemental literal tests and the frozen PR report 299 at
`e852641`. Those are historical results with exact identities, not a rerun of
current reviewer HEAD. The separate inherited ten lint/XML failure identities
must remain visible; compare identities, not only totals. Read the final W2
review report and updated runner before adopting its final counts.

Before A07 coding, verify:

1. Final accepted W2 commit, review verdict and exact-head CI; all recursive
   submodule pins (optimizer `b1b38ecfefec7200d5bcb243f115af1d795b3766`).
2. `scripts/project_a/setup.sh` and the accepted source's
   `scripts/project_a/verify.sh all work/w3/baseline` pass their functional gates.
   Preserve legacy failure identities and before/after source manifests.
3. Trusted A04 approval capture and both validators' signatures/report identities
   are understood; q ancestry is separately audited through traces, not inferred
   from a hash. Retain any final reviewer lineage and analytic/oracle tests.
4. The exact supported `NumericPolicy`, geometry/dynamics policies, footprints,
   caps and model coverage are fixed independently of received artifact bytes.
5. Packaging uses Python 3.10.12/Humble and the hash-locked numerical environment.
   Python 3.12 `sum` can shift seed anchors by ulps; do not enlarge anchor
   tolerances to support an unvalidated runtime.
6. Installed examples have explicit synthetic approval/provenance. No approved
   physical 240 m course or calibrated car is supplied by archived map presence.

Current policy ledger (F; preserve final accepted values):

| Authority | Defaults / hard distinction |
|---|---|
| A04 solver | spacing .4 m, width .30 m, curvature 1/m, linearization error .1/m, 3–8 iterations, 512 points, 120 s cooperative driver, 1,000,000 chart pairs |
| A04 child fit/QP | fresh process, 20 s wall/20 CPU s/2 GiB address space; numerical imports follow limit setup; condition <=1e12, QP residual <=1e-7, offset <=1e-8 m |
| A05 geometry | 2,048 segments, 2 MiB encoded route, 512 polygon vertices, 2,000,000 polygon-work units; depth24/50,000 leaves; gate depth52/20,000 boxes; exact rational polynomial/polygon predicates |
| A06 producer | sparse squared-speed LP, <=10,000 knots/1,000,000 rows/100,000 iterations; depth20; 10 s cooperative including HiGHS remaining time; residual1e-8, inward margin1e-9 |
| A06 independent checker | 100,000 intervals, depth20, 10,000 knots, 120 s cooperative; normalized residual1e-8; angle1e-10 rad; metadata `1e-7 + 1e-8*abs(expected)` |
| Synthetic integration | rectangle front/rear .10 m, width .12 m, separate margin .01 m; explicit ground/upper-deck models and optional supplied steering, never car calibration |

A05 proves full rectangle/disc sweeps with bounded interval motion against
original owned legal ribbons; unrelated projected XY crossings stay unrelated.
Unsupported holes/union geometry, missing required physical coverage or proof
exhaustion cannot PASS. A06 checks u=v² affine in true arc on every edge,
including closure, both distance-error extremes, endpoint constraints, original
q cap transport and both portal models. Its LP maximizes a distance-weighted
squared-speed surrogate, not minimum lap time. A04's unchanged frozen-derivative
curvature surrogate can worsen actual integrated curvature energy (recorded S0
1.0471975681 -> 1.16278187265 1/m); do not advertise improvement from convergence.


## 3. Exact source/API inventory (F)


Paths abbreviated `GP=planner/global_planner/global_planner`.

| Source | Exact facts useful to A07 |
|---|---|
| `GP/route_input.py:63–66,88–130,133–264` | A01 canonical input encoder, `Occurrence(id,surface_id,seed,left,right,caps)` with caps `(local polyline seed metres,max m/s)`; `Portal(id,source,target,gate,support,before,after)`; `Route(occurrences,portals,encoded)` with SHA256 of immutable encoded bytes and fresh-copy `.payload`; `load_route(path)` rejects duplicate keys/nonfinite constants before `validate_route`. Strict root input schema includes topology, physical-map identity/registration/coverage/provenance, surfaces, original legal chains, gate sequence/finish and initialization. Approval is an annotation assertion, never authenticated physical evidence. Direct record construction bypasses input trust boundary. |
| `GP/route_reference.py:16–38,40–45,191–216,271–285,295–430` | `NumericPolicy(arc_abs=1e-10,station_abs=1e-8,join_abs=1e-8,min_speed=1e-7,quad_limit=100,regularity_depth=24,regularity_budget=10000,max_samples=100000)`. `CubicSegment` stores normalized-t ascending `[x[a0..a3],y[a0..a3]]` float coefficients; derived length/error/speed bound/breaks reconstructed. `Curve(coefficients, owners=None, policy)` is the actual immutable periodic authority with tuple segments/cumulative/owners; it checks position, tangent and curvature joins plus seam. `.coefficients`, `.length`, `.station(segment,t)`, `.wrap(s)`, `.locate(s)`, `.sample(s,occurrence_id=None)`, `.window(s0,s1,step)` exist. `Curve.interpolate` is preparation only and must never be used by artifact loading/export. |
| `GP/route_reference.py:375–421` | Exact endpoint `(last,1)` station is L; `sample(L)` wraps to seam/first owner. Metric ownership is half-open right-hand at coefficient knots; tiny negative modulo that rounds to L returns representable predecessor. Supplied occurrence mismatch rejects. `Sample` returns wrapped s, segment/t, xy,tangent,left_normal,+X CCW heading,signed curvature,occurrence/surface. Query does not infer owner from XY or track history. |
| `GP/route_corridor.py:17–90,93–107,155–200` | `OrderedCurve(route,curve,q)` stores one q per coefficient knot plus terminal q. q is original seed-metric lineage, not actual final station. `.progress(segment,t)` is affine q interpolation; `.station_at_q(q)` transports original cap/portal anchors via coefficients. Occurrence boundaries must remain knots; owner each segment is `(occurrence_id,surface_id)`. `seed_curve`, `resample_ordered` (uniform true metric plus exact semantic events), `refit_ordered` exist for numerical preparation; none is a loader authority. |
| `GP/route_corridor.py:258–309,388–437` | `Corridor` stores original owned signed-normal interval; right/left widths derived with inward epsilon. `normal_interval(ordered,sample,chart_min=.05)` and `PreparedRoute`/`prepare_route` preserve owner/support and TUM right normal. Nearest global XY distances in legacy helper are unsuitable for new exporter. |
| `GP/iqp_route_adapter.py:40–122,350–421` | `SolverPolicy`, `QPResult`, `IterationTrace`, `OptimizationResult`; `optimize(route,policy=SolverPolicy(),numeric_policy=NumericPolicy(),initial=None)`. Result status CANDIDATE is numerical only; failures expose `ordered=None`; final actual shifted TUM coefficient authority retained. Traces hold source q, `(segment,t,q)` lineage, current/shifted coefficients, original corridors, normals, QP identity/residual/condition/runtime/RSS and fit resources. A07 needs final authority + policies/helper/source identity, not all bulky traces inside reference identity. |
| `GP/route_validate.py:287–386,552–636,753–759` | `Footprint(front_m,rear_m,width_m,margin_m)`. Independent `GeometryValidationPolicy` embeds separately expected NumericPolicy, curvature limit, finite resources and optional required physical coverage. `ValidationReport(status,reason,intervals,gates,offending_interval,route_sha256,coefficients_sha256,coverage,assumptions)`. `IntervalCertificate` includes segment, float t0/t1, exact rational endpoint numerator/denominator pairs, owner/portal, curvature/speed/displacement/clearance/margin/error and method. `GateCertificate` carries portal,segment,t bracket,q bracket,direction bound. Preserve reports as evidence; replay checker does not accept stored PASS/leaves as authority. |
| `GP/cyclic_retime.py:43–177,180–193,303–463` | Frozen `SteeringLimits(wheelbase_m,angle_max_rad,rate_max_radps)`, `RegionLimits(speed_min_mps,speed_max_mps,ax_pos_mps2,ax_neg_mps2,ay_mps2,motor_mps2,drag_over_mass,provenance)`, `ModelRegion(occurrence_id,surface_id,limits)`, `DynamicsModel(regions,provenance,steering=None)`. `SpeedKnot(segment,t,u)`, `SpeedProfile(knots,curve_digest,model_digest,lap_time_s)`, `ProfileMetadata(stations_m,velocity_mps,acceleration_mps2,curvature_per_m,time_s,lap_time_s,curve_digest)`, `RetimePolicy`, `RetimeResult`. `retime(ordered,model,spacing_m=.5,policy=RetimePolicy())` returns CANDIDATE with profile + metadata. `curve_digest(ordered)` binds coefficients,owners,q,route SHA,NumericPolicy; `model_digest(model)` binds full `asdict(model)`. |
| `GP/cyclic_retime.py:466–519` | `limits_from_tables(ggv_path,motor_path,*,speed_min_mps,speed_max_mps,braking_mps2,drag_over_mass,provenance)` snapshots each bounded CSV once; provenance contains source SHA/range/conservative interpolation rule. Three-column GGV/two-column motor alone supply neither braking/drag nor car calibration. Reference can independently validate explicit resulting axes; archival table files are reproducibility inputs, not hidden runtime paths. |
| `GP/route_validate_dynamics.py:23–106,166–274,314–334,548–668` | `DynamicsValidationPolicy` independently supplies expected NumericPolicy, residual/angle/metadata tolerances, speed floor, required steering and resources. Independent model coverage must exactly match every original occurrence/surface. Profile starts `(0,0)`, strictly ordered half-open t in [0,1), u>0, every coefficient boundary present. `DynamicEdgeCertificate` has edge,segment,t0/t1,closing,nominal/lower/upper ds,acceleration interval,K,Ks,cap,support owners,residual,steering residual,bound work,time enclosure. `DynamicsValidationReport` has status/reason/edges/worst residuals/offending edge,curve/model identities,nominal/lower/upper/error lap time,coverage/assumptions. Checker rebuilds true local distances, closing acceleration and all metadata; independent from LP rows/applicability helpers. |


## 4. A07 minimal implementation design (P)

### 4.1 One authority, three small modules

Add `global_planner/route_artifact.py` for bounded typed JSON, immutable whole
reference, exact reconstruction, identity and publication. Add
`route_compile.py` for explicit-input orchestration and one console entry point.
Add `route_legacy_export.py` for a pure export view plus lazy ROS message/serializer
adapter. Keep the numerical kernel, solver equations and independent checkers in
their current modules. Do not build a registry, graph, server, plugin backend,
custom binary format or new validation framework. No new third-party dependency
is needed. Existing `route_reference.py` remains the geometry kernel; use a thin
loader re-export there only if the established public import contract requires it.

Proposed public surface (spellings to freeze after final W2 API review):

```python
compile_reference(approved_route, model, footprint, policies) -> CompileResult
load_reference(path, *, expected_H, validation_context) -> Reference
Reference.locate(s_m) -> tuple[int, float]
Reference.sample(s_m, occurrence_id=None) -> ReferenceSample
Reference.window(s0_m, s1_m, step_m) -> tuple[ReferenceSample, ...]
export_waypoints(reference, *, step_m, output_dir) -> ExportResult
```

`CompileResult` has explicit status/reason, H/path only on accepted publication,
geometry/dynamics reports and a separate run report. `Reference` contains only
frozen records/tuples, H and validated authority. `validation_context` selects
supported checker/kernel contract and required coverage independently. A caller
may pin route/model/footprint/policy identities explicitly; an externally trusted
H can instead bind those complete embedded inputs. Do not require redundant
external copies of every model value merely to prove approval. Unknown kernel,
changed required policy or mismatched expectation fails closed and requires
explicit revalidation/regeneration. No default load/query/export skips checks.

### 4.2 Smallest coherent payload

Use one UTF-8 JSON `reference.json` in a new digest directory. Avoid a multi-file
attachment resolver in v1 by embedding bounded source route/model data and the
two structured validation reports. Keep run duration, RSS, command logs, host
paths and timestamps in a separate run report outside immutable identity.

| Payload member | Meaning / reconstruction |
|---|---|
| schema + conventions | version1; units/frame/heading/left-positive offsets; supported compiler/checker/numerical contract versions; explicit synthetic planar coverage |
| approved_route | A01 canonical payload including original left/right legal geometry, occurrence order, portals/support, initialization, caps, physical-map hash/registration and annotation provenance; independently reparse with `validate_route` |
| curve | exact `(N,2,4)` ascending-power coefficients in local t∈[0,1], N ownership pairs, N+1 inherited q values; **no sampled XY or alternate spline** |
| approved_curve_digest | W2 full curve digest frozen immediately at trusted final A04 return, retained through all downstream steps |
| model + footprint | exact supported `DynamicsModel`/regions/steering and provenance; separately named body margin; table byte SHA256/provenance when imported; embed imported table snapshot if future re-import is promised, otherwise normalized conservative model is the declared revalidation authority |
| speed_profile | exact half-open `(segment,t,u)` knots, curve/model digests and declared main lap time; every cubic boundary represented; no interpolated-v authority |
| policies | complete Numeric/Solver/Retime/GeometryValidation/DynamicsValidation policy values and required coverage; v1 strictly supports known combinations |
| implementation identity | accepted W2 source SHA, W3 compiler/checker/kernel contract identity, numerical dependency versions and relevant helper/module content hashes; gitlinks/build image/fixture identity in provenance/run manifest; behavior/kernel changes invalidate old approval |
| validation | complete A05/A06 report records, including interval/gate/edge witnesses, assumptions, coverage and time enclosure; evidence to compare with recomputation, never authorization by stored status |

Envelope: `{schema_version, H, payload}`; H is SHA256 of the documented canonical
payload bytes, excluding H and volatile run metadata. Unsupported schema/unknown
behavioral members are rejected. JSON key order/whitespace on incoming bytes can
be permitted only through the single typed canonicalization contract; the
published file uses canonical **envelope** bytes, while H hashes canonical
**payload** bytes only (never the envelope containing H). Shape, finite value, integer,
boolean, null and text rules are schema-specific. Preserve exact W2 curve/model
identity serialization separately from artifact H.

**F/E serialization trap:** A01 `canonical_bytes` is a *route-input* normalizer,
not a generic artifact writer. It converts integral floats and negative zero to
integers, restricts all text to ID rules, and rejects bool/None. Applying it to
W2 authority fields changes W2's compact `json.dumps` digest (`-0.0`, `1.0` are
not serialized as `0`, `1` there); policies contain booleans and model steering
may be None. Do not reuse `_normalize` on the whole artifact. Preserve captured
float values/encodings including negative zero; do not normalize authority
fields after approval capture. This narrow exception to the old architecture's
generic negative-zero advice must be recorded in DECISIONS. It avoids changing
accepted W2 digest semantics. Route bytes remain A01 canonical route bytes.

Do not persist cumulative arc tables, headings, normals, curvature, speed,
acceleration, station arrays or sampled boundary widths as another authority.
A06 `ProfileMetadata` is reproducible evidence; if stored, regenerate and compare
under independent checker allowances. Gate `(segment,t)` intervals and exact
rational interval endpoints come from validation reports. Build query support
from exact q/route anchors and those checked records, never rounded export views.

### 4.3 Compile, load and publication trust chain

1. Strictly parse independently supplied manifest, explicit model/body/policies;
   validate model coverage and provenance before solve. Use caller paths, never
   map-name defaults or `stack_master` discovery.
2. Run accepted A04; stop unless numerical CANDIDATE with usable ordered curve.
   Immediately freeze full `expected_curve_digest` from that trusted return,
   independently of the profile or serialized candidate. Retain A04 trace audit
   evidence; a digest does not prove historical q inheritance.
3. Independently validate geometry with approved route/body/policy and retained
   expectation; retime that exact ordered object; independently validate profile
   and metadata with model/policy and the same expectation. Require both PASS
   identities equal expectation. Any failure/uncertainty/unsupported required
   coverage returns a report with no accepted output.
4. Encode exact authority and reports into a private same-filesystem stage.
   Strictly decode that staged payload, reconstruct `Curve(coefficients, owners,
   independently expected NumericPolicy)` and `OrderedCurve(route, curve, q)`;
   reconstruct typed speed/model records; rerun both validators on these **loaded
   coefficients**, using the independently retained expectation. Check equality
   of actual authority and policies, not only stored hashes.
5. Compute canonical H; close/flush/fsync all staged accepted files. Publish the
   complete digest directory in one atomic rename under an explicit per-H
   no-overwrite writer lock, checking an existing target is refused. Use a stage
   under the same output parent; fsync stage and parent where durable publication
   is claimed. POSIX rename alone is not a race-safe no-overwrite design. Use
   standard-library POSIX locking in this Linux/Humble deployment; document its
   scope rather than add a filesystem abstraction. Existing digest directories
   are immutable; idempotent discovery may read/verify them but must not replace
   them. Orphan `.tmp-*`/lock paths are never loadable references.
6. Caller receives H/path and PASS reports in a compile receipt. A later loader
   requires expected_H from a trusted caller/published release manifest; a
   freely mutable adjacent receipt or the artifact's internal H alone is not
   independent approval. Verify H *before* treating its embedded approval
   digest/context as trusted. Externally pinned H may authorize the embedded
   A04 approval digest, route/model/body/policies; never take an unverified
   embedded curve digest and call it an independent expectation.
7. Loader verifies version/context/runtime identities and resource bounds,
   reconstructs exact authority and reruns both checkers. Stored PASS is
   insufficient. Query/export operate only on the resulting immutable validated
   reference. Changed checker/kernel policy is explicit stale/unsupported input,
   never silent acceptance under old reports.

Crash contract: at every injected failure, final digest path is absent or is a
complete independently loadable reference; existing content is unchanged.
A crash after rename but before receipt/parent fsync may leave a complete valid
reference with no receipt or uncertain power-loss durability. Do not promise
transactional rollback of already published valid content or hardware-level
persistence beyond the filesystem contract. Failures produce no partial accepted
reference. Unknown-directory loaders require the exact expected H and all checks.

Bound encoded bytes, JSON depth/containers/text and declared counts before
expensive reconstruction. Preserve W2's own route/segment/polygon/model limits;
set and document a finite full-artifact/report cap based on measured maximum
accepted fixtures, since complete proof reports can exceed A01's 2 MiB route cap.
Do not misapply route cap to the whole product or allocate arbitrary reported
N before checking shape/counts. Reject duplicate nested keys, NaN/Inf/overflow,
bool-as-number, wrong integers/owners, truncated input and unknown contract IDs.

### 4.4 Query and speed semantics

`Curve.sample` already supplies true s, segment/t, XY/tangent/left normal,+X/CCW
heading, signed curvature and owner/surface, with right-hand half-open knots and
seam wrapping. Wrap a full reference around it to add H, speed, right-hand cyclic
acceleration, elapsed model time and explicit applicable portal support. q remains
lineage; it is not distance. Locate the profile edge using checked segment/t
ordering; compute the local *metric* arc integral, interpolate u (not v, t or q),
then take sqrt. For fixed edge endpoints use constant right-hand acceleration
`a_i=(u_{i+1}-u_i)/(2*Δs_i)`, including the closing edge. Full moving-edge time is
`2*Δs_i/(sqrt(u_i)+sqrt(u_{i+1}))`; partial time at local distance δs is
`2*δs/(sqrt(u_i)+sqrt(u_query))`, added to prior complete-edge times.
`Reference.locate(s_m)` delegates to the existing geometry locator. Use W2 local arc/error
contracts; never approximate by index×.1. A period-wrapped sample at L is the
right-hand s=0 state; export's terminal duplicate deliberately uses unwrapped
s=L/time=T with seam state. Query remains supplied-progress/stateless, without
nearest-XY occurrence inference.

### 4.5 Proposed installed CLI (not implemented now)

One console script `compile_route = global_planner.route_compile:main` with four
subcommands. This exposes load through validate/query and the public loader,
without a redundant fifth command. All paths explicit; no GUI/node launch.

```text
compile_route compile --manifest PATH --vehicle-config PATH --policy PATH
                      --output DIR --report PATH
compile_route validate --artifact PATH --expected-h HEX --policy PATH --report PATH
compile_route query --artifact PATH --expected-h HEX --policy PATH --s-m FLOAT
                    [--occurrence-id ID]
compile_route export --artifact PATH --expected-h HEX --policy PATH
                     --step-m FLOAT --output DIR --report PATH
```

`--vehicle-config` is a small strict W3 input schema for supported model/body and
provenance only, not an inferred car configuration. `--policy` is the caller's
approved acceptance/runtime context with complete independent validator policies,
required coverage and allowed contract IDs. Compile records the chosen context
identity; reload rejects mismatch. JSON success/error reports use a fixed schema. Compile receipts contain
`status`, `H`, `artifact_path`, full `geometry`/`dynamics` reports and separate run
telemetry; successful overall status is PASS, with both report statuses PASS.
Return nonzero exit for FAIL, INCONCLUSIVE, UNSUPPORTED or RESOURCE_LIMIT. Never emit a
usable artifact path for an unaccepted candidate. Separate statuses faithfully
preserve W2's own result vocabularies; do not rename uncertainty into failure
witnesses or PASS. Artifact parse errors also produce machine-readable reasons.

Install the small selected fixture/model/policy examples with `data_files` under
`share/global_planner/project_a/{fixtures,models,policies}` and use
`ament_index_python.packages.get_package_share_directory` to find examples.
The compiler itself takes the resulting explicit paths; it has no dependency on
package-share lookup. Source/gitlink identity must come from build-time metadata
installed with the contract or an explicit trusted run manifest, never a runtime
`git` lookup in a presumed checkout. Runtime module/helper hashes and dependency
versions are checked against the supported contract; informational source hashes
do not by themselves approve a new checker. Keep ROS imports lazy and only in waypoint serialization.
Do not import `global_planner_node` or `global_planner_utils` into the compiler:
they drag in map/plot/optimizer/ROS assumptions and legacy heading conversion.


## 5. ROS and installed-interface compatibility (F/E)


- `utilities/libraries/f110_msgs/msg/Wpnt.msg:1`: `int32 id`; ten `float64` fields `s_m,d_m,x_m,y_m,d_right,d_left,psi_rad,kappa_radpm,vx_mps,ax_mps2`. `WpntArray.msg:1`: `std_msgs/Header header`, `f110_msgs/Wpnt[] wpnts`. These interfaces contain no q, occurrence, surface, proof hash, model, margin, coverage or phase metadata. Keep authoritative product outside messages; messages are a lossy compatibility projection.
- `f110_msgs/CMakeLists.txt:31` uses `rosidl_generate_interfaces`, including Wpnt and WpntArray, with std_msgs/geometry_msgs; generated interfaces are the installed authority. Preserve `.msg` definitions.
- `planner/global_planner/global_planner/readwrite_global_waypoints.py:13` writes exactly nine required groups to `<map_dir>/global_waypoints.json`: `map_info_str` (`{'data':str}`), `est_lap_time` (Float32 data), `centerline_markers`, `centerline_waypoints`, `global_traj_markers_iqp`, `global_traj_wpnts_iqp`, `global_traj_markers_sp`, `global_traj_wpnts_sp`, `trackbounds_markers`. Remaining objects are ROS ordered dictionaries. Reader at `:69` unconditionally looks up every key and reconstructs ROS messages with `set_message_fields`; there is no artifact digest/version/authority verification. Writer at `:65` opens destination directly and `json.dump`s, so it is not an atomic accepted-artifact publisher. Reuse it only as an export serializer in an unpublished staging directory; atomic rename staged export separately if publication semantics required.
- `global_trajectory_publisher.py:28-51` always creates main WpntArray publisher; shortest-path and centerline publishers are gated by `publish_shortest_path`/`publish_centerline`. Reader call `:72-76` loads all nine groups; only FileNotFoundError is caught. `:85-89` derives track length from final waypoint station. Empty optional arrays/markers roundtrip today (existing ROS test proves this); do not place main profile into unavailable SP/centerline groups. Export map_info must explicitly identify absence; consumers requiring missing groups are UNSUPPORTED.
- `global_planner_utils.py:595-675` `create_wpnts_markers` consumes seven columns `[s,x,y,psi,kappa,v,a]` although docstring says six; it applies `conv_psi = psi+pi/2` to a TUM +Y-axis heading, then wraps only values above pi. It also imports cv2, matplotlib, skimage, optimizer and ROS at module import. W2 `route_reference.py:411-421` returns `heading=atan2(tangent_y,tangent_x)` already in conventional +X axes and signed analytic curvature. New exporter should instantiate Wpnt/MarkerArray directly; applying legacy helper unmodified rotates heading by pi/2.
- `route_reference.py:375-421`: `station(last,1)=L`; `sample(L)` wraps to start and returns `s=0`. Export must explicitly set the terminal duplicate `s_m=L` after sampling seam geometry, preserving start XY/heading/curvature/speed and declaring cyclic edge-acceleration convention. Kernel accepts unique knots without terminal duplicate (`:343-363`); export duplicate must never be fed back as new geometry.
- `state_machine/state_machine/state_machine.py:124-127` and `planner/local_planners/local_planner/local_planner/local_planner.py:131-138` discard final point because it equals first, use final `s_m` as lap length, use final id as max index. `controller/controller/controller_manager.py:372-374` and spline planner `:220-227` also take last `s_m` as L. This makes terminal duplicate mandatory for existing consumers.
- `utilities/libraries/frenet_conversion/frenet_conversion/frenet_converter.py:14,20-31,44-52` hardcodes 0.1 m approximate-index station, reconstructs station by polygon chords, then fits independent CubicSplines. Local planner `:60` also assumes 0.1 m spacing. W2 artifact authority and occurrence support cannot survive arbitrary legacy converter refits/nearest-XY association. Export acceptance is serialization + documented coordinate-field compatibility, not proof that current downstream localization or tracking preserves canonical geometry. Supplying progress/occurrence remains downstream responsibility. A uniform nominal export step 0.1 m with a final short edge still does not make index*.1 exact. Do not silently change true metric station to accommodate this.
- Float32 estimated lap time is rounded for legacy compatibility; preserve authoritative double lap time in artifact, compare exported Float32 to correct Float32 rounding, not arbitrary decimal tolerance.

### Installed package state

- `planner/global_planner/setup.py:10-18` installs `packages=[global_planner]`; share resources are package.xml, launch XML glob, rviz glob and ament index marker only. Top-level pure A01-A06 `.py` modules install; fixtures, synthetic models, vehicle/optimizer config, optimizer submodule and docs are not package resources. `setup.py:27-30` installs only `global_planner`, `mapping_node`, `global_trajectory_publisher` entrypoints. No compile/validate/load/query/export entrypoint exists yet.
- `setup.cfg:1-4` puts scripts under `<prefix>/lib/global_planner`; `ros2 run global_planner <entry>` is the reliable installed invocation, PATH alone need not expose package scripts. `package.xml:11-12` has runtime numpy/scipy but setuptools install_requires only setuptools; package dependencies do not currently describe complete TPH/quadprog closure used by A04.
- `scripts/project_a/Dockerfile` pins Humble/Jammy base digest `860e53793ccf575e5369b5e9a19939de2bfcfb46a299954d06f54f2af54fed19` and locked Python closure in a Python 3.10 system-site-packages venv. `requirements.lock` pins numpy 1.26.4, scipy 1.11.4, trajectory-planning-helpers 0.79, quadprog 0.1.7; do not replace those blindly because A04 checks helper source digests.
- `scripts/project_a/setup.sh` recursively initializes submodules, verifies pins, builds project-a-humble:w0. `verify.sh` requires nonroot, fresh scratch output, checks source before/after, uses only standalone `docker-compose.test.yaml`; 4 GiB, 2 CPU, pids 256, network none, readonly root/source, writable /work, tmpfs /tmp 256 MiB. Never use root hardware compose.
- `scripts/project_a/container_verify.sh:34-48` copies selected packages to /work/src, builds non-symlink colcon install /work/install, wheels pinned optimizer into /work/python; current installed tests run while /src remains mounted.
- `scripts/project_a/tests/test_ros.py:22-61` verifies actual Humble CDR messages, installed module origins, optimizer wheel import, nine-group roundtrip (including an empty SP array), and one straight Frenet roundtrip. These are valuable ROS checks, not geometric/export proofs. `test_w1_installed.py:13` and `test_w2_installed.py:22` still load s0 fixture from /src. W2 test does optimize -> independent geometry -> retime -> independent dynamics, but builds synthetic model inline, emits an unversioned evidence JSON (not immutable artifact) and never reloads it. It does not demonstrate source-free resource access, CLI, immutable persistence, query, or validated export.
- `global_planner_utils.get_data_path:18-22` builds a checkout-relative stack_master path from an installed share prefix; W3 CLI must not call it. `write_centerline:493-496` writes to Path.home()/.ros; new offline flow must not invoke it or rely on map/global defaults.


## 6. A08 legacy comparator, assets and benchmark readiness


Use `GP=planner/global_planner/global_planner`, `OPT=GP/global_racetrajectory_optimization/global_racetrajectory_optimization`. Sources in TPH are installed `/opt/project-a/lib/python3.10/site-packages/trajectory_planning_helpers/` in the pinned image, not speculative upstream master.

| Finding / source | Verified behavior / implication |
|---|---|
| GP/global_planner_node.py:1–24, 41–65, 85–104 | `TkAgg` selected at import; ROS Node constructs publishers and immediately loads a map and plots. `input_path` requires stack_master share. Do not instantiate node for offline comparator. |
| GP/global_planner_utils.py:18–22 | `get_data_path` reconstructs `<share-prefix parents[3]>/src/race_stack/stack_master`, so the legacy utility is explicitly checkout-layout coupled. A07/A08 pure CLI must not reuse this path helper. |
| GP/global_planner_node.py:92–97; all three archived YAMLs | All three YAMLs have resolution/origin/image thresholds but no `initial_pose`; direct map loading raises KeyError absent explicit comparator metadata. Never silently infer pose/orientation as physical data. |
| GP/global_planner_node.py:221,265,284 | `self.map_editor_mode` is referenced but neither assigned nor declared anywhere in this source. This is a proven source-level full-node compatibility defect, not a demonstrated solver defect. Short-circuit with `show_plots=False` happens to avoid accessing it; do not count that as a repaired contract. |
| GP/global_planner_node.py:111–174; utils.py:25–102,105–139,142–286 | Skeleton contours choose shortest closed loop matching approximate length; smoothing; watershed demands exactly two closed bounds, inner/outer by perimeter; fallback distance transform. This is annular-map extraction, unsuitable for manually selected occurrence/surface routes. Preserve original legacy flow; comparator should accept explicit route-derived input instead. |
| GP/global_planner_utils.py:291–398,403–463 | Unsigned minimum XY distances to globally interpolated boundaries; symmetric distance-transform fallback; optional index interpolation. Not owned signed original-corridor widths. |
| GP/global_planner_utils.py:466–526 | `write_centerline` writes `$HOME/.ros/map_centerline[ _2].csv`; GP/node.py:181–185 supplies same fixed path. Avoid calls from scouting/new CLI; scratch comparator writes explicit CSV paths. |
| OPT/helper_funcs_glob/src/import_track.py:25–68 | 3-column width split; 4-column `[x,y,right,left]`; 5-column drops z; optional reverse flips rows without exchanging right/left; optional new start uses global nearest XY. Wrapper sets reverse/start=False, one lap (trajectory_optimizer.py:63–67), so latent reverse defect must not be misreported as active default behavior. |
| OPT/trajectory_optimizer.py:109,133–144,196–238 | Output directory is module-local; raw wrapper is not read-only safe because it creates `outputs/` even before preparation. Calls stock prep. Use a scratch package copy/isolated namespace for full wrapper characterization, never the pinned production checkout or installed read-only package. |
| OPT/helper_funcs_glob/src/prep_track.py:38–51,57–81,89–102 | Calls TPH smoothing then spline calculation; crossing-normal guard commented out; optional min-width inflation. Wrapper min_track_width=None: inflation is latent, not active. |
| TPH/spline_approximation.py:52–81,93–101,121–134,144–146 | Periodic smoothing, approximate chord length at ~0.25m, uniform parameter samples, independent unbounded Nelder–Mead nearest parameters (seeded by initial progress), signed Euclidean width shift, np.interp without monotonicity requirement. `dist_to_p` passes array t to splev -> shape (2,1) -> SciPy euclidean rejects. No observed occurrence jump in newly measured controls; unrestricted closest mapping remains a source-supported risk. |
| TPH/iqp_handler.py:112–123,140–181 | Aliases caller reftrack; unbounded while True; damping; in-place right-=alpha/left+=alpha; interpolates widths with inherited spline index/t; recomputes splines without distance scaling. It does preserve index lineage, but widths are transported rather than reintersected with original legal geometry after normals turn. External comparator watchdog is mandatory. |
| TPH/create_raceline.py:49–75; calc_spline_lengths.py:7,65–75; interp_splines.py:79–89,117–124 | Chord-estimated lengths and linear nominal-distance fraction -> polynomial t, not inverse true arc. Accept resulting exact coefficients as legacy candidate geometry, reconstruct metric station with W2 kernel for validation; do not reinterpret nominal station as true metric. |
| OPT/helper_funcs_glob/src/check_traj.py:49–67; interp_track.py:36–49 | Local interp_track returns Nx4 array, but checker `[0]` truncates to one 4-value row per boundary. Minimal honest harness repair is remove `[0]` **and take `[:, :2]`**, yielding full Nx2 arrays; merely remove `[0]` leaves Nx4 even though downstream only reads XY. |
| OPT/helper_funcs_glob/src/calc_min_bound_dists.py:33–64; check_traj.py:72–137 | Even repaired checker measures unsigned corner-to-sampled-boundary distances, reconstructs own borders, has no ownership/swept/segment coverage, prints warnings only, uses global extrema of speed-dependent acceleration tables. Retain as diagnostic only, never publication authority. |
| OPT/trajectory_optimizer.py:410–431,512–544 | Calls TPH closed velocity solver, appends first speed before closing acceleration, appends terminal trajectory at L. Do not claim legacy universally omits closing edge. Must still independently evaluate final coefficients and cyclic speeds against common explicit model. |
| GP/node.py:200–215,286–287; utils.py:621–632,656–675 | Legacy centerline s=index*.1 and open numerical curvature; helper converts north-zero TPH heading once; published est_lap_time is shortest-path time, not main IQP time. A07 should use canonical +X heading directly, compute own canonical queries/main time, avoid double conversion. `_create_wpnts_markers` correctly calls imported `create_wpnts_markers`; no undefined-name defect there. |

Architecture reference 124 calls for a repaired checker; roadmap A08:183 proposes a submodule commit, but this task expressly preserves gitlinks and asks to avoid needless optimizer changes. Smallest coherent W3 choice: planner-owned **test-only comparator harness** loads authenticated source into isolated namespace/scratch copy, makes precisely logged scalar-objective + checker-array fixes and adds bounds/watchdog. Keep optimizer equations byte-identical, record original failure beside repaired output. A production/submodule patch is not a prerequisite for honest comparison; if later promoted, separate reviewed upstream work.

### Executed bounded legacy measurements (E)

Pinned image: `project-a-humble:w3-scout`, image ID `sha256:67d8c6416a3b65359a0c5228738624493cee251d5dba7443cfff765f4f0949ef`; Python 3.10.12, NumPy 1.26.4, SciPy 1.11.4, TPH 0.79; single-thread BLAS. Each probe ran with `timeout 30s`, 1 CPU, 1 GiB memory, pids limit 128, network none, read-only root and source mounts, tmpfs 128MiB. Both completed exit 0. Raw unmodified preparation failure is an intended measured outcome; no full stock/repaired wrapper optimization was run. Host initially lacked TPH (`ModuleNotFoundError`); initial structural script ran Python3.12.14/NumPy2.3.5, then same results were rerun in pinned image; report pinned results as primary.

Exact executed commands (scripts are scratch, not committed):

```sh
timeout 30s docker run --rm --network none --read-only --cap-drop ALL --user 1000:1000 --pids-limit 128 --memory 1g --cpus 1 --tmpfs /tmp:rw,nosuid,nodev,size=128m --mount type=bind,src=/workspace/work/w3-scout,dst=/workspace/work/w3-scout,readonly --mount type=bind,src=/workspace/race_stack/planner/global_planner/global_planner/global_racetrajectory_optimization,dst=/workspace/race_stack/planner/global_planner/global_planner/global_racetrajectory_optimization,readonly --mount type=bind,src=/workspace/work/legacy-recon,dst=/workspace/work/legacy-recon --entrypoint /opt/project-a/bin/python3 project-a-humble:w3-scout /workspace/work/legacy-recon/probe_check_and_assets_pinned.py > /workspace/work/legacy-recon/probe_stdout_pinned.txt
timeout 30s docker run --rm --network none --read-only --cap-drop ALL --user 1000:1000 --pids-limit 128 --memory 1g --cpus 1 --tmpfs /tmp:rw,nosuid,nodev,size=128m --mount type=bind,src=/workspace/work/legacy-recon,dst=/workspace/work/legacy-recon --entrypoint /opt/project-a/bin/python3 project-a-humble:w3-scout /workspace/work/legacy-recon/probe_tph.py > /workspace/work/legacy-recon/tph_stdout_pinned.txt
```

`probe_check_and_assets_pinned.py` loads the pinned check_traj/interp_track/calc_min_bound_dists modules with importlib, a stub package namespace avoids eager optimizer imports; observes input arrays to actual calc_min_bound_dists; executes unchanged checker once and isolated source string with exactly two `stepsize_approx=1.0)[0] -> stepsize_approx=1.0)[:, :2]` replacements once. Circle fixture N=64, R=6m, widths=.75m, body .535m×.30m, heading is TPH north-zero. Measured stock arrays `(4,)/(4,)`, corner distance range `[.6569294102108685,11.10322278665073]`m; repaired `(43,2)/(33,2)`, range `[.5861648053696025,.6569294102108685]`m. This directly discriminates truncation; neither checker result proves swept legality.

`probe_tph.py`: t=linspace(0,2π,80,endpoint=False), ellipse `(8cos t,5sin t)` and crossing `(8sin t,5sin 2t)`, widths .75m, `s_reg=1,stepsize_prep=.05,stepsize_reg=.4`. Actual unmodified `tph.spline_approximation.spline_approximation` ellipse fails `ValueError: Input vector should be 1-D.` Isolated cloned module namespace repairs only `dist_to_p` to `spatial.distance.euclidean(p, interpolate.splev(float(np.asarray(t).item()),path))`; records unchanged fmin results. Ellipse output (104,4), closest parameters .0010625..1.00107421875, strictly increasing. Crossing output (138,4), -.00003125..1.0, strictly increasing. Both finite; **no occurrence-jump claim**. These exact closest-parameter values differ from historical probes because this mesh/settings differ; record this run independently.

Metric analytic control `coeffs_x=[[0,1,0,0]], coeffs_y=[[0,0,1,0]], spline_lengths=[.5√5+.25asinh(2)],incl_last_point=True,stepsize_approx=.1` gives total true arc `1.4789428575445975`m and max nominal-vs-true intermediate progress error `.1669380946018666`m. This reproduces W0 regression's exact .1m result, not historical .16557464 at a different mesh.

Evidence identities:

| Scratch evidence | SHA256 |
|---|---|
| probe_check_and_assets_pinned.py | a60572860412642436e4088e8bdb77c9da2cd0cb5e4a08e17b8e1734fa6fa7c8 |
| probe_tph.py | 3858e9b3473b74ef92de7f1ea8fdbad72d885ff214d372293b1de8cf2f7524bb |
| probe_results_pinned.json | dabb1498c54d60b3ec790695ef80df978e0f70ffaa5d02023570d266fd72ef99 |
| tph_results_pinned.json | d47206ba48fae03fb01a7eb9356a3ceebd6fce8616fce506f2ae5019aa3fcaa5 |
| pinned check_traj.py | a7f397f1375dc8624b6e651b9fccde7017b7e00446256ee479ef498a2c8c01ed |
| TPH opt_min_curv.py | a2ce75c33498426a5276e5b3455f2059040e8c5e5e54734aee3dde0436bef46d |
| TPH spline_approximation.py | a1e6259858f24ba28493d1f049e88710385d2d218a5cbca1a1d2835904e81d52 |
| TPH iqp_handler.py | b764ff805fd5585a6dfb30e23b1c0b3ef667c91d66129dca78d9b37a356f65ae |
| TPH interp_splines.py | 5d957672e66b9a6e7c1cb40b6e1d50c51327ce0b5be5ceb4d54e6fd5f1c89fba |

### Archived assets: present, parseable, not approved ground truth

Use `git ls-tree -r --name-only HEAD stack_master/maps` or `rg --files --no-ignore` for inventory: default `rg --files` excludes lowercase `glc_ot_ez` due to repository ignore pattern despite files being tracked. All three requested archives are present in frozen commit.

| Asset (under stack_master/maps/) | PNG / grid spacing | stored centerline count / last s | stored IQP count / terminal L | stored SP count / terminal L | global_waypoints.json SHA256 |
|---|---|---|---|---|---|
| GLC_smile_small | 297×573, .05000000074505806m | 293 /29.2m |263 /26.10387919377321m |239 /23.733717789581974m |4eae381ab150838a8679524a411d91eee32f2bbea17660ef50355e11404e9aee |
| glc_ot_ez |288×572, same resolution |257 /25.6m |228 /22.66487739865598m |211 /20.950673406095685m |4b0ee088305a430eaf6b242d1ad941dbbf2aba42d43736532226729350373560 |
| hangar_1905_v0 |429×771, same resolution |621 /62.0m |547 /54.55156200579975m |510 /50.8319361511186m |18c618a4a6b42ed7dbaa8108ae991755287fb2e2e8618ec36223ee0809349d33 |

All have main map PNG/YAML, pbstream, nine-group global_waypoints JSON. GLC/glc additionally PF PNG/YAML, overtaking sectors and speed_scaling YAML; glc has `.bak` JSON of older provenance. Hangar has no pf_map/sector files in frozen tree. All YAML origins/resolution are available; none has `initial_pose`. None supplies an approved legal route manifest, directed occurrences/portals, physical-coverage annotation, calibrated model or clearance evidence. Saved widths/marker boundaries are legacy-derived data, not independently approved legal truth.

All JSON groups exactly `map_info_str,est_lap_time,centerline_markers,centerline_waypoints,global_traj_markers_iqp,global_traj_wpnts_iqp,global_traj_markers_sp,global_traj_wpnts_sp,trackbounds_markers`. All waypoint numeric fields finite and stored widths positive; IQP and SP terminal XY equals first XY at stored L; centerline is unique/open list rather than terminal duplicate. Static format/metadata/closure regression can run immediately. Full certified compile/comparator needs explicit legal annotations/model; archive-derived synthetic annotations may be created and labeled software-only, never called measured physical ground truth.

New arithmetic diagnostics using stored station and linear squared speed (not true-arc physical validation): main IQP times `5.820960136370713,4.089356597567713,9.554434048535391`s; SP times `6.0440909110939005,4.482183184697021,9.668970483427733`s. Each stored `est_lap_time` matches SP, not IQP. Every stored ax equals `(v_next²-v²)/(2Δs)` to binary64 exactness for these arrays; GLC IQP closing edge is **−19.520023423211473m/s²**. This is an explicit strong negative dynamic diagnostic under modest braking budgets; it is not cured by claiming omitted cyclic acceleration or silently smoothing the archive. Current stack config itself gives a constant 12m/s² GGV table, but no physical calibration is established. Do not treat current stack model, pinned optimizer table and W2 synthetic model as interchangeable: test_cyclic_retime.py:223–236 explicitly imports **pinned optimizer** tables, uses conservative motor minimum 5.3m/s², braking=2m/s² and drag/mass=.03; stack_master motor file differs.

### Existing S0–S6 readiness

| Scenario | Frozen implementation evidence | W3 work still required |
|---|---|---|
| S0 | s0_route.json is a synthetic circle, plus reversed/rotated JSON; full fresh A04→A05→A06→independent dynamics pipeline in test_w2_pipeline.py:16–95. test_route_ellipse_dynamics.py:43–77 constructs deterministic affine ellipse axes8/5 from S0 and tests A06 on seed coefficients with independent arc/lateral oracles. W0 direct 64-knot ellipse QP exists. | Freeze/name ellipse benchmark (or reuse documented deterministic construction), run full fresh optimization/artifact/export. Do not relabel circle as ellipse or seed-retime control as full optimized ellipse. |
| S1 | test_route_corridor.py:132–138 changes physical-map coverage/hash with legal ribbon unchanged and demonstrates preparation unchanged. Geometry validator requires_physical_coverage -> INCONCLUSIVE (test_route_validate_geometry.py:183–187). | Package explicit wall-gap/coverage software fixture and assert unchanged legal plan; a physical map parser/obstacle certificate does not exist. Software-only unsupported coverage is an accepted explicit outcome. |
| S2 | s2_upper_route.json/s2_lower_route.json with approved synthetic selected cycles; full W2 integrated pipeline. | A07 same-profile roundtrip/export; benchmark altered branch cap on same geometry and complete-lap retiming, not artificial path equality. |
| S3 | s3_surfaces_route.json and s3_notch_route.json, weaker upper-deck dynamics in full pipeline; independent wrong-deck-at-coincident-XY geometry negative at test_route_validate_geometry.py:375–404. | A07 serialize ownership/q/report proofs; final benchmark query/export, repeated runs and fair same-input legacy contrast. |
| S4 | test_route_corridor.py:271–293 deterministically duplicates S0 occurrences/gates with repeat- IDs. Identical XY/heading visits retain o0 vs repeat-o0 in seed/query/preparation. | Promote frozen manifest or deterministic benchmark generator, full compilation then static supplied-progress/occurrence queries. No runtime ambiguity estimator. |
| S5 | S3 includes ground/upper-deck labels and conservative region models. No frozen ramp/contact/vertical-clearance fixture or grade model. Route input points are XY (route_input.py:69–74). | Explicit planar connector/portal + surface/cap annotated synthetic fixture; record contact/3D clearance UNSUPPORTED. Do not infer ramps from labels. Real ramp acceptance requires missing physical calibration beyond W3. |
| S6 | No archived ~240m course or committed S6 manifest; three archived main trajectories are ~22.7/26.1/54.6m and not approved legal geometry. | Freeze deterministic polygon-valid ~240m synthetic whole-lap fixture before benchmark, keep it software-only, run measured bounded resources. Actual competition-course claim remains unavailable without approved annotations/calibration. See §7 for measured numerical count/time evidence. |

All existing fixture provenance is explicitly synthetic software tests only. A08 should report unsupported/missing-input results where real physical requirements are absent; these do not prevent synthetic A07/A09 capability acceptance.

### Minimal repaired comparator and fair protocol (P)

1. Keep **three clearly labeled rows**: unmodified stock (known prep failure, preserve exception); explicitly repaired legacy preparation + bounded stock-equation driver; new W2 adapter. Add identical prepared-input single-QP parity control (already test_iqp_route_adapter direct helper control) so no apparent gain can be attributed to unequal preparation.
2. Freeze one benchmark run manifest: source/submodule/image/helper hashes; approved legal route bytes/digest, ordered seed, selected occurrences/gates, physical coverage limitations, footprint front/rear/width/margin; curvature bound, numerical tolerances, model speeds/drive/brake/lateral/motor/drag/steering and provenance; predeclared spacing, min/max iterations, deadline, max N, linearization threshold; random seed only if noise case exists. Same settings and final independent authority checks for both sides; never use differing legacy safety_width=.7 vs W2 body width=.12 by accident.
3. Isolate stock wrapper by scratch package copy (`__file__` output root consequently scratch), MPL Agg/headless direct numeric API, explicit CSV and config/model paths. Local namespace scalarizes dist_to_p and repairs checker arrays. Bound `iqp_handler` by a QP-call guard + parent-process timeout/memory; record cap hit as resource failure. Guard is a containment addition, not an optimizer improvement. Leave min_width=None. Never modify global installed TPH or pinned submodule. Record exact source transformations/hashes per run.
4. Separate **pipeline fidelity** from **fair geometric comparison**: full repaired stock preparation intentionally remains legacy smoothing/width transport (report its mismatch and independently reject illegal output); matched-equation row receives same owned original-corridor preparation. Do not replace all preprocessing and continue to call it original legacy. For legacy shifted/smoothed candidates, inherited parameter lineage must be explicitly transported into W2 OrderedCurve and validated against gates/original route; if correspondence is nonmonotone/outside supported owner interval, reject/UNSUPPORTED, never nearest-XY recover.
5. Capture actual final spline coefficients before wrapper discards them (trajectory_optimizer.py:372–377 local coeffs_x_opt/y_opt; return at end exposes sampled trajectory/bounds/time only). Use scratch wrapper instrumentation/hook to return/capture these locals or a bounded numerical harness reproducing unchanged calls. Do **not** fit a second spline through saved samples and claim independent validation of original legacy candidate. Capture provenance of lineage. Saved archive arrays alone cannot meet canonical-coefficient acceptance.
6. Retiming comparison must not credit dynamics changes to geometric optimizer. Run common W2 retimer on each independently legal final geometric candidate using identical model/caps; retain original legacy speed output as separate diagnostic row with metric consistency limitations. For full legacy speed feasibility comparison, translate its speed anchors to exact candidate segment/t using captured indices/t, recompute true arc, evaluate independently and label semantics change explicitly; if no valid continuous profile is recoverable, report unsupported instead of fabricating.
7. Measure separate prepare/corridor, spline, each QP, full solve, geometry, retime, dynamics, serialization/query/export walls and peak RSS; total process timeout includes compilation/validation; preserve first failure, retries and all verdicts, iteration/N/residuals. Benchmark same meshes twice on pinned single-thread environment; no successful-only averages, no invented improvement threshold or 120s deadline promise.
8. Independent controls: analytic metric curve, checker full-array shape test, known illegal between-node sweep, wrong coincident deck, seam acceleration mutation and stale model/certificate mutation; producer-generated outputs cannot be their own expected oracle. Geometry/dynamics validators are common required authority, stock checker warnings never count PASS.

### Comparator failure discrimination (P)

- **Proven blocker to unmodified full legacy prep:** pinned SciPy shape exception reproduced. Test stock failure exact type/message; repaired scalar objective is opt-in and source-authenticated.
- **Proven legacy checker defect:** measured row truncation. Spy full `(N,2)` boundary arrays with N>2 at multiple circle positions; an illegal outside path still must fail independent signed/swept validator regardless of stock warnings.
- **Proven blocker to direct installed-node archive run:** no initial_pose and checkout-dependent paths; map_editor_mode source contract absent. Keep CLI/headless harness pure with explicit metadata; regression must run outside checkout. No need repair runtime node for A08 numeric comparison.
- **Proven data gap for real-course claims:** no approved legal/physical/calibrated archive manifests or genuine 240m course. Freeze explicit synthetic annotations, mark real-course unsupported; physical metadata must not be invented.
- **Plausible fairness failure:** unequal prep, vehicle margins, sampling or common retimer semantics. Hash run-manifest inputs; assert exact equal setup and include matched single-QP result at tolerance1e-8m; pipeline changes separately labeled.
- **Plausible false validation:** reconstructing legacy spline from sampled output or nearest XY for owners. Capture original coefficients/index-t lineage; poison sample rows while coefficients fixed and verify independent verdict follows coefficients; missing correspondence -> unsupported.
- **Nonblocking limitation:** repaired legacy checker remains warning-only/unsigned/sampled; absent physical evidence/3D does not block synthetic software handoff. Never reinterpret those diagnostics as independent final PASS.

## 7. S6 feasibility and measured resource evidence


All production reads were at `e852641849b2497efea51dfca5ead38ad4476235`, read-only source mount `/workspace/work/w3-scout`. No optimizer/submodule/source/test changes. Scratch only `/workspace/work/scaling`.

- `planner/global_planner/global_planner/iqp_route_adapter.py::SolverPolicy`, `optimize`, `_run_child`, `_worker`: default .4 m / max512, 120s cooperative driver; dense fit/QP fresh children with20s wall/20CPU s/2GiB AS; child forces one BLAS thread. Original seed-segment sum>512 rejects before `seed_curve`; current length>spacing*512 rejects before metric resampling; `ceil(length/spacing)+len(occurrences)+sum(caps)+2*len(portals)>512` conservatively rejects even if some anchors duplicate. The length and semantic-count guards repeat each iteration; the initial seed-count guard runs once. Therefore any actual current curve >204.8m is guaranteed rejected with default policy; no additional RAM can remove this software guard.
- `route_corridor.py::resample_ordered`: `count=ceil(L/spacing)` uniformly metric stations plus exact source-q occurrence/cap/portal-support anchors; metric samples numerically indistinguishable from anchors omitted. q is lineage, not metric distance. Actual N depends on anchors; no global fixed `L/spacing` exact count. Curve NumericPolicy max_samples100000 independent of solver512.
- Installed unchanged TPH0.79 `calc_splines.py`: dense `(4N,4N)` matrix, two `np.linalg.solve` calls. `opt_min_curv.py`: explicit `np.linalg.inv(A)`, dense products and `(N,N)` Hessians, constraints4N-by-N, `quadprog.solve_qp`. Adapter also computes dense2-norm condition with `np.linalg.cond(matrix)` (SVD) each QP. Storage grows O(N²); dense factorizations/inverse/SVD and dense products O(N³). Native active-set QP timing depends on actual geometry/constraints.
- `iqp_route_adapter.py::_geometry`: portal checks, n original-owned normal intersections, then same-occurrence normal-chart pair checks O(sum(n_owner²)), budget1,000,000; each iteration does this for reference AND shifted fit. Original-border polygon complexity matters independently of solver N.
- `route_validate.py::validate_geometry`: separate exact-rational preprocessing/simple-polygon/stitched-union checks, gate isolation, coefficient/semantic interval splitting, Bernstein and swept rectangle/disc certificate; max2048 coefficient segments,512 polygon vertices,2M polygon work,50k intervals/depth24. GeometryValidationPolicy has no wall deadline; bound it externally in A08. Number of leaves, original polygon complexity, geometric slack and rational bit cost matter; no inference from QP timing alone.
- `cyclic_retime.py::retime`: rebuild route/curve, coefficient boundaries retained in profile in addition to metric/semantic samples, exact curvature bounds, sparse COO→CSR HiGHS LP; default10s cooperative deadline/10k knots/1M rows. `route_validate_dynamics.py::validate_dynamics`: separately rebuilds authority and performs exact-rational whole-edge checks and metadata recomputation;120s cooperative deadline/100k bound intervals/10k knots. Both have2048 coefficient-segment preflight cap. A hypothetical .1m optimization mesh on240m exceeds2048 even if A04 max512 were separately raised; a .1m query/export view of a coarser curve adds no coefficients.

### Counts, storage and inference (F/E/I)

For exactly240m, uniform counts600/1200/2400 at.4/.2/.1m. Add conservative supplied-event upper bound E in adapter preflight (duplicates do not save the conservative check). Four-occurrence S0-derived control: E=4+4+8=16, upper count616/1216/2416; actual low-level resampling measured608/1208/2408, because occurrence/cap duplicates and uniform coincidences reduce unique anchors. All exceed512. At.5m uniform480,E16,actual488; this shows mesh count room for this synthetic event set ONLY. No .5m optimize was run and no changed policy is accepted. Required spacing to clear just count+E is at least240/(512-E), .4838709677m forE16 (strict guard and rounding still apply).

One float64 spline matrix alone is `8*(4N)^2=128*N²` bytes, excluding copies/inverse/SVD workspace/QP arrays/serialized requests/Python:

| N (no anchors) | one matrix bytes | MiB | dense-cubic work ratio vs512 (arithmetic estimate, not measured runtime) |
|---:|---:|---:|---:|
|600|46,080,000|43.9453125|1.6093|
|1200|184,320,000|175.78125|12.8746|
|2400|737,280,000|703.125|102.9968|

At2400 a few such arrays plausibly exceed2GiB; no2400 solve was attempted. Current measured512 run uses310MB RSS, far below2GiB. More memory is not justified as the first change; no observed memory failure here. Sparse spline solves/implicit derivatives could remove dense costs, but would be a future equation-parity-reviewed numerical change, not an A07 convenience refactor. First obtain representative legal S6 geometry, freeze events/polygons/seed density, profile end-to-end phases under unchanged accepted policy, and report limit failure. If a separately declared coarser solver policy is authorized in implementation, validate its exact retained coefficients continuously and query/export them finely without refit. A08 may truthfully report RESOURCE_LIMIT; it must not claim successful240m optimization from these microbenchmarks.

### Executed environment and boundaries (E)

Image `project-a-humble:w3-scout`, built with frozen `scripts/project_a/Dockerfile`, image ID `sha256:67d8c6416a3b65359a0c5228738624493cee251d5dba7443cfff765f4f0949ef`; pinned Python3.10.12/NumPy1.26.4/SciPy1.11.4/quadprog0.1.7/TPH0.79. Every run: nonroot1000:1000, network none, read-only root/source, capabilities dropped, no-new-privileges, pids128,3GiB container RAM,2CPU quota,/tmp128MiB. Adapter child limits unchanged20s/20CPU s/2GiB/1BLAS thread. Outer hard command bounds50s micro/kernel,180s per phase,40s unscaled seed control; kill-after5s. Micro and kernel measurements could overlap other agents' installed-package probes; single-run descriptive measurements, no controlled speedup claim. Phase measurements started after the ROS agent confirmed its CPU-heavy work ended. Docker VFS startup/removal overhead is outside printed phase/child times. All completed commands exit0; explicit failure statuses below remain failures despite shell success.

#### Measured actual bounded kernels

Uniform circle input with nominal circumference 240 m (radius 38.197186342 m), no original legal geometry/retiming/continuous validation. These exercise installed pinned helpers through real adapter child limits, not full S6 planning; inherited q uniform gives condition45.040943, unlike difficult nonuniform semantic-anchor real inputs. Each row one observation.

| N | fit child s | fit peak RSS bytes | QP child s including condition/helper | QP peak RSS bytes | QP outer call s |
|---:|---:|---:|---:|---:|---:|
|64|.013155|72,634,368|.037101|76,054,528|.283152|
|128|.022099|76,460,032|.112001|89,223,168|.359205|
|256|.075087|86,695,936|.570697|134,836,224|.809327|
|384|.183760|101,445,632|1.649157|209,125,376|1.884406|
|512|.366835|119,513,088|4.082528|309,829,632|4.358682|

All QPs pass adapter residual/condition checks; max measured primal violation7.883e-14. No micro attempts above512, no policy limits raised, no timeout/OOM.

A separate scratch wrapper times unchanged installed helper calls atN512 under the same20CPU s/2GiB limits. Fit .348610s (dense solves .175756+.168068s); QP+condition4.282319s: condition SVD2.107874s, inverse.703935s, native quadprog.803143s; remaining.667368s is other helper preparation/products/diagnostics. RSS214,888,448bytes. This direct-helper split does not include adapter IPC/copying and is not interchangeable with adapter RSS. Dense preparation/condition cost is material, so calling everything “QP solve time” obscures the bottleneck.

#### Measured complete phase records

Base fixture canonical route digest `29212981a9b9247829967846f3883d32494eb3decfbc0765e623e3f1cc061648`.

S0: load .035934s; seed.184436s/128segments/L37.69911153890856m; actual default optimization4.162534s/CANDIDATE/3iterations, final98segments/L34.3689501974305m; final-curve resample.4m .179473s/N96; original corridor.047118s; independent geometry6.891507s/PASS/224leaves/4gates; retime.567927s/CANDIDATE/166edges; independent dynamics.509763s/PASS/166edges,166boundintervals. Parent peakRSS79,732,736bytes, childRSS separately above. Synthetic model is explicitly (.05,4,2,3,4,2.5,.02) perRegionLimits; no steering supplied in this performance probe. Geometry footprint front/rear .10m,width.12m,margin.01m unchanged synthetic W2 integration body. This run shows independent geometry can cost more than optimization on a small fixture.

240m surrogate: uniformly scale every coordinate in S0 and every cap/portal/init metric by240/base seed-curve length; preserve selected topology/labels, label synthetic only. This is NOT archived map data or approved S6 geometry. Canonical derived route digest `6040dc1a3a2c655ab839b7964fd8b96066802e50bc5440c287bdf41da577e1cd`,20389bytes. Load+transform.249906s; seed.181428s/128segments/L239.99999999999997m. Actual default `optimize` .189575s → RESOURCE_LIMIT, reason **point budget exhausted before remeshing**,0traces/no candidate. Low-level read-only resamples: .4m→608points/1.735984s; .2→1208/3.433902s; .1→2408/7.261764s; .5→488/1.322650s. These do not run A04 solver.

The unoptimized scaled seed is checked separately only to characterize phase work: original corridor.061480s; independent geometry.491797s → **FAIL, missing or multiple independent directed gate passages: p1**,0leaves/0gates. It is NOT an accepted feasible240m fixture; this failure cannot establish a certificate timing or a W2 accepted-input scaling defect. Retiming of that same unaccepted seed3.577941s/CANDIDATE/584edges, independent dynamics2.590694s/PASS/584edges/584boundintervals. Dynamics PASS cannot override geometry FAIL. Parent peakRSS86,495,232bytes. No full240m optimized/certified lap was produced. Discriminating unscaled-seed control (same S0 seed_curve, before IQP) also FAILs independent geometry: **missing or multiple independent directed gate passages: p2**, .537444s, L37.69911153890856m, shell exit0. Thus scaled-seed gate rejection is not evidence that scaling created a new accepted-input defect; the producer returns an unaccepted seed in both cases.


## 8. Dependency graph, files and checkpoint sequence (P)

```text
final independently ACCEPTed W2 SHA + green exact-head evidence
  -> delta audit + baseline reproduction
  -> A07a strict input codec + immutable Reference + metric speed query
  -> A07b compile / trusted C capture / dual independent validation
  -> A07c staged reload/revalidation + canonical H + atomic no-overwrite publication
  -> A07d fail-closed installed CLI + lazy nine-group ROS export + package resources
  -> A07 adversarial/installed gate
  -> A08 matched equations + stock characterization + explicit repaired comparator
  -> A08 frozen S0–S6 fixtures/readiness + bounded resource campaign + repeat runs
  -> A09 source-free fresh install/runbook/evidence/compatibility handoff
  -> independent W3 review, exact-head CI, reviewable PR (no automatic merge)
```

Read-only legacy fixture characterization and S6 resource probes may be prepared
alongside A07. Final artifact comparisons require A07; A09 requires the actual
A07/A08 results. Keep commits checkpoint-sized and update STATUS/RESULTS/DECISIONS
only on the implementation branch, after each completed checkpoint.

| Change | Minimal scope |
|---|---|
| `planner/global_planner/global_planner/route_artifact.py` | typed model/body/policy input parser, artifact codec, frozen full reference, loader/query, identity and publisher; split a helper only if measured complexity requires it |
| `.../route_compile.py` | explicit compile/validate/query/export orchestration and machine-readable CLI; no numerical acceptance logic copied from checkers |
| `.../route_legacy_export.py` | original-owned distances, field projection, lazy generated ROS messages, staged existing JSON writer; no node |
| `planner/global_planner/setup.py`, `package.xml` | one added console entry and selected share fixture/model/policy data; only demonstrated dependency declarations; preserve legacy entries |
| `planner/global_planner/test/test_route_artifact.py`, `test_route_compile.py`, `test_route_legacy_export.py` | A07 strictness/trust/atomicity/query/export tests |
| `planner/global_planner/test/benchmark_project_a.py`, `test_project_a_regression.py`, frozen benchmark manifests/fixtures | A08 reproducible harness with explicit repairs and full failure/resource history; no pinned submodule edits needed |
| `planner/global_planner/test/test_project_a_handoff.py`, `scripts/project_a/tests/test_w3_installed.py` | A09 separate-process and source-inaccessible installed acceptance |
| `scripts/project_a/container_verify.sh`, `verify.sh`, source manifests/CI as needed | explicitly run new suites and second runtime container; retain W0–W2 tests and legacy failure reporting |
| `planner/global_planner/PROJECT_A_GUIDE.md`, `docs/validation/GLOBAL_PLANNER_PROJECT_A_RESULTS.md`, control docs | exact executed handoff commands, evidence/limits; reconcile RESULTS rather than duplicate inconsistent result authorities |

Do not edit production optimizer, message definitions, original maps, car/controller,
localization, perception or hardware launch. The existing root hardware Compose
is forbidden. A08 uses a clearly declared scratch/test-local repair. If a later
change truly needs a submodule edit, it is a separate authenticated fork commit
and reviewed gitlink change, never a dirty vendor directory; it is not needed
for the proposed baseline strategy.

## 9. Required acceptance tests and objective failure discrimination (P)

All current W0–W2 checks, exact tolerances, fixtures and final reviewer regressions
remain mandatory. Add meaningful public-boundary tests; avoid testing only a
producer against its own serialized expected arrays.

| Test/fixture | Objective acceptance |
|---|---|
| Exact reload | binary64 coefficient/q/profile/model/policy values preserved (including signed zero where valid); W2 C/model digests unchanged; no interpolate/refit during load/query/export (replace those functions with raising sentinels) |
| Independent approval attack | replay W2 coordinated monotone-q/cap/profile/selfhash alteration; original external H/C must reject even after every internal hash/report is regenerated; missing expected approval never yields accepted handle |
| Identity mutations | separate coefficient, owner, route cap/topology, model axis/table hash, footprint/margin, policy/tolerance, checker/kernel identity changes produce different H and reject old approval; valid same-data re-encode deterministically reproduces H |
| Malformed/oversized input | nested duplicate keys, invalid UTF-8, NaN/Inf/1e999, bool-as-real, fractional segment ID, truncated bytes, unknown/missing fields/version, excessive depth/bytes/counts, wrong owner, q order, missing profile coefficient boundary, u<=0 and model coverage are rejected before unsafe work |
| Corrupted/stale evidence | stored PASS/clearance/lap-time/profile metadata cannot authorize acceptance; direct validator replay recomputes certificates; changed kernel/model/policy contract cannot silently load old proof |
| Atomicity | inject write/serialize/close/fsync/validation/rename/parent-fsync errors and writer termination; concurrent same-H writers, occupied/symlink target and cross-filesystem stage; final absent or complete valid content, old target never replaced, temps never accepted |
| Metric dynamic query | independent polynomial derivative + 96-point/split high-precision arc oracle, constant-speed and linear-u analytic time/acceleration; nonuniform profile edge and closing edge; no interpolation in q/t/v |
| Boundaries | exact and nextafter on both sides of every cubic/profile/owner/cap/portal event, s<0,s=L,s>L, shuffled stateless queries, excessive/nonfinite progress and wrong supplied occurrence; correct right-hand values and two-model portal support |
| ROS field oracle | known +X/+Y headings, reversed/swapped sides, rotated origin, asymmetric ribbon/notch, S3 coincident XY with different owners; true s, correct signed kappa, d_m=0, original-owned side distances |
| ROS compatibility | generated Wpnt/WpntArray actual CDR, existing nine-group reader, sequential IDs and terminal duplicate s=L, first outgoing seam ax, Float32 main time conversion; explicit empty centerline/SP without invented trajectories |
| Installed package | all authoritative module origins and resources under clean prefix; separate source-free runtime, no source on PYTHONPATH/filesystem; installed CLI compile, new-process validate/load/query/export; no hidden map/HOME/.ros writes |
| Comparator fairness | same fixed preparation matched-equation test, original stock failure retained, exact explicit repair source/hash, same legal geometry/body/model/margins/budgets/final independent evaluator; no QP-only legal claim |
| Resource/benchmark | all failed/retried cases recorded; expected default 240 m rejection; each alternative policy declared *before* measurement; per-phase wall/CPU/RSS/size/residual/counts; repeat exact accepted inputs twice without hiding unsuccessful runs |

Use the existing circle/ellipse/true-arc, Decimal coefficient-bound and motor/drag
oracles. The checkers share the W1 arc kernel and A05 bound primitives: their
separate code paths do not establish complete statistical independence. Retain
reviewer shared-kernel fault-injection controls and independently derived analytic
or high-precision checks. Sampling controls detect defects but never replace
continuous swept certification. A fixture generator must independently pass
polygon/topology/owner validity before its failure is attributed to the optimizer.

Risk classification:

| Finding | Class | Safe decision / discriminating test |
|---|---|---|
| Final W2 API/authority still under review | **Proven launch blocker** | wait for explicit exact-SHA ACCEPT; audit final delta and replay inherited handoff attack |
| 240 m at .4 m exceeds default max512 | **Proven default-resource blocker** | retain explicit RESOURCE_LIMIT; test coarser declared mesh or separately justified resource change, never remove preflight silently |
| A01 encoder changes authority representation; no full artifact/query/model JSON/installed examples | **Proven W3 implementation prerequisites**, not B-backend failure | typed schema and exact digest tests; source-free installed test |
| Legacy angle/width/time/checker/metadata assumptions differ | **Proven compatibility hazards** | explicit exporter mapping and repaired comparator fixtures; no full legacy node as a fair default baseline |
| Second curve authority / self-approved model-policy-proof / partial publication | **Plausible high-impact implementation risks** | loaded-byte dual revalidation, external H trust and failure injection as above |
| Dense and polygon/certification scaling beyond measured inputs | **Plausible scaling risks** | bounded full-lap phase campaign; do not extrapolate microbenchmark success to S6 |
| Legacy consumers refit geometry or assume .1 m index; messages omit ownership | **Nonblocking documented compatibility limit** for offline handoff | distinguish JSON/CDR compatibility from canonical downstream runtime support; require downstream supplied progress/owner |
| Missing approved course/physical car/3D/contact/localization/tracking | **Nonblocking unsupported physical claims** | hand off synthetic software; explicitly report unavailable real-course result rather than fabricate evidence |
| Excess abstraction/dependencies | **Plausible delivery risk** | three small modules, standard JSON/dataclasses/pathlib/hashlib, existing SciPy/ROS only; no registry/server/framework |


## 10. A09 reproducible handoff and fresh installed test (P)

The implementation task first branches from final accepted W2, implements A07/A08,
and then tests its own exact W3 candidate SHA in a **fresh recursive clone**.
Checking out final W2 alone cannot run proposed W3 commands. The final guide
must replace all example placeholders with executed W3 values and record all
failed attempts. A fresh developer must need only git/submodule access, the safe
pinned build environment and installed synthetic inputs; no private Drive source,
GUI, workstation directory, map defaults or original source path is required.

```bash
# At implementation dispatch: set this to the independently ACCEPTed exact W2 SHA.
git clone --recurse-submodules https://github.com/Felix-Grote/race_stack.git race_stack
cd race_stack
git checkout "$FINAL_ACCEPTED_W2_SHA"
git submodule update --init --recursive
git switch -c project-a/w3-implementation
scripts/project_a/setup.sh
scripts/project_a/verify.sh all work/w3/baseline
# Implement and commit A07–A09; then repeat acceptance from exact W3 candidate SHA
# in a second fresh recursive clone, never merely from the development worktree.
```

Current dependencies are digest-pinned ROS Humble/Jammy/Python3.10.12 and
hash-locked build/numerical wheels: NumPy1.26.4, SciPy1.11.4, TPH0.79,
quadprog0.1.7 (source-built against pinned Cython), matplotlib3.7.5, pytest8.3.5,
plus inherited legacy import closure in `requirements.in`/lockfiles (CasADi,
scikit-learn, OpenCV-headless, scikit-image, PyYAML). `package.xml` NumPy/SciPy
alone is insufficient to reproduce A04. Do not install the optimizer's loose
`requirements.txt`. The pure W3 path does not need to import its wrapper; the
existing installed legacy regression may still use the pinned optimizer wheel.
Generated f110_msgs/rclpy/rosidl_runtime_py/std_msgs/visualization_msgs and ament
index come from the selected Humble build/runtime.

Use the existing non-symlink colcon build of f110_msgs, frenet_conversion and
global_planner in a build-only container, preserving source read-only. A second
network-none runtime container mounts **only** install prefix, required installed
wheel target, a copied runtime test script and new output directory. Do not mount
`/src`, `/work/src`, build trees or optimizer sources. Prove their absence.
Set import paths to installed prefixes only and assert every authoritative module
origin. Run from a directory unrelated to checkout. Selected installed resources
are obtained through ament; the compiler receives their explicit absolute paths.

Planned commands inside that source-free container, after sourcing Humble and
`/work/install/setup.bash` (CLI is proposed, not executable on frozen W2):

```bash
set -euo pipefail
mkdir -p /work/runtime
cd /work/runtime
W3_SHARE=$(python -c 'from ament_index_python.packages import get_package_share_directory; print(get_package_share_directory("global_planner"))')
W3_POLICY="$W3_SHARE/project_a/policies/synthetic_planar.json"
ros2 run global_planner compile_route compile \
  --manifest "$W3_SHARE/project_a/fixtures/s0_route.json" \
  --vehicle-config "$W3_SHARE/project_a/models/synthetic_planar.json" \
  --policy "$W3_POLICY" --output /work/runtime/routes \
  --report /work/runtime/compile.json
python - <<'PY_RECEIPT' > /work/runtime/trusted-receipt.txt
import json, re
from pathlib import Path
r = json.loads(Path('/work/runtime/compile.json').read_text())
assert r['status'] == r['geometry']['status'] == r['dynamics']['status'] == 'PASS'
assert type(r['H']) is str and re.fullmatch('[0-9a-f]{64}', r['H'])
p = Path(r['artifact_path']).resolve(strict=True)
assert p.is_file() and p.is_relative_to(Path('/work/runtime/routes').resolve())
assert p.name == 'reference.json' and p.parent.name == r['H']
print(p)
print(r['H'])
PY_RECEIPT
readarray -t W3_RECEIPT < /work/runtime/trusted-receipt.txt
W3_ARTIFACT=${W3_RECEIPT[0]}
W3_REFERENCE_H=${W3_RECEIPT[1]}
ros2 run global_planner compile_route validate --artifact "$W3_ARTIFACT" \
  --expected-h "$W3_REFERENCE_H" --policy "$W3_POLICY" --report validate.json
ros2 run global_planner compile_route query --artifact "$W3_ARTIFACT" \
  --expected-h "$W3_REFERENCE_H" --policy "$W3_POLICY" --s-m 0 > query-zero.json
ros2 run global_planner compile_route query --artifact "$W3_ARTIFACT" \
  --expected-h "$W3_REFERENCE_H" --policy "$W3_POLICY" --s-m -0.1 > query-negative.json
ros2 run global_planner compile_route export --artifact "$W3_ARTIFACT" \
  --expected-h "$W3_REFERENCE_H" --policy "$W3_POLICY" --step-m 0.1 \
  --output /work/runtime/legacy --report export.json
```

The receipt is trusted here because it came directly from this test's controlled
compile process. For downstream distribution publish the approved H/context in
an independently trusted release manifest; reading a mutable colocated JSON file
is not approval. The runtime handoff test must additionally invoke
`load_reference(..., expected_H=..., validation_context=...)` in a new interpreter,
query randomized/shuffled supplied progress/occurrences and read the exported
file using the **existing installed** `read_global_waypoints`, then actual CDR.
The test wrapper itself must be copied into the runtime mount, never imported
from source. Test S0, reverse/rotated, both S2 routes and S3 surface/notch, plus
S4 supplied-progress distinctions. If proof runtime makes every query process
expensive, a process may load once then batch stateless queries through the
public API; do not add an unvalidated fast-loader escape hatch.

Fresh installed acceptance must demonstrate:

- no checkout resources, editable installs or symlinks; fixture/model/policy
  resources have committed hashes and complete explicit provenance;
- compile → dual independent PASS → atomic persist → new-process load/revalidate
  → metric query → nine-group export/reader/CDR; loaded authority equals validated
  authority, including closing edge and cap/portal support;
- no production/map/HOME `.ros` writes, ROS node launch, network access, device or
  hardware use; existing three legacy console entry points preserved;
- machine-readable failures for wrong expected H, altered model/kernel/policy,
  corrupt artifact, unsupported required coverage and all fault injections;
- exact W3 SHA/gitlinks/image/runtime/dependency/model/table/fixture/policy hashes,
  commands/exits/counts/residuals/time enclosures and every benchmark attempt.

The downstream contract is offline reference queries at supplied true metric
progress, with supplied occurrence when needed, and a lossy Wpnt projection.
It does not supply localization/occurrence association, following/controller
permission, calibrated tire traction, contact/grade/3D clearance or physical
safety. Missing real-course inputs stay UNSUPPORTED. Old consumers that refit
XY or assume index×.1 do not inherit W2's exact curve/ownership certificates.

## 11. Ready-to-dispatch W3 Codex Cloud implementation prompt

Copy this entire block into a new implementation task **only once the exact
final W2 acceptance condition in §1 is met**. Substitute the actual accepted SHA,
review/evidence URLs and scouting-document commit URLs at dispatch; do not guess
an SHA from branch HEAD or use frozen scout ancestry.

> You own W3 A07–A09 for `Felix-Grote/race_stack`, standalone offline ForzaETH
> Project A. Implement the campaign now, starting from final independently
> adversarially ACCEPTed W2 SHA `<FINAL_ACCEPTED_W2_SHA>`, supported by
> `<FINAL_W2_ACCEPT_REVIEW_URL>` and `<EXACT_HEAD_W2_EVIDENCE_URL>`. Read the
> committed `docs/project_a/W3_SCOUT.md` and `W3_HANDOFF.md` at
> `<SCOUT_DOCUMENT_COMMIT_URL>` as source-specific preparation. They are scouting
> evidence and proposals, not W3 implementation or W2 ACCEPT. Their frozen
> reference is e852641849b2497efea51dfca5ead38ad4476235; reviewer interfaces were
> changing afterward. Do not branch production work from the scouting branch.
>
> Verify review/CI SHA and recursive gitlinks, create a separate
> `project-a/w3-implementation` branch from the accepted W2 SHA, inspect all final
> W2 API/report/policy deltas and the final reviewer findings, and reproduce the
> safe functional baseline before changes. Read AGENTS, EXECUTION_PLAN, STATUS,
> RESULTS, DECISIONS, W2_NUMERICS and canonical architecture/A01–A09 roadmap.
> Preserve final W0–W2 tests/tolerances, reviewer lineage/approval regressions,
> all maps/configs/message definitions and submodule pins. Do not interfere with
> another task's W2 branch or self-merge upstream.
>
> Execute A07 first: exact immutable whole-reference artifact, schema-aware
> strict bounded JSON, deterministic H, complete approved route/model/body/policy
> and checker/numerical provenance, actual normalized-t coefficients/owners/q and
> segment/t/u profile. No refit or alternate geometric authority. Capture the
> independent final curve digest immediately at trusted A04 return; both
> independent validators and loaded-byte replay use that retained expectation.
> Stored PASS or internally recomputed selfhash cannot approve an artifact.
> Reload requires externally trusted expected_H and independently selected
> supported acceptance context. Preserve existing W2 digest representations;
> do not run A01's route normalizer on the full artifact. Separate volatile run
> telemetry from H. Stage, reload/revalidate exact written bytes, then atomic
> no-overwrite publication with crash/concurrency tests. No accepted output for
> any required-policy failure/uncertainty/unsupported result.
>
> Use small `route_artifact.py`, `route_compile.py`, `route_legacy_export.py`
> modules and one `compile_route` console entry with compile/validate/query/export
> subcommands, following the scout's consistent proposed flags. Implement the
> full frozen Reference query using true local arc and affine squared speed,
> right-hand acceleration/time including closure, immutable identity/owner/surface
> and explicit portal support. Keep pure commands free of ROS/node/map imports;
> install explicit small synthetic route/model/policy resources via data_files.
> Add only necessary dependencies. Export actual f110_msgs unchanged through
> the nine-group serializer in staging, conventional +X/CCW heading directly,
> original-owned side distances, true stations, terminal duplicate s=L and cyclic
> ax, Float32 projection of main reference time. Empty optional SP/centerline
> groups explicitly mean unavailable. Never fabricate a shortest path or claim
> old refitting/nearest-XY consumers preserve W2 authority.
>
> Execute A08 after A07 passes: build a planner-owned bounded test-local repaired
> comparator, leaving pinned optimizer/TPH source unchanged. Preserve stock
> failure separately; declare/hash scalarized prep objective, full Nx2 checker
> arrays, headless explicit inputs/output and watchdog containment. Match original
> legal geometry, ownership, model/body/margins, meshes and solver budgets; include
> same-prepared-input equation control. Capture legacy's actual final coefficients
> and lineage before its wrapper discards them; never refit saved samples for
> acceptance. Use both independent validators for final evaluation and common
> retiming for isolated geometry comparisons; retain legacy speed diagnostics
> separately. Inventory all three archived maps as archival software data, not
> physical ground truth. Freeze explicit S0–S6 software fixtures/annotations; use
> truthful unsupported cells where physical/calibration inputs are absent.
>
> S6~240m is a known default resource failure (.4m uniform600 plus anchors >512).
> Scouting measured direct kernels only up to512 and a geometrically failing
> scaled-route surrogate; no accepted S6 solve exists. Validate fixture gates/
> polygons first. Measure all phases and wall/CPU/RSS/condition/residual/N/leaf
> counts with external limits, record every failure/retry and repeat runs.
> Predeclare any alternative coarser mesh/resource policy in evidence. Prefer
> validated coarse optimization with fine query/export; no claim from sample
> density alone. Do not weaken legal/numerical acceptance or rewrite solver/
> switch B→C on estimates. Propose sparse changes or larger budgets only if a
> credible valid fixture and measured limiting phase justify them.
>
> Execute A09 from a fresh recursive exact-W3 checkout and non-symlink install.
> Build selected packages safely, then run separate offline runtime containers
> without source/build trees: installed compile → independent validate → persist
> → new-process load → query → ROS export/old reader/CDR. Assert module/resource
> origins and no hidden paths. Preserve existing legacy regressions. Wire every
> new suite into the runner, retain inherited legacy failure identities, update
> STATUS/RESULTS/DECISIONS, write the guide/final result matrix, preserve raw
> reproducible evidence and make small checkpoint commits. Run exact-head CI,
> self-review and seek independent W3 review; push a reviewable PR without merge.
>
> Work autonomously through routine repairs. Stop only for genuine ownership,
> input, environment or consequential architecture blockers; do not ask routine
> reconnaissance questions. Never run hardware Compose/stack, nodes affecting a
> car, device access or control/localization/perception changes. A software PASS
> excludes real-car localization/tracking/traction/contact/3D/physical safety.
> Final report must give exact SHA, commands/exits/counts/evidence, all S0–S6
> outcomes and limitations; never claim an unexecuted benchmark or full W3
> acceptance from partial tests.


## 12. Scouting closeout verification (E)

Scouting deliberately did not run/repair a mutable W2 acceptance campaign.
Independent read-only reviews checked artifact trust/atomicity, ROS/installed
commands and scaling claims; the final edits clarify partial-edge time,
right-hand acceleration, locator delegation, receipt failure handling and
payload-versus-envelope hashing. The existing source-free W2+ROS scratch probe
passed; no W3 product or exporter was implemented.

Executed source-preservation checks before committing documentation:

```bash
python3 scripts/project_a/source_manifest.py > /workspace/work/w3-source-final.json
cmp /workspace/work/w3-source-before.json /workspace/work/w3-source-final.json
git diff --exit-code e852641849b2497efea51dfca5ead38ad4476235 -- . ':!docs/project_a/W3_SCOUT.md' ':!docs/project_a/W3_HANDOFF.md'
git diff --cached --check
git -C /workspace/race_stack submodule foreach --recursive --quiet 'test -z "$(git status --porcelain)" || exit 1'
git -C /workspace/race_stack submodule status --recursive > /workspace/work/original-submodules-final.txt
cmp /workspace/work/original-submodules-before.txt /workspace/work/original-submodules-final.txt
```

All exit 0. The source manifest covers production Python, fixture and harness
bytes. The only staged paths are the two requested Markdown documents; all five
parent gitlinks and seven recursive pins are unchanged. The separate original
checkout stays on `work` at `67981ed7964a6d35e1da48f0c22bbd9f6d123d5e` with clean
submodules. All shell evidence/workflow fences pass `bash -n`; embedded scratch
Python bodies match the hashes reported above. There is no full-W3 test claim.
The scouting commit SHA and remote document links are reported by the delivery
message so the document does not contain a self-referential commit hash.

## Appendix A. Exact scratch reproduction and preserved results

These are executed reconnaissance scripts, **not proposed production code**.
Reproduction uses the frozen scouting checkout and its pinned image; final W3
acceptance must use the final accepted W2 API, including its independent approval
argument. Frozen scripts intentionally preserve original signatures. Scratch
paths below are historical execution paths, not installed runtime dependencies.
Timings are single-run observations, not guarantees.

### A.1 Image build

```bash
env -u DOCKER_HOST -u DOCKER_CONTEXT -u DOCKER_TLS -u DOCKER_TLS_VERIFY -u DOCKER_CERT_PATH docker --host=unix:///var/run/docker.sock build --secret id=system_ca,src=/etc/ssl/certs/ca-certificates.crt -f scripts/project_a/Dockerfile -t project-a-humble:w3-scout .
```

Build exited 0, image identity is recorded in §§6–7. No source/submodule setup
mutation was necessary: stock optimizer was read from a separate clean checkout
at its exact pin. Experiments did not run the full acceptance suite against a
mutable reviewer branch.

### A.2 Route-encoder incompatibility

Executed command (host Python only, no numerical claims or tracked writes):

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=planner/global_planner python3 - <<'PY'
import hashlib,json
from global_planner.route_input import canonical_bytes
value={'schema_version':1,'coefficients':[-0.0,1.0,1e-14]}
raw=json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
normalized=canonical_bytes(value)
print('raw_json='+raw.decode())
print('route_canonical_json='+normalized.decode())
print('same_bytes='+str(raw==normalized))
print('same_digest='+str(hashlib.sha256(raw).hexdigest()==hashlib.sha256(normalized).hexdigest()))
for key,value in [('required',False),('steering',None),('provenance','p'*129)]:
    try: canonical_bytes({key:value})
    except Exception as exc: print(key+'='+type(exc).__name__+': '+str(exc))
PY
```

Exact output:

```text
raw_json={"coefficients":[-0.0,1.0,1e-14],"schema_version":1}
route_canonical_json={"coefficients":[0,1,1e-14],"schema_version":1}
same_bytes=False
same_digest=False
required=RouteError: expected number, not boolean
steering=RouteError: expected number, not boolean
provenance=RouteError: invalid ID/text
```


### A.3 Scaling exact scripts


Original commands were `bash /workspace/work/scaling/run-probes.sh`, `bash /workspace/work/scaling/phase-run.sh`;N64 used the same docker invocation separately with `python /work/probe.py micro --n 64`; direct split used same container profile plus `python /work/profile_kernel.py 512`, outer50s. Read-only source mount and pinned image above required. Raw files remain scratch evidence; exact scripts are embedded below for durable documentation-only reproduction.

- `probe.py` SHA256 `c25408e896f638c90611067a732be5a752c7a8a834a48be301a0191433d3b9c2` (micro function unchanged after an added phase-resample loop).
- `profile_kernel.py` SHA256 `7cf2d64ec739c0530e6103dc8f9b9d398e5d962ff6ad97c0f2206f840afdc1af`.
- `run-probes.sh` SHA256 `fb8e34953aa16a2fc093f09320bf5c82f9d90e12b415769213f4bb6b33b939fa`.
- `phase-run.sh` SHA256 `d5871415806195b87ed2dbe2b4328e5bb0b2b5a58c9088d853b3109f3efd2849`.
- `micro-{64,128,256,384,512}.jsonl` retain actual alpha/objective/residuals; `phase-{0,240}.jsonl` retain all statuses/policies/counts/times. All stderr empty. Initial source-location search used wrong `optimizer/trajectory_planning_helpers` path and exited2; subsequently inspected actual installed TPH source from pinned image. Host venv was not used for acceptance because it is Python3.12/SciPy1.12 and lacks TPH.

<details><summary>Executed scratch run-probes.sh</summary>

```bash
#!/usr/bin/env bash
set -u
runner=(docker --host=unix:///var/run/docker.sock run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges --pids-limit 128 --memory 3g --cpus 2 --tmpfs /tmp:rw,nosuid,nodev,size=128m --mount type=bind,src=/workspace/work/w3-scout,dst=/src,readonly --mount type=bind,src=/workspace/work/scaling,dst=/work --user 1000:1000 -e PYTHONPATH=/src/planner/global_planner project-a-humble:w3-scout python /work/probe.py)
for n in 128 256 384 512; do
  timeout --signal=TERM --kill-after=5s 50s "${runner[@]}" micro --n "$n" > "/workspace/work/scaling/micro-$n.jsonl" 2> "/workspace/work/scaling/micro-$n.stderr"
  printf '%s\n' "$?" > "/workspace/work/scaling/micro-$n.exit-code"
done
```

</details>

<details><summary>Executed scratch phase-run.sh</summary>

```bash
#!/usr/bin/env bash
set -u
runner=(docker --host=unix:///var/run/docker.sock run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges --pids-limit 128 --memory 3g --cpus 2 --tmpfs /tmp:rw,nosuid,nodev,size=128m --mount type=bind,src=/workspace/work/w3-scout,dst=/src,readonly --mount type=bind,src=/workspace/work/scaling,dst=/work --user 1000:1000 -e PYTHONPATH=/src/planner/global_planner project-a-humble:w3-scout python /work/probe.py)
for length in 0 240; do
  timeout --signal=TERM --kill-after=5s 180s "${runner[@]}" phase --length "$length" > "/workspace/work/scaling/phase-$length.jsonl" 2> "/workspace/work/scaling/phase-$length.stderr"
  printf '%s\n' "$?" > "/workspace/work/scaling/phase-$length.exit-code"
done
```

</details>

<details><summary>Executed scratch probe.py</summary>

```python
"""Frozen-source reconnaissance; no production mutation. Execute with bounded runner."""
import argparse
from dataclasses import asdict
import hashlib
import io
import json
import math
import resource
import sys
import time
from pathlib import Path

import numpy as np

from global_planner import iqp_route_adapter as adapter
from global_planner.route_corridor import seed_curve, resample_ordered
from global_planner.route_input import load_route, validate_route
from global_planner.route_validate import Footprint, validate_geometry
from global_planner.cyclic_retime import DynamicsModel, ModelRegion, RegionLimits, retime
from global_planner.route_validate_dynamics import validate_dynamics

ROOT = Path('/src/planner/global_planner/test/fixtures/project_a')

def emit(event, **values):
    print(json.dumps(dict(event=event, **values), allow_nan=False), flush=True)

def timing(fn):
    began = time.monotonic()
    value = fn()
    return value, time.monotonic() - began

def scaled_route(target_length):
    base = load_route(ROOT / 's0_route.json')
    original = seed_curve(base)
    scale = target_length / original.curve.length
    payload = base.payload
    def coordinates(points):
        return [[float(x * scale), float(y * scale)] for x, y in points]
    for o in payload['occurrences']:
        for key in ('seed', 'left', 'right'):
            o[key] = coordinates(o[key])
        for c in o['caps']:
            c['at_m'] *= scale
    for p in payload['transitions']:
        p['gate'] = coordinates(p['gate'])
        p['support'] = coordinates(p['support'])
        p['before_m'] *= scale
        p['after_m'] *= scale
    payload['initialization']['zone'] = coordinates(payload['initialization']['zone'])
    payload['initialization']['seed_interval_m'] = [x * scale for x in payload['initialization']['seed_interval_m']]
    payload['course_id'] = 'scout-scaled-s0-' + str(target_length)
    payload['provenance']['source'] = 'scout uniform scaling of S0; synthetic only, not S6 approved geometry'
    return validate_route(payload), scale


def micro(n):
    theta = np.linspace(0., 2 * np.pi, n, endpoint=False)
    xy = np.column_stack((38.19718634205488 * np.cos(theta), 38.19718634205488 * np.sin(theta)))
    q = np.linspace(0., 240., n + 1)
    request = io.BytesIO()
    np.savez(request, operation=np.array('fit'), points=xy, q=q)
    response, wall = timing(lambda: adapter._run_child(request.getvalue(), adapter.SolverPolicy(), None))
    fitted = np.load(io.BytesIO(response), allow_pickle=False)
    matrix, normals = fitted['matrix'], fitted['normals']
    emit('fit', n=n, outer_wall_seconds=wall, child_peak_rss_bytes=float(fitted['resources'][0]),
         child_elapsed_seconds=float(fitted['resources'][1]), matrix_bytes=matrix.nbytes)
    track = np.column_stack((xy, np.full((n, 2), .75)))
    try:
        qp, wall = timing(lambda: adapter.solve_qp(track, normals, matrix))
        emit('qp', n=n, outer_wall_seconds=wall, **asdict(qp))
    except Exception as exc:
        emit('qp_failure', n=n, error=type(exc).__name__, message=str(exc))


def phase(length, spacing):
    route, seconds = timing(lambda: load_route(ROOT / 's0_route.json') if length == 0 else scaled_route(length)[0])
    emit('route', seconds=seconds, digest=route.digest, encoded_bytes=len(route.encoded), synthetic=True)
    ordered, seconds = timing(lambda: seed_curve(route))
    emit('seed_curve', seconds=seconds, length=ordered.curve.length, segments=len(ordered.curve.segments))
    numerical, seconds = timing(lambda: adapter.optimize(route))
    emit('optimize_default', seconds=seconds, status=numerical.status, reason=numerical.reason,
         traces=len(numerical.traces), policy=asdict(numerical.policy))
    if numerical.ordered is not None:
        ordered = numerical.ordered
    events = len(route.occurrences) + sum(len(o.caps) for o in route.occurrences) + 2 * len(route.portals)
    for requested in ((.4,.2,.1,.5) if length else (spacing,)):
        samples, seconds = timing(lambda: resample_ordered(ordered, requested))
        emit('resample', seconds=seconds, spacing=requested, length=ordered.curve.length,
             segments=len(ordered.curve.segments), uniform_count=math.ceil(ordered.curve.length / requested),
             conservative_events=events, actual_count=len(samples))
    _, seconds = timing(lambda: adapter._geometry(ordered, adapter.SolverPolicy()))
    emit('original_corridor', seconds=seconds, n=len(ordered.curve.segments))
    geometry, seconds = timing(lambda: validate_geometry(ordered, route, Footprint(.10, .10, .12, .01)))
    emit('geometry', seconds=seconds, status=geometry.status, reason=geometry.reason,
         leaves=len(geometry.intervals), gates=len(geometry.gates))
    limits = RegionLimits(.05, 4., 2., 3., 4., 2.5, .02, 'scout synthetic values; no car calibration')
    model = DynamicsModel(tuple(ModelRegion(o.id, o.surface_id, limits) for o in route.occurrences),
                          'scout uniform synthetic model, no physical claims')
    timed, seconds = timing(lambda: retime(ordered, model, spacing_m=.5))
    emit('retime', seconds=seconds, status=timed.status, message=timed.message, edge_count=timed.edge_count)
    if timed.profile is not None:
        dynamics, seconds = timing(lambda: validate_dynamics(ordered, timed.profile, model, metadata=timed.metadata))
        emit('dynamics', seconds=seconds, status=dynamics.status, reason=dynamics.reason,
             edges=len(dynamics.edges), bound_intervals=sum(e.bound_intervals for e in dynamics.edges))
    emit('parent_resources', peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024)

parser = argparse.ArgumentParser()
parser.add_argument('mode', choices=('micro', 'phase'))
parser.add_argument('--n', type=int, default=64)
parser.add_argument('--length', type=float, default=0)
parser.add_argument('--spacing', type=float, default=.4)
args = parser.parse_args()
try:
    if args.mode == 'micro': micro(args.n)
    else: phase(args.length, args.spacing)
except Exception as exc:
    emit('failure', error=type(exc).__name__, message=str(exc))
    raise
```

</details>

<details><summary>Executed scratch profile_kernel.py</summary>

```python
import resource
resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3))
resource.setrlimit(resource.RLIMIT_CPU,(20,20))
import json, sys, time
import numpy as np
import quadprog
import trajectory_planning_helpers as tph
n=int(sys.argv[1]); events=[]
def observed(name, original):
    def wrapped(*args,**kwargs):
        began=time.monotonic(); out=original(*args,**kwargs)
        events.append({'phase':name,'seconds':time.monotonic()-began})
        return out
    return wrapped
np.linalg.solve=observed('spline_dense_solve',np.linalg.solve)
np.linalg.inv=observed('qp_dense_inverse',np.linalg.inv)
np.linalg.cond=observed('condition_svd',np.linalg.cond)
quadprog.solve_qp=observed('native_quadprog',quadprog.solve_qp)
t=np.linspace(0,2*np.pi,n,endpoint=False)
xy=np.column_stack((38.19718634205488*np.cos(t),38.19718634205488*np.sin(t)))
began=time.monotonic()
x,y,matrix,normals=tph.calc_splines.calc_splines(np.vstack((xy,xy[0])),el_lengths=np.full(n,240/n),use_dist_scaling=True)
fit=time.monotonic()-began
began=time.monotonic(); condition=np.linalg.cond(matrix)
alpha,error=tph.opt_min_curv.opt_min_curv(np.column_stack((xy,np.full((n,2),.75))),normals,matrix,1.,.30,print_debug=False,plot_debug=False)
qp=time.monotonic()-began
print(json.dumps({'n':n,'fit_seconds':fit,'qp_condition_helper_seconds':qp,'condition':condition,'curvature_error':error,'events':events,'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}))
```

</details>

Unscaled seed-control exact Python payload, same container invocation, no writable source mount, outer40s:

```python
import json,time
from global_planner.route_input import load_route
from global_planner.route_corridor import seed_curve
from global_planner.route_validate import validate_geometry,Footprint
r=load_route("/src/planner/global_planner/test/fixtures/project_a/s0_route.json")
c=seed_curve(r);t=time.monotonic();v=validate_geometry(c,r,Footprint(.10,.10,.12,.01))
print(json.dumps(dict(status=v.status,reason=v.reason,seconds=time.monotonic()-t,length=c.curve.length)))
```

The helper split bootstrap itself setsRLIMIT_AS2GiB/RLIMIT_CPU20 before imports. Timing wrappers replace functions only in this scratch process and call originals unchanged. The production helper source hashes are verified by the actual adapter worker in micro runs; the split run uses the same pinned installed package without modifying files.

### A.4 Installed ROS/core evidence and exact scripts


No failed probe runs. Image `project-a-humble:w3-scout`, built from the frozen Dockerfile, was image ID `sha256:67d8c6416a3b65359a0c5228738624493cee251d5dba7443cfff765f4f0949ef`. Both runtime containers used uid/gid 1000, readonly rootfs, `--network none --ipc private --cap-drop ALL --security-opt no-new-privileges --pids-limit 256 --memory 4g --cpus 2`, `/tmp` 256 MiB tmpfs, one BLAS/OpenMP thread. Results are functional, not performance measurements (a scaling container existed during part of the initial build).

Build command (each source mount readonly, all outputs private scratch):

```
env -u DOCKER_HOST -u DOCKER_CONTEXT -u DOCKER_TLS -u DOCKER_TLS_VERIFY -u DOCKER_CERT_PATH docker --host=unix:///var/run/docker.sock run --rm --name w3-scout-ros-build --user 1000:1000 --read-only --network none --ipc private --cap-drop ALL --security-opt no-new-privileges --pids-limit 256 --memory 4g --cpus 2 --tmpfs /tmp:rw,nosuid,nodev,size=256m,mode=1777 -e HOME=/work -e PYTHONDONTWRITEBYTECODE=1 -e MPLBACKEND=Agg -e OPENBLAS_NUM_THREADS=1 -e OMP_NUM_THREADS=1 --mount type=bind,src=/workspace/work/w3-scout,dst=/src,readonly --mount type=bind,src=/workspace/race_stack/planner/global_planner/global_planner/global_racetrajectory_optimization,dst=/optimizer,readonly --mount type=bind,src=/workspace/work/ros_install,dst=/work project-a-humble:w3-scout /bin/bash /work/build_probe.sh
```

`build_probe.sh` sourced Humble; copied only global_planner, f110_msgs, frenet_conversion to /work/src; copied s0 fixture to /work/fixtures and frozen `test_ros.py`/`test_w2_installed.py` to /work; copied readonly pinned optimizer into scratch /work/optimizer; ran exactly:

```
python /usr/bin/colcon --log-base /work/log build --base-paths /work/src --build-base /work/build --install-base /work/install --packages-select f110_msgs frenet_conversion global_planner --parallel-workers 2
(cd /work/optimizer && python setup.py bdist_wheel --dist-dir /work/wheels)
python -m pip install --no-index --no-deps --target /work/python /work/wheels/*.whl
export PYTHONPATH=/work/python
source /work/install/setup.bash
cd /work
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q -p no:cacheprovider test_ros.py test_w2_installed.py --junitxml=/work/frozen-installed-tests.xml
```

Result: exit 0, `Summary: 3 packages finished [17.8s]`, setuptools byte-compilation-disabled warnings only, `5 passed in 15.41s`. Optimizer gitlink source `b1b38ecfefec7200d5bcb243f115af1d795b3766`; scratch wheel version 0.0.1. Log `/workspace/work/ros_install/build_probe.log` and XML `/workspace/work/ros_install/frozen-installed-tests.xml`.

Second run (no repository/build sources mounted):

```
env -u DOCKER_HOST -u DOCKER_CONTEXT -u DOCKER_TLS -u DOCKER_TLS_VERIFY -u DOCKER_CERT_PATH docker --host=unix:///var/run/docker.sock run --rm --name w3-scout-ros-no-source --user 1000:1000 --read-only --network none --ipc private --cap-drop ALL --security-opt no-new-privileges --pids-limit 256 --memory 4g --cpus 2 --tmpfs /tmp:rw,nosuid,nodev,size=256m,mode=1777 --tmpfs /work:rw,nosuid,nodev,size=64m,mode=1777 -e HOME=/work -e PYTHONDONTWRITEBYTECODE=1 -e MPLBACKEND=Agg -e OPENBLAS_NUM_THREADS=1 -e OMP_NUM_THREADS=1 --mount type=bind,src=/workspace/work/ros_install/install,dst=/work/install,readonly --mount type=bind,src=/workspace/work/ros_install/python,dst=/work/python,readonly --mount type=bind,src=/workspace/work/ros_install/fixtures,dst=/work/fixtures,readonly --mount type=bind,src=/workspace/work/ros_install/no_source_probe.py,dst=/probe.py,readonly --mount type=bind,src=/workspace/work/ros_install/results,dst=/results project-a-humble:w3-scout /bin/bash -c 'source /opt/ros/humble/setup.bash; export PYTHONPATH=/work/python; source /work/install/setup.bash; cd /work; python /probe.py'
```

Result: exit 0. Probe explicitly asserted `/src`, `/work/src`, `/work/optimizer` absent and all seven imported planner/core/messages/reference modules resolved under /work/install. It loaded copied explicit s0 fixture SHA256 `29212981a9b9247829967846f3883d32494eb3decfbc0765e623e3f1cc061648`, ran actual installed `optimize(route)`→CANDIDATE, independent geometry→PASS with footprint front/rear=.1, width=.12, margin=.01, `retime`→CANDIDATE with explicit synthetic speed [.05,3], ax+/ax-=2/3, ay=4, motor=2.5, drag/mass=.02, independent dynamics→PASS. Then actual WpntArray CDR and existing nine-group serializer/reader roundtripped a synthetic smoke message with empty centerline/SP arrays. This is no new W3 exporter or persisted-artifact test. Output `/workspace/work/ros_install/results/no-source-result.json`, log `no_source_probe.log`.

The installed share inventory contained only ament hooks/package metadata, `launch/global_trajectory_publisher_launch.xml`, `rviz/editor.rviz`; zero Project A fixtures/models. Installed console scripts were exactly the three existing legacy entries. Thus source-free W2 numerical use with explicitly copied fixture is demonstrated; installed resource CLI/artifact/export remains an A07 prerequisite.

#### Exact scratch probe bodies (reproduction evidence, not proposed production code)

Build probe:

```bash
#!/usr/bin/env bash
set -eo pipefail
source /opt/ros/humble/setup.bash
mkdir -p /work/src /work/fixtures
cp -a /src/planner/global_planner /work/src/
cp -a /src/utilities/libraries/f110_msgs /src/utilities/libraries/frenet_conversion /work/src/
cp /src/planner/global_planner/test/fixtures/project_a/s0_route.json /work/fixtures/
cp /src/scripts/project_a/tests/test_ros.py /src/scripts/project_a/tests/test_w2_installed.py /work/
cp -a /optimizer /work/optimizer
python /usr/bin/colcon --log-base /work/log build --base-paths /work/src --build-base /work/build --install-base /work/install --packages-select f110_msgs frenet_conversion global_planner --parallel-workers 2
(cd /work/optimizer && python setup.py bdist_wheel --dist-dir /work/wheels) > /work/optimizer-wheel.log 2>&1
python -m pip install --no-index --no-deps --target /work/python /work/wheels/*.whl
export PYTHONPATH=/work/python
source /work/install/setup.bash
cd /work
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q -p no:cacheprovider test_ros.py test_w2_installed.py --junitxml=/work/frozen-installed-tests.xml
```

Source-inaccessible probe:

```python
import hashlib
import importlib
import json
from pathlib import Path
from ament_index_python.packages import get_package_share_directory
from f110_msgs.msg import Wpnt, WpntArray
from rclpy.serialization import deserialize_message, serialize_message
from rosidl_runtime_py.convert import message_to_ordereddict
from std_msgs.msg import Float32
from visualization_msgs.msg import MarkerArray
import global_planner.iqp_route_adapter as optimizer
import global_planner.cyclic_retime as retimer
import global_planner.route_validate as geometry
import global_planner.route_validate_dynamics as dynamics
from global_planner.route_input import load_route
from global_planner.readwrite_global_waypoints import read_global_waypoints, write_global_waypoints
assert not Path('/src').exists()
assert not Path('/work/src').exists()
assert not Path('/work/optimizer').exists()
identities = {}
for name in ('global_planner', 'global_planner.iqp_route_adapter', 'global_planner.cyclic_retime', 'global_planner.route_validate', 'global_planner.route_validate_dynamics', 'f110_msgs', 'frenet_conversion'):
    module = importlib.import_module(name)
    path = Path(module.__file__).resolve()
    assert str(path).startswith('/work/install/'), path
    identities[name] = str(path)
route = load_route('/work/fixtures/s0_route.json')
run = optimizer.optimize(route)
assert run.status == 'CANDIDATE', (run.status,run.reason)
body = geometry.Footprint(front_m=.1, rear_m=.1, width_m=.12, margin_m=.01)
g = geometry.validate_geometry(run.ordered,route,body)
assert g.status == 'PASS',g
limits = retimer.RegionLimits(speed_min_mps=.05,speed_max_mps=3.,ax_pos_mps2=2.,ax_neg_mps2=3.,ay_mps2=4.,motor_mps2=2.5,drag_over_mass=.02,provenance='Explicit synthetic scratch installed probe')
model = retimer.DynamicsModel(regions=tuple(retimer.ModelRegion(o.id,o.surface_id,limits) for o in route.occurrences),provenance='Synthetic planar probe; no vehicle calibration')
timed = retimer.retime(run.ordered,model)
assert timed.status == 'CANDIDATE',timed
v = geometry.validate_dynamics(run.ordered,timed.profile,model,metadata=timed.metadata)
assert v.status == 'PASS',v
# This is serialization smoke only, intentionally not a new W3 exporter.
point = Wpnt(id=0,s_m=0.,x_m=1.,y_m=2.,vx_mps=3.)
array = WpntArray(wpnts=[point]);array.header.frame_id='synthetic_map'
assert message_to_ordereddict(deserialize_message(serialize_message(array),WpntArray)) == message_to_ordereddict(array)
output = Path('/results/smoke-legacy');output.mkdir(exist_ok=True)
groups = (MarkerArray(),WpntArray(),MarkerArray(),array,MarkerArray(),WpntArray(),MarkerArray())
write_global_waypoints(str(output),'Synthetic serialization smoke only',Float32(data=12.5),*groups)
loaded = read_global_waypoints(str(output))
for left,right in zip(groups,loaded[2:]):
    assert message_to_ordereddict(left)==message_to_ordereddict(right)
share = Path(get_package_share_directory('global_planner'))
resources = sorted(str(p.relative_to(share)) for p in share.rglob('*') if p.is_file())
entries=importlib.metadata.entry_points(group='console_scripts')
entries=sorted(f'{e.name}={e.value}' for e in entries if e.dist.metadata['Name']=='global-planner')
result={'source_absent':True,'modules':identities,'route_sha256':route.digest,'geometry':g.status,'dynamics':v.status,'installed_share_files':resources,'global_planner_entrypoints':entries,'legacy_groups':list(json.loads((output/'global_waypoints.json').read_text())),'scope':'Installed W2 synthetic pipeline and existing ROS serializer; no W3 compile/artifact/load/query/export capability claimed.'}
Path('/results/no-source-result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
```

Hash ledger: frozen Dockerfile `22fd6d9b79438347b914352eeb926732e7ca3aadb988f83b4dc9c03b710f6619`; requirements.lock `e920fd8b288646455f7c0ecf98275c1a998ec8ddbe49a1b452d8364df18a9aa5`; requirements.build.lock `57ba542c8ca996ee477a216227fbc53003fc37acf4f2c21c6c9962fa2e1b4efe`; Wpnt.msg `162c01ccb4f2f843d33d3bfbca3b50a8727080ab2a10065e50e27bc5c080468e`; WpntArray.msg `d77d8432a9855ed35a736d6fc1867bf009d10e7abeb0c9a7b433f4c1c16431c2`. Installed W2 test lap time 11.456316732476841 s is synthetic software output, not a comparative performance or physical claim.

### A.5 Legacy exact scratch scripts

The exact pinned probe commands, settings, outputs and hashes are in §6.
Create these two scratch scripts verbatim before invoking those commands.
They alter code only in an isolated in-memory namespace and never write
production helper files.

<details><summary>probe_check_and_assets_pinned.py</summary>

```python
"""Read-only source characterization; no installed optimizer/TUM import required."""
import hashlib, importlib.util, json, math, pathlib, sys, types
import numpy as np
REPO=pathlib.Path('/workspace/work/w3-scout')
OPT=pathlib.Path('/workspace/race_stack/planner/global_planner/global_planner/global_racetrajectory_optimization/global_racetrajectory_optimization')
def file_module(name,path):
 spec=importlib.util.spec_from_file_location(name,path)
 module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module
interp=file_module('scratch_interp',OPT/'helper_funcs_glob/src/interp_track.py')
calc=file_module('scratch_calc',OPT/'helper_funcs_glob/src/calc_min_bound_dists.py')
seen=[]
def observe(**kwargs):
 result=calc.calc_min_bound_dists(**kwargs)
 seen.append({'bound1_shape':list(kwargs['bound1'].shape),'bound2_shape':list(kwargs['bound2'].shape), 'min_distance_min_m':float(result.min()),'min_distance_max_m':float(result.max()), 'min_distances_m':result.tolist()})
 return result
helper=types.SimpleNamespace(src=types.SimpleNamespace(interp_track=interp,calc_min_bound_dists=types.SimpleNamespace(calc_min_bound_dists=observe)))
fake=types.ModuleType('global_racetrajectory_optimization'); fake.helper_funcs_glob=helper
sys.modules[fake.__name__]=fake
source=(OPT/'helper_funcs_glob/src/check_traj.py').read_text()
kwargs={}
n=64; t=np.arange(n)*2*np.pi/n
kwargs['reftrack']=np.column_stack((6*np.cos(t),6*np.sin(t),np.full((n,2),.75)))
kwargs['reftrack_normvec_normalized']=np.column_stack((np.cos(t),np.sin(t)))
kwargs['trajectory']=np.column_stack((6*t,6*np.cos(t),6*np.sin(t),t,np.full(n,1/6),np.full(n,2.),np.zeros(n)))
kwargs.update(ggv=np.array([[0.,12.,12.],[15.,12.,12.]]),ax_max_machines=np.array([[0.,9.],[15.,1.]]),v_max=15.,length_veh=.535,width_veh=.30,debug=False,dragcoeff=.0136,mass_veh=3.518,curvlim=1.)
ns={}; exec(compile(source,str(OPT/'helper_funcs_glob/src/check_traj.py'),'exec'),ns)
ns['check_traj'](**kwargs)
stock=seen.pop()
needle='stepsize_approx=1.0)[0]'; assert source.count(needle)==2
repaired=source.replace(needle,'stepsize_approx=1.0)[:, :2]')
ns={}; exec(compile(repaired,'<explicit scratch checker-shape-repair>','exec'),ns)
ns['check_traj'](**kwargs)
fixed=seen.pop()
out={'environment':{'python':sys.version,'numpy':np.__version__},'optimizer_pin':'b1b38ecfefec7200d5bcb243f115af1d795b3766','checker_sha256':hashlib.sha256(source.encode()).hexdigest(),'check_fixture':{'N':n,'radius_m':6.,'half_widths_m':.75,'length_veh_m':.535,'width_veh_m':.30},'stock_checker':stock,'scratch_repaired_checker':fixed,'repair':'two exact replacements stepsize_approx=1.0)[0] -> stepsize_approx=1.0)[:, :2]; production/submodule sources unchanged','assets':{}}
for folder in sorted((REPO/'stack_master/maps').iterdir()):
 p=folder/'global_waypoints.json'; d=json.loads(p.read_text()); report={'json_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'est_lap_time':d['est_lap_time'],'map_info_str':d['map_info_str'],'groups':list(d),'profiles':{}}
 for group in ('centerline_waypoints','global_traj_wpnts_iqp','global_traj_wpnts_sp'):
  w=d[group]['wpnts']; result={'count':len(w),'last_stored_s_m':w[-1]['s_m'],'terminal_matches_first_xy':w[-1]['x_m']==w[0]['x_m'] and w[-1]['y_m']==w[0]['y_m'],'finite':all(all(math.isfinite(v) for v in a.values()) for a in w),'positive_widths':all(a['d_left']>0 and a['d_right']>0 for a in w)}
  if group!='centerline_waypoints':
   errs=[]; time=0
   for i in range(len(w)-1):
    a,b=w[i:i+2]; ds=b['s_m']-a['s_m']; derived=(b['vx_mps']**2-a['vx_mps']**2)/(2*ds)
    errs.append(abs(derived-a['ax_mps2'])); time+=2*ds/(a['vx_mps']+b['vx_mps'])
   result.update(stored_station_linear_u_time_s=time,max_stored_ax_edge_discrepancy_mps2=max(errs),closing_stored_ax_mps2=w[-2]['ax_mps2'],closing_edge_derived_ax_mps2=(w[-1]['vx_mps']**2-w[-2]['vx_mps']**2)/(2*(w[-1]['s_m']-w[-2]['s_m'])))
  report['profiles'][group]=result
 out['assets'][folder.name]=report
path=pathlib.Path('/workspace/work/legacy-recon/probe_results_pinned.json'); path.write_text(json.dumps(out,indent=2,allow_nan=False))
print(json.dumps({k:v for k,v in out.items() if k not in ('stock_checker','scratch_repaired_checker')},indent=2))
print('stock checker boundary shapes:',stock['bound1_shape'],stock['bound2_shape'],'distance range:',stock['min_distance_min_m'],stock['min_distance_max_m'])
print('repaired checker boundary shapes:',fixed['bound1_shape'],fixed['bound2_shape'],'distance range:',fixed['min_distance_min_m'],fixed['min_distance_max_m'])
print('evidence:',path)

```

</details>

<details><summary>probe_tph.py</summary>

```python
import hashlib, json, math, pathlib, sys, types
import numpy as np
import scipy
from scipy import interpolate, spatial, optimize
import trajectory_planning_helpers as tph
out={'python':sys.version,'numpy':np.__version__,'scipy':scipy.__version__,'scope':'bounded characterization; no full optimizer wrapper solve; scratch scalarization only','helpers':{},'preparation':{}}
for n in ('spline_approximation.py','interp_splines.py','iqp_handler.py','create_raceline.py','calc_spline_lengths.py','opt_min_curv.py'):
 p=pathlib.Path(tph.__file__).parent/n; out['helpers'][n]=hashlib.sha256(p.read_bytes()).hexdigest()
t=np.linspace(0,2*np.pi,80,endpoint=False)
track=np.column_stack((8*np.cos(t),5*np.sin(t),np.full((80,2),.75)))
try:
 tph.spline_approximation.spline_approximation(track,s_reg=1,stepsize_prep=.05,stepsize_reg=.4)
 out['unmodified_prep']={'status':'UNEXPECTED_SUCCESS'}
except Exception as e: out['unmodified_prep']={'status':'FAIL_CHARACTERIZED','exception_type':type(e).__name__,'message':str(e)}
source=(pathlib.Path(tph.__file__).parent/'spline_approximation.py').read_text()
ns={};exec(compile(source,'<unchanged installed spline_approximation>','exec'),ns)
# Each repair is local to this cloned namespace. Do not monkeypatch TPH or SciPy.
ns['dist_to_p']=lambda t,path,p: spatial.distance.euclidean(p,interpolate.splev(float(np.asarray(t).item()),path))
for name,xy in [('ellipse',np.column_stack((8*np.cos(t),5*np.sin(t)))),('projected_crossing',np.column_stack((8*np.sin(t),5*np.sin(2*t))))]:
 params=[]
 def fmin_record(*args,**kwargs):
  result=optimize.fmin(*args,**kwargs); params.append(float(np.asarray(result).item()));return result
 ns['optimize']=types.SimpleNamespace(fmin=fmin_record)
 raw=np.column_stack((xy,np.full((80,2),.75)));result=ns['spline_approximation'](raw,s_reg=1,stepsize_prep=.05,stepsize_reg=.4)
 out['preparation'][name]={'status':'SCRATCH_SCALAR_OBJECTIVE_ONLY','output_shape':result.shape,'closest_t_min':min(params),'closest_t_max':max(params),'closest_t_strictly_increasing':bool(np.all(np.diff(params)>0)),'finite':bool(np.isfinite(result).all())}
L=.5*math.sqrt(5)+.25*math.asinh(2)
_,_,ts,nominal=tph.interp_splines.interp_splines(np.array([[0.,1.,0.,0.]]),np.array([[0.,0.,1.,0.]]),spline_lengths=np.array([L]),incl_last_point=True,stepsize_approx=.1)
actual=.5*ts*np.sqrt(1+4*ts**2)+.25*np.arcsinh(2*ts)
out['metric_probe']={'curve':'x=t,y=t^2','exact_total_arc_m':L,'nominal_spacing_m':.1,'max_nominal_true_arc_discrepancy_m':float(np.max(np.abs(actual-nominal)))}
p=pathlib.Path('/workspace/work/legacy-recon/tph_results_pinned.json');p.write_text(json.dumps(out,indent=2,allow_nan=False));print(p.read_text())

```

</details>
