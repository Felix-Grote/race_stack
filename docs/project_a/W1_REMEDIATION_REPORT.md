# W1 independent review remediation report

16 October 2026 · ForzaETH Project A · PR #1 · A01–A03 only

## Decision and exact source

All five confirmed findings have corrective implementations and failing-first
regressions. The corrected mathematical/preparation implementation is commit
`becfe8fc46e7490e8857f630a37f0617f477da71` on
`Felix-Grote/race_stack`, branch `project-a/w1-geometry`. Its base remains
`6370d0436aabd011d1b885fe1f500644b957b536`. The independently reviewed defective
revision was `133a96fd6653e4d3b16d71c38e1c70fc38585101`.

**Local verification: PASS. Publication acceptance requires successful independent
GitHub Actions on the exact final containing commit.** The final delivery records
that commit SHA and exact run URL after the workflow completes. Documentation
and evidence closeout do not change the corrected production/test bytes; compare
the recorded source hashes rather than treating an earlier CI run as final-head
evidence. [Branch workflow runs](https://github.com/Felix-Grote/race_stack/actions?query=branch%3Aproject-a%2Fw1-geometry)
and [PR #1 checks](https://github.com/Felix-Grote/race_stack/pull/1/checks) expose
the independent publication gate. The PR remains unmerged.

W2 may begin from the final corrected W1 HEAD once that exact-head gate is green.
This means acceptance of the stated mathematical, route-input and corridor-mesh
foundation. It does not grant A05 continuous swept-footprint acceptance or any
physical vehicle certification. No W2 implementation was performed.

## Resolved findings

Paths use `GP=planner/global_planner/global_planner`.

| Finding | Correction | Regression evidence |
|---|---|---|
| F1 P1 — tangent boundary intervals joined | `GP/route_corridor.py:203` unions positive interior overlaps; a touching separator is removed only at an explicitly declared shared portal gate. Ordinary side tangencies and support-mask cuts remain separate. The origin-containing component stops at the first boundary. | Original full route/prepared sample, rotations/translations, near-contact and disconnected-owner cases; authorized shared caps remain supported. Eight selected failures before repair; final complete A03 passes. |
| F2 P1 — ~2.67e-6 m station error | `GP/route_reference.py:118` integrates exact coefficient speed using Gauss32 with an analytic Taylor-derivative remainder bound and explicit arithmetic allowance. Conservative boxes and bounded heap refinement reject unresolved/resource-exhausted cases. Speed-extrema roots accelerate but cannot authorize acceptance. | Single cubic, accepted periodic embedding, strictly monotone near-minimum cubic, feature center/width/scale/partial-query matrix, independent split-Gaussian oracles, resource exhaustion. Twenty-six failures before the main correction. |
| F3 P2 — exact cap event receives upstream cap | `GP/route_corridor.py:140–155` evaluates known q anchors at their source segment/t and derives s, preserving exact semantic events. Cap ordering has no global EPS smear. Unrepresentable ordering rejects. | Original warped-circle cap event now retains exact q and 1 m/s; distinct sub-EPS events and forged fields are checked. Separate failing-first resolution/seam/source-owner controls also pass. |
| F4 P2 — endpoint/seam owner inconsistency | `GP/route_reference.py:375–409` returns canonical cumulative stations at exact endpoints, maps upward-rounded negative modulo to the representable predecessor of L, and normalizes only bounded local subtraction overshoot after selecting the owner. | Five failing-first controls, every endpoint and adjacent representable station on nonuniform curves, tiny negative/subnormal progress. No broad tolerance snap across occurrences. |
| F5 P2 — scale-dependent gate rejection | `GP/route_input.py:218` compares signed normal travel in metres, dividing the gate/travel cross product by gate length before applying unchanged EPS. | Twelve width/scale/rigid-motion subdivision cases; six failed before repair. All 60 A01 tests now pass. |

During combined review, a nextafter query just before an occurrence boundary
exposed an additional manifestation of F3/F4: the coefficient kernel retained
the preceding segment while rounded q selected the next corridor owner. Ordinary
metric samples now retain q in that source segment's directed representable
half-open interval, and the declared owner must agree. Exact semantic anchors
still use their right-hand source knot. Sixty independent cross-module boundary
queries now agree without explicit rejection. Refits and corridor queries strictly
validate the complete sample against the same coefficient authority.

## Numerical repair and the rounding follow-up

The former QUADPACK estimate missed a narrow regular speed feature and then
validated its own inaccurate inverse. The new bound is independent of quadrature
sample agreement. On a panel, quadratic derivative Bezier controls bound speed
below by m and its derivative norms by D0/D1/D2. Taylor bounds for squared speed
are `G1=2D0D1`, `G2=D1²+D0D2`, `G3=D1D2`, `G4=D2²/4`, zero thereafter.
From `f²=g`, the recurrence
`Fk=(Gk+sum(Fj*F(k-j)))/(2m)` bounds `|f^(k)/k!|`.
The n-point Gauss remainder is bounded by
`h*(n!)^4/((2n+1)*((2n)!)²)*F(2n)`.

The original 1e-10 m whole-lap arc budget, 1e-8 m station tolerance, default
100-panel budget and all other NumericPolicy values are unchanged. Some hard
stress cases declare 256 panels explicitly; a default-budget rejection is
tested and is not silently converted into a plausible numerical value. The
original demonstrated segment and periodic counterexamples succeed under the
default policy.

Combined testing caught an overly pessimistic initial arithmetic allowance that
rejected two unchanged extreme negative A03 candidates before their intended
geometry checks. Those exact coefficients were preserved as two new failing
reference regressions. The follow-up fixes Gauss32 roots/weights to correctly
rounded constants, generated with a 100-digit Decimal Legendre recurrence, and
uses an operation-count-derived 32-eps*S*h quadrature-value allowance. Separate
128-eps box/remainder inflation and final-sum allowance remain. No existing test
body or assertion was weakened. Independent 120-digit regeneration matches every
stored binary64 constant; maximum degree0…63 mapped moment error is 1.3301e-17.

The derivation, explicit floating-point model and retained generators are in
[W1_NUMERICAL_ERROR_CONTROL.md](W1_NUMERICAL_ERROR_CONTROL.md) and
`evidence/w1-remediation/f2-roundoff`. These controls are numerical software
assumptions, not a machine-checked IEEE-754 proof or an A05 legal-geometry certificate.

## Executed verification

Pinned environment: Ubuntu 22.04.5 / ROS Humble / Python 3.10.12 / NumPy 1.26.4 /
SciPy 1.11.4 / pytest 8.3.5 / TPH 0.79 / quadprog 0.1.7. Image:
`sha256:8c9c36d25927e34e03ab3e9978bd1a1a56ab4f60a7ec57ce90c17c053c7ab8d3`.
Execution uses nonroot UID1000, read-only source/root, network none,
no-new-privileges and no effective capabilities. Pip consistency and scoped
new-source flake8 pass.

Commands:

```bash
scripts/project_a/setup.sh
scripts/project_a/verify.sh all work/remediation/validation/w1-final
```

The setup is the existing safe, standalone test path; no hardware Compose or
stack launch was used. A fresh W0 replay also executed its unchanged complete
runner from a verified exact W0 archive in the same image; all 656 archive blobs
were checked against the W0 tree. The final W1 replay uses the actual clean
corrected git worktree. Checkpoint logs preserve red runs before source changes.

| Gate | Fresh W0 | Corrected W1 |
|---|---|---|
| A01 / A02 / A03 | Not present | 60 / 47 / 38 passed |
| Original numerical checks | 7 passed | 7 passed |
| Actual installed ROS checks | 4 passed | 4 passed |
| Installed W1 module/geometry check | Not present | 1 passed |
| Selected packages built | 3 passed | 3 passed |
| Separate legacy aggregate | 12 reports / 10 failures / 2 skips | 157 reports / 0 errors / 10 failures / 2 skips |
| Failing/skipped identities versus W0 | Baseline | Exact match |

The legacy failures remain red and separate from functional acceptance: CMake
formatting, XML-schema access and existing flake8/pep257 cases. CI's `all` mode
records them as warnings; the independent exact-identity comparison is therefore
retained instead of interpreting a green workflow as legacy lint success.

Independent adversarial replay against the final four production-file hashes:

- 18 regular low-speed/non-retracing curve families, including rigid transforms
  and reversal, all accepted under default100; 90 inverse queries. Maximum
  length difference **3.914e-15 m** and station residual **9.901e-11 m** versus
  independent split Gauss256/512 oracles.
- 24 randomized periodic curves with **408** exact/adjacent endpoint queries.
- **32** transformed tangent/microgap normal cases; returned first-component
  upper widths never exceed the first supported contact.
- Exact three cap events separated by .4e-9 m and 2.1e-9 m; original accepted
  **163-sample** warped-route preparation; forged metadata rejects.
- **60** cross-module occurrence/seam boundary queries with consistent owners
  and no rejection; narrow-gate collinear subdivision invariant.

All six independent groups pass with stable source hashes. A separate reviewer
checked final code, formulas, constant generation, source/pin preservation and
existing-test preservation. All 32 original helper/test function bodies remain
unchanged by AST comparison; only new tests/imports were added. Original maps,
legacy planner/interfaces, vehicle code, optimizer pin, dependencies, locks and
test isolation files are unchanged. All seven recursive gitlinks match W0.

## Commits, evidence and reproducibility

Corrections are incremental fast-forward commits on the same PR branch:

| Commit | Purpose |
|---|---|
| `78f44e4` | Preserve original independent findings/evidence; reopen acceptance |
| `5864423` | F5 dimensional gate direction |
| `74cebe0` | F1 contact topology |
| `eed1cb5` | F2 independently bounded integration |
| `27d9c35` | F4 canonical endpoints |
| `f3edd0d` | F3 exact anchors and owner coherence |
| `becfe8f` | Fixed Gauss constants and derived evaluation rounding |

The unedited original report is [W1_INDEPENDENT_ADVERSARIAL_REVIEW.md](W1_INDEPENDENT_ADVERSARIAL_REVIEW.md).
Its complete original evidence/reproducers are in
`evidence/w1-independent-review/review-evidence.zip`. The repair regressions are
in the three existing `test_route_*.py` suites, so the original runner and CI
execute them. Per-finding red/green logs, JUnit where applicable, source hashes,
constant generator and arithmetic derivation are in `evidence/w1-remediation`.
The final-validation archive contains full-suite logs/JUnit, fresh W0 comparison,
independent scripts/runtime/source maps, final summaries and reviewer evidence.
SHA256SUMS accompany retained evidence.

An intermediate exact-head CI run at `74cebe0` passed; it is historical evidence
only and does not substitute for the final containing commit's required push CI.
The final handoff records that final SHA and CI URL after completion; no
self-referential hash is fabricated in this committed report.

## Remaining limits and W2 continuation

No confirmed finding remains unresolved. W2 must preserve these contracts:

- Load original route authority through `load_route`/`validate_route`; public
  record construction is an internal/factory trust boundary, not an authenticated
  untrusted-object parser. Use original owned borders and supplied q throughout
  every refit; no global nearest-XY association or width transport shortcut.
- Resource/roundoff uncertainty fails closed. Very close events remain distinct
  when representable; unresolved event ordering or too-short interpolation edges
  reject rather than silently disappear. Larger resource budgets must be explicit.
- A03 checks prepared samples, directed portal roots and sampled chart validity.
  A05 still must independently validate actual final spline/footprint containment
  between nodes. A04 optimizer iterations and A06 cyclic dynamics remain future
  work. Holes are explicitly unsupported/rejected in v1.
- No real-course approval, sensed wall coverage, 3D bridge clearance, tire/contact
  model, controller behavior or physical safety certification was established.

Once exact final-head push CI passes, **W2 can safely begin using the repaired W1
as its stated mathematical and topological software foundation**. Keep A05/A06
acceptance separate from numerical optimizer success. Do not merge PR #1 or
deploy physical systems as part of this remediation.
