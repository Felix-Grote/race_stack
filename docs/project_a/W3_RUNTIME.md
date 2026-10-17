# W3 installed offline planner handoff

The delivered product is an offline, synthetic planar planning subsystem. A07's
continuous geometry and declared-model dynamics checks approve a particular
immutable reference under a particular supported implementation and policy.
Independent W3 adversarial review remains the release gate. A successful test,
solver convergence or a waypoint JSON file does not establish race readiness.

## Reproduce an exact committed candidate

Use a normal nonroot developer account with Git/submodule access and the managed
Docker daemon. Start from the published W3 branch and choose its exact reviewed
candidate SHA. The helper requires a literal 40-character SHA and an absent output
directory:

```bash
git clone --recurse-submodules https://github.com/Felix-Grote/race_stack.git
cd race_stack
git switch project-a/w3-reference-benchmarks
candidate=$(git rev-parse HEAD)
scripts/project_a/fresh_verify.sh "$candidate" work/w3-fresh-candidate
```

`fresh_verify.sh` makes a new clone without hardlinks, detaches at that exact
commit, initializes every recursive submodule and refuses a dirty candidate.
It checks the exact SHA and clean state before setup, after setup and after
verification, so setup-time edits cannot become an accepted dirty baseline.
It builds the digest-pinned Ubuntu 22.04 / ROS 2 Humble image with the existing
hash-locked numerical dependencies, then invokes the full verification runner.
The original hardware Compose file is never used.

The build copies only `global_planner`, `f110_msgs` and `frenet_conversion` into
private scratch and performs an ordinary colcon install without `--symlink-install`.
It builds the unchanged pinned optimizer wheel separately. Immediately before
building, `source_manifest.py` replaces the staged copy's build manifest with the
actual source SHA, dirty flag, recursive gitlinks, source/resource/interface hashes
and dependency-lock hashes. It never writes that generated identity into the
source checkout. Runtime compilation receives that installed manifest explicitly;
it performs no Git lookup.

`isolated_runtime.sh` launches a second container using the recorded immutable
image ID. Its only bind mounts are the installed prefix, the installed optimizer
wheel, a minimal copied test harness and an explicit results directory. The first
three are read-only. The repository, build tree and optimizer checkout are absent.
The root filesystem and `/work` are read-only, the working directory is `/results`,
the network is disabled, capabilities are dropped and the process is nonroot.
Only `/results` and a bounded `/tmp` are writable. It does not set or require a
user HOME or `.ros` directory, map defaults, a GUI, physical vehicle configuration
or running ROS nodes.

The source-free test asserts module origins and hashes, installed input hashes,
the exact source commit and unchanged recursive pins. It invokes installed console
scripts in separate processes for compile, validate, metric query and export.
It feeds exported JSON to the actual existing reader and serializes/deserializes
all nine generated ROS message groups through CDR. Every failed process preserves
its machine-readable report, stdout and stderr.

The broader source-free campaign compiles forward/reversed/rotated S0, both S2
selected alternatives, S3 surfaces/notch and the accepted S4 repeated-location
fixture, plus the competition-scale S6 fixture, with their explicit installed
models. Each of the nine cases gets separate-process
revalidation, metric CLI queries, an additional public-API interpreter probe,
export and actual nine-group reader/CDR. The API probe shuffles progress, checks
negative/multiple-lap/seam and coefficient-boundary queries, and asserts every
supplied occurrence/surface pair independently of XY. S4's fixture/model bytes
are copied unchanged from the independently validated benchmark preflight.

S6 uses `fixtures/s6_competition_route.json`, its explicit
`models/s6_competition_route_model.json`, and `policies/s6_coarse_policy.json`.
The latter differs from the default policy only in `solver.spacing_m=0.52`.
The primary benchmark records the numerical reason for that choice:

| Optimization spacing | Actual S6 outcome |
| --- | --- |
| 0.4 / 0.2 / 0.1 m | RESOURCE_LIMIT before remeshing; point budget exhausted, no traces/candidate |
| 0.5 m | SOLVER_FAILURE, ill-conditioned TUM system; N=490, condition 9.72380961479247e18 exceeds unchanged 1e12 limit, no completed iteration/candidate |
| 0.52 m | Independent geometry/dynamics PASS twice; N=474, three iterations, maximum condition 21448.671356240695 and primal residual 2.5368596112684827e-14 |

This is an explicit mesh choice. Solver point/memory/time limits, numerical
tolerances, footprint, retiming and continuous proof policies are unchanged.
The source-free S6 reproduction compiles that same fixture/model with the 0.52 m
policy, reloads the saved coefficients and queries/exports them at finer metric
resolution without refitting. The benchmark also retains a 0.1 m query/export
view. All unsuccessful attempts remain part of the results; a successful
synthetic S6 certificate provides no physical race-course approval.

## Explicit installed commands

In a runtime containing only the installed prefix and its pinned dependencies,
source Humble and the install setup. Obtain resource paths through the installed
ament index; the compiler itself has no package-share or map discovery defaults:

```bash
source /opt/ros/humble/setup.bash
source /work/install/setup.bash
planner_share="$(ros2 pkg prefix --share global_planner)/project_a"

ros2 run global_planner compile_route compile \
  --manifest "$planner_share/fixtures/s0_route.json" \
  --vehicle-config "$planner_share/models/synthetic_model.json" \
  --policy "$planner_share/policies/synthetic_policy.json" \
  --build-manifest "$planner_share/build_identity.json" \
  --output /results/references --report /results/compile.json
```

The controlled build supervisor captures `H` and `artifact_path` from that
successful compile receipt before handing the product to another process. This
is the trust step. A mutable adjacent receipt or an artifact's own embedded `H`
cannot independently approve an artifact received from another party. A downstream
team obtains the expected H through its trusted release/approval channel and
independently selects its supported installed policy context.

For this controlled local example, capture the receipt once, retain those values,
then use them for all subsequent commands:

```bash
trusted_h=$(python -c 'import json; print(json.load(open("/results/compile.json"))["H"])')
artifact_path=$(python -c 'import json; print(json.load(open("/results/compile.json"))["artifact_path"])')

ros2 run global_planner compile_route validate \
  --artifact "$artifact_path" --expected-h "$trusted_h" \
  --policy "$planner_share/policies/synthetic_policy.json" \
  --report /results/validate.json

ros2 run global_planner compile_route query \
  --artifact "$artifact_path" --expected-h "$trusted_h" \
  --policy "$planner_share/policies/synthetic_policy.json" --s-m -0.125

ros2 run global_planner compile_route export \
  --artifact "$artifact_path" --expected-h "$trusted_h" \
  --policy "$planner_share/policies/synthetic_policy.json" --step-m 0.5 \
  --output /results/legacy --report /results/export.json
```

All nonquery commands require an explicit report path and emit JSON on stdout.
Query emits its JSON result on stdout. Non-PASS outcomes return a nonzero exit
code. No failed compilation exposes an accepted reference path. The original
three legacy console entry points remain installed.

## Artifact and query contract

`<output>/<H>/reference.json` contains the typed version-1 envelope
`{schema_version,H,payload}`. H is SHA256 of the canonical payload alone: UTF-8,
sorted keys, compact separators, Unicode text and finite JSON numbers. The codec
preserves binary64 values, integral floats and signed zero as required by W2's
coefficient/model/digest semantics. A01's route-input normalizer is used only for
the approved route, never for the whole artifact. Volatile solver/resource run
telemetry is recorded in receipts, outside immutable identity.

The payload retains original approved route geometry, surfaces, directed
occurrences, gates, portals, boundaries and caps; exact final cubic coefficients,
owners and inherited q; the cyclic `(segment,t,u)` squared-speed profile; explicit
model, footprint and margins; separate numerical/solver/retiming/geometry/dynamics
policies; the trusted A04 curve-approval digest; implementation/dependency
identities; independent validation reports and coverage limitations; and input
and build provenance. Saved coefficients are never refitted.

The loader requires `expected_H` and a separately selected `ValidationContext`.
Contract ID is `forzaeth.offline-reference.v1`. Full artifacts are bounded at
64 MiB, JSON depth 32 and 2,000,000 nodes; individual strings are bounded at
65,536 UTF-8 bytes and integers at 1,024 bits. The route retains its separate W2
2 MiB limit. Duplicate keys, nonfinite numbers, booleans used as numbers,
unknown fields/contracts and unsupported coverage fail closed. The loader
verifies H/context/runtime identities, reconstructs
the actual saved coefficients and profile, and reruns both independent validators
with the same H-authorized A04 expectation before returning an immutable handle.
Stored PASS reports or self-consistent internal hashes are insufficient.
The payload preserves historical producer reports exactly. Their supported
authority/identity/coverage/assumption and internal coherence checks remain
strict, but new numerical bounds or valid adaptive partitions need not be
bit-identical to that historical run. The accepted handle exposes only both
fresh independent PASS reports. It never substitutes a historical PASS for
replay, changes saved coefficients/q/model/profile, or adds a numerical tolerance.
The exposed main lap T is the exact stored producer dynamics nominal, checked
inside both historical and fresh enclosures. The legacy Float32 field projects
that frozen T, including rounding-midpoint cases. Fresh replay nominal and
derived query prefix times may have bounded arithmetic differences; no prefix
rescaling or change to the saved speed profile is permitted.
Publication also requires the producer's separately retained expected H and A04
curve digest. It writes a private same-filesystem stage, reloads/revalidates its exact
bytes, syncs them, and atomically publishes a new digest directory without
replacing existing content. Linux publication uses no-follow directory/file
descriptors, a per-H flock and `renameat2(RENAME_NOREPLACE)`. An interrupted write leaves no partial accepted
reference. A crash after a successful rename may leave a complete valid reference
without a receipt; filesystem power-loss durability has the documented fsync scope.

Use a publication directory whose full ancestry is owned by the effective user or
root, with no group/other write permission. The publisher rejects unsafe ancestry
for references and legacy exports. Root-owned sticky `/tmp` may be traversed into
a trusted-owned child without group/other writes; a shared directory itself cannot
be the stage parent. Linux POSIX ACL write masks are covered by the mode check.
The effective user, root, privileged capabilities and filesystem administration
are trusted throughout publication. Same-user mutation and distributed filesystem
namespace/locking semantics are outside this local Linux contract.

For a Python consumer:

```python
from global_planner.route_artifact import load_reference
from global_planner.route_compile import load_policy

_, context, _ = load_policy(explicit_trusted_policy_path)
reference = load_reference(explicit_artifact_path, expected_H=externally_trusted_h,
                           validation_context=context)
state = reference.sample(supplied_metric_progress_m, occurrence_id=supplied_occurrence_id)
```

Progress is true physical arclength. Negative and multiple-lap progress wrap
cyclically; s=L returns the right-hand seam state. Each sample gives XY, +X/CCW
heading, signed curvature, supplied occurrence/surface, applicable portal support,
speed, right-hand acceleration and elapsed model time from the wrapped lap origin.
Squared speed is affine in true local metric arclength, including the closing
edge. q, cubic parameter t and waypoint index are never substituted for distance.
The caller supplies progress/occurrence; there is no nearest-XY localization or
runtime branch inference. A mismatching optional occurrence assertion fails.

## Legacy projection and downstream ownership

The unchanged nine-group JSON schema and `f110_msgs/Wpnt`/`WpntArray` definitions
remain the compatibility interface. The main IQP array contains true metric s,
conventional +X/CCW heading, signed curvature, original occurrence-owned side
distances, cyclic speed and right-hand acceleration. Sequential IDs include the
mandatory terminal duplicate at unwrapped s=L. The main reference's binary64 lap
time remains in the artifact; the legacy Float32 field is its correct binary32
projection. Unavailable centerline and shortest-path arrays/markers are explicitly
empty and identified in the export report/map text. They are not fabricated.

Waypoint fields omit H, q, occurrence/surface identity, per-waypoint time and
mathematical coverage. Map text includes H as information; the original reader
does not authenticate it or bind it to waypoint contents. External H and artifact
replay remain necessary. Waypoints are a lossy view. Legacy consumers that refit
a spline or assume `index * 0.1`
produce their own geometry/station and do not preserve the canonical reference.
Export may include event stations and a short final interval. JSON/CDR acceptance
does not establish that existing downstream algorithms preserve the certificate.

The planner owns immutable offline geometry, numerical/model policies, validation
and explicit projections. State estimation/localization must establish frame
registration, metric progress and occurrence continuity at overlapping XY/heading
locations. Control integration must define timing, latency, tracking-error margins,
actuation limits, stop/fault handling and whether it consumes the canonical
reference or a newly assessed projection. Route/model changes require new offline
approval and a new externally distributed H. No runtime route-switching protocol,
automatic legacy fallback or authority to operate a physical car is provided.

Supported coverage remains the declared planar ribbon/shared-cap domain and the
explicit synthetic dynamics model. Approved real-course geometry, calibration,
3D bridge clearance, grade/contact/traction, physical obstacles, localization,
controller tracking and real-car safety evidence remain external requirements.

## Evidence and independent review

The additional [811bd708 portability challenge](evidence/w3-report-portability/README.md)
found that identical source, inputs, build manifest and dependencies can produce
different exact binary64 coefficients/q and different C/H on two hosts. Both
fresh products passed their own independent checks. The subsequent unchanged-
artifact cross-host load exposed exact historical-report equality as a false
rejection. The focused repair keeps both real validators, strict external H/C
and supported context, and treats historical snapshots as audit evidence.
Fresh-compilation byte identity across hosts remains unguaranteed. Capture each
controlled compile's own trusted H, or transport an unchanged approved product.
The root cause of numerical drift is not established: CPU feature/BLAS dispatch
was not captured. No curve, q, digest or model value is rounded to hide it.
The containing remediation candidate requires complete fresh and exact-head CI;
its final artifact portability outcome and controlled catalogs are published in
PR #3. The 531667 equality observation below is historical, not a general promise.

The clean implementation candidate
`531667abc0ad38236ec46825a544a3644c324b4f` passed
`scripts/project_a/fresh_verify.sh 531667abc0ad38236ec46825a544a3644c324b4f work/w3/a09-fresh`
and exact-head push CI 38926539747: 552 functional tests in 27 groups, all nine
source-free scenarios, three ordinary package builds and zero functional
failures/errors/skips. The separate legacy aggregate remains 541 reports,
ten inherited failures and two original skips, with zero errors and no added
style diagnostics. All nine controlled artifact identities match across local
fresh and hosted runs. Complete original logs, products, mutation reasons,
provenance, CI archive and checksums are in
[the A09 evidence index](evidence/w3-a09/README.md). The later evidence-containing head receives its
own exact-head CI, recorded externally in the PR/final report.

Keep the exact candidate SHA, recursive gitlinks, image ID, dependency manifests,
input/build/module hashes, JUnit reports and raw logs together. Source-free evidence
lives under `source-free/results`, with command-level reports and the accepted
artifact under `w3-installed`. Preserve failed attempts as well as successful ones.
The runner compares the exact ten inherited legacy failure identities and two
actual copyright skips against the W0 baseline; new failures reject verification.
Strict W3 source lint runs independently of those inherited red tests.

The installed adversarial suite changes coefficients, approval, model and policy
while retaining the original external H; it also rewrites all internal hashes.
It independently tests changed approval/policy/implementation and a stale profile
after a model change under a recomputed fixture H,
wrong expected H, corrupt/truncated stages and unsupported coverage. These attacks
must fail before exposing an accepted handle. The A07 suite additionally injects
publication interruptions, fsync failures, races and symlink targets. Reviewers
should rerun these tests from the PR's literal head, challenge shared numerical
assumptions and inspect complete S0–S6 evidence. Passing the author's tests is
not independent W3 acceptance.

An internal review identified a gap in the initial A07 installed negative tests:
paths named `mutated-*.json` and `corrupt.json` were interpreted as directories by
the public loader, so those runs proved path rejection and did not exercise the
mutated contents. Retained A07 evidence is not credited as installed content
mutation coverage. The A09 correction puts each mutation in its own directory as
`reference.json`, verifies that it is the only file, and asserts the intended
hash, parse, context or independent replay reason. Truncation in a normal product
directory is tested separately from intentional private-stage rejection. The
independent A07 source artifact mutation suite already used valid product paths.

## Installed command timeout evidence

The installed acceptance helper preserves a real timed-out command's partial
stdout/stderr bytes and appends its command record before reraising the timeout.
A separate `*.timeout.json` records RESOURCE_LIMIT, the command, original timeout,
null return code, retained stream paths and any existing producer-report path.
It does not overwrite the producer report. The invocation remains failed; the
existing 240 s limit and all numerical budgets are unchanged. Two actual-process
failing-first regressions and their corrected results are retained in the
[independent evidence](evidence/w3-independent/installed-timeout.json).
