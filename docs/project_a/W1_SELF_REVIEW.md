# W1 adversarial self-review — 2026-10-16

Reviewed production modules, tests, fixtures, runner/installation boundary and
canonical A01–A03 acceptance against the actual implementation. No sub-agents or
external physical evidence were used. This is a self-review, not independent human
approval. Independent *numerical oracles* are identified separately below.

| Concern | Finding and executed resolution |
|---|---|
| Incorrect topology abstraction | One selected ordered cycle; separate unique occurrence/surface IDs. No graph search, nearest XY correspondence or runtime state. Added a double-visit same-XY/**same-heading** test: two supplied progress values return different owners. S2 alternatives load/prepare separately; S3 crossing cannot change owner. |
| Strict malformed input | Review found numeric strings/lists could yield inconsistent type exceptions, and map registration values were not individually checked. Enforce numeric fields explicitly; seven new malformed-type tests require RouteError. |
| Unstable area computation | Global cross-product sums lose small local area far from origin. Translate polygon coordinates before compensated area summation; a 0.1 mm square near XY=99999 m remains valid under the declared predicate policy. |
| Ownership end caps | Seed edges now reject recrossing internal ownership caps. Portal support is a mask on adjacent original ribbons; an arbitrarily enlarged support cannot enlarge legal width. Unsupported connector/endcap geometry rejects. |
| Root-solver blind spot | Cubic double roots can appear as a complex pair. Independently inspect stationary polynomial values within an error allowance, reject uncertain/collinear/tangent contacts and gate-endpoint ambiguity. A cubic with double contact plus a real crossing exercises the omitted-root failure. Actual periodic missing/reverse/multiple-crossing fixtures reject. |
| Metric unsoundness | Parabola analytic oracle catches the known linear-parameter defect. Independent Gauss integration/polynomial differentiation/ellipse integral verify the same coefficients. Total-lap integration budget, compensated cumulative sums, checked inverse residual and derivative regularity are explicit. QUADPACK estimates are not presented as formal interval certification. |
| Boundary inflation / lost notch | Original legal chains remain authority; inward 1e-9 m allowance. Signed widths are recomputed under rotated normals after refit/resampling. S3 notch stays on its own deck; 2x2 independent intersection oracle uses the actual fitted normal. Invalid Jacobian is rejected, never truncated or inflated. |
| Resource/complexity | Four small pure modules including one private predicate module; no new dependency or geometry framework. Pairwise same-occurrence normal checks are deliberately simple and capped at 1000000 comparisons. Max-sample, regularity and integration exhaustion reject. W2 must characterize solve scaling rather than claim S6 performance now. |
| Inadequate regression separation | New suites are explicit gates; new-file flake8 enforced. Original four installed ROS checks remain intact; one additional installed W1 check proves imports resolve under /work/install. Legacy failure identities compare exactly with the committed W0 baseline, despite 76 added passing colcon tests. |
| Scope creep | Legacy planner/map/config/control/localization/actuation files and all optimizer/submodule gitlinks remain unchanged. No A04–A09 solver, speed, artifact/export, tracker or runtime service is implemented. |

Final self-review suite: `scripts/project_a/verify.sh all work/w1-review`, exit 0:
47 A01, 12 A02, 17 A03, 7 W0 numerical, 4 W0 ROS and 1 installed W1 test pass;
three-package build passes. Legacy remains 10 failures / 2 skipped, 88 aggregate
reports; exact original failure identities are unchanged. Numerical and fixture
identities are in `evidence/w1-review`. New-file flake8 passes; no new pep257
warning appears in the legacy log.

Remaining limits are deliberate checkpoint boundaries: mesh preparation is not
continuous whole-curve/footprint acceptance; q is necessary correspondence, not
physical passage evidence by itself. A03 does additionally check actual local
directed portal roots. Holes and arbitrary non-shared connector caps are rejected;
connectors require explicit occurrences. No measured real course, 3D clearance,
contact, traction, calibrated vehicle envelope or optimized trajectory is approved.
W2 A04–A06 must implement the solver and independent continuous/dynamic gates.
