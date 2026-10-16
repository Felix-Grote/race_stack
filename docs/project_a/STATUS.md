# Project A status — 2026-10-16

**W2 IN PROGRESS. A04–A06 AND FRESH PIPELINES PASS; FULL/INSTALLED/FINAL CI PENDING.**

The current authorized work is W2 A04–A06 on `project-a/w2-optimization`, created
directly at corrected W1 commit
`9440c2ce68e3dee549de7efacff1cf723fe830df`. No rebase or upstream merge occurred.
The exact W1 push CI
[38879680224](https://github.com/Felix-Grote/race_stack/actions/runs/38879680224)
passed. All seven recursive gitlinks match, including optimizer
`b1b38ecfefec7200d5bcb243f115af1d795b3766`.

Fresh safe setup and `scripts/project_a/verify.sh all work/w2/baseline` both exit
0: A01/A02/A03 **60/47/38**, W0 numerical **7**, actual installed ROS **4**,
installed W1 **1**, and three package builds pass. The separate legacy aggregate
is **157 reports / 0 errors / 10 failures / 2 skips**; failing report identities
exactly match W0. [Baseline evidence](evidence/w2-baseline/SHA256SUMS).

The additive A04 adapter preserves pinned TUM equations, uses inherited q-scaled
splines and actual coefficients, recomputes original owned widths each iteration,
and bounds dense fits/QPs in OS-limited child processes. Frozen-source command
`scripts/project_a/unit.sh work/w2/a04-final-stable planner/global_planner/test/test_iqp_route_adapter.py -x`
exits **0: 18 passed**. New-file lint passes and independent adversarial review
accepts the stated numerical-candidate scope. Seven fixtures converge in three
iterations each; maximum observed QP primal violation is **3.45e-15**.
[A04 evidence and review](evidence/w2-a04/SHA256SUMS).
Checkpoint **`604ad5da4cefd2ce5f052a4e71d30d5b5467bd27`** is pushed; exact-head
[push CI 38885077894](https://github.com/Felix-Grote/race_stack/actions/runs/38885077894)
is **SUCCESS**. Retrieved full logs confirm 60/47/38 + 18 A04 + 7/4/1 passing
tests, three package builds and unchanged legacy failure identities (175 reports,
10 failures / 2 skips). [Hosted evidence](evidence/w2-a04-ci/SHA256SUMS).
It returns numerical candidates only. Read [W2 numerical contracts](W2_NUMERICS.md)
for resource/tolerance policy and the measured local-surrogate limitation; actual
curvature energy improvement or global optimality is not established.

Independent A05 continuous geometry and swept-footprint validation now passes
**50 tests in 103.41 s**, exit 0, frozen production/fixture/harness hashes. All
seven actual A04 coefficient candidates receive **PASS**, with **164–269**
continuous certificate leaves and four independently isolated directed gates
each. Exact rational bounds and full-rectangle/disc sweep proofs cover interiors,
every join and the seam. Two independent reviewers accept the planar scope.
[A05 evidence/review](evidence/w2-a05/SHA256SUMS).

A05 checkpoint **`1fea1213896ca6e32eb93dfd14acd18cfdb78701`** is pushed. Exact-head
[push CI 38888550247](https://github.com/Felix-Grote/race_stack/actions/runs/38888550247)
is **SUCCESS**: 225 functional tests pass across nine groups, three packages
build, and all ten legacy failure identities remain unchanged (225 reports,
0 errors / 10 failures / 2 skips). Full logs and exact metadata are retained.

An independent 44-knot S3 adversary has every nodal footprint legal, yet its
between-node exit is correctly FAIL; the retained reproducer passes in 5.07 s.
Unsupported geometry/resources/required physical coverage remain INCONCLUSIVE.
A06 now passes a single globally frozen **70-test** run in **169.24 s**, exit 0:
20 retimer, 34 independent dynamics, eight independent math oracles and eight
fresh whole-pipeline/repeatability cases. Strict 99-column lint passes. Two
independent source/math reviews ACCEPT. All seven freshly optimized S0/reversed/
rotated, S2 alternatives and S3 surface/notch cases receive geometry **PASS** and
dynamics **PASS** on the same final coefficients. Maximum observed LP residual is
**2.853e-12**; independent certificates have no positive normalized residual.
[evidence/review](evidence/w2-a06/SHA256SUMS), [numerical contracts](W2_NUMERICS.md).

Next: full `scripts/project_a/verify.sh all` at the committed A06 checkpoint,
including actual installed W2 pipeline and unchanged W0/W1 regressions, then
exact-head hosted CI, final evidence/report and reviewable PR. W2 is not declared
complete until those gates pass. No immutable A07 artifact or physical vehicle
result is claimed. The historical W1 record below is retained as evidence; this W2
section supersedes its old continuation/status statements.

## Historical corrected W1 status

**W0 COMPLETE. W1 CORRECTED; LOCAL ACCEPTANCE PASS. A04–A09 NOT STARTED.**

All five findings from independent review of `133a96fd` are repaired with
failing-first regressions. The complete pinned W0/W1 suites and independent
adversarial probes pass for corrected implementation
`becfe8fc46e7490e8857f630a37f0617f477da71`. No accepted optimized trajectory,
continuous footprint certificate or physical vehicle result exists.

**Publication gate:** the final commit containing these documentation/evidence
records must independently pass exact-head push CI before W2 uses it. The final
delivery gives the actual final SHA and successful run URL after completion;
do not substitute an earlier run or PR merge checkout. Check [branch workflows](https://github.com/Felix-Grote/race_stack/actions?query=branch%3Aproject-a%2Fw1-geometry).

## Source and review route

- Repository: `Felix-Grote/race_stack`, branch **`project-a/w1-geometry`**,
  [draft PR #1](https://github.com/Felix-Grote/race_stack/pull/1). No merge or
  history rewrite. The live starting head was exactly the reviewed `133a96fd`.
- W0 base/merge base remains
  **`6370d0436aabd011d1b885fe1f500644b957b536`** on
  `project-a/w0-cloud-foundation`; no rebase onto upstream.
- All seven recursive submodules remain pinned and clean. Optimizer:
  `b1b38ecfefec7200d5bcb243f115af1d795b3766`. Original maps, legacy planner,
  interfaces, vehicle systems, dependency locks and test isolation are unchanged.
- Approved route objects come from `load_route`/`validate_route`; direct record
  construction is not an untrusted-input validation boundary.

## Findings and corrective commits

| Finding | Corrective commit | Current result |
|---|---|---|
| F1 P1 tangent side contact bridged | `74cebe0` | Ordinary contact stays an interior cut; only declared shared gates permit touching union |
| F2 P1 metric bound violated | `eed1cb5`, `becfe8f` | Analytic Gauss remainder + explicit arithmetic model; original segment/periodic/monotone examples satisfy unchanged tolerances |
| F3 P2 semantic cap anchors | `f3edd0d` | Exact source q/t events; strict cap order, sample integrity and source-owner coherence |
| F4 P2 endpoint ownership | `27d9c35` | Canonical endpoint station, directed half-open modulo and bounded subtraction normalization |
| F5 P2 gate scale dependence | `5864423` | Signed normal travel in metres, invariant under collinear subdivision |

Original findings/report/evidence are preserved by `78f44e4`; the user explicitly
authorized autonomous corrections on this same PR branch. Read the
[remediation report](W1_REMEDIATION_REPORT.md),
[unaltered independent review](W1_INDEPENDENT_ADVERSARIAL_REVIEW.md) and
[numerical derivation](W1_NUMERICAL_ERROR_CONTROL.md).

## Final local verification

Executed safe setup and prescribed verification:

```bash
scripts/project_a/setup.sh
scripts/project_a/verify.sh all work/remediation/validation/w1-final
```

Both exit **0**. The verified code checkout was clean at `becfe8f`; final closeout
changes documentation/evidence only, with the same production/test hashes.

| Gate | Result |
|---|---|
| A01 / A02 / A03 | **60 / 47 / 38 passed** |
| Original W0 numerical / actual ROS | **7 / 4 passed**, also rerun on fresh exact W0 archive |
| Installed W1 modules/geometry | **1 passed**; installed bytes match source |
| Selected package build | **3 passed**: f110_msgs, frenet_conversion, global_planner |
| Scoped flake8 / pip consistency | PASS |
| Legacy aggregate | 157 reports, 0 errors, **10 pre-existing failures / 2 skips** |
| Legacy identity comparison | Exact match to fresh W0 (12 reports, same failures/skips) |

Image:
`sha256:8c9c36d25927e34e03ab3e9978bd1a1a56ab4f60a7ec57ce90c17c053c7ab8d3`.
Ubuntu22.04.5 / Humble / Python3.10.12 / NumPy1.26.4 / SciPy1.11.4.
Tests use nonroot UID1000, read-only source/root, network none, zero effective
capabilities and no-new-privileges; no hardware Compose or driving-node launch.

Independent final adversaries: 18 difficult arc families / 90 inverse queries
(maximum residual **9.901e-11 m**), 408 endpoint queries on 24 random curves,
32 tangent/microgap normal cases, exact close-cap events/forgery rejection,
60 cross-module boundary queries and gate subdivision. All pass against final
committed production hashes. All 32 original test/helper bodies remain unchanged.

Evidence: `evidence/w1-remediation/final-validation.zip` with SHA256SUMS, plus
per-finding red/green/checkpoint hashes. This preserves original failures and
the arithmetic follow-up discovered during combined validation; it does not hide
them behind an aggregate green result. The legacy checks remain red by design.

## Current capability and limits

A01 validates a strict selected directed cycle with original side boundaries,
surfaces, gates, caps and provenance. A02 provides one exact periodic coefficient
authority with controlled metric integration/inversion and stateless queries.
A03 preserves source lineage, re-intersects original occurrence-owned borders,
checks local charts and actual directed portal roots, and supplies TUM geometry.

No tolerance/default resource limit was relaxed. Hard regular cubics can require
an explicitly declared larger quadrature budget; unresolved uncertainty rejects.
Distinct representable semantic events are retained; unrepresentable event order
and unsupported tiny interpolation edges fail explicitly. Simple ribbon/shared-cap
v1 geometry remains the supported domain; holes are rejected.

A03 is mesh preparation, not continuous legal spline/footprint certification.
A04–A06 optimization/validation/dynamics, A07–A09 artifact/export/benchmarks,
runtime association, physical clearance/contact and vehicle certification are
not implemented. W2 may start after final exact-head CI is green, from that exact
W1 SHA, while preserving all W0/W1 gates. No PR merge or physical deployment is
authorized by this status.
