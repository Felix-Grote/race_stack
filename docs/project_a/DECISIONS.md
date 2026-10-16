# Project A decision ledger

## 2026-10-16 — Independent review and authorized W1 remediation

- The independent review of exact CI-tested `133a96fd` supersedes the earlier
  self-review acceptance: two P1 and three P2 findings are reproducible.
  Preserve the original report and complete hashed reproductions as historical
  evidence; do not rewrite the report to imply the original source was correct.
- The user explicitly lifted read-only restrictions and authorized incremental
  commits and normal pushes to `project-a/w1-geometry`, PR #1. Recheck remote head
  before pushing; never force-push, merge, or overwrite concurrent work.
- Repair original A01–A03 contracts with failing regressions and pinned Humble
  evidence. Do not loosen tolerances, infer connectivity, inflate widths, or
  introduce W2/physical-system implementation. Independent final exact-head CI
  and a new adversarial examination are required before restoring acceptance.

### F5 — Dimensionally consistent gate direction

Divide the gate/travel cross product by nonzero gate length before comparing
with the original 1e-9 m uncertainty threshold. The result is signed normal
travel in metres, so harmless collinear seed subdivision cannot be mistaken
for reversed/tangent direction merely because the gate is narrow. Keep all
nondegenerate/endcap/topology checks and EPS unchanged. The failing-first
regressions include rigid motions and geometric scaling, not just one fixture.

## 2026-10-16 — W0 environment and ownership

1. **Path D selected by execution**, not assumption. Host Debian 13/Python 3.12 has
   no native ROS. Managed local Docker works and runs digest-pinned Ubuntu 22.04 /
   Humble / Python 3.10 without host networking or privileged/device access. Keep
   host untouched; use isolated numerical and actual ROS suites inside that image.
2. **Writable fork route:** upstream `ForzaETH/race_stack` reports pull=true,
   push=false; `Felix-Grote/race_stack` reports push=true. Base matches upstream
   `ros2-humble` at `67981ed7964a6d35e1da48f0c22bbd9f6d123d5e`. Publish review branch
   on the existing fork; never merge upstream automatically.
3. **Re-establish P01 capabilities rather than reuse unpublished files.** Existing
   workspace-only onboarding built messages/Frenet using host network and did not
   build planner. New repo-local setup, isolated Compose, planner install/wheel,
   numerical and serialization checks replace that dependency. No original setup,
   vehicle code, configuration, map or submodule is modified.
4. **Pin kernel, retain helper equations.** NumPy 1.26.4/SciPy 1.11.4/TPH 0.79/
   quadprog 0.1.7 use declared build tools, full numerical dependency hashes and
   versioned apt venv packages. Do not follow optimizer's obsolete dependency file.
   TPH source hashes match research. No global helper patch or optimizer gitlink
   update is made. CasADi imports are not minimum-time verification.
5. **W0 smoke is deliberately limited.** Two single ordered QPs with 64 synthetic
   knots, half-width .75 m, vehicle width .30 m, curvature bound 1/m; finite output
   and nodal offset bound .60 m + 1e-8 m. No convergence, optimized legal curve,
   continuous footprint or vehicle claim. Quadprog analytic tolerance 1e-10,
   independent analytic arc oracle 1e-12 m, installed Frenet smoke 1e-6 m.
6. **Record legacy red independently.** Old selected colcon lint/XML failures stay
   red. `all` gates new functional acceptance and records baseline exit codes;
   `legacy` returns failure. CI warning/report makes this separation explicit.
   No legalization/numerical criterion is weakened to pass W0.
7. **Bounded collection repair:** Humble launch-testing auto-discovery imported ROS
   tests during numerical collection before messages were built. Disable external
   pytest plugin autoload only for explicit W0 files; legacy colcon keeps normal
   plugins. Assertions, source and generated interfaces remain unchanged.
8. **Historical references remain dated inputs.** Vendor byte-identical canonical
   architecture/roadmap and current execution plan. Their workstation paths and
   old SHAs are not fresh evidence. W0 does not act on older A01-only orchestration.
9. **Closeout evidence is separate from executable changes.** Commit `73afd1f`
   was pushed, cloned recursively, retested with clean source and independently
   passed hosted CI. The closeout commit adds documentation/raw evidence only.
   Preserve the exact tested implementation identity rather than imply a
   self-referential final evidence-commit hash.
10. **Branch satisfies publication despite PR restriction.** Actual upstream draft
    PR creation was denied by the GitHub integration. The authorized fork push
    succeeded; deliver its reviewable branch and prepared PR text, without
    requesting routine confirmation or implying that an upstream PR exists.
    CI ZIP retrieval also returned 403, while CI job logs and metadata were
    accessible; preserve those exact logs and do not infer missing artifact data.

## 2026-10-16 — A01 selected input contract

- User-required W0 HEAD takes precedence over the historical rebase instruction.
  Start `project-a/w1-geometry` at `6370d0436aabd011d1b885fe1f500644b957b536`.
- v1 supports simple local ribbons, shared directed end caps and explicit portal
  support/progress brackets. Connectors require their own occurrence. Reject holes,
  alternate graph fields and disconnected cap contracts instead of guessing edges.
- Portal support is a restriction on adjacent original legal regions, never an
  additive polygon that could inflate legality. A03 will enforce this intersection.
- Use private planar predicates, no new geometry dependency/framework. Coordinate
  range <=1e5 m, distance ambiguity 1e-9 m; later charts may reject valid input.
- Canonical binary64/NFC/integral/-0 normalization and frozen tuples are documented
  in W1_GEOMETRY.md. Physical provenance/coverage remains a separate input identity.
- Legacy colcon discovers the new functional tests too: aggregate count grows;
  compare failure identities and scoped new-file lint, not just total count.

## 2026-10-16 — A02 metric authority

- Use SciPy periodic interpolation only to obtain exact stored normalized cubic
  coefficients. Load/reconstruct from those coefficients without a refit.
- Allocate 1e-10 m estimated integration error across the entire lap, use
  compensated cumulative sums, and enforce 1e-8 m inverse residual. QUADPACK
  estimates are numerical control, not a formal interval/continuous legal proof.
- Conservative derivative Bézier boxes reject zero/uncertain derivative or
  exhausted budgets. All joins/seam check XY, unit tangent and signed curvature
  at 1e-8; normalized parameter derivative magnitudes may differ.
- Owners are explicit per ordered segment. Pure `sample/locate/window` has no
  mutable closest index/history. Unresolvable huge progress is rejected.
- Independent tests use analytic integration, fixed Gaussian quadrature, complete
  elliptic integral and independent polynomial differentiation. Preserve the W0
  legacy metric-defect characterization alongside the new inverse regression.
- Add explicit NumPy/SciPy ROS package dependencies and a separate installed pure
  module check; preserve the original four W0 ROS tests and all entry points.

## 2026-10-16 — A03 original ownership and progress

- q is inherited piecewise original seed metric. Repeated resampling inserts
  occurrence, cap and portal bracket anchors; refits must retain those anchors
  and source segment/t/q. Never infer correspondence from XY.
- Re-intersect current normals with original owner; only an explicitly active
  adjacent portal permits a union, clipped by support. Shared cap removal is
  specific to that portal. Support is never additive legal area.
- Use only the connected normal interval containing the reference. Disconnected
  intervals, unlike a continuous legal union at a declared cap, cannot bridge gaps.
  Inset widths by 1e-9 m, require full chart Jacobian >=.05; reject rather than
  narrow an invalid chart or inflate a legal corridor.
- Polynomial gate intersections prove local directed portal passage within q
  brackets. q alone is not passage evidence. Full continuous final-curve and
  footprint validity remain A05, deliberately not implemented here.
- Bound same-occurrence normal-pair checks to 1000000 comparisons. Unrelated
  deck/occurrence normals are not globally rejected; their overlap is legal input.
- A notch oracle initially compared a fitted normal to its analytic generating
  normal at 2e-9 m. The observed ~2.2e-8 m difference was interpolation, not arc
  or intersection error. Correct the oracle to independent ray/edge linear solves
  on the actual fitted normal; keep 2e-9 m intersection tolerance and separately
  declare 1e-6 m generating-geometry approximation. No production tolerance changed.

## 2026-10-16 — W1 final adversarial hardening

Self-review added explicit numeric type validation, seed ownership-cap recrossing
rejection, translation-stable compensated polygon area, stationary-value checks
for potentially hidden tangent gate roots, and rejection of endpoint ambiguity.
Eight A01 and two A03 regressions were added. Identical XY/heading repeated
visits remain distinct by supplied ordered progress. No tolerance was weakened.
See W1_SELF_REVIEW.md. CI now triggers on Project A documentation too, so final
closeout commits receive actual exact-HEAD validation; artifact names cover W1.

Closeout adds direct cap-recrossing and gate-endpoint regressions; production code
is unchanged from `129c281`. Final local counts 48/12/18; fresh clone and push CI
at `129c281` pass with 47/12/17 plus unchanged W0/install checks. Retain those
source/test identities separately. The W1 draft PR targets the fork's W0 branch
because the foundation has not yet been merged upstream; PR creation succeeded.
