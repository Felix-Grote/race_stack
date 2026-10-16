# Project A validation matrix — W0

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
