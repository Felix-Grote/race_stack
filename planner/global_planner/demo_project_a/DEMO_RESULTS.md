# Project A Demo — Results (technical meeting summary)

- Git HEAD: `e7cd76914bee5719bc2645b42c73193b7745ddf1` (branch `ao/forzaeth-project-a/root`, demo files uncommitted)
- Runtime: CPython 3.10.12, numpy 1.26.4, scipy 1.11.4, quadprog 0.1.7,
  trajectory-planning-helpers 0.79, matplotlib 3.10.9
- Command: `PYTHONPATH=planner/global_planner .venv-demo/bin/python scripts/run_project_a_demo.py --all`
- Output: `demo_project_a/output/run-20261106-093958/` (figures + `summary.json`;
  a later clean rerun produces an equivalent new directory)

## Evidence matrix (measured)

| Scenario | Compile | Geometry | Dynamics | Reload | Length [m] | Model lap [s] | Runtime [s] | Artifact H (short) | Cyclic closure |
|---|---|---|---|---|---|---|---|---|---|
| S0 ellipse | PASS | PASS | PASS | PASS | 41.287 | 13.762 | 13.1 | `b26dd9942cfa` | yes |
| S1 Route A | PASS | PASS | PASS | PASS | 41.886 | 13.962 | 11.4 | `ae60fefb832a` | yes |
| S1 Route B | PASS | PASS | PASS | PASS | 42.518 | 14.173 | 14.2 | `63e93ab10ee8` | yes |
| S2 bridge lemniscate | PASS | PASS | PASS | PASS | 49.216 | 18.222 | 14.2 | `7a7f9279b94b` | yes |

S1 comparison (same model/policy, manually selected routes — no branch
selection by the planner): Route B is 0.63 m longer and 0.21 s slower
under the synthetic model; both independently validated.

## Adversarial results (S3)

| Case | Intended stage | Observed |
|---|---|---|
| A1 disconnected transition | input validation | `RouteError: seed must meet directed end caps` |
| A2 reversed portal gate | input validation | `RouteError: invalid portal end caps` |
| B tampered artifact under original H | trusted loading | `ArtifactError: externally trusted artifact H mismatch` |
| C tight hairpin (κ beyond support) | geometry stage | `GEOMETRY_FAILURE: folded/degenerate local chart`, no artifact published |

No invalid case produced an accepted artifact.

## Tests

`pytest planner/global_planner/test/test_project_a_demo.py -q` → **5 passed**
(deterministic fixtures, schema/portal validation, S2 surface ownership at
overlapping XY, S0 compile→reload→query with cyclic closure and speed-limit
checks, tamper rejection).

## Verified vs unverified

- Verified: synthetic software correctness through the real IQP optimizer,
  retimer, and independent validators; immutable publication and trusted
  reloading; occurrence/surface semantics at overlapping XY.
- Unverified: real-car behaviour, 3D bridge clearance, ROS integration,
  autonomous route/branch selection (explicitly not implemented in E1).
