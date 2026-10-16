# Final literal coverage and completeness review

Three promoted regressions pass in the pinned environment: **3 passed,
57 deselected in 8.75 s**, exit 0, stable source/fixture/harness hashes. Strict
flake8 --max-line-length=99 is clean (exit 0). promotion-closeout.json contains
the exact selected command; each file is explicitly included in the full runner.
The final hosted workflow executes all tests without this selection filter.
No production numerical code, model tolerance or original fixture changed.

The explicit ellipse has semiaxes 8/5 m, true-arc/nonuniform-mesh independent
96/48-point oracles, active curvature limits, closing-edge and independent
dynamics PASS. Wrong S3 deck ownership FAILs at the same XY legal in both
projected ribbons despite success/false-clearance claims. The narrower original
S3 notch (0.935959 m vs adjacent 1.192171/1.142275 m) gets a supplied 1 m/s cap
for .25 m of inherited progress; unchanged geometry/coefficients/q are retained,
retiming applies the cap and upstream braking, and independent dynamics PASSes.
Reference acceleration may include drag; the declared longitudinal axis acts
on a+c*u, as documented. None is a physical-car measurement.

The independent completeness map records the original literal test gaps;
promotion-closeout.json records their resolution. Prior scratch outputs and the
first three-test run are historical; a module-docstring line was wrapped before
final strict lint and frozen acceptance. No assertions/budgets were weakened.

independent-zero-motion retains a separate source-stable 3-test adversarial
review and exact reproducer. Reproduce it with unit.sh and that test file path.
It is independent review evidence, separate from primary suite counts: all-zero
injected solver success returns structured INCONCLUSIVE; isolated zero and
below-floor numerical candidates independently FAIL. Numerical CANDIDATE is
never an acceptance verdict. No production change was needed.

Full original/derived route identities, coefficients/q/owners, explicit models,
profiles, metadata, relevant certificates and oracle errors are compressed here.
The extra ellipse/notch unit cases establish dynamics; only the main seven fresh
pipeline cases claim both independent geometry and dynamics on the same final
reference. All evidence is synthetic planar software only.
