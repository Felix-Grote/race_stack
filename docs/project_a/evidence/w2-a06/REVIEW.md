# A06 frozen acceptance and independent review

Verdict: ACCEPT for the explicitly supplied synthetic planar model.

Final frozen command (from repository root):

```bash
scripts/project_a/unit.sh work/w2/a06-final-frozen planner/global_planner/test/test_cyclic_retime.py planner/global_planner/test/test_route_validate_dynamics.py planner/global_planner/test/test_route_dynamics_oracle.py planner/global_planner/test/test_w2_pipeline.py -x
```

Exit 0: **70 passed in 169.24 s** (20 retimer, 34 independent checker, eight
independent oracles, eight fresh pipeline/repeatability cases). Full planner,
fixtures, helper and Compose source hashes match before/after. Strict 99-column
flake8 is clean with no ignore overrides; strict source manifests also match.

Production SHA256: retimer
`7ff74dbf3f57500731e5eebb069882d35efc6ed6d2b5805e22c796556286ceb3`;
checker `76e162abd99ef8d6fcc2a4b03cca08929622ef67eb63745a95d2712c3605af08`.
Two independent source/math reviews accept the supported scope. Their retained
JSON reviews describe exact corner inequalities, applicability, steering,
metric/time enclosures, numeric witnesses and repaired resource/input guards.
The small final model-text guard was separately reviewed after the math review.

All seven pipeline cases rerun the actual pinned TUM optimizer; their same final
coefficients pass independent continuous geometry and dynamics. The full trace,
coefficients, q/owners, original route identity, synthetic footprint/model,
numerical policies, speed profiles, regenerated metadata and both certificates
are in w2-pipeline.json.gz. It is numerical evidence, not an A07 immutable
published reference artifact. metrics.json is a derived summary of that file.

Historical concurrent-development runs are labelled exploratory, with real
JUnit/log/hash drift preserved. They never substitute for final acceptance.
The initial duplicate endpoint produced an unresolved zero interval; canonical
endpoint aliases repair it without dropping source constraints. A deliberately
incompatible steering-rate/moving-floor model remains a rejection control;
a separately declared lower-floor model tests feasible slow traversal. Initial
13/15, later 17/17 and 19/19 retimer, 30/30 and 34/34 checker and 6/6 then 8/8
oracle records are preserved. No prior W0/W1 test or constraint tolerance changed.

The analytic cyclic braking envelope agrees within 1.6775e-8 m²/s² against a
predeclared 1e-7 oracle comparison budget; closing acceleration is
-0.999999998991 m/s². Separate known speed and motor/drag optima and 96/48-point
independent derivative quadrature controls pass. Samples/oracles do not grant
continuous acceptance: exact bounds and model residual certificates do.

Synthetic planar software only. No minimum-time/global exact-curvature optimum,
3D bridge/contact/tire/calibration/actuator/tracking/physical-safety claim.
Full W0–W2 and installed-package acceptance are recorded separately after this
checkpoint; native/phase deadlines remain the documented cooperative limits.
