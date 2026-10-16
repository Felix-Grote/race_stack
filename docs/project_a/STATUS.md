# Project A status — 2026-10-16

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
