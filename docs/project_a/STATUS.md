# Project A status — 2026-10-16

**W0 COMPLETE. W1 REMEDIATION IN PROGRESS. A04–A09 NOT STARTED.**
No accepted optimized trajectory, continuous footprint certificate or physical
vehicle result exists. Independent review of `133a96fd6653e4d3b16d71c38e1c70fc38585101`
found two P1 and three P2 defects; W2 foundation acceptance is blocked pending
regression-first repairs and independent exact-head CI. The user authorized
autonomous corrections on this same branch without rewriting history.

The original [independent adversarial review](W1_INDEPENDENT_ADVERSARIAL_REVIEW.md)
and its [hashed evidence/reproducers](evidence/w1-independent-review/SHA256SUMS)
are preserved. Findings: F1 tangent normal contacts, F2 metric error control,
F3 semantic cap anchors, F4 endpoint ownership, F5 gate predicate scale.
The sections below retain the historical pre-review W1 completion evidence;
this current remediation status supersedes its acceptance claims.

### Remediation checkpoint progress

- **F5 repaired:** gate direction uses signed normal travel in metres, independent
  of gate width. Twelve subdivision/rigid-motion/scale regressions were executed
  first: 6 failed / 6 passed before repair; full A01 now **60 passed** in pinned
  Humble. Red/green JUnit, logs and source hashes: `evidence/w1-remediation/f5`.
- **F1 repaired:** touching open normal interiors remain separated unless their
  contact lies on an explicitly declared shared portal gate. Failing-first
  tests: 8 failures / 6 passes; full A03 now **32 passed**. The actual sampled
  tangent-notch route retains its first legal component. Evidence:
  `evidence/w1-remediation/f1`.
- **F2 repaired:** speed integration now uses Gauss32 with an independent
  derivative-remainder/roundoff bound and bounded refinement. Original segment,
  periodic and non-retracing counterexamples meet unchanged default tolerances;
  hard stress cases use an explicit larger panel budget or fail closed. A02:
  **39 passed**, with 26 failing regressions preserved before implementation.
  Independent 14-family/70-inverse-query check passes (worst station residual
  9.91e-11 m). Evidence: `evidence/w1-remediation/f2`.
- **F4 repaired:** exact coefficient endpoints return canonical cumulative
  stations; tiny negative modulo retains the preceding owner in the half-open
  domain; bounded prefix-subtraction roundoff does not change the selected owner.
  Five new endpoint regressions failed before repair and now pass. Evidence:
  `evidence/w1-remediation/f4`.
- F3 and final combined numerical/geometry verification remain in progress;
  no final acceptance or final CI claim yet.

## Source and review route

- Repository: `Felix-Grote/race_stack`, durable branch **`project-a/w1-geometry`**.
- Required W0 starting branch `project-a/w0-cloud-foundation` fetched and verified
  at exactly **`6370d0436aabd011d1b885fe1f500644b957b536`**. W1 branches from that
  SHA; it was not reset/rebased onto upstream `ros2-humble`.
- [Draft PR #1](https://github.com/Felix-Grote/race_stack/pull/1) targets the fork's
  W0 branch, showing only W1. Both foundation and W1 remain reviewable; no merge.
- All seven recursive submodules remain pinned and clean. Optimizer unchanged:
  `b1b38ecfefec7200d5bcb243f115af1d795b3766`. Legacy planner/entry points, original
  maps/config, control/localization/actuation and messages remain unchanged.

| Checkpoint | Commit | Acceptance and evidence |
|---|---|---|
| A01 input | `6dc2b38dd7862ed81410f474161c53dc68ab2c77` | 39 input tests + W0; `evidence/w1-a01` |
| A01 style follow-up | `cd6749d88139222bd6d4016bee5bb160feb19405` | 39 tests, enforced new-file style; `evidence/w1-a01-clean`; CI 38865240952 SUCCESS |
| A02 metric kernel | `61c320e0b5551dc983d5b866460900a3f8428de2` | 12 kernel tests + A01/W0/install; `evidence/w1-a02`; CI 38865798545 SUCCESS |
| A03 corridor | `f4048adac1471c4db03616d5292f06aa83f78a13` | 15 corridor tests + A01/A02/W0/install; `evidence/w1-a03`; CI 38866587975 SUCCESS |
| Adversarial hardening | `129c28100cd060d155cafb4a1a4e0469e0855cae` | 47/12/17 checkpoint tests; `evidence/w1-review`; CI 38867033917 SUCCESS |
| Final closeout | Commit containing this status | Two additional cap/gate regressions, final 48/12/18 tests; `evidence/w1-final`; final HEAD is `git rev-parse HEAD` on this published branch |

The final closeout changes tests/documentation/evidence only; production module
bytes match independently tested commit `129c281`. Source/fixture/runner hashes
are committed per checkpoint. CI also triggers on Project A documentation, so
the final closeout commit receives its own exact-HEAD CI check. The final delivery
message supplies that exact HEAD and actual run URL/result; no self-referential
commit hash is invented within this file.

## Final verified capability

A01: strict canonical v1 selected directed complete cycle; unique occurrences,
explicit surfaces/shared-cap portals/gate order, side/seed geometry and provenance,
physical-map identity separate from legality, frozen records and deterministic
identity. Seven fixed JSON fixtures: S0 forward/reverse/rotated, both S2 selections,
S3 crossing and asymmetric S3 notch. Adversarial same-XY/same-heading repeated
visits preserve distinct supplied occurrence ownership.

A02: exact immutable periodic cubic coefficients; nonzero derivative checks,
whole-lap budgeted true-arclength integration and bracketed metric inverse;
stateless `sample/locate/station/window`, right-hand knots/seam, +X CCW heading and
signed curvature. Parabola inverse error **1.2471490506982263e-10 m**; old linear
fraction error **.1670177992500138 m** on the same oracle mesh.

A03: inherited monotone seed q and cap/occurrence/portal anchors through metric
resampling/refits; unique directed polynomial portal roots; signed normal
intervals against original owned ribbons, adjacent support only when declared;
no disjoint-gap bridging or boundary inflation. Reject corrupt ownership,
off-route/ambiguous geometry, unsupported caps, folded/intersecting local charts
and exhausted budgets. TUM rows/normals are geometric solver input only.

## Executed final checks

`scripts/project_a/verify.sh all work/w1-final`, exit **0**:

| Check | Result |
|---|---|
| A01 / A02 / A03 | **48 / 12 / 18 passed**, no errors/failures/skips |
| Original W0 numerical / installed ROS | **7 / 4 passed**, unchanged tests |
| Installed W1 geometry/corridor | **1 passed**, imports resolve under `/work/install` |
| Colcon build | **3 passed**: f110_msgs, frenet_conversion, global_planner |
| New-file flake8 / new pep257 diagnostics | PASS / none |
| Legacy colcon baseline | **90 aggregate / 0 errors / 10 failures / 2 skipped**; 78 new passing tests; original failure identities match W0 exactly |
| Recursive pins / legacy and vehicle source preservation | PASS |

Fresh remote recursive clone at `129c281` ran setup and full verification, exit 0,
source clean before/after: **47/12/17 + 7 W0 numerical + 4 W0 ROS + 1 installed**;
same original failure identities, 88 legacy aggregate reports. Its production
modules are byte-identical to final closeout. [Clean-clone evidence](evidence/w1-clean-clone/SHA256SUMS).
[Hosted CI 38867033917](https://github.com/Felix-Grote/race_stack/actions/runs/38867033917)
at that SHA completed **SUCCESS**; retrieved full logs explicitly confirm the
same counts/build and retained baseline. [CI metadata/logs](evidence/w1-ci-129c281/SHA256SUMS).

See [RESULTS](RESULTS.md), [decisions](DECISIONS.md), [geometry contract](W1_GEOMETRY.md),
[adversarial self-review](W1_SELF_REVIEW.md) and [reproduction](RUNBOOK.md).
No technical or permission blocker remains. PR creation in the fork succeeded.

## W2 continuation instruction

**Resume from the exact published W1 HEAD reported with this delivery, on
`Felix-Grote/race_stack:project-a/w1-geometry`; create
`project-a/w2-solver-validation` from that HEAD. Preserve W0/W1 infrastructure and
run the committed verification suite first. Read execution/status/decision/results,
canonical architecture/roadmap and W1_GEOMETRY. Implement A04 bounded whole-lap
TUM IQP adapter, A05 independent continuous geometry/footprint validation and A06
cyclic retiming/independent dynamics validation sequentially, with committed
checkpoint evidence, original-boundary re-intersections after every iteration,
analytic/adversarial tests and actual hosted CI. Do not treat W1 preparation as
continuous acceptance. Do not implement A07–A09, live tracking or vehicle-facing
changes in W2; preserve optimizer gitlink unless separately authorized.**
