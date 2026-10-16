# Project A — dependency-ordered implementation roadmap

Status: **proposed PRs, not production implementation**. Companion: [Project A architecture](GLOBAL_PLANNER_PROJECT_A_ARCHITECTURE.md). Original [16-PR team roadmap](IMPLEMENTATION_ROADMAP.md) remains intact. This plan reuses P01, then proposes **nine planner-owned PRs**, A01→A09. No controller, state-estimation, actuation, perception, vehicle recording or full-stack launch work is a dependency.

## 1. Decision and evidence available now

**TUM verdict: B, conditional go.** Reuse minimum-curvature QP and ordered spline helpers; replace preprocessing, inherited correspondence/normal-width preparation and the unbounded iteration wrapper. Direct ordered ellipse and projected figure-eight IQP solves succeeded. This is evidence against a blanket no-intersections limitation in the equations—not proof that stock widths preserve legal ownership or that their output footprint is legal.

Parent HEAD `00a166de963134746540c1971c7d888203c5ac46`, optimizer `b1b38ecfefec7200d5bcb243f115af1d795b3766`; all seven recursive submodules clean and matching P01. Existing untracked work preserved. Only the two requested Project A Markdown documents are created in the repository by this investigation.

**A0 / P01 already available:** [baseline results](../development/ROS_HUMBLE_BASELINE.md); raw `/mnt/storage/forza-p01-evidence/`. Humble amd64 image `sha256:0095af8de2c1a73b4be52801176506cebe4b193c19892681b0dcfcbfa65aed3c`, Python 3.10.12, TPH 0.79, quadprog 0.1.7, NumPy 1.26.4, SciPy 1.11.4. Selected planner/interfaces/reference-library builds passed twice; optimizer wheel/import and ROS message smoke passed. Existing selected tests fail lint/offline XML schema (12 aggregate reports, 0 errors, 10 failures, 2 skipped); pure limiter had 17 passes. No need to repeat/full-green the racing stack. Do not install conflicting modern quadprog or rerun hardware setup scripts.

### Source-level experiments actually executed in this investigation

Evidence/scripts: `/mnt/storage/forza-project-a-feasibility/`; source-copy TPH hashes and result details are in the architecture. Exact commands (before the evidence directory was moved from `/tmp`):

```bash
mkdir -p /tmp/forza-project-a
docker cp forza-p01-j-test:/opt/test-python/lib/python3.10/site-packages/trajectory_planning_helpers /tmp/forza-project-a/tph
docker compose -p forza-project-a -f docker-compose.test.yaml run -d --name forza-project-a-probes test -c 'sleep infinity'
docker cp /tmp/forza-project-a/probe_preparation.py forza-project-a-probes:/work/probe_preparation.py
docker cp /tmp/forza-project-a/probe_iqp.py forza-project-a-probes:/work/probe_iqp.py
docker inspect forza-project-a-probes > /tmp/forza-project-a/container-inspect.json
docker exec forza-project-a-probes bash -c 'cd /work; OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 /work/probe_preparation.py'
docker exec forza-project-a-probes bash -c 'cd /work; OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 /work/probe_iqp.py'
# Preparation rerun: only an explicitly labeled in-memory scalar objective repair.
docker exec forza-project-a-probes bash -c 'cd /work; OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 /work/probe_preparation.py --scalar-objective'
docker cp forza-project-a-probes:/work/. /tmp/forza-project-a/outputs
docker stop forza-project-a-probes
mv /tmp/forza-project-a /mnt/storage/forza-project-a-feasibility
```

Outputs were redirected to `preparation.log`, `iqp.log`, then `preparation-unmodified-final.log` / `preparation-scalar-final.log` for the final optional-flag script. Raw preparation exit=1; scalar-objective diagnostic exit=0; IQP probe exit=0. The script's scalarization was first tested unconditionally, then made opt-in and rerun; helper/production files were never edited. The stopped probe container/volume remain for reproduction; do not merge the Compose file with hardware configuration.

- Unmodified preparation fails `ValueError: Input vector should be 1-D` in `spline_approximation.dist_to_p` (SciPy `splev` receives an array parameter). Imports alone had passed P01. Scalarized diagnostic S0/S3 had increasing closest parameters; **no occurrence jump demonstrated**, but values can extend outside [0,1] and source has no ownership/monotonicity constraint.
- Ordered stock numerical IQP, approximately equal-arc 64-knot S0/S3: both solve in three iterations; curvature-error=.01920915/.04606338 per m; sampled final max |curvature|=.25407694/.39677981 per m. Input widths mutate .2 m. Nodal limits pass to roundoff. No independent footprint/legal certificate or full optimizer wrapper solve.
- `interp_splines` on `x=t,y=t²`: nominal versus true intermediate arc-progress error .16557464 m despite supplying exact total length. Source confirms linear fraction→t, not inverse arc.
- Actual container metadata was checked for pinned image, nonroot/read-only root/source, network none/private IPC/capability drop/no devices. No ROS nodes, new dependencies or infrastructure changes.

**Conclusion:** enough evidence to begin A01 immediately. The earliest further decisive experiment belongs to A04: new recomputed corridor ownership plus final swept validity, not another survey or an automatic backend rewrite.

## 2. Milestones, dependency graph and conventions

```text
A0: P01 (available; preserve failures and image)
A1: A01 legal-route input → A02 canonical curve/stateless query kernel
A2: A03 ordered corridor → A04 bounded TUM IQP adapter
A3: A05 independent continuous geometry validation → A06 cyclic speed/dynamics validation
A4: A07 immutable artifact/CLI/legacy ROS export → A08 repaired-baseline & S0–S6 benchmark
A5: A09 subsystem handoff/evidence
```

A05 can start after A02/A03 in parallel with A04; analytic candidates do not require solver success. A06 can start after A02 with synthetic models, but full candidate acceptance requires A05. A08's checker regression/asset diagnosis can be developed after P01, while its final comparison requires A04–A07. No candidate/intermediate is a published accepted artifact before A05+A06.

Paths: `PKG=planner/global_planner`, `GP=PKG/global_planner`, `OPT=GP/global_racetrajectory_optimization/global_racetrajectory_optimization`. All newly proposed tests under `PKG/test`; fixtures under `PKG/test/fixtures/project_a`; numerical config under `PKG/config/project_a`. These paths do **not** yet exist.

Use the existing isolated image, no new environment feature needed for pure tests. After P01's baseline script creates `/work/src` and `/work/install`, enter that container; new implementation should be copied to fresh scratch on each review. Future command convention:

```bash
source /opt/ros/humble/setup.bash
source /work/install/setup.bash
cd /work/src
export PYTHONDONTWRITEBYTECODE=1 MPLBACKEND=Agg
export PYTHONPATH="/work/src/planner/global_planner:/work/python:${PYTHONPATH:-}"
unit() { python3 -m pytest -q -p no:cacheprovider "$@"; }
bld() { python3 /usr/bin/colcon --log-base /work/project-a-log build --base-paths /work/src --build-base /work/project-a-build --install-base /work/project-a-install --packages-select global_planner f110_msgs; }
# After build, source /work/project-a-install/setup.bash, then inspect installed artifacts.
```

`python3 /usr/bin/colcon` is deliberate: its system-Python shebang otherwise misses the numerical venv. Unit tests import only pure modules; ROS serialization tests require built interfaces but never start nodes. All logs/candidates/exports stay in `/work`; no editable installation, writes to source or archived maps. Existing lint failure is recorded separately from functional acceptance; new code must not add failures. Every numerical PR pins fixture seed/config/helper identity and states tolerances before comparison. No dependency on global_planner_node's GUI, hidden `~/.ros` CSV or stack_master runtime parameters for the new CLI.

## 3. Review-sized PRs

### A01 — Strict selected legal-route input (first functionality PR)

**Objective:** a useful, independently testable parser/validator for manually approved directed routes, including multiple visits and surfaces. Not a full final-artifact schema yet.

**Likely files:** `GP/route_input.py`; `PKG/test/test_route_input.py`; fixtures `s0_route.json`, `s2_upper_route.json`, `s2_lower_route.json`, `s3_surfaces_route.json`, malformed variants; `PKG/setup.py`/`package.xml` only for explicit dependencies/install needs. No new shared package, ROS messages or legacy converter edits.

**Depends:** P01 only. **Evidence:** route/order/side conventions and real existing source identity available; physical approvals not required for synthetic fixtures.

**Exact acceptance command:**
`unit planner/global_planner/test/test_route_input.py`.

**Objective assertions:**
1. Parse a selected closed route with unique occurrence IDs; repeated XY visits on different surfaces stay distinct; exactly consecutive declared transitions including final→first. No inferred edge or automatic branch selection.
2. Both S2 choices load independently; reject missing/extra/disconnected portals and wrong gate/finish order. Directed reversal fixture swaps sides and transforms gates; rotated origin preserves directed cyclic order, with its own identity.
3. Physical-map hash/provenance and legal geometry remain separate; removing physical wall coverage cannot expand legal geometry. Approval provenance is recorded as a human assertion, not authenticated physical truth.
4. Reject duplicate JSON keys/IDs, NaN/Inf, boolean IDs, wrong units/version, zero-length consecutive seed edges, invalid boundary polygons/side orientation and unknown required surface/transition references. Nonadjacent equal XY is **not** rejected automatically.
5. Canonical encoding/digest independent of JSON key order; changing selected order, border, surface, cap or approval/model provenance changes content identity; input arrays are not mutated.
6. Tests run without importing rclpy/TUM or starting ROS. No geometry solve, speed planner, query tracker or deployment feature in this PR.

**Risks:** validation must separate annotation/topology acceptance from later chart/footprint feasibility. **Rollback:** remove the new module/fixtures; existing planner remains unchanged. Useful output even if IQP later rejects a route: validated selected topology and precise annotation errors.

### A02 — Canonical periodic cubic and stateless metric query kernel

**Objective:** one geometric authority for sampling, finalization and downstream static queries; establish true arc length before optimizing.

**Files:** `GP/route_reference.py`; `test_route_reference.py`; coefficient fixtures/analytic oracle tests; package dependencies. Implement frozen coefficient records, bounded integration/inversion, sample/locate/window; final artifact I/O comes in A07.

**Depends:** A01. **Evidence:** TPH coefficients available; nominal-station defect executed; no need for ROS or a vehicle model.

**Tests:** `unit planner/global_planner/test/test_route_reference.py`. Analytic `x=t,y=t²` arc length catches the .1656 m error; periodic ellipse/cubic fixtures, nonuniform knot spacing, negative/multiple-lap queries, seam right-hand convention, direction reversal, zero derivative/invalid closure, independent high-accuracy integration and derivative oracle. Synthetic policy starts with station error <=1e−7 m and reconstruction/closure tolerances explicitly recorded in fixtures (software tolerances, not track margins).

**Accept:** geometry/headings/curvature from the same coefficients; segment/t↔metric s roundtrip within declared error; exact seam position/tangent/curvature checks; no .1 indexing or independent refit, no state/history or XY association. Arc bounds and monotone inverse fail closed when budget exhausted.

**Risks:** integration error accumulation/near-singular derivatives; cross-platform bit equality not promised. **Rollback:** kernel is additive; reject unsupported curves, never substitute chords silently.

### A03 — Occurrence-owned corridor preparation and correspondence

**Objective:** produce a single ordered solver-ready reference with original-border normal intervals and explicit portal ownership.

**Files:** `GP/route_corridor.py`; `test_route_corridor.py`; fixed S0–S3 asymmetric border/portal fixtures. Shared low-level polygon predicates may remain private to this module or reference module; no generalized geometry framework/dependency added without need.

**Depends:** A01/A02. **Evidence:** stock preprocessing/width inflation/global-nearest risks source-confirmed; actual recomputed corridor not yet implemented.

**Tests:** `unit planner/global_planner/test/test_route_corridor.py`. Check TUM `[x,y,right,left]`, right-positive alpha vs left-positive offset, circle heading/curvature signs, inherited q through nonuniform resampling, narrow notch, physical wall gap, fork alternatives, coincident disconnected surfaces, rotated normals, invalid end caps/portals and chart folding. Every normal intersection belongs to its original occurrence or explicitly declared adjacent support; disjoint ray intervals cannot be bridged.

**Accept:** no `extract_track_bounds`, `dist_to_bounds`, unbounded nearest spline mapping or min-width inflation; monotone q and directed correspondence at every resample; preparation stays in selected original legal geometry or rejects. State cap/gate transport by inherited anchors, not unrestricted nearest XY.

**Risks:** a periodic interpolant may overshoot or have invalid charts; excessive smoothing can move gates. **Rollback:** require better annotations/seed or reject; no automatic Cartesian backend. More smoothing becomes an option only after a named failing fixture requires it.

### A04 — Bounded whole-lap TUM IQP adapter (first decisive solver gate)

**Objective:** retain numerical equations/damping, replace incompatible preparation and repeated width transport with A03 after every shifted spline.

**Files:** `GP/iqp_route_adapter.py`; `test_iqp_route_adapter.py`; iteration traces/fixtures; explicit solver policy. Default leaves optimizer submodule and TPH helpers unchanged.

**Depends:** A02/A03; geometry validation integration uses A05 before final acceptance. **Evidence:** direct numerical S0/S3 solved; legal footprint/portal preservation still unverified.

**Tests:** `unit planner/global_planner/test/test_iqp_route_adapter.py`. Reproduce 64-knot S0/S3 control with same numerical equations; compare a single QP on identical reftrack/normals/A with the direct pinned helper (offset tolerance initially 1e−8 m). Instrument q/owner/normal intersections before **every** QP. Use asymmetric crossing widths and a narrow border restriction on only one occurrence; reverse/shift origin; inject QP exception, nonfinite result, curvature error that never converges and resource-limit failure.

**Accept:** whole route/connectors/seam solved jointly; no solve+merge of separately optimized pieces; every iteration uses original geometry and current normals; no input mutation or accumulative width update; bounded iterations/time/N produce explicit failure without artifact. The asymmetric S3 candidate must pass A05's independent swept/gate checks before claiming adapter feasibility. Curvature/error thresholds, mesh and budgets are predeclared fixture inputs, not enlarged to make failure pass.

**Risks:** re-intersections change feasible intervals; original error criterion is not global optimality; cubic interpolation can overshoot; dense matrix scaling. **Rollback/fallback:** reject candidate, improve seed/coarsen a still-valid numerical mesh, or stop for a specific chart/scaling counterexample. C requires measured evidence; no new backend for XY overlap alone.

### A05 — Independent continuous geometry and footprint validator

**Objective:** make optimized geometry testable without trusting optimizer widths/convergence; no PASS from point density alone.

**Files:** `GP/route_validate.py` (geometry part); `test_route_validate_geometry.py`; analytic interior-excursion, hole/edge-intersection and portal fixtures. Tests can start while A04 is pending.

**Depends:** A01/A02/A03 for conventions; not solver success. **Evidence:** legacy checker defect/source and required error bounds identified; certified predicate/subdivision implementation not available yet.

**Tests:** `unit planner/global_planner/test/test_route_validate_geometry.py`. Reject spline border excursion with legal endpoints, an interior curvature peak, zero derivative, seam discontinuity, incorrect gate order, illegal transition at coincident XY, footprint corner/edge/overhang exit, polygon hole covered by rectangle, missing required physical coverage; accept disconnected projected crossing with valid owned corridor. Deliberately corrupt stored widths/metadata and solver-success flag: verdict must be unchanged. Force exhausted bound/subdivision budget → INCONCLUSIVE, not PASS.

**Accept:** report original-geometry ownership, all joins/closing edge, regularity, unique directed portals and full reference-aligned swept footprint; interval K/arc/clearance error budgets justify every accepted interval. Robust predicate/numerical error allowances explicitly documented. Independent dense/high-precision oracle is a regression aid, **not** the continuous certificate. Clearly label legal-planar coverage versus unsupported 3D/contact/physical evidence.

**Risks:** conservative bounds reject tight but feasible routes; nonconvex geometry and numerical signs near contact. **Rollback:** keep rejection; do not shrink real margins or relabel sampling as proof. This is a release gate even if solver results look visually correct.

### A06 — Cyclic retiming and independent dynamics/metadata validation

**Objective:** static caps before retiming; whole-lap feasibility on the actual final curve under an explicitly supported planar model.

**Files:** `GP/cyclic_retime.py`; extend `route_validate.py` with dynamics; `test_cyclic_retime.py`, `test_route_validate_dynamics.py`; synthetic models and documented import of existing GGV/motor data from explicit files. No runtime sector tuner change or minimum-time backend.

**Depends:** A02/A05 (A04 for integrated geometry); synthetic model permits development without physical calibration. **Evidence:** archived table/config exists; seam defect/LP reported previously, not rerun here; new LP/validator unimplemented.

**Tests:** `unit planner/global_planner/test/test_cyclic_retime.py planner/global_planner/test/test_route_validate_dynamics.py`. Nonuniform metric edges; last→first acceleration; cap on the seam with upstream braking; interior lateral curvature violation; diamond and motor/drag residuals at both edge endpoints and interior bounds; asymmetric acceleration/braking; multiple surface budgets at portals; steering angle/rate where model supplied; infeasible cap/zero-motion lap; solver failure. Open-edge ablation must be rejected by full cyclic evaluator. Inject stale vx/ax/kappa/time metadata.

**Accept:** exact edge acceleration formula on canonical arc including closing edge; finite moving-lap profile within predeclared model/caps; LP is sufficient distance-weighted squared-speed maximization, not claimed minimum time. Conservative table minima over supported speed range verified; no undocumented extrapolation. Independent residual <= recorded numerical allowance (initial synthetic LP residual target 1e−8 in normalized constraints); tighter oracle/refined edge evaluation agrees. Limits absent but required by policy → UNSUPPORTED.

**Risks:** conservatism; unmeasured tire/grade/contact/actuator limits; speed-dependent envelope complexity. **Rollback:** reject infeasible input; add richer sufficient envelope only after a specific useful route demonstrates need. No hardware observation is required to test synthetic mathematics.

### A07 — Immutable artifact, pure compile CLI and legacy waypoint export

**Objective:** independently revalidatable offline product, not a planner server or ROS launch.

**Files:** `GP/route_compile.py`, `route_legacy_export.py`; artifact load/write completion in `route_input.py`/`route_reference.py`; `PKG/setup.py`, `package.xml`, fixture/model installation; `test_route_compile.py`, `test_route_artifact.py`, `test_route_legacy_export.py`. Existing JSON helper reused; Wpnt/WpntArray definitions unchanged. No state messages/services.

**Depends:** A01–A06. **Evidence:** existing nine-group serializer and message smoke available; exact new schema/CLI behavior proposed.

**Tests:** `unit planner/global_planner/test/test_route_artifact.py planner/global_planner/test/test_route_compile.py planner/global_planner/test/test_route_legacy_export.py`; `bld`, source installed prefix, rerun from `/work` with source path removed from PYTHONPATH. Then proposed `compile_route --manifest /work/fixtures/s3_route.json --vehicle-config /work/fixtures/synthetic_model.json --output /work/routes` with explicit inputs.

**Accept:** loader/query matches validated coefficients/profile within kernel bounds, no coefficient refit; digest changes for geometry/caps/model/tolerance/topology mutations; reject wrong H/duplicate keys/nonfinite/unknown version; arrays/records immutable. Only total required-policy PASS is committed by atomic rename; no partial accepted files after injected failures. Explicit resource paths work outside checkout; no `stack_master`, map defaults or module-local outputs. Legacy JSON roundtrips through existing reader; terminal duplicate at s=L and cyclic ax fields correct; main reference time used; SP/centerline absence explicit, not fabricated solutions. All output goes outside original maps/source.

**Risks:** serializer portability, derived arc tolerance, resource packaging, optional legacy groups expected by downstream code. **Rollback:** new CLI/export opt-in; old maps and simple-track workflow unchanged. Consumers requiring SP are told unsupported unless separately validated data exists.

### A08 — Repaired baseline comparator and planner-only S0–S6 campaign

**Objective:** fair numerical/compatibility evidence, including rejected routes and failures; no end-to-end racing claim.

**Files:** scoped optimizer submodule `OPT/helper_funcs_glob/src/check_traj.py` repair (`interp_track(...)[0]` → full Nx2 array), regression test in optimizer `test/test_check_traj_contract.py`, separately reviewed submodule commit and parent gitlink; `PKG/test/test_project_a_regression.py`, `benchmark_project_a.py`, frozen fixtures/manifests/results. If needed, **planner-only** headless/input-metadata compatibility fixes in `GP/global_planner_node.py`/utils must be individually characterized; no launch/runtime subsystem repairs. Do not modify global TPH to hide failure: comparator scalar-objective repair belongs in a clearly labeled scratch test harness or authenticated separately pinned upstream patch, never silently in production code.

**Depends:** P01 for checker characterization; A04–A07 for integrated comparison. **Evidence:** checker truncation inspected, helper-shape failure executed, archived assets present; repaired comparator, complete solves and campaign not yet executed.

**Tests:** `unit planner/global_planner/global_planner/global_racetrajectory_optimization/test/test_check_traj_contract.py planner/global_planner/test/test_project_a_regression.py`; future `python3 planner/global_planner/test/benchmark_project_a.py --output /work/benchmarks --manifest /work/fixtures/benchmark_manifest.json`.

**Accept:** circular checker fixture confirms full boundary arrays; signed/outside/swept shortcomings remain documented. Legacy and new solver receive equivalent selected geometry, model, footprints/margins, solver mesh and final independent validator. Record original stock failure, explicitly repaired preprocessing result, and unchanged-equation comparator separately. Test all three existing waypoint/map assets (`GLC_smile_small`, `glc_ot_ez`, `hangar_1905_v0`) as **archival** geometry/metadata inputs, not approved survey truth; do not overwrite them or silently smooth unsafe profiles. Final query/export regressions match their own validated curves.

S0–S6 required matrix below passes or reports explicit unsupported/infeasible/scaling failures. S6 measures actual full-course solve/validation memory/time; report all retries/failures, no successful-only averages. Same mesh/fixture repeated twice gives reproducible verdicts/residuals within predeclared tolerance and identical artifact bytes on the pinned environment where deterministic; no cross-platform identical-solve promise. No invented lap-time improvement thresholds.

**Risks:** historical merger absent; comparing repaired wrapper to differently prepared new input can misattribute benefits; dense scaling may fail. **Rollback:** comparator changes are separate from new compiler; keep source failure columns, do not change margins to secure success. Promote sparse algebra only after measured dense limits, retain equations and full-lap coupling.

### A09 — Planner subsystem handoff and limits

**Objective:** stable static input/output/query contract and reproducible acceptance evidence for external teams.

**Files:** `PKG/PROJECT_A_GUIDE.md`, `docs/validation/GLOBAL_PLANNER_PROJECT_A_RESULTS.md`; final fixture/run manifest and small checked reference example (only after A07 validation), installation/interface tests `test_project_a_handoff.py`. Large outputs/bags are external artifacts; no runtime implementation.

**Depends:** A07/A08; no full-stack or hardware prerequisites. **Evidence:** external responsibilities agreed; final planner evidence not yet available.

**Tests:** `unit planner/global_planner/test/test_project_a_handoff.py`; fresh P01 scratch install; documented compile→validate→load→query→legacy export example executed verbatim without source mutation or node launch.

**Accept:** another team can load by H and sample a supplied metric progress using only stateless reference code; documented frame/units, side/sign, edge conventions, occurrence/portal support, init/completion metadata, numerical/model/coverage limits, required data/calibration and runtime responsibilities. Include source/submodule/image/fixture hashes, commands, successes and failures. Real routes lacking approved geometry or model coverage remain explicitly unapproved—not a blocker for handing off tested synthetic capability.

**Risks:** confusing immutable offline validity with runtime localization/control permission. **Rollback:** revoke affected artifact/policy version and regenerate offline; no runtime switching protocol or automatic legacy fallback promised.

## 4. Reused benchmark, planner-specific assertions

Use the existing S0–S6 protocol, not a new literature/competitor exercise. Fixtures freeze seeds, polygon construction, directed occurrence/portal metadata, models, footprint and numerical tolerances. Any invalid generated polygon is a fixture failure, not a solver result. Pure deterministic analytic tests precede bounded-noise stress. No new stochastic tracker tests belong here.

| Scenario | Required Project A assertion / PR gates |
|---|---|
| S0 ellipse + existing simple-track assets | Periodic metric curve, correct signs, reversed route/swapped boundaries, shifted origin, consistent serialization/export; matched-equation baseline and same final evaluator (A01–A08). |
| S1 physical wall gaps, unchanged legal ribbon | Removing walls changes physical coverage only; line/footprint cannot shortcut legal boundary; no physical-map mutation (A01/A03/A05/A08). |
| S2 selected upper/lower branch and common return | Separate manifests produce complete legal cycles; explicitly permitted split/remerge portals; no unselected branch or short loop; altered branch cap causes complete-lap retiming (A01/A03–A08). |
| S3 self-crossing, disconnected bridge surfaces | Preserve occurrence/q/normal owners at every iteration; no adjacency from XY; asymmetric borders independently checked, final gate and swept containment (A03–A08). |
| S4 identical XY/heading sections | Static artifact/query distinguishes supplied progress/occurrence and reports correct surface label. **No runtime identification or ambiguity estimator test assigned to Project A.** |
| S5 ramps/surface labels | Explicit connector/portal support and supplied caps/model budgets; pure-planar validation limitations named. Unsupported contact/vertical clearance cannot be certified (A01/A03/A05–A09). |
| S6 ~240 m course | Fixed legal polygon validity, full-lap memory/time/N and solver limits, coarse solver meshes .4/.2/.1 m where feasible versus fine export, nonuniform seeds; no deadline claim from unexecuted 120 s research target (A04/A08). |
| Adversarial geometry | Inconsistent sides, invalid portals, degenerate/near-zero derivative, narrow corridor/notch, smooth border exit between samples, folded local chart, missing physical coverage and resource-budget failure → rejection/inconclusive, never inflated legality (A01–A08). |
| Adversarial speed/artifact | Closing acceleration, interior curvature peak, caps applied late, stale derived metadata, mutated coefficients/H, changed numerical kernel, malformed JSON → reject; curve queried equals curve validated (A02/A05–A08). |

Increasing complexity requires evidence: input/q tests first; then owned preparation; then matched S0 equation control and asymmetric S3 sweep; then cyclic synthetic dynamics; then immutable roundtrip/export; only then S6 scaling/richer envelopes. A failure at one gate is not permission to build graph search, a tracker or a Cartesian backend. Repair the demonstrated bounded cause or document no-go.

## 5. Blocking uncertainties and team-level delta

**No blocker to A01.** Blocking later release claims: (1) new iterative border ownership + footprint validity, (2) credible fail-closed continuous numerical bounds, (3) cyclic profile feasibility under an explicit supported model, (4) S6 dense solver scaling. Authentic full legacy wrapper comparison also needs declared handling of the discovered helper shape bug, checker bug, GUI/data coupling and historical asset metadata. These are numerical/software gates, not unknown sensor/actuation requirements.

Real legal annotations/physical coverage/vehicle calibration block **real-course physical validity**, not synthetic planner development. Old TPH/quadprog constraints are resolved for the pinned tested environment; direct IQP feasibility is established only for two small supplied cases. No further dependency installation is justified by this investigation.

Changes from the original team roadmap: reuse P01; move planner-owned representation/stateless queries from frenet_conversion into global_planner; split old P03–P05 into input, curve, preparation, IQP, independent geometry, cyclic dynamics and artifact/export PRs; incorporate old P13 checker repair in an explicit comparator PR. Remove P02 and P06–P12/P14–P16 from Project A prerequisites. Do not assign runtime sector-scaler repairs, history association, state messages or command guards to the planner. Keep broader team work and its obligations unchanged.

Final adversarial gate: q inheritance is not mistaken for gate passage; no normal intersects an unrelated deck; smoothing/resampling never replaces original legal geometry; final validation covers interiors/seam on serialized coefficients and actual arc length; no measured tire/contact/localization claim from fresh labels or synthetic limits. Exact coefficients with derived arc tables are the smaller coherent representation. The first PR is useful even before the optimizer adapter exists. Only A01 implementation should begin after approval; this investigation itself changes no production code.
