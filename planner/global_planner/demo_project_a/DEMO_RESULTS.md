# Project A Demo — Results (technical meeting summary)

- Git HEAD measured: `00befb01116e` (branch
  `ao/implement-the-hardening/pr1-logic`, clean tree; this results file
  is refreshed in the commit immediately following the measured head)
- Runtime: CPython 3.10.12, numpy 1.26.4, scipy 1.11.4, quadprog 0.1.7
  (SHA-256-verified sdist, documented build patches — see
  `scripts/setup_project_a_demo.sh`), trajectory-planning-helpers
  0.79, matplotlib 3.10.9, pytest 8.3.4
- Setup: `scripts/setup_project_a_demo.sh` (clean-room, self-checking)
- Command: `PYTHONPATH=planner/global_planner .venv-demo/bin/python scripts/run_project_a_demo.py --all`
- Exit status: **0** (`suite_ok=true` in `summary.json`); standalone
  `--scenario s3` also verified exit 0 with all adversarial cases
  enforced. Output: a new `demo_project_a/output/run-<timestamp>/`
  (figures + `summary.json` with per-scenario `run_report` diagnostics)

## Evidence matrix (measured)

| Scenario | Compile | Geometry | Dynamics | Reload | Length [m] | Model lap [s] | Runtime [s] | Solver iters | Curvature energy seed→opt | Speed range [m/s] | Artifact H (short) | Cyclic closure |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S0 ellipse | PASS | PASS | PASS | PASS | 41.287 | 13.762 | 11.0 | 3 | 1.208→1.007 (−16.6%) | 3.00–3.00 | `b26dd9942cfa` | yes |
| S1 Route A | PASS | PASS | PASS | PASS | 41.886 | 13.962 | 9.3 | 3 | 1.141→0.988 (−13.4%) | 3.00–3.00 | `ae60fefb832a` | yes |
| S1 Route B | PASS | PASS | PASS | PASS | 42.518 | 14.173 | 10.5 | 3 | 1.005→0.963 (−4.1%) | 3.00–3.00 | `63e93ab10ee8` | yes |
| S2 bridge lemniscate | PASS | PASS | PASS | PASS | 49.216 | 18.222 | 10.9 | 3 | 2.397→2.362 (−1.4%) | 2.07–3.00 | `7a7f9279b94b` | yes |
| S4 braking circuit | PASS | PASS | PASS | PASS | 53.867 | 18.607 | 22.3 | 3 | 2.194→1.848 (−15.8%) | 2.29–3.00 | `dc91087401f2` | yes |

S1 comparison (same model/policy, manually selected routes — no branch
selection by the planner): Route B is 0.63 m longer and 0.21 s slower
under the synthetic model; both independently validated.

S4 is the braking/acceleration-rich evidence: speed varies over the
full 2.29–3.00 m/s range with distinct braking and acceleration zones
(see its `fig4_velocity`), unlike the flat, static-cap-limited S0/S1
profiles. Full phase timings, per-iteration curvature energies and
retimer statistics are in `summary.json` (`run_report` per scenario).

## Adversarial results (S3 — five cases, four stages, all enforced)

| Case | Stage | Observed (asserted: class + reason / status + no artifact) |
|---|---|---|
| A1 whole-occurrence translation | input validation | `RouteError: disconnected portal seeds` |
| A2 reversed portal gate | input validation | `RouteError: invalid portal end caps` (validator checks end caps before direction; the direction check is unreachable by gate reversal) |
| B valid-JSON tampered artifact under original H | trusted loading | `ArtifactError: externally trusted artifact H mismatch` |
| C tight hairpin (κ beyond support) | optimizer geometry preparation | `GEOMETRY_FAILURE: folded/degenerate local chart`, no artifact published |
| D valid S0 route, oversized footprint | independent geometry validator | `FAIL: demonstrated actual rectangle midpoint exit`, no artifact published |

No invalid case produced an accepted artifact, and any case accepting,
or rejecting with the wrong class/reason/status, makes the runner
exit nonzero.

## Tests

`pytest planner/global_planner/test/test_project_a_demo.py -q` →
**15 passed, 1 skipped** on the pinned environment (deterministic
fixtures; schema/portal validation; isolated A1/A2 rejection reasons;
S0/S1/S2/S4 compile→reload→query with cyclic closure; S2 accepted-ref
ownership at the XY crossing with the 2.5 m/s upper-deck cap; S4
non-flat braking profile; valid-JSON tamper H-mismatch; hairpin and
footprint-validator rejections; figure-table mapping and occurrence
boundaries; run_report trimming; suite exit-status predicate). The
skipped test is the committed-fixture byte-equivalence gate, which
activates once the stacked fixtures PR lands the JSON files.

## Verified vs unverified

- Verified: synthetic software correctness through the real IQP
  optimizer, retimer, and independent validators; immutable
  publication and trusted reloading; occurrence/surface semantics at
  overlapping XY; braking-rich cyclic speed profiles under the
  synthetic model; five enforced rejection paths.
- Unverified: real-car behaviour, 3D bridge clearance, ROS
  integration, autonomous route/branch selection (explicitly not
  implemented in E1).
