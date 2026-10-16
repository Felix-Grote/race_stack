# W3 current evidence

A07 commit `0c2d7c35fc50051a2ae96b9260de636610e280f4` passes exact-head push
[CI 38918290086](https://github.com/Felix-Grote/race_stack/actions/runs/38918290086):
532 functional tests / 24 groups, no functional failures/errors/skips, three
builds, and exact inherited legacy 528 / zero errors / ten failures / two skips.
All 1,173 emitted style diagnostics are unchanged from the complete W0–W2
baseline. [A07 hosted evidence](evidence/w3-a07-ci/REPRODUCE.md),
[artifact specification](W3_ARTIFACT.md), [baseline](evidence/w3-baseline/REPRODUCE.txt).

A08 completes **92 primary + four separately predeclared matched S6 attempts**:
58 complete accepted synthetic outputs, 28 original stock preparation failures,
eight point-budget rejections and two .5 m new-adapter conditioning failures.
All 151 independent saved-output checks and 13 copied-package regression tests
pass without tolerance changes. Every S0–S5 variant passes both repeated new
and adapted repaired paths. S1 physical completeness and S5 3D/contact remain
unsupported; requiring unavailable physical coverage remains INCONCLUSIVE.
The [complete result matrix](W3_BENCHMARKS.md) retains every successful,
unsuccessful and exploratory attempt with its actual provenance.

S6 .52 m completes three iterations (472/474/474 points), 1,184 geometry leaves,
955 dynamic edges and 2,409 fine metric queries. Its exact final coefficients
describe 240.856069139 m with model time 68.009787876 s. Repeated complete wall
time is 117.96–121.53 s, maximum spline-system condition 21448.6713562 and QP
inequality violation 2.537e-14; QP child peak RSS is about 280 MB. The matched
adapted repaired .52 m output has 467 cubics, model time 67.912308846 s and wall
time 110.09–114.44 s. Actual curvature energies are 0.189922802 / 0.189997285 1/m.
These are common-model diagnostics, not native legacy speed, minimum curvature,
minimum lap time or measured vehicle performance. The circle's actual energy
increases despite solver convergence. Default finer meshes and the .5 m
conditioning failure remain explicit engineering limitations.
Two additional predeclared resource-only .52 m replays PASS with original
authority. Linux wait4 collects startup/import through serialization/exit and
reaped numerical children: whole-worker CPU is **130.628536 / 124.494186 s**
(new / repaired), with maximum process RSS **278,716,416 / 270,630,912 bytes**.
These replay wall times are explicitly non-isolated. The original 96-attempt
outcome matrix and isolated wall measurements remain separate.

A09 fresh recursive exact-candidate/source-free verification and final exact-head
CI remain pending. Separate independent W3 adversarial review is required.

# Project A validation matrix — W0/W1/W2

## Independent adversarial W2 final implementation — 2026-10-16

Reviewed e852641 from exact corrected W1 9440c2c. Original F1/F2 findings and red
runs precede separate corrections 6b778519 and 37b36ccc. Final implementation
37b36ccc full local command `scripts/project_a/verify.sh all work/adversarial/final-full`
exits 0 with 373 functional passes/19 groups, zero functional failures/errors/skips,
strict scoped 99-column lint, three builds (17.3 s), ROS 4 and installed W1/W2 (1+1).
Source manifests match before/after and all 92 exact committed source/fixture
files; SHA256 c4076eb430c38cd1e1faf956f7830fbdc1a0c3d09136a7f0c8c82b1a2d6bf132.
Separate legacy 372/0 errors/10 failures/2 skips exactly matches initial ten raw
failure identities. Final retained seven-case pipeline SHA256:
fb42f757f888a524be7e8912ba2bb77e9b87f584c59c26cac0e513643bc3f862.

Exact-code push [38906194264](https://github.com/Felix-Grote/race_stack/actions/runs/38906194264)
and PR [38906201603](https://github.com/Felix-Grote/race_stack/actions/runs/38906201603)
SUCCESS. Push job 116990251430 / artifact 12049420387 independently downloaded;
archive SHA256 c980acf5f5df4234914276e4de6d70818554c2285d4324634a0f650645de6aa7.
All 373 tests, source/Git/installed hashes, same-authority seven/novel pipeline and
exact inherited legacy failures verified from artifact, not only workflow status.

New F2 exact-cap 49 + original A03 38 pass 87 / 49.36 s; new unchanged analytic ellipse
probe+permanent full pipeline pass 2 / 31.13 s. The novel case has 129 segments,
330 swept leaves,4 gates and 221 speed knots. Independent 80-digit Decimal/GEOS and
true-arc oracle checks 2967 bodies/3757 dynamic points; time 13.759213225603533 s
is inside [13.759213225499257,13.759213225707809] s. Independently checked actual
final seven-case output covers 1541 leaves/7705 bodies/28 gates and 1267 edges/
11403 dynamic points at both functional and retained output stages. Only 126
RSS/time scalars differ; complete mathematical payloads are exactly identical.

Full report, per-group ledger, exact commands, complete source/fixture identities,
independent oracle scripts, preserved failed experiments and archive checksums:
[review](W2_INDEPENDENT_ADVERSARIAL_REVIEW.md),
[reproduction](evidence/w2-adversarial/REPRODUCE.md).
The report-containing commit still requires its own exact-head publication CI;
its final literal SHA/verdict is supplied by the companion publication manifest.
This does not substitute 37b36ccc CI for a later commit or authorize PR merge.

## W2 full local, hosted A06 and literal-coverage closeout — 2026-10-16

At committed **e3f94dce130cf0cee8cc0dfdbf697b57efbd7b87**, the full command
`scripts/project_a/verify.sh all work/w2/full` exits **0** with complete source,
fixture and harness hashes unchanged. **296 functional tests** pass in fourteen
groups: A01 **60**, A02 **47**, A03 **38**, A04 **18**, A05 **37+13**, A06
**20+34+8**, fresh same-curve pipeline **8**, numerical **7**, actual ROS **4**,
installed W1 **1**, installed W2 **1**. Three selected packages build in 26.0 s.
The actual installed W2 pipeline freshly optimizes S0 and independently passes
geometry/dynamics in 18.69 s; module hashes under `/work/install` match source.

The separate legacy run reports **295 tests / 0 errors / 10 failures / 2 skips**.
Every failing identity exactly matches W0/W1; the inherited lint/XML failures
remain visible. [Full local evidence](evidence/w2-full/SHA256SUMS), including
JUnit, runtime/dependency inventories, full logs and installed coefficient/profile
certificates. Exact A06 [push CI 38891088081](https://github.com/Felix-Grote/race_stack/actions/runs/38891088081)
is **SUCCESS**, independently confirming the same 296 tests/builds/legacy
identities. [Hosted evidence](evidence/w2-a06-ci/SHA256SUMS).

Final literal-coverage controls, promoted after that source freeze:

- Closed ellipse axes 8/5 m: 224 speed knots, nonuniform edges
  .0029387–.392027 m, independent coefficient-arc length 41.386275696668 m.
  Analytic ellipse shape discrepancy is -3.76e-7 m against a separate 1e-5 m
  cubic-approximation allowance; metric-kernel tolerances are unchanged.
  Curvature about .32047 versus .07810/m produces squared speeds about 6.18
  versus 25.02 m²/s². Independent dynamics PASS; model time 11.713779280290 s is
  inside the certified time interval.
- At actual S3 XY (.128091022251, -.000981424079), both projected legal ribbons
  contain the point. Replacing original ground ownership by upper-deck ownership
  independently FAILs despite success and 1,000,000 m clearance claims.
- Original notch normal width .935959 m versus neighboring 1.192171/1.142275 m:
  supplied cap 1 m/s over inherited q 7.065451418853–7.315451418853 m applies
  before retiming, with unchanged borders/coefficients/q and upstream braking.
  Independent dynamics PASS. Reference acceleration includes supplied drag;
  the declared longitudinal diamond constrains a+c*u.

The final selected command in [promotion closeout](evidence/w2-supplemental/promotion-closeout.json)
exits **0: 3 passed, 57 deselected in 8.75 s** with frozen hashes and strict
99-column lint. Final full-runner collection includes all three without the
selection filter; the exact delivered head's complete hosted result is recorded
in [PR #2 checks](https://github.com/Felix-Grote/race_stack/pull/2/checks) and its
workflow artifacts/final technical report. No unexecuted result is substituted
for a completed run. Production mathematical modules remain byte-identical to
A06 e3f94dc. [Supplemental audit/evidence](evidence/w2-supplemental/SHA256SUMS).

A separate retained zero-motion review passes three adversarial cases: all-zero
solver success returns structured INCONCLUSIVE; isolated zero and below-floor
numerical candidates independently FAIL. This confirms the mandatory candidate
versus acceptance boundary; no production repair or numerical relaxation was
needed. Original and corrected command provenance and real exploratory failures
remain retained as historical evidence.

## W2 A06 and fresh pipeline checkpoint — 2026-10-16

The single frozen-source command in [A06 review](evidence/w2-a06/REVIEW.md) exits
**0: 70 passed in 169.24 s**, with stable source/fixture/helper/Compose hashes:
**20 retimer + 34 independent dynamics + 8 math oracles + 8 fresh pipeline**.
Strict flake8 at 99 columns and two independent source/math reviews pass. No
original W0/W1 test, release tolerance, dependency or gitlink was changed.

Every integration case reruns actual pinned IQP and then certifies the same
final coefficients geometrically and dynamically under explicit synthetic
footprint/model/policies. All include the closing edge and supplied steering.

| Scenario | Geometry / dynamics | Speed knots | Nominal time s | Time error bound s |
|---|---|---:|---:|---:|
| s0_route | PASS / PASS | 166 | 8.593509770 | 8.48e-11 |
| s0_reverse_route | PASS / PASS | 166 | 8.593509770 | 8.48e-11 |
| s0_rotated_route | PASS / PASS | 166 | 8.593509770 | 8.48e-11 |
| s2_upper_route | PASS / PASS | 155 | 9.411623853 | 1.01e-10 |
| s2_lower_route | PASS / PASS | 151 | 8.587343725 | 9.38e-11 |
| s3_surfaces_route | PASS / PASS | 231 | 16.419262764 | 1.17e-10 |
| s3_notch_route | PASS / PASS | 232 | 16.419182802 | 1.16e-10 |

Maximum observed normalized LP residual against inward constraints: **2.853e-12**
(target 1e-8). Independent normalized residual maxima are nonpositive; their
largest value is approximately -1.11e-16. Geometry uses 164–269 continuous leaves
and four independently isolated directed gates per case; minimum sweep slack is
8.949819e-5 m. The time-error column propagates arc and square-root numerical
allowances; it describes synthetic model time, never measured vehicle time.
Repeating S0 optimization agrees within 1e-10 m coefficient tolerance; identical
retiming returns exactly equal profiles and metadata.

An independent asymmetric cyclic braking envelope agrees within **1.6775e-8
m²/s²** (predeclared comparison 1e-7), with closing a=-0.999999998991 m/s².
Known constant-speed and motor/drag optima, nonuniform 96/48-point derivative
quadrature, table dips and unchanged legacy CSV imports pass. False candidates
with only a bad closing edge, hidden interior curvature, motor/drag/diamond,
steering rate/angle, wrong surface budgets and stale metadata fail independently.
Missing required models are UNSUPPORTED; exhausted/unrepresentable proof remains
INCONCLUSIVE. Initial real debugging failures and source-drift runs are retained
as exploratory evidence, never substituted for frozen acceptance.

Full raw traces, final coefficients/q/owners, models, policies, profiles, metadata
and both certificates: [A06 evidence](evidence/w2-a06/SHA256SUMS). Full W0–W2,
actual installed-module pipeline and exact-head hosted CI remain the final gates.
A05 exact-head hosted CI [38888550247](https://github.com/Felix-Grote/race_stack/actions/runs/38888550247)
passed 225 functional tests and three builds; legacy 225/0 errors/10 failures/
2 skips retained the exact original ten failure identities.
[Hosted A05 evidence](evidence/w2-a05-ci/SHA256SUMS).

## W2 A05 local checkpoint — 2026-10-16

`scripts/project_a/unit.sh work/w2/a05-final-formatted planner/global_planner/test/test_route_validate_geometry.py planner/global_planner/test/test_route_validate_bounds_oracle.py`
exits **0: 50 passed in 103.41 s**. Production, tests, complete fixtures, helper
and Compose hashes are unchanged before/after. Scoped lint passes. Two
independent reviewers accept the exact-input planar certificate implementation.

All seven actual A04 candidates PASS continuous geometry and swept-rectangle
containment with the original .01 m margin, independent 1/m curvature limit and
four actual directed gates each. Certificate leaves **164–269**, certified
curvature upper maxima **0.2125–0.4535/m**, minimum certificate slack across
the campaign **8.9498e-5 m** beyond motion, margin and numerical allowances.
Both enclosing-disc and full-rectangle curvature sweep methods are exercised;
every coefficient interval is covered without gaps, including the periodic seam.

Adversaries include actual between-node reference/rectangle-edge exits despite
legal solver-node bodies; an interior curvature peak despite legal nodal values;
wrongly phased actual gate passage; forged authority/owners/q/policies; stale
curve metadata; degenerate/seam corruption; holes, nonexact shared caps and
resource/required physical-coverage uncertainty. Thirteen separate high-precision
oracles check whole-interval derivative, curvature and curvature-rate bounds,
cancellation, transforms/scales, subnormal conversion and overflow behavior.

Independent pinned S3 hidden-footprint reproducer: **1 passed in 5.07 s**,
exit 0, all **44 nodal bodies legal**, continuous actual exit correctly FAIL.
Full negative route, coefficients/q/body, command and report are retained.
First frozen main run had **44 passes / 1 test-fixture failure**; corrected cap
placement preserves the notch. Second run **49 passed**; final adds input-size
hardening and explicit nodal-body controls. No old acceptance gate changed.

Exact A04 checkpoint push CI at **604ad5d**, run **38885077894**, is SUCCESS;
retrieved logs show 60/47/38 + 18 + 7/4/1 passes and three builds. Separate legacy
aggregate grows to 175 reports with the same 10 failures / 2 skips.
See [A04 hosted logs](evidence/w2-a04-ci/SHA256SUMS),
[A05 evidence/review](evidence/w2-a05/SHA256SUMS),
[independent reproducer](evidence/w2-a05-independent/SHA256SUMS) and
[numerical contract](W2_NUMERICS.md). A06/combined trajectory acceptance remains
pending. These are synthetic planar software results, without physical evidence.

## W2 A04 local checkpoint — 2026-10-16

Base is exactly corrected W1 `9440c2ce68e3dee549de7efacff1cf723fe830df`.
Fresh setup + `verify.sh all work/w2/baseline` exit 0: **60/47/38 A01–A03,
7 numerical, 4 installed ROS, 1 installed W1**, three package builds. Separate
legacy: 157 reports / 0 errors / original 10 failures / 2 skips, exact W0 failure
identities. Exact-base push CI 38879680224 is SUCCESS.

`scripts/project_a/unit.sh work/w2/a04-final-stable planner/global_planner/test/test_iqp_route_adapter.py -x`
exits **0**, **18 passed in 84.37 s**, before/after source hashes identical.
Pinned-environment new-file lint passes. Independent source/adversarial review
accepts the bounded TUM-surrogate candidate scope.

All seven fixed S0/reverse/rigid-rotation/S2-upper/S2-lower/S3/s3-notch fixtures
converge in three QPs. Final solver N ranges **89–135**, maximum primal residual
**3.45e-15**, maximum matrix condition **3.738e8**, maximum observed child RSS
**98,988,032 bytes**. Actual process timeout/memory, infeasibility, conditioning,
oversized preparation, nonconvergence and corrupt-result tests pass. Identical
fixed-input 64-knot ellipse/crossing QPs match direct pinned helper offsets within
**1e-8 m** and linearization errors within **1e-10/m**.

The exact-coefficient diagnostic for S0 rises from **1.0471975681** to
**1.16278187265 1/m** integrated squared curvature: surrogate convergence does
not establish actual objective improvement/global optimality. Cyclic identical-
knot QP parity meets 1e-8 m; seam-dependent remeshing has **1.543 mm** measured
q-correspondence sensitivity. These limits are retained explicitly.

No geometric/footprint/dynamic acceptance is claimed at A04. See
[numerical policy](W2_NUMERICS.md), [baseline evidence](evidence/w2-baseline/SHA256SUMS)
and [A04 full traces, hashes and review](evidence/w2-a04/SHA256SUMS).
The historical W0/W1 sections below retain their original evidence.

## Final corrected W1 local acceptance — 2026-10-16

Corrected implementation: `becfe8fc46e7490e8857f630a37f0617f477da71`.
All F1–F5 findings are repaired. Safe `setup.sh` and prescribed
`verify.sh all work/remediation/validation/w1-final` exit **0** on a clean
checkout; final documentation/evidence closeout preserves those code/test bytes.
Independent exact-head push CI on the final containing commit is the publication
acceptance gate, recorded by the workflow and final delivery after completion.

| Gate | Final result |
|---|---|
| A01 / A02 / A03 | **60 / 47 / 38 passed** |
| W0 numerical / actual ROS / installed W1 | **7 / 4 / 1 passed** |
| Selected package build | **3 passed** |
| Scoped flake8 / pip check | PASS |
| Separate legacy aggregate | 157 reports, 0 errors, **10 failures / 2 skips** |
| Fresh W0 legacy comparison | Exactly identical failing/skipped identities |
| Installed package identity | All four modules byte-identical to source |
| Independent final adversaries | Six groups PASS; 18 arc families, 90 inverse queries, 408 endpoint queries, 32 normal cases, exact close caps, 60 coherent boundaries |

Independent maximum station residual is **9.901e-11 m** against unchanged
1e-8 m policy; maximum length difference **3.914e-15 m**. The final probe's four
production hashes map to committed code. All nine production/test/runner hashes
remained unchanged through full verification. Fresh W0 also passes 7 numerical,
4 actual ROS and three-package build, with its known 10 failures/2 skips.

Read [W1_REMEDIATION_REPORT.md](W1_REMEDIATION_REPORT.md),
[W1_NUMERICAL_ERROR_CONTROL.md](W1_NUMERICAL_ERROR_CONTROL.md) and current STATUS.
Complete local commands, logs/JUnit, runtime/image/dependency identity, old/new
legacy comparisons, independent probes, constant-generation verification and
protected-source/test-preservation review:
`evidence/w1-remediation/final-validation.zip` with its SHA256SUMS.
Per-finding failing-first evidence remains in the sibling directories; the
unaltered original independent review and evidence archive are retained.
No W2/physical-system change, tolerance relaxation, test weakening, history
rewrite or PR merge occurred. Continuous footprint and physical evidence remain
outside W1.

The following sections are historical measurements and the remediation ledger;
this final summary supersedes their interim pending/failed-stage statements.

## Independent W1 review and reopened acceptance — 2026-10-16

The [independent report](W1_INDEPENDENT_ADVERSARIAL_REVIEW.md) reviewed exact
CI-tested SHA `133a96fd6653e4d3b16d71c38e1c70fc38585101`; verdict **CHANGES REQUIRED**.
Its complete original scripts, minimal counterexample manifests, runtime hashes,
CI logs and local W0/W1 replay are preserved in
`evidence/w1-independent-review/review-evidence.zip` with SHA-256 checksums.
All 12 final independent probes executed on Python 3.10.12 / NumPy 1.26.4 /
SciPy 1.11.4 in isolated ROS Humble. Two P1 failures (tangent interval bridging,
approximately 2.67e-6 m station error versus 1e-8 m) and three bounded P2 failures
(cap anchors, exact endpoints, gate subdivision) reopen W1 acceptance.
Existing 48/12/18 + 7 W0 numerical + 4 ROS + 1 installed tests still passed;
legacy failure/skip identities were identical to W0. Passing those original
tests is not evidence that the five findings are resolved.

The numerical tolerances and original geometry contracts remain unchanged.
Remediation will add failing regressions before repairs and publish new evidence;
historical results below are retained as dated measurements.

### F5 gate-direction repair

Command inside the pinned, nonroot/network-none/read-only-source Humble image:
`python -m pytest -q -p no:cacheprovider planner/global_planner/test/test_route_input.py`.
The 12 new geometric subdivision cases first produced 6 failures / 6 passes
with `-k collinear_seed`; after repair all **60 A01 tests pass** (exit 0).
The cases cover scale .01/1/100, full width .0001/.2 m before scaling, and
rotation/translation. Existing malformed/reverse input tests remain passing.
Exact source/test hashes, red/green logs/JUnit and unchanged image identity are
in `evidence/w1-remediation/f5`. EPS remains 1e-9 m; no supported scale restriction
or legal requirement was relaxed.

### F1 tangent-contact interval repair

Pinned command: `python -m pytest -q -p no:cacheprovider
planner/global_planner/test/test_route_corridor.py`. Fourteen new selected cases
first produced **8 failures / 6 passes**; after repair all **32 A03 tests pass**
(exit 0). Cases include the original public preparation counterexample, rotated
and translated tangencies, near-contact cuts, disconnected owner intervals and
authorized shared-cap union. Raw red/green logs and exact source/test hashes:
`evidence/w1-remediation/f1`. The returned interval stops at the first legal-side
contact instead of merging through it. No width inflation, tolerance change or
continuous-footprint certification is introduced.

### F2 bounded metric integration repair

Pinned full A02 suite: **39 passed**, including all 12 original tests and
27 new regressions; 26 new counterexamples failed before source correction.
The original hidden-pocket segment and accepted periodic embedding now satisfy
their unchanged arc/station budgets under the default 100-panel policy.
The 24-case feature-center/width/scale matrix uses an explicit 256-panel policy
with identical tolerances; one difficult case verifies that the default budget
rejects rather than silently returning an inaccurate value. This is a declared
resource increase in that stress test, not relaxed numerical acceptance.

Independent split Gauss256/512 oracles over 14 additional families and five
inverse stations each report maximum length difference 3.89e-15 m and maximum
station residual 9.91e-11 m; all those families succeeded with default100.
Raw failing/initial/final passing logs, JUnit, scoped flake8 and source hashes:
`evidence/w1-remediation/f2`. The mathematical control is documented in
[W1_NUMERICAL_ERROR_CONTROL.md](W1_NUMERICAL_ERROR_CONTROL.md).

### F4 canonical endpoint repair

Five failing-first endpoint regressions now pass in pinned Humble: nonuniform
5/8/17/64-knot curves, every coefficient endpoint and adjacent representable
station, plus tiny negative/subnormal progress retaining the preceding owner.
Exact endpoint stations use the stored compensated cumulative knots. Only a
modulo result rounding to L and local subtraction overshoot within four lap ulps
are normalized; distinct nearby stations are not broadly snapped across owners.
Raw red/green JUnit, logs and source hashes: `evidence/w1-remediation/f4`.
Full combined A02/A03 verification follows after the remaining anchor work.

### F3 exact semantic anchors and coherent source ownership

Before implementation, the reparameterized cap cases and close-event case
failed (3 tests); additional failing-first controls cover unrepresentable global
anchors, the periodic seam and the independently reproduced source-owner
mismatch at a nextafter boundary. All six new cases pass. Scoped A03 is
**36 passed / 2 deselected**; the two unchanged existing extreme negative
candidates currently reach the new conservative integration roundoff floor
before their geometry assertions, and the separate F2 follow-up addresses
that resource/allowance issue rather than weakening those tests.

Independent checks pass: exact cap events only .4e-9 m and 2.1e-9 m apart,
forged metadata rejection, original accepted 163-sample preparation, and 60
source/corridor owner checks around occurrence boundaries on five fixtures.
Raw failing/green/lint logs, original two integration failures and source hashes
are retained in `evidence/w1-remediation/f3`; combined verification follows.

### F2 arithmetic follow-up and complete focused suites

The broad initial 128-eps value-evaluation allowance exceeded tight per-segment
budgets in two unchanged extreme A03 negative candidates. Their exact segments
were captured and two reference regressions failed before the follow-up.
Correctly rounded fixed Gauss32 roots/weights plus an operation-count-derived
32-eps*S*h value allowance restore those cases; the separate 128-eps Bezier box
and positive bound inflation are unchanged. No tolerance, resource default,
input requirement or existing test assertion changed.

Pinned combined run: **49 passed / 36 deselected** (all **47 A02**, including
degree0..63 moment and two tight-budget regressions, plus the two unchanged A03
negative cases). Separate full A03 run: **38 passed**. Scoped flake8 passes.
Generation script, 100-digit decimal roots/weights and moment records, arithmetic
derivation, red/green JUnit/logs and source hashes:
`evidence/w1-remediation/f2-roundoff`. Final A03 log is also retained in
`evidence/w1-remediation/f3`. Full W0/W1 build/install/legacy comparison follows.

Tested source base: `67981ed7964a6d35e1da48f0c22bbd9f6d123d5e`, with W0 changes
identified by [implementation SHA-256 manifest](evidence/implementation-files.json).
No production source or gitlink changes. Final clean-clone verification follows in
STATUS; local logs are evidence, not substitutes for a committed branch identity.

Executed commands:

```bash
scripts/project_a/setup.sh
scripts/project_a/verify.sh all work/final-pinned
bash -n scripts/project_a/setup.sh scripts/project_a/verify.sh scripts/project_a/container_verify.sh
git diff --check
git submodule foreach --recursive --quiet 'test -z "$(git status --porcelain)" || exit 1'
```

Setup and functional runner exit **0**. Image:
`sha256:cd722a05da5819643684d723d61fd59ca07687c9efe9a21ecc40443c739b2d2a`.
Base ROS manifest digest:
`sha256:860e53793ccf575e5369b5e9a19939de2bfcfb46a299954d06f54f2af54fed19`.

| Check | Executed result | Tolerance / scope |
|---|---|---|
| Numerical pytest | **7 passed**, 0 failed/errors/skipped | Synthetic dependency/QP/defect characterization only |
| Analytic active-set QP | PASS | absolute 1e-10 |
| Ordered ellipse QP | finite, max offset 0.6000000000000008 m | bound .60 + 1e-8 m; linearization error .09313225043408788 /m |
| Ordered projected-crossing QP | finite, max offset 0.600000000000008 m | same bound; linearization error .3629228282846315 /m |
| SciPy arc oracle x=t,y=t² | PASS | absolute 1e-12 m, integration estimate <1e-12 |
| Unmodified legacy prep | **FAIL characterized**, expected ValueError | `Input vector should be 1-D`; no patch applied |
| Legacy spline station | **incorrect characterized** | measured .1669380946018666 m max discrepancy at .1 m nominal sampling; differs from historical probe mesh |
| Colcon build/install | **3 packages passed** | f110_msgs, frenet_conversion, global_planner; non-symlink installation |
| Optimizer wheel/import | PASS | unchanged pinned submodule; wheel under output directory |
| Actual ROS/install pytest | **4 passed**, 0 failed/errors/skipped | generated Wpnt/WpntArray CDR, all 9 JSON groups, installed utilities, Frenet |
| Installed straight Frenet roundtrip | PASS | absolute 1e-6 m, rtol=0; no new tracker |
| Runtime isolation | PASS | nonroot; CapEff=0; NoNewPrivs=1; loopback only; readonly root/source |
| Legacy selected colcon tests | **FAIL**: 12 aggregate reports, 0 errors, 10 failures, 2 skipped | colcon test=1, test-result=1; existing lint/XML-schema access |
| A01–A09 / full IQP / continuous legal geometry / cyclic dynamics | **NOT IMPLEMENTED** | no accepted trajectory or product artifact |
| Real course, vehicle, 3D/contact/traction | **UNSUPPORTED / NOT TESTED** | no approved measurements, calibration or hardware work |

[Curated full evidence](evidence/pinned-run/SHA256SUMS) includes JUnit, helper
hashes, exact dependency/OS inventories, runtime identity, QP measurements, build
and wheel output and gzip-compressed raw logs. `run.log.gz` contains selected build
output; `legacy.log.gz` and `legacy-results.txt.gz` preserve the complete red
baseline. `exit-code.txt` refers to functional acceptance, **not** legacy success.
Numerical and ROS test counts are separate; no pure-Python check is called ROS.

TPH QP, IQP handler and preparation hashes match the canonical research values.
The W0 probes call one QP per curve, not the unbounded stock IQP wrapper. Neither
single-QP error is treated as convergence, continuous curvature feasibility or
legal footprint evidence. No margins, widths or release tolerances were weakened.

Initial setup iterations are recorded: collection failed exit 4 before message
build because launch-testing imported neighboring ROS tests. The bounded runner
repair disables plugin autoload for explicit W0 files; legacy tests keep plugins.
`evidence/initial-collection-failure.log` preserves that failure. Direct-only pins
were expanded to a hash-locked numerical/build closure before the final run.

## Repetition from the published source and independent hosted execution

Implementation/test commit: **73afd1f95600da8aac1a29a0aa871aed227b4e49**. A fresh
remote recursive clone ran setup and `verify.sh all work/clean-verify-final`:
exit 0; **7 numerical, 4 ROS and 3 package builds passed**; same 12/0/10/2 red
legacy aggregate; clean source before/after. Both QP measurement reports are
identical to the pinned working-tree run. [Clean-clone evidence](evidence/clean-clone/SHA256SUMS)
records the exact SHA, image and gitlinks. Subsequent closeout changes contain
only documentation/evidence; executable-file hashes remain those in
`evidence/implementation-files.json`.

Independent hosted run [38862974185](https://github.com/Felix-Grote/race_stack/actions/runs/38862974185)
at that SHA: **SUCCESS**, Ubuntu 22.04 GitHub runner, digest-pinned Humble container.
Fetched job logs explicitly show **7 passed in 0.24 s**, **3 packages built in
26.2 s**, **4 ROS tests passed in 1.11 s**, and the same red legacy aggregate.
The locally built image ID there was
`sha256:2af52db62ac0320d2404573e275159da55576e8b62063034105595c10a08d48e`;
local image IDs need not match across rebuilds (documented in RUNBOOK).
[CI metadata/full logs](evidence/ci-73afd1f/SHA256SUMS) and artifact ID/digest are
committed. The artifact ZIP fetch returned HTTP 403; hosted artifact contents
were not inspected. Job logs and metadata were retrieved successfully, and full
Cloud JUnit/inventories are committed independently.

Authored scripts/docs pass syntax/compile/whitespace checks. The imported
execution-plan document retains intentional Markdown hard-break spaces; raw logs
retain their original whitespace. The scoped whitespace check is:

```bash
git diff --check 67981ed HEAD -- scripts/project_a .github/workflows docker-compose.test.yaml .gitignore planner/global_planner/AGENTS.md 'docs/project_a/*.md' ':!docs/project_a/EXECUTION_PLAN.md'
```

Production byte preservation was checked with `git diff --exit-code 67981ed HEAD
-- planner/global_planner/global_planner planner/global_planner/setup.py
planner/global_planner/package.xml utilities controller state_estimation
perception stack_master .gitmodules` and recursive clean-submodule checks (exit 0).

## W1 / A01 — strict selected route input

Base: `6370d0436aabd011d1b885fe1f500644b957b536`. Command:
`scripts/project_a/verify.sh all work/w1-a01-final`, exit **0**.
**39 A01 + 7 W0 numerical + 4 installed ROS passed**, three packages built.
Legacy: 51 collected aggregate, 0 errors, same 10 failures / 2 skipped (the new
39 functional tests also pass under colcon). The initial checkpoint retained one E128 formatting diagnostic in its test file;
a follow-up checkpoint run removes it and adds an enforced scoped flake8 gate. The initial run exposed formatting diagnostics in new
files; corrected before the checkpoint. No legacy assertion was modified.

Six frozen fixtures: S0 forward/reverse/rotated, both selected S2 cycles, S3
crossing with ground/upper-deck occurrences. Acceptance covers explicit complete
cycle/closure, gate order/direction, shared caps, invalid polygons/sides, unknown
surfaces, malformed JSON/duplicate keys/NaN/Inf/booleans, canonical hash mutations,
immutability and ROS/TUM-free import. Annotation tolerance **1e-9 m** within the
coordinate range **|XY| <=1e5 m**. No solver, speed or physical acceptance.
[Raw evidence and exact implementation/fixture hashes](evidence/w1-a01/SHA256SUMS).

Environment setup exit 0; rebuilt image
`sha256:0698a83758f1d8155b2f758ccb148175a2b19b890d0aff39be68c0272be9fbe0`.
A preliminary runner invocation before the image build finished failed at image
inspection; no test result was claimed for that invocation. The completed setup
and subsequent full acceptance are the authoritative results.

A01 follow-up: `verify.sh all work/w1-a01-clean` exit **0**, same counts;
enforced new-file flake8 passes and no new pep257 diagnostic appears in legacy
logs. [Corrected evidence](evidence/w1-a01-clean/SHA256SUMS), parent `6dc2b38`.

## W1 / A02 — periodic canonical metric geometry

Tested parent `cd6749d88139222bd6d4016bee5bb160feb19405` + exact source hashes in
[evidence/w1-a02](evidence/w1-a02/SHA256SUMS). Command:
`scripts/project_a/verify.sh all work/w1-a02-final` exit **0**.
**12 A02 + 39 A01 + 7 W0 numerical + 4 W0 ROS + 1 installed W1 test passed**;
three-package build passes. Legacy 63 aggregate, same 10 failures / 2 skipped;
new-file scoped flake8 passes, no new pep257 diagnostics. Initial focused runs
stopped on new-file formatting errors; corrected before full acceptance.

Analytic `x=t,y=t²`: exact L **1.4789428575445975 m**, computed
**1.4789428575445973 m**; quadrature estimated error **1.364128191450888e-13 m**;
maximum inverse station residual **1.2471490506982263e-10 m** over 51 queries.
The rejected linear-fraction assumption has **0.1670177992500138 m** maximum
error on that mesh. Acceptance <=1e-8 m (roadmap <=1e-7 m); total-lap estimated
arc budget 1e-10 m. Independent nonuniform ellipse Gauss oracle agrees within
1e-10 m; analytic ellipse length within 1e-6 m on 300 nonuniform cubic knots.
Radius-6 circle/reversal tests bound interpolation error separately (5e-6 m lap,
2e-6 m radius, 1.4e-4 /m curvature). All joins/seam tolerance 1e-8.

Tests reject nonperiodic XY/tangent/curvature, interior zero derivative, NaN,
regularity/integration exhaustion, ownership mismatch and nonfinite/unresolvable
progress. Exact coefficient reconstruction, immutable records and periodic
negative/multiple-lap/right-hand queries pass. No optimized/legal swept result.

## W1 / A03 — occurrence-owned original corridor

Parent `61c320e0b5551dc983d5b866460900a3f8428de2` + exact source/fixture hashes in
[evidence/w1-a03](evidence/w1-a03/SHA256SUMS). Command:
`scripts/project_a/verify.sh all work/w1-a03-final`, exit **0**.
**15 A03 + 12 A02 + 39 A01 + 7 W0 numerical + 4 W0 ROS + 1 installed W1 pass**;
three packages built; legacy 78 aggregate / 0 errors / original 10 failures /
2 skipped. Scoped new-file flake8 and installed corridor checks pass. Initial
formatting errors and the notch oracle mismatch were corrected; no legalization
or numerical tolerance relaxed (see DECISIONS).

S3 report: 132 prepared samples at requested .4 m spacing plus inherited anchors;
seed q period **48.76566357269199 m**, actual cubic length **48.77778272770468 m**;
minimum original-normal left/right widths **.3713079805827014/.5699481563955641 m**.
Four unique directed gates, including seam; repeated reftrack/gate results identical.
Fixed asymmetric S3 notch stays on o0 only through two meshes/refit; independent
ray/edge solves agree within **2e-9 m**. Inward allowance **1e-9 m**; full returned
chart Jacobian >=**.05**. No physical-map wall removal changes legal widths.

Adversaries cover altered owner/deck, corrupt/nonmonotone lineage, off-route
refit, unsupported end cap, disjoint ray components, rotated normals, arbitrary
support enlargement, missing/reverse/ambiguous gates, actual folded chart,
overlapping portal brackets and sample/pair budget exhaustion. S0 reverse/rotated,
selected S2 cycles and S3 projected crossing all prepare without topology inference.
This is geometric solver-input preparation, not continuous swept acceptance.

## W1 final adversarial self-review

`verify.sh all work/w1-review` exit **0**: **47 A01 + 12 A02 + 17 A03 + 7 W0
numerical + 4 W0 ROS + 1 installed W1 test passed**; three-package build passes.
Legacy **88 aggregate / 0 errors / 10 failures / 2 skipped**. Compared the failing
report identities directly with `evidence/pinned-run/legacy-results.txt.gz`:
**exact match**; the 76 additional colcon tests pass. Scoped new-file flake8 passes;
no W1 pep257 diagnostic. [Evidence](evidence/w1-review/SHA256SUMS), including the
failure-identity comparison, and [adversarial review](W1_SELF_REVIEW.md).

Additional review regressions reject incorrect numeric types consistently, retain
small polygon area near coordinate-range limits, prevent ownership-cap recrossing,
expose hidden double gate roots and distinguish identical XY/heading repeated
visits. Kernel tolerances and physical scope are unchanged. A03 checkpoint hosted
CI [38866587975](https://github.com/Felix-Grote/race_stack/actions/runs/38866587975)
succeeded at `f4048adac1471c4db03616d5292f06aa83f78a13`; final reviewed source is
subsequently published and independently checked again.

## W1 final publication and continuation

Published production implementation:
**`129c28100cd060d155cafb4a1a4e0469e0855cae`**, branch `project-a/w1-geometry`,
[W1-only draft PR #1](https://github.com/Felix-Grote/race_stack/pull/1) against
`project-a/w0-cloud-foundation`. PR creation in the fork succeeded; no merge.

Fresh recursive remote clone at that SHA: setup +
`verify.sh all work/w1-clean-verify` exit **0**, clean source before/after,
**47 A01 / 12 A02 / 17 A03 / 7 W0 numerical / 4 W0 ROS / 1 installed W1 pass**,
three-package build; 88 legacy aggregate / 10 original failures / 2 skips.
[Clean-clone evidence](evidence/w1-clean-clone/SHA256SUMS).

Independent **push** CI run
[38867033917](https://github.com/Felix-Grote/race_stack/actions/runs/38867033917)
at exactly that SHA: **SUCCESS**. Retrieved job logs explicitly show 47/12/17,
7 numerical, 4 ROS, 1 installed, three-package build and original red baseline.
All setup/test/artifact steps succeeded. [Full job logs/metadata](evidence/w1-ci-129c281/SHA256SUMS).

Two additional final regressions exercise the new end-cap recrossing and gate
endpoint rejections directly. `scripts/project_a/verify.sh all work/w1-final`
exit **0**: **48 A01 + 12 A02 + 18 A03 + 7 W0 numerical + 4 W0 ROS + 1 installed
W1 passed**, no errors/failures/skips; three-package build passes. Legacy now
**90 aggregate / 0 errors / 10 failures / 2 skipped**; 78 new passing tests.
Failure identities compare **exactly** with W0. New-file flake8 passes; no new
pep257 diagnostic. Production module bytes equal the clean clone/CI-tested
`129c281`; final commit adds tests/docs/evidence only.
[Final evidence and full implementation hashes](evidence/w1-final/SHA256SUMS).

The final closeout commit itself also runs CI (Project A docs are in the workflow
path filter). Its exact SHA and verified run are reported in the delivery message;
`git rev-parse HEAD` and the branch Checks identify it without a self-referential
hash in its own contents. W1 has no outstanding technical blocker. Proceed to
W2 A04–A06 **from that final W1 HEAD**, preserving these gates. A07–A09, accepted
optimized/continuous-footprint/dynamic artifacts and physical deployment remain
unimplemented/unapproved.
