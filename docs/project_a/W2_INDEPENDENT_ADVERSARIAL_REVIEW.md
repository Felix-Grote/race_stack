# ForzaETH ICRA27 Project A — W2 independent adversarial review and remediation

**Technical review: both demonstrated defects are repaired and independently verified. Final publication gate: pending.** Full corrected local/installed verification and exact-code push CI pass on `37b36ccc1f33300ce50e6c120c886147db11b4a7`. This report does not issue ACCEPT for its own future containing commit. The companion final publication manifest and final delivery must identify that commit and completed exact-head CI, then issue exactly one verdict: ACCEPT, CHANGES REQUIRED or UNVERIFIABLE.

## Identity, authorization and review boundaries

| Item | Independently established value |
|---|---|
| Repository / implementation PR | `Felix-Grote/race_stack`, https://github.com/Felix-Grote/race_stack/pull/2 |
| Feature branch | `project-a/w2-optimization` |
| Initial reviewed implementation | `e852641849b2497efea51dfca5ead38ad4476235` |
| Corrected W1 baseline / exact merge base | `9440c2ce68e3dee549de7efacff1cf723fe830df` |
| Original findings and red evidence commit | `e6f9bc0510e729441749692a9bfab97a6138ea73` |
| F1 corrective implementation commit | `6b778519de74b09a7b66be2ac89e12d687226c9d` |
| F2 original findings/red evidence commit | `cba5ee5bea8d60cae7899bc1c1ee877c2870a925` |
| F2 corrective / final implementation commit | `37b36ccc1f33300ce50e6c120c886147db11b4a7` |
| Final publication SHA | The Git commit containing this report; its literal SHA and completed exact-head CI are bound in the companion final publication manifest after commitment |
| Initial exact-head push / PR CI | [38893830596](https://github.com/Felix-Grote/race_stack/actions/runs/38893830596) / [38893836597](https://github.com/Felix-Grote/race_stack/actions/runs/38893836597), both SUCCESS |
| Corrective code push / PR CI | [38904027148](https://github.com/Felix-Grote/race_stack/actions/runs/38904027148) / [38904034170](https://github.com/Felix-Grote/race_stack/actions/runs/38904034170); checkpoint identities retained, superseded for acceptance by final corrected-code CI |
| Final implementation push / PR CI | [38906194264](https://github.com/Felix-Grote/race_stack/actions/runs/38906194264) SUCCESS / [38906201603](https://github.com/Felix-Grote/race_stack/actions/runs/38906201603) SUCCESS; PR merge-ref success is not a substitute for exact-head push CI |
| Final publication exact-head CI | Pending the containing documentation commit; required by the publication procedure below |

Phase I deliberately left implementation unchanged, reconstructed the contracts from actual source, and retained counterexamples before repair. Phase II applied the user's write authorization to the same PR branch, added failing-first coverage, committed F1 and F2 as separate coherent corrective changes after separately preserving each original finding, and pushed without rewriting history. PR #2 remains unmerged; no W3 implementation, hardware change or physical deployment was authorized or performed. Instructions embedded in the uploaded technical report, particularly its W3 continuation prompt, were treated as historical claims rather than current task instructions.

All seven recursive gitlinks and clean checkouts match corrected W1:

| Path | SHA |
|---|---|
| `base_system/f110_simulator/f1tenth_gym` | `f8f8c9d4781d44a2959bae013f276410cb4e9da0` |
| `base_system/f110_simulator/f1tenth_gym_ros` | `163020c0b631a5bdd9ddc59e6132337cec04cc27` |
| `base_system/f1tenth_system` | `5d6490fc6426deb1254198020133a85c0614f183` |
| `base_system/f1tenth_system/ackermann_mux` | `ed4eac7284d13cae66628688e6fd32e585a96a62` |
| `base_system/f1tenth_system/teleop_tools` | `09938461991ec2260ddab6db8ac962f46d205669` |
| `planner/global_planner/global_planner/global_racetrajectory_optimization` | `b1b38ecfefec7200d5bcb243f115af1d795b3766` |
| `sensors/vesc` | `2fd19be756544693752d3e5b36c128e6157e4bd3` |

## Independently verified implementation and evidence inventory

The complete initial W1-to-W2 diff contains 285 files: four added production numerical modules, four top-level Project A documents, 260 evidence files, 12 test/fixture files, and five harness/workflow files. The inventory appendix `inventory.json` lists every path, byte count, SHA256, diff line counts and category. The initial 23 pre-existing ordinary planner source/test/fixture blobs and the optimizer gitlink are unchanged. The F1 remediation changes the two W2 validation entry points, report identity, their call sites/tests and documentation/harness coverage. The later F2 correction intentionally changes one W1 primitive, `_route_geometry.line_intervals`, to give an undirected shared edge a single floating arithmetic representation; its exact diff, independent AST review and dedicated regressions are recorded in the review index. The remaining W1 kernel/corridor/input modules and original fixtures remain intact. Initial byte preservation and the justified later repair must not be conflated.

| Component | Source and principal mechanisms inspected |
|---|---|
| A04 numerical adapter | `iqp_route_adapter.py`: original-border intersections before each QP and after shifted fits, monotone inherited source segment/t/q, q-scaled periodic TUM fit, right-positive offsets, damping, exact shifted coefficient retention, matrix conditioning/primal checks and bounded fit/QP children |
| A05 independent geometry | `route_validate.py`: exact rational polynomial/Bernstein bounds, outward square roots, exact polygon/body predicates, exact shared-cap unions, directed finite-gate root isolation, initialization, whole-interval rectangle/disc sweep and fail-closed resource decisions |
| A06 cyclic retimer | `cyclic_retime.py`: static cap/model applicability before LP, true-arc edges and seam, squared-speed constraints, asymmetric axes, drag/motor, optional steering, bounded table snapshots and source hashes, model/profile identity and metadata |
| A06 independent checker | `route_validate_dynamics.py`: independent route/curve/model/metadata reconstruction, rational inequalities, independent support/constraint logic, closing edge, violation witnesses, time enclosures and unsupported/uncertain decisions |
| Shared trusted primitives | W1 `route_reference.py`, `route_corridor.py`, `route_input.py`, `_route_geometry.py`; independent source/analytic/precision controls specifically challenge their correlated use |
| Permanent W2 tests | Original adapter/geometry/bounds/retimer/dynamics/oracle/ellipse/pipeline modules, new `test_route_w2_handoff.py`, `test_route_w2_numerical_oracle.py`, and independent `test_route_w2_trace_oracle.py` used by fresh seven-case pipeline tests |
| Verification and installed behavior | `container_verify.sh`, `verify.sh`, `unit.sh`, `source_manifest.py`, native installed-package numerical pipeline and actual ROS serialization checks, GitHub workflow |
| Project contracts | `W2_NUMERICS.md`, `STATUS.md`, `RESULTS.md`, `DECISIONS.md`, `EXECUTION_PLAN.md`, package AGENTS, canonical architecture/roadmap, corrected W1 remediation report, uploaded W2 report and raw numerical records |

The actual pinned helper sources were read, not inferred from their descriptions: `opt_min_curv.py` SHA256 `a2ce75c33498426a5276e5b3455f2059040e8c5e5e54734aee3dde0436bef46d`, `calc_splines.py` `2943a4cb0c614a541551a8c6d031cf43b18b81b701221ac02ae51337fbf075a8`, and `iqp_handler.py` `b764ff805fd5585a6dfb30e23b1c0b3ef667c91d66129dca78d9b37a356f65ae`.

All 263 entries across eleven initial committed W2 checksum manifests match exact Git blobs and working bytes, covering 249 unique evidence files. All 68 uploaded final-CI checksum entries match. The uploaded artifact ZIP SHA256 is `3734c49b76204e5dd6e70f94c73e365ebb21a68c9460ce1d5a0007b382ced967`; its 86-file source manifests agree before/after and with reviewed source. Initial source-manifest SHA256 is `c4430e8fee3faeed14fa178e439b6d84ed610b16b14d38f0edf63ae765cf89b2`. Raw uploaded JUnit totals 299 passing functional tests across fifteen groups, separate from legacy failures. These integrity checks verify provenance/counts, not mathematical correctness.

## Confirmed finding F1 — P1: independently approved final q authority was missing

Initial source references are `route_validate.py:554` onward (route/curve/q reconstruction and structural ownership tests) and `route_validate_dynamics.py:575` onward (candidate/profile self-digest comparison). A05 checked monotone q, occurrence anchors, owners and gate applicability, but had no separately retained final A04 identity. A06 compared the profile digest to the candidate's own coefficient/q digest. Coordinated downstream replacement could therefore change the accepted original-seed correspondence and regenerate every self-hash.

The minimal reproducer uses the actual S0 A04 coefficients. Add an original-seed cap of 0.1 m/s over q=[3,3.01] m. Leave every coefficient and owner unchanged and replace internal q values only in 1<q<8 by

```python
q_new = q + 1.5 * sin(pi * (q - 1) / 7) ** 2
```

This remains strictly monotone and retains occurrence, initialization and portal anchors. Retiming under the changed q regenerates a consistent profile and all candidate digests. The same speed profile then violates the original cap correspondence.

| Observation | Initial source | Required / corrected behavior |
|---|---|---|
| Geometry with coordinated q/profile replacement | PASS | FAIL against retained original A04 authority |
| Independent dynamics with replaced q and regenerated profile digest | PASS | FAIL against retained original A04 authority |
| Same coefficients/profile restored to original q | FAIL: original static/model speed violation at edge 14 | FAIL remains; the changed profile is actually invalid under intended cap placement |
| No independent final expectation supplied | PASS on a feasible fixture | INCONCLUSIVE, never PASS |
| Malformed expected identity | No such API | FAIL |

The exact original q arrays, statuses, curve digests and complete original probe/red test evidence are preserved by the findings commit and `phase-i/original-handoff-reproducer.zip`. Initial canonical and altered curve digests are respectively `2a2179ba122458e00c1f01d76e3b984cd38d15e7a68a3639a6ccdf533f984545` and `6e37d46a730e211e4939baafd41e1c4bf5f33aa2d48a76b66b66877be4af86b8`.

F1 is a demonstrated authority boundary failure under the explicit intermediate-tampering scope. The inequalities were valid under the supplied changed q map; this is not a false enclosure of body clearance, curvature or acceleration, nor evidence that A04 computes incorrect q. Final displaced coefficients cannot uniquely reveal historical original-seed ancestry. The W1 factory/internal-record trust boundary explains the old behavior but does not satisfy this review's post-A04 corruption requirement.

Correction `6b778519de74b09a7b66be2ac89e12d687226c9d` adds keyword-only `expected_curve_digest` to both validators and the lazy dynamics facade. The expectation is captured immediately from the trusted, separately audited final A04 return, before downstream processing; neither profile metadata nor a hash recomputed after corruption can supply approval. It binds all coefficients, q entries, owners, original route digest and NumericPolicy. A05 independently recomputes it after original-route and Curve reconstruction; A06 uses its separately implemented identity reconstruction. Missing expectation is INCONCLUSIVE; malformed or mismatched expectation is FAIL. Every original mathematical check remains necessary.

Corrected references: A05 required-input guard `route_validate.py:573`, complete actual hash and comparison `:639`, full report identity `ValidationReport.curve_digest`; A06 guard `route_validate_dynamics.py:577`, independent comparison `:585`; source pipeline `test_w2_pipeline.py:51` and installed pipeline `scripts/project_a/tests/test_w2_installed.py:25` capture one expectation and require both PASS report hashes and profile/metadata hashes equal it. New permanent handoff regressions include coordinated rehashing, different geometry/dynamics authorities, missing/malformed/mismatched expectations and facade forwarding. A monkeypatched false optimizer digest helper cannot authorize A05.

This is an explicit trusted input contract, not an authentication system or a claim that an arbitrary supplied hash proves optimization history. Models, footprint and independent validation policies remain separately supplied trusted authorities. The full A04 history is independently replayed from the approved seed using different periodic-spline equations. Custom initial coefficient/q authorities require their own caller approval. An attacker replacing the trusted producer or the independently retained expectation is outside this repaired handoff boundary.

No other verified P0/P1 intrinsic geometry or dynamics defect was established. No legal margin, numerical tolerance, feasible domain or production acceptance inequality was relaxed. Code review confirms 28 geometry helpers and 21 dynamics helpers are AST-identical, and original assertions are unchanged apart from supplying the new argument; the old pipeline digest equality is strengthened. F1 was repaired as one coherent change after original observations/red tests were separately committed. The later independently generated route revealed F2, documented below and repaired/verified in its separate checkpoint.

## Confirmed finding F2 — P2: reversed shared-edge roundoff splits one legal normal interval

This finding came from a genuinely new full-pipeline route, rather than transforming an existing implementation fixture. The independent generator constructs a 128-interval ellipse with semiaxes 9.7/4.6 m, rotation .37 rad, translation (19.25,-7.5) m, left width .7+.1*cos(3*theta), right width .55+.1*sin(2*theta), four exact shared-cap occurrences and an interior 1 m/s cap on occurrence e1 at local q=[1.37,1.87] m. Original route validation PASSes; the actual seed independently receives A05 PASS with 137 swept leaves. Under the unchanged default A04 policy, geometry checking of the first damped shifted fit nevertheless returns GEOMETRY_FAILURE, `reference outside/ambiguous connected legal interval`, with no completed iteration trace or candidate. A separate replay against the exact old primitive records two geometry calls and one QP: the reference geometry succeeds, then shifted geometry fails before the trace append. The initial interpretation as a failure before the first QP was incorrect; `diagnostic/failure-stage.json` and the corrected committed finding state the proven stage explicitly.

Initial and corrected source reference: `planner/global_planner/global_planner/_route_geometry.py:84` (`line_intervals`), with canonical endpoint orientation inserted at line 90; the deliberately unchanged strict merge is `route_corridor.py:203`. At the e1/e2 shared cap, the same physical polygon edge is traversed in opposite directions by the two occurrence polygons. `_route_geometry.line_intervals` computes each floating line intersection using its received directed endpoints. Different arithmetic/cancellation yields adjacent interval endpoints -7.56631403522638e-14 and -7.25105095042528e-14, creating an artificial positive gap of 3.152630848011e-15 m. The W1 open-interval merge correctly refuses to bridge a positive gap; consequently the reference point near that cap has no connected containing interval. The merge rule is preserving its safety contract; the inconsistent representation of the same exact shared edge is the cause.

The minimal numerical case uses reference point (10.346273849151595,-10.953427375385925), normal (.9350684075601509,.3544673090468617), and exact shared gate endpoints (9.693644707538146,-11.20655817764086) / (10.765821154985087,-10.790700430881152). The separate Fraction oracle interprets the binary64 inputs exactly and obtains the identical rational intersection for both directions:

```text
-6493513456432416 / 89282567569951896214720469081
approximately -7.272991394814918e-14
```

Thus this is a demonstrated preventable false rejection of approved shared-cap geometry, not a real narrow gap, optimizer infeasibility, unsupported union or request to weaken a margin. Evidence is retained in `integration/novel/run1` and `integration/novel/diagnostic`, including the complete independent generator/approved input, red full-pipeline log/JUnit, exact coordinates and Fraction calculation. The initial route digest/file SHA256 is `742b03fa77cef8bfab9f203787ac8dd5435e479a6fddf9449ac4138e83c5a0aa`.

The applied bounded correction canonicalizes the undirected edge endpoints lexicographically before any floating arithmetic inside line_intervals. Identical reversed shared edges then execute identical operations and produce exactly equal cut values. It changes no EPS, clearance, interval merge/touch rule, legal domain or polygon union approval. The new and original W1 controls continue to reject genuine tangent boundary contact and genuine microgaps; only the separately declared exact shared-cap join connects touching open intervals. Preservation records explicitly identify this justified repair of one W1 primitive instead of claiming all W1 source bytes are unchanged.

Independent code review approves the applied four-line canonicalization and confirms that removing only its if/swap restores the complete original line_intervals AST; every other helper, EPS and merge rule is unchanged. Both F1 validators are byte-identical to their approved checkpoint. The new permanent 49-case shared-cap/gap/tangent tests and exact-fixture complete-pipeline test are explicitly wired into CI. Correction `37b36ccc1f33300ce50e6c120c886147db11b4a7` is committed and pushed. The original exact minimal shared-cap test fails on the old primitive (one expected failure in .052 s, stable source). The permanent 49 shared-cap tests together with all 38 original A03 tests pass **87 tests in 49.36 s**, exit 0 with stable source. The independent original novel probe and permanent complete-pipeline regression pass **2 tests in 31.13 s**, exit 0 with stable source. Full final local/installed verification and exact-code push CI subsequently pass on the committed correction; the containing documentation commit still requires its own final publication exact-head CI. The F1-only full run remains a separate retained checkpoint. The relevant W1/F2 tests, full local/installed verification and exact corrected-code hosted CI were rerun after F2; final repaired-source evidence therefore does not depend on the earlier 6b778519 checkpoint.

## A05: mathematical sufficiency and independent geometric challenges

For d=r', g=d·d and c=cross(d,d'), independent differentiation yields

```
kappa = c / g^(3/2)
d(kappa)/ds = (2*c'*g - 3*c*g') / (2*g^3).
```

Exact power-to-Bernstein transforms bound all polynomial products over the complete interval. The derivative lies in its quadratic Bezier control hull: the maximum control-vector norm bounds V above, and distance of the component box from zero bounds speed below. A box containing zero requests subdivision or INCONCLUSIVE; sampled regularity does not grant PASS.

For any body-fixed point z with |z|<=R, P(s)=r(s)+Q(theta(s))z gives P_s=T+kappa*J*Qz, hence |P_s|<=1+R*K. Every point in a parameter leaf is at metric distance at most V*dt/2 from its midpoint, proving displacement <=(1+R*K)*V*dt/2. This covers every rectangle interior point, corner and edge, including curvature sign changes. The separate enclosing-disc criterion follows from center displacement plus R. Each cubic leaf is closed and certified independently; both one-sided join/seam footprints are covered. Clearance must strictly exceed this bound, the unchanged legal margin and numerical allowance.

Position/derivative evaluation and polygon predicates use exact rational binary64 inputs. Only normalization/conversion/square roots use floating arithmetic. The supported coefficient/speed domain avoids derivative-norm overflow/underflow on accepted paths; `512*eps*(1+R)*max(1,V/v_min)` conservatively covers component conversion, stated one-ulp hypot error and standard binary64 division normalization and half-width rounding under the declared model. Rational rectangle construction avoids global-translation cancellation. Scaled rational sqrt conversion prevents squared-value underflow; outward nextafter/ldexp steps enclose representable results, and unrepresentable bounds give uncertainty. This remains conditional on the stated elementary-function model, not a machine-checked floating-point proof.

Whole-body polygon tests cover corners, edge crossings and legal-boundary vertices enclosed by the body. Only explicitly adjacent original ribbons with exact common caps and a simple stitched union can remove their cap, further restricted by portal support. Unknown holes/schema extensions, invalid/ambiguous unions and unsupported topology cannot add legal area. Exact sign-variation gate-root isolation covers directed finite-gate crossings and coefficient endpoints; tangencies, multiplicity or exhausted isolation cannot become sampled PASS. Unrelated bridge surfaces remain occurrence-owned even at identical XY.

Independent controls do not reuse production polygon/bound assumptions: 80-digit Decimal derivative/normalization plus GEOS/Shapely 2.1.2 separately checks full rectangle containment/union/intersection/distance. Across 7,705 bodies from all seven actual candidates, minimum sampled body clearance is 0.019275699389656977 m against a 0.01 m supplied margin; tested movement/curvature/speed values lie within production leaves, maximum movement/bound ratio 0.9999780322709407. These samples attempt falsification; they never authorize continuous acceptance.

Pinned independent primitive challenges add 629 extreme-exponent sqrt cases, 250 random cubic speed/curvature/rate cases, cancellation, near-singular derivatives, large translations and extreme footprint scales. A separate 110-digit campaign checks 20,000 exact sqrt inputs (18,984 enclosed, 1,016 explicitly uncertain), 2,500 normalization/body-corner examples, and 240 analytic arc families (231 supported, nine explicit geometry/budget rejections). No enclosure violation was found. Maximum observed frame-error/allowance is 0.001312055 and actual arc-error/returned-bound 0.019672861. Compact independent tests are now permanent CI coverage.

Original and new adversaries include legal knots with illegal interior curve/body/curvature, narrow notches, concavity and body-edge escape, coincident wrong-deck ownership, tangency, gate phase/direction, illegal unions/holes, initialization, periodic seams, near-zero clearance and exhausted preprocessing/subdivision budgets. No discovered false-positive intrinsic geometry PASS remains in the demonstrated cases. The initial minimum recorded certificate slack 8.949819347124821e-5 m was independently recomputed from raw leaves; no tested conversion/normalization error consumes it.

One exploratory straight-cubic cancellation example produces endpoint tangent error 7.95e-8 rad near parameter speed 1.1e-7, but also problematic floating curvature. It is not a complete accepted-curve counterexample and is not misreported as a false PASS. Binary64 join/frame checks remain a declared numerical limitation; adjacent interval body proofs cover both endpoint orientations.


### Independent geometry checks on the actual final output, at both stages

The external 80-digit Decimal / GEOS oracle was adapted to consume the actual fresh final-full pipeline, not the initial frozen coefficient fixture. It independently checks the complete retained handoff digest, route/owner order and portal applicability, exact certificate partition, full bodies and original margin, derivative/curvature and midpoint movement bounds, and all directed finite gates using analytic derivative critical points plus 80-digit bisection, rather than production Bernstein isolation. It imports no production planner/geometry/corridor/bound/retimer code. On each actual stage it passes **seven scenarios, 1,541 leaves, 7,705 bodies and 28 directed gates**; minimum body clearance is 0.019275699389656977 m and maximum sampled movement/bound ratio 0.9999780322709407.

The full verifier's legacy pass reruns the pipeline and overwrites its JSON with another fresh result. Both actual inputs and oracle results are preserved: initial functional-stage pipeline SHA256 `886a5ae3f048db79bebad842eb24c24f4c1ce4893d35c1ce313555e65afbbf83`, and final retained pipeline SHA256 `fb42f757f888a524be7e8912ba2bb77e9b87f584c59c26cac0e513643bc3f862`. The final oracle reruns after the complete verifier closes. Its source SHA256 is `373c71fd92fc5d11c5aa20ff583cd00ce559bbc5419f6c954643be20d3cb0cad`; its result records 60 explicit source/input/script hashes. Functional and retained stage records differ only in solver timing/RSS diagnostics, not mathematical data. External Python3.12/Shapely2.1.2/GEOS3.13.1 is explicitly an independent oracle environment; production acceptance remains pinned Python3.10/Humble.

## A06: whole-edge dynamics, independent oracles and shared-kernel failure modes

With true edge length D and u=v² affine in arc, a=(u_j-u_i)/(2D), including last-to-first. Nonnegative drag c gives drive term a+c*u; braking uses its negative with the separate negative longitudinal axis. For a whole-edge curvature bound K, supplied axes A+/A-, lateral axis Ay and motor M, sufficient inequalities are

```
 +(a+c*u)/A+ + K*u/Ay <= 1
 -(a+c*u)/A- + K*u/Ay <= 1
 (a+c*u)/M <= 1.
```

These mathematical inequalities are affine in acceleration and u; checking both endpoint u values and both certified D extremes bounds a rectangle containing the physically correlated values. This is sufficient, although conservative. The unchanged numerical checker separately allows a normalized residual of 1e-8 and steering angle residual of 1e-10 rad; these are software acceptance allowances, not an exact zero-residual claim. The actual accepted final profiles have no positive recorded normalized residual. Every relevant original occurrence/portal model budget and cap applies. Optional steering angle is atan(b*kappa); rate is b*|kappa_s|*sqrt(u)/(1+(b*kappa)^2), and replacing its denominator by one is conservative. The exact moving-edge time is 2D/(sqrt(u_i)+sqrt(u_j)), including equal-speed endpoints; outward distance/sqrt bounds propagate to total lap enclosures.

Speed-table interpolation is piecewise linear; full declared-range minima include all interior table knots. Exact rational interpolation followed by inward conversion yields conservative constant limits. The parsed values and source SHA256 derive from the same bounded byte snapshot; extrapolation/missing coverage is unsupported. Independent source reconstruction does not consume candidate residuals, LP rows or claimed constraint applicability.

A distinct 70-digit mpmath oracle, independently generated 24/40-order quadrature and direct derivative/model arithmetic challenges seven retimings at a new 0.613 m requested mesh. It uses no production arc, interval/support, LP-row or residual helper for expected arithmetic. Profiles have 154/154/154/143/139/213/214 knots. Independent edge arcs and times, including closure, and total times lie inside reported enclosures; nine independently evaluated true-arc positions per edge have no positive sampled residual. All 42 digest/time/missing-boundary/negative-speed/overspeed mutations reject. Across 400 scale-varied coefficient boxes, four remain uncertain and all 13,068 independent points in the 396 certifiable boxes satisfy speed/curvature/rate bounds. The entire oracle is rerun after remediation with source-stable exit 0.

New analytic controls use a separate 0.731 m mesh: constant speed 2.3 m/s differs by at most 9.24e-16 in u; the cyclic motor/drag optimum u=M/c for M=.7,c=.23 differs by 3.0435e-9, consistent with the predeclared inward margin. Two unequal narrow cap pulses with asymmetric axes 1.3/.7 are independently solved by directed-cycle distance cones; the 148-knot envelope agrees within 1.2933e-8 in squared speed. Existing analytic cyclic braking, ellipse/nonuniform arc, closing-edge violations, optional steering, motor/drag and table-interior-minimum controls remain.

The checker independently reconstructs constraints but shares W1 metric integration and A05 interval_bounds/_sqrt. A deliberate 1% common arc overestimate makes retimer and checker agree on PASS while the external oracle observes acceleration 1.0099999989845 against an axis of 1. This injection explicitly violates the unchanged trusted primitive's error model; it demonstrates correlated dependency risk, not an actual source defect. The independent analytic arc campaign and high-precision oracles address that risk. Future changes to shared kernels must retain external controls; two-module agreement alone is insufficient.

The shared W1 Gauss32 bound was independently rederived: for the true Taylor coefficients, f²=g implies 2*f*f_k=g_k-sum(f_j*f_(k-j)). Given f>=m>0 and absolute upper bounds G_k and F_j, the bound recurrence is F_k=(G_k+sum(F_j*F_(k-j)))/(2*m). The implemented inflated version bounds the 64th Taylor coefficient, f^(64)/64!, entering the analytic Gauss remainder. Separate coefficient-scale roundoff allowances cover cancellation. No defect in this actual primitive was demonstrated; uncertainty stays fail-closed.


### Independent dynamics on both actual final-output stages

A separate standalone 70-digit mpmath oracle imports no production numerical, geometry, support, hash or retimer helper. It independently normalizes the approved route files and reconstructs route/model/full-curve identities, a circular cap/occurrence/portal event overlay, actual coefficient derivatives, true-arc squared-speed interpolation, acceleration and edge/lap time from independently generated 24/40-point rules. The actual functional-stage records pass one pinned test in 16.78 s, and the final retained fb42 records pass a separate frozen test in 17.73 s. Each covers all seven actual profiles, 1,267 edges and 11,403 dynamic sample points including every seam. Each independent edge distance/acceleration/time lies in its certificate enclosure; total times lie in lap enclosures. The closest sampled normalized residual is about -1.00233e-9; maximum 24/40-rule discrepancy is below 8.58e-55 m.

Exact comparison of both complete pipeline snapshots finds 126 scalar differences, all solver RSS/time diagnostics. Removing only the named resource fields produces identical complete mathematical payloads: coefficients/q/owners/policies, route/model, profile/metadata, numerical history and both certificate sets. Their common canonical mathematical-payload SHA256 is `aef04784288e6c0718db106bfac672cf9e0bd692942f2d9b6466b27d0e2e354e`; no tolerance is used for that equality. Both complete snapshots, successful pinned oracle runs, original functional report, updated review and equality proof are retained in `final-dynamics-evidence.zip`, SHA256 `46705a00eef4bbc803691a68354ff35d509a97e8395d8fa4a0f1b1a64df0d5e8`. These controls remain independent falsification, not sampled replacement certification.

## A04: retained TUM behavior, objective quality and cyclic origin

Source inspection and independent trace replay confirm original occurrence-owned boundary re-intersection at every iteration, right-positive TUM alpha and correct damping, exact inherited segment/t/q, q-scaled periodic fitting, primal/condition checks and final shifted coefficients without an unvalidated refit. Failures expose no final candidate. Fit/QP child processes set address-space/CPU limits before numerical imports and direct-child wall timeouts; parent phases have explicitly cooperative deadlines. The pinned native libraries launch no extra child process in the inspected execution.

The independent trace oracle reconstructs the approved seed and each reference/shifted periodic spline using a cyclic second-derivative system, rather than TUM/Curve.interpolate or candidate hashes. It checks complete source-q ancestry, half-open segment/t inheritance, semantic anchors/owners, normals, damping, eroded nodal bounds and exact final coefficient/q linkage. All seven preserved histories pass; the permanent fresh pipeline repeats the audit and rejects changed final q. This separates actual history evidence from opaque hash agreement.

Independent adaptive integration of actual coefficients confirms S0 curvature energy worsens from 1.0471975680989947 to 1.162781872642269 /m (+11.04%), through 1.0858573260 and 1.1477757015. The analytic radius-six circle has energy 2*pi/6=1.0471975511965976 /m. This is inherent in the retained frozen-derivative surrogate: for circular reference r0 and shifted radius r, frozen curvature is r/r0², favoring contraction while true energy 2*pi/r increases. Scalar QP normalization cannot reverse this direction. Actual right-normal signs, damping and coefficients agree; no avoidable adapter sign/lineage defect was demonstrated. W2 explicitly retains this surrogate and disclaims true-objective descent/global optimality, so no new backend or retroactive quality threshold was introduced.

| S0 measurement | Original origin (.4 m mesh) | Changed origin | Refined .2 m mesh |
|---|---:|---:|---:|
| Iterations | 3 | 3 | 3 |
| Actual energy, /m | 1.162781872642269 | 1.162781872649986 | 1.15989095762 |
| Actual peak absolute curvature, /m | .209266684447123 | .209266685160346 | .29378987281 |
| Synthetic model lap time, s | 8.593509770179757 | 8.593509770331961 | 8.89808722728 |
| Geometry / dynamics | PASS / PASS | PASS / PASS | PASS / PASS |

Fixed identical-mesh cyclic QP permutation agrees to 3.09216008354e-9 m, within the existing 1e-8 m parity budget. Changing occurrence origin phases the uniform metric grid differently before semantic-anchor insertion. At 8,192 independent q-correspondence probes, maximum position difference is 1.546390 mm, tangential component 1.527003 mm and normal component 1.262704 mm; independent polynomial projection shows physical shape difference about 1.262685 mm. It includes a remeshing ripple, not solely relabeling q. Stable conditions, errors, energy and three-step convergence give no evidence of numerical instability or a broken correspondence contract. Finer remeshing raises peak curvature by 40.4% and model time by 3.54%; it is not established as a quality improvement. Exact invariance across changed meshes was never specified. A future stable semantic-anchor mesh phase is a possible explicitly specified quality policy, not a W2 correctness requirement invented after observing data.

Independent adaptive arc/time recomputation agrees with base/origin/refined profile times within 8.89e-15 s, all inside checker enclosures; separate sampled residuals show no positive constraint violation. Seed time 9.42477788473 s is diagnostic only: the seed fails strict directed gate p2 geometry, so it is not a combined accepted reference.


The quality campaign was repeated after the shared-cap repair, with two source-stable tests passing in 49.10 s (`adapter/f2-quality`). The base coefficients/q and all quality/model-time quantities are bit-identical. Changed-origin coefficients differ by at most 3.7658161493661635e-9 m; .2 m remeshed coefficients differ by 5.765940424770633e-10 m. Origin sensitivity remains 1.5463902639211455 mm and projected shape discrepancy 1.2626849932009564 mm. The corrected changed-origin/refined model times are 8.593509770211897 / 8.898074718327077 s; the refined difference from its historical value is -1.2508949208012154e-5 s. Independent arc/time recomputation again lies inside all enclosures, with at most 3.56e-15 s reported-time difference and no positive sampled residual. The preceding table records the original historical quality run; this final rerun shows F2 does not materially alter those conclusions and makes the small discretization/conditioning sensitivity explicit.

### Genuinely new eighth complete pipeline after F2

The independently generated asymmetric ellipse is retained exactly as originally approved: fixture SHA256 `742b03fa77cef8bfab9f203787ac8dd5435e479a6fddf9449ac4138e83c5a0aa`, with no input/width/policy repair. After canonical shared-edge arithmetic, default A04 converges in three IQP iterations with 129 actual final coefficient segments; A05 certifies 330 continuous leaves and 4 directed gates, and A06 uses 221 speed knots. Both independent validators return PASS on retained authority `e8023c26bd60d12d3bbf42a6b4627468eba49dc2220e77d1971705079e0a2666`, equal to profile/metadata identities. The independent periodic-spline lineage oracle also passes the complete new history.

An external oracle imports no production planner modules. It uses 80-digit Decimal exact-binary64 differentiation/normalization, GEOS 3.13.1/Shapely 2.1.2 polygon operations and distinct adaptive QUADPACK arc integration. Across 2,967 complete bodies it finds zero geometry violations and minimum body clearance 0.08830955971564132 m against unchanged 0.01 m margin. Across 3,757 dynamics samples, maximum diamond utilization is 0.9999921634171196, motor 0.7889209381672765, lateral 0.8844398884195922, steering angle 0.09386536337169575 rad and steering rate 1.6160869220823628 rad/s (<3); the supplied original interior speed cap is respected. Independent true coefficient length is 46.242835799711905 m and lap time 13.759213225603533 s, inside [13.759213225499257,13.759213225707809] s. Maximum independently recomputed acceleration/metadata difference is 4.7406523151494184e-14 m/s². These distinct samples/oracles supplement rigorous production certificates and do not replace them.

All raw corrected coefficients/q/owners, complete traces/model/profile/policies and both certificates, exact source/fixture manifests, stable-run JUnit and external oracle source/results are retained under `integration/novel/run3-stable`. The oracle report SHA256 of its input candidate report is `216fba22d34a787863432b91245d4bbfee2b8563a4cbcb5c0fee16f5ff5a8da5`. This case is independently generated beyond the seven inherited fixtures and establishes a complete eighth approved-route→A04→A05→A06→independent-dynamics experiment.

## Cross-module adversaries, resource limits and W1 preservation

All seven original S0/reversed/rotated, S2 upper/lower and S3 surface/notch fixtures are freshly run A04→A05→A06→independent dynamics with one frozen final authority in the permanent corrected source pipeline. Detailed coefficients/q/owners, full traces, models, policies, profiles and both certificate sets are retained. The final retained seven-case output SHA256 is `fb42f757f888a524be7e8912ba2bb77e9b87f584c59c26cac0e513643bc3f862`; its source manifest SHA256 is `c4076eb430c38cd1e1faf956f7830fbdc1a0c3d09136a7f0c8c82b1a2d6bf132`. The actual final values are below, and complete records remain in final-local.zip.


| Final retained scenario | Segments / leaves / speed knots | Geometry / dynamics | Synthetic lap time s | Time error bound s |
|---|---|---|---:|---:|
| s0_route | 98 / 224 / 166 | PASS / PASS | 8.593509770180 | 8.48e-11 |
| s0_reverse_route | 98 / 224 / 166 | PASS / PASS | 8.593509770196 | 8.48e-11 |
| s0_rotated_route | 98 / 224 / 166 | PASS / PASS | 8.593509770234 | 8.48e-11 |
| s2_upper_route | 92 / 170 / 155 | PASS / PASS | 9.411623852760 | 1.01e-10 |
| s2_lower_route | 89 / 164 / 151 | PASS / PASS | 8.587343724789 | 9.38e-11 |
| s3_surfaces_route | 134 / 266 / 231 | PASS / PASS | 16.419262763707 | 1.17e-10 |
| s3_notch_route | 135 / 269 / 232 | PASS / PASS | 16.419182801565 | 1.16e-10 |

All seven retained cases use three IQP iterations and four independently isolated directed gates. Both report digests equal the separately frozen expectation in each case. Maximum final LP residual is 2.8527180617743397e-12; minimum final certificate slack is 8.949819354105348e-5 m.

New metamorphic controls cover quarter-turn rotation, exact algebraic half-subdivision without a refit, translation by (2^14,-2^14) m, similarity scales 1/8 and 16, and S3-notch rotation/subdivision. Similarity scale a scales body/margin/wheelbase by a, curvature policy by 1/a, acceleration/lateral/motor and drag/mass by 1/a, and steering rate by 1/a; speed stays fixed while distances and times scale by a. All seven variations receive both certificates under independently approved transformed authorities; external QUADPACK length/time controls agree. Reversal, cyclic-origin change and remeshing are separately tested with the appropriately transformed ownership/boundary semantics.

Quarter-turn versus half-subdivision retiming times differ 8.59396246115154 versus 8.592439496674894 s (~.0177%): subdivision adds profile boundaries and can tighten conservative curvature bounds. Neither the LP's distance-weighted u objective nor its discretization promises a unique invariant continuum/minimum-time solution.

Nine coordinated faults deny combined PASS: changed route provenance, owner/surface, relaxed numeric policy, nextafter-altered q period, reduced model speed with rehash, excessive speed, geometry uncertainty with dynamics PASS, dynamics uncertainty with geometry PASS, and missing required model. Combined acceptance requires both exact PASS statuses on the same retained authority; INCONCLUSIVE/UNSUPPORTED/disagreement cannot be combined into success. A07 production artifact/compiler work remains W3.

A bounded new 241.274313849015 m scaled input immediately returns RESOURCE_LIMIT, `point budget exhausted before remeshing`, with no traces/candidate under the unchanged default .4 m / 512-point policy. This is a measured default-policy incompatibility with ~240 m S6: .4*512=204.8 m even before semantic anchors. It is not a measurement that larger justified policies or the architecture are impossible. W3 must measure dense-matrix time/memory/conditioning at explicit mesh and child-process budgets; simply raising limits establishes nothing.

At the initial W2 and F1-only checkpoint, the four corrected W1 production modules and three W1 test suites are byte-identical. The later F2 repair intentionally changes only the shared-edge arithmetic in `_route_geometry.line_intervals`; the new regressions explicitly identify that exception and preserve all original W1 test assertions. The final full W0/W1 suites reexecute all five prior fixes: open-interior tangent contact; analytic bounded arc quadrature; exact semantic cap/source anchors; half-open seam/endpoint ownership; dimensionally normalized gate travel. No old fixture, policy tolerance, original map, dependency/gitlink or hardware file is altered.

## Executed verification ledger and retained failures

Acceptance-environment runs use the pinned isolated Ubuntu 22.04 / ROS Humble, Python 3.10.12, NumPy 1.26.4, SciPy 1.11.4 image. Current local image ID is `sha256:78d2201ecb18b242c03348876bc9b5e43128d012e1bf30d571b2244ac2d7a3ae`. Runtime identity records UID1000, only loopback, zero effective capabilities, no-new-privileges and read-only root/source. Host Debian/Python 3.12 identities describe orchestration or explicitly labeled external oracles, not supported route acceptance. Full package/dependency/source/fixture identities accompany every accepted run.

| Run / evidence directory under work/adversarial | Outcome |
|---|---|
| `baseline-full` at e852641 | exit 0; 299 passing functional tests/15 groups, strict lint, three builds, actual ROS and installed W1/W2; source hashes stable |
| `geometry/runtime-primitives` | 3 passed, 1.07 s, exit 0, stable |
| `contracts/final-pinned` | one 20,000-sqrt / 2,500-frame / 240-arc campaign passed, 27.63 s, stable |
| `adapter/runtime-quality-final` | 2 passed, 57.78 s, exit 0, stable |
| `dynamics/pinned-mesh` / `pinned-oracle-analytic` / `pinned-shared-kernel` | one test each passed, 6.08/36.09/1.79 s, stable; final is intentional dependency fault experiment |
| `integration/phase1b` | 3 passed, 117.46 s, exit 0, stable |
| `integration/handoff-red` | 2 failed, 9.31 s, stable original source; retained expected red |
| `geometry/authority-red` / `dynamics/missing-identity-red` | one expected failure each, 7.26/.61 s, stable |
| `dynamics/remediation-focused-frozen` | 72 passed, 68.77 s, exit 0, stable |
| `dynamics/remediation-high-precision-frozen` | independent full oracle passed, 46.71 s, exit 0, stable |
| `integration/handoff-pipeline-green` | 20 passed, 125.95 s, exit 0, stable; fresh seven-case trace replay |
| `integration/phase2-metamorphic` | 3 passed, 107.11 s, exit 0, stable |
| `remediation-red-replay` | original two red regressions plus three permanent numerical controls: 5 passed, 4.15 s, exit 0, stable |
| `corrected-full` at 6b778519, F1-only checkpoint | exit 0; 323 functional tests / 17 groups, zero failures/errors/skips, strict lint, three builds and installed pipeline; source stable; legacy 322/0 errors/10 failures/2 skips exactly matches initial ten identities; does not include later F2 repair |
| New novel-route F2 red run `integration/novel/run1` | Independently approved/seed-certified route; A04 GEOMETRY_FAILURE after one QP, in first damped shifted geometry, due reversed-edge artificial gap; exact Fraction oracle proves identical true roots |
| `geometry/shared-cap-red` | exact old-primitive minimal case fails as expected in .052 s, source stable |
| `geometry/shared-cap-final` | 87 A03 + new shared-cap/gap/tangent tests pass in 49.36 s, exit 0, stable |
| `integration/novel/run3-stable` | 2 independent original/permanent novel complete-pipeline tests pass in 31.13 s, exit 0, stable; external Decimal/GEOS/QUADPACK oracle also passes |
| `final-full` at 37b36ccc, final corrected implementation | exit 0, 373 functional tests / 19 groups, strict new-source 99-column lint, three builds, actual ROS and installed W1/W2, stable exact-source manifests; legacy372/0 errors/10 failures/2 skips with exact inherited identities |
| Final implementation push CI 38906194264 | SUCCESS, job 116990251430, 373 functional/19 groups; independently downloaded artifact 12049420387 exactly matches tested37b36ccc source |
| Final publication hosted CI | Required after the report-containing commit; companion publication manifest records its literal SHA, actual checkout, source/artifact hashes and completed result |

Focused precommit source-identity.txt files name e6f9bc0 with uncommitted corrections; they are accepted only as source-stable focused evidence with matching exact correction bytes, not as final committed-SHA evidence. The F1-only full corrected run supplies its checkpoint gate; the further complete final run and exact corrected-code hosted workflows independently verify the later F2 repair. Only the containing documentation commit publication gate remains prospective. The machine-readable `executed-run-ledger.json` independently parses JUnit, exit codes, source stability and recorded commands; source/fixture hashes are retained rather than substituted by summary claims.

The independently generated novel ellipse failure is retained as verified F2, distinct from test-harness/unsupported-domain failures. All other unsuccessful experiments are retained and classified: out-of-domain 2^20 translation (fixture error, corrected to 2^14); Python 3.12 tiny-semantic-interval uncertainty (unsupported acceptance runtime, no tolerance relaxation); mpmath/Fraction harness TypeError; seed geometry expectation failure; invalid exact semantic inverse/forward-roundtrip assumption; scratch relocation fixture-resolution failure; real missing-authority red results; and source-drift-invalidated runs. In particular, A05's 40 functional passes during live copies, A06's first 72-pass applied run, and promoted compact primitive tests with changed source hashes are explicitly not frozen acceptance evidence. Successful later stable runs supersede them without deleting them.

The initial fresh full legacy aggregate has the same exact ten raw identities as the uploaded original push. They are `lint_cmake`, `xmllint`, three f110_msgs whitespace CMake identities (lines29/42/45), f110_msgs package.xml, and flake8/pep257 for each of frenet_conversion/global_planner. CTest wrappers duplicate some reports; this is ten reported identities, not ten independent defects. The original aggregate is 298 tests/0 errors/10 failures/2 skips. The final local and independently downloaded exact-code CI aggregates are both **372 tests, zero errors, ten failures and two skips**. Parsing the raw failure blocks, rather than trusting the summary, gives exactly the same ten identities as the initial baseline. Existing failures remain visible and are excluded from passing functional counts. CI currently warns/records legacy status but does not automatically enforce the failure identity set; raw comparisons are therefore part of this independent release verification, and automatic identity hardening is a nonblocking maintenance recommendation.


### Exact corrected-code CI and installed-source verification

Push run [38906194264](https://github.com/Felix-Grote/race_stack/actions/runs/38906194264), job[116990251430](https://github.com/Felix-Grote/race_stack/actions/runs/38906194264/job/116990251430), completed SUCCESS on exact implementation 37b36ccc. Downloaded artifact 12049420387 has SHA256 `c980acf5f5df4234914276e4de6d70818554c2285d4324634a0f650645de6aa7`. Independent artifact inspection verifies all 92 source entries match exact Git/pinned optimizer bytes, before/after manifests agree with SHA256 `c4076eb430c38cd1e1faf956f7830fbdc1a0c3d09136a7f0c8c82b1a2d6bf132`, all 373 functional tests/19 groups have zero failures/errors/skips, all seven retained report authorities and the novel fixture match, installed package bytes match source, and raw legacy identities equal the original ten. The full job log, exact downloaded artifact and independent verification JSON are committed separately. This establishes final **implementation** CI, while a later report-containing commit still needs exact-head publication CI.

The final local run independently records the same 92 exact source/fixture/harness files, 373 functional passes across 19 groups and stable source, builds all three packages in 17.3 s, runs four actual ROS checks, and runs installed W1/W2 checks in 1.22/12.69 s. Installed optimizer, retimer and both validator module hashes match the committed source manifest. The local ledger records the individual group counts/durations and installed module identities.

## Remaining limits and W3 prerequisites

The supported result is synthetic planar software under explicit geometry/model/numerical/elementary-function assumptions. Holes and unsupported unions, missing required physical/model coverage, exhausted budgets, unresolved derivatives/roots and nontraversable profiles cannot PASS. This is no tire/contact, 3D bridge/grade/clearance, obstacle, tracking, jerk, actuator, calibrated vehicle or physical-safety certificate. No minimum lap time or exact/global curvature optimum is established. Parent/native deadlines remain cooperative except the documented hard fit/QP child limits.

W3 must begin from the final CI-tested publication identity and preserve the independently approved exact coefficients/q/owners/profile/model/policy through immutable atomic artifact publication, loader/query/CLI/export and installed/ROS roundtrips. It must retain both validators' same-authority conjunction, explicit unsupported cases and external analytic/precision controls for shared primitives. It must benchmark actual energy/peak curvature/model time without invented improvement thresholds, include a fair declared repaired comparator, and measure ~240 m S6 mesh/conditioning/memory/time under justified budgets. Missing real-course approvals or models remain unapproved inputs, not permission to infer physics from surface IDs. These are prerequisites, not W3 implementations performed by this review.

## Publication and final verdict gate

A report cannot contain its own final Git SHA without a self-referential follow-up commit. Commit this self-contained report/evidence after completed local verification; then independently verify the final publication head in hosted push CI. The companion final publication manifest must bind that exact commit, this report's SHA256, complete archive/source hashes, completed run/job/artifact identities and actual checkout evidence. The final chat verdict must name that exact final SHA and run, not an earlier correction or PR merge checkout. Documentation-only publication does not waive exact-head CI.

**Final publication verdict is deliberately not assigned in this committed report.** The final delivery and companion manifest must assign it after the containing commit completes exact-head CI: ACCEPT requires no unresolved demonstrated blocking defect, committed final bytes, complete required local/installed/lint checks, preserved exact ten legacy identities and final exact-head push CI SUCCESS. Use CHANGES REQUIRED if demonstrated blocking defects remain, or UNVERIFIABLE if necessary independent evidence cannot be established. Do not auto-merge PR #2.

## Evidence and exact-command appendices

The committed evidence package retains this report, component reports, machine-readable inventories, source/fixture/environment/checksum manifests, original failing reproducers, corrected handoff/trace/numerical oracle source, per-run JUnit/log/exit codes and numerical records. The final implementation inventory lists 299 changed paths relative to corrected W1; the initial inventory remains separately preserved. See [REPRODUCE.md](evidence/w2-adversarial/REPRODUCE.md) and [SHA256SUMS](evidence/w2-adversarial/SHA256SUMS). The initial full inventory and final code inventory are in [review-index](evidence/w2-adversarial/review-index). Archive member indexes record every retained path/hash; caches, build/install copies and virtualenv binaries are excluded. The original committed Phase I archive remains immutable. Commands below are exact historical run identities; reruns require fresh output-directory names and the same pinned setup. Run the prescribed scripts as a nonroot user against only docker-compose.test.yaml.

```bash
scripts/project_a/setup.sh
scripts/project_a/verify.sh all work/adversarial/baseline-full
scripts/project_a/unit.sh work/adversarial/geometry/runtime-primitives work/adversarial/geometry/test_adversarial_geometry.py
scripts/project_a/unit.sh work/adversarial/contracts/final-pinned work/adversarial/contracts/test_numerical_contracts.py
scripts/project_a/unit.sh work/adversarial/adapter/runtime-quality-final work/adversarial/adapter/test_independent_adapter.py -x
scripts/project_a/unit.sh work/adversarial/dynamics/pinned-mesh work/adversarial/dynamics/test_runtime_mesh.py -x
scripts/project_a/unit.sh work/adversarial/dynamics/pinned-oracle-analytic work/adversarial/dynamics/test_independent_oracle.py -x -s
scripts/project_a/unit.sh work/adversarial/dynamics/pinned-shared-kernel work/adversarial/dynamics/test_shared_metric_fault.py -x
scripts/project_a/unit.sh work/adversarial/integration/phase1b work/adversarial/integration/test_integration_adversarial.py
scripts/project_a/unit.sh work/adversarial/integration/handoff-red work/adversarial/integration/test_handoff_binding_regression.py
scripts/project_a/unit.sh work/adversarial/geometry/authority-red work/adversarial/geometry/test_geometry_authority_failing_first.py
scripts/project_a/unit.sh work/adversarial/dynamics/missing-identity-red work/adversarial/dynamics/test_expected_digest_required.py -x
scripts/project_a/unit.sh work/adversarial/dynamics/remediation-focused-frozen planner/global_planner/test/test_route_validate_dynamics.py planner/global_planner/test/test_cyclic_retime.py planner/global_planner/test/test_route_dynamics_oracle.py planner/global_planner/test/test_route_ellipse_dynamics.py work/adversarial/dynamics/test_expected_digest_required.py -x
scripts/project_a/unit.sh work/adversarial/dynamics/remediation-high-precision-frozen work/adversarial/dynamics/test_independent_oracle.py -x -s
scripts/project_a/unit.sh work/adversarial/integration/handoff-pipeline-green planner/global_planner/test/test_route_w2_handoff.py planner/global_planner/test/test_w2_pipeline.py
scripts/project_a/unit.sh work/adversarial/integration/phase2-metamorphic work/adversarial/integration/proposed/test_integration_adversarial_bound.py
scripts/project_a/unit.sh work/adversarial/remediation-red-replay work/adversarial/integration/test_handoff_binding_regression.py planner/global_planner/test/test_route_w2_numerical_oracle.py -x
scripts/project_a/verify.sh all work/adversarial/corrected-full
scripts/project_a/unit.sh work/adversarial/geometry/shared-cap-final planner/global_planner/test/test_route_corridor.py planner/global_planner/test/test_route_w2_shared_cap.py
scripts/project_a/unit.sh work/adversarial/integration/novel/run3-stable work/adversarial/integration/novel/test_novel_complete_pipeline.py planner/global_planner/test/test_route_w2_novel_pipeline.py
scripts/project_a/verify.sh all work/adversarial/final-full
```

Host-only external oracle commands are `work/adversarial/geometry/oracle-venv/bin/python work/adversarial/geometry/independent_oracle.py`, `python work/adversarial/adapter/quality_oracle.py`, and `python work/adversarial/adapter/profile_time_oracle.py`; their own version/source/input ledgers identify that scope. The two original frozen independent evidence scripts in the earlier W2 report omit the now-required digest keyword: replay them at their recorded SHA or retain a separate scratch-copy migration with an independently captured authority, rather than silently rewriting historical evidence.

The independent novel external oracle is reproducible with:

```bash
work/adversarial/geometry/oracle-venv/bin/python work/adversarial/integration/novel/host_independent_oracle.py work/adversarial/integration/novel/run3-stable/approved-route.json work/adversarial/integration/novel/run3-stable/novel-report.json work/adversarial/integration/novel/run3-stable/host-independent-oracle.json
```
