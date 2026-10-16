# A08 reproducible comparison and resource campaign

The campaign evaluates synthetic offline planar software. The unchanged legacy
planner, original maps, ROS messages, optimizer gitlink and installed TPH sources
remain unchanged. No result establishes race readiness or physical car safety.

## Reproduction protocol

Run `scripts/project_a/benchmark_w3.py` in the pinned Project A Humble image,
with explicit `--repo`, `--fixtures` and a new writable `--output` directory.
The script writes and fsyncs `manifest.json` before executing any attempt. It
freezes all route bytes, model values, footprint, numerical/proof policies,
dependency versions, helper/source hashes and every planned attempt. The
append-only `attempts.jsonl` preserves successes, failures, timeouts and retries.
Each result has a deterministic gzip file containing actual authority,
optimization traces, lineage and independent validation witnesses. The summary
is a projection of these results, never an acceptance certificate.

Each worker has an external 240 s wall/CPU limit and 3 GiB address-space limit;
its process group is killed on timeout. The accepted A04 child limits remain
20 s wall, 20 s CPU and 2 GiB address space, with one numerical thread. The
whole-lap solver limit remains 120 s, 512 points and 1e12 condition number.
All original geometry and dynamics proof policies remain unchanged. Phase
records include wall and parent/child CPU time, peak process memory, fit/QP
resources, N/iterations, condition/residuals, original-corridor re-intersection,
continuous proof leaves, retiming/dynamics work, publication and fine metric
queries. Nested phase records must not be summed twice. Peak RSS is a process
high-water mark, not an exclusive per-phase allocation.

The telemetry field `qp_condition_max` is the maximum binary64 2-norm condition
of the TUM spline equality system `A` supplied to the bounded QP helper
(`numpy.linalg.cond(A)` in accepted A04). It is not the QP Hessian condition;
no Hessian condition measurement is claimed. The failed-input condition diagnostic
uses the same matrix definition. `qp_primal_residual_max` is the accepted helper's
maximum primal inequality violation after the actual solve.

## Fairness and exact authority

Three rows are distinct: unmodified stock preparation, explicitly repaired
legacy preparation plus the bounded unchanged-equation IQP driver, and the
accepted W2 original-border adapter. The same legal route, solver width .30 m,
body front/rear .10 m, body width .12 m, margin .01 m, curvature bound, solver
settings and explicit surface-specific model apply. Legacy smoothing remains
legacy smoothing, and its widths remain transported widths; these differences
are reported rather than attributed to different optimization equations.

`w3_benchmark_support.py` authenticates the pinned preparation and IQP source.
It executes them in isolated namespaces, scalarizes only SciPy's one-element
optimization parameter in `dist_to_p`, and contains the otherwise unbounded IQP.
No installed SciPy/TPH or submodule file is patched. The checker control executes
the original pinned checker and a source copy with precisely two replacements:
`stepsize_approx=1.0)[0]` becomes `stepsize_approx=1.0)[:, :2]`. Full Nx2 arrays
are demonstrated; the checker remains an unsigned sampled warning diagnostic.
A same-prepared-input direct QP control checks offsets within 1e-8 m against
the accepted adapter. The helper surrogate is not the comparison objective.

The legacy driver records actual final `create_raceline` coefficient arrays and
the inherited source-index/t/q history before sampled outputs are discarded.
Initial legacy nearest-parameter correspondence must be monotone and cyclic;
unsupported correspondence fails closed. The periodic endpoint adjustment and
its observed discrepancy are recorded. The raw legacy coefficient knots usually
omit original occurrence anchors. Therefore raw legacy geometry authorization is
explicitly **UNSUPPORTED**. A separate declared output adaptation algebraically
subdivides those polynomials at original q ownership events and rotates the seam;
it never refits samples. Raw coefficients/q/objective and adapted binary64
coefficients/q/objective remain separate. Exact rational composition arithmetic
independently bounds the coordinate roundoff caused by this adaptation. Common
independent certificates apply only to the adapted exact binary64 authority.

Both independent validators use the expectation captured immediately at their
trusted numerical producer return. Common W2 cyclic retiming is run only after
geometry PASS to isolate geometric comparison from speed-producer differences.
Original legacy continuous speed recovery is declared UNSUPPORTED in this
geometry-only comparator; no common-retimer lap time is called legacy native
lap time. Curvature energy is integrated on actual coefficients as a diagnostic,
not certified global optimality. The frozen-derivative TUM surrogate may increase
actual curvature energy. Convergence never implies minimum curvature or lap time.

The new adapter records every original-border corridor re-intersection separately.
The legacy driver transports widths and performs no corresponding re-intersection;
its initial original-corridor construction is included in its combined driver
phase, not separately timed. Its native smoothing time, every bounded spline fit
and QP resources are also retained. Failed new-QP phase timing includes the explicit
retained-input condition diagnostic; it is not pure solver latency.

## Frozen scenario construction

The generator preserves original W2 circle, reversal, rotated origin, selected
S2 upper/lower and S3 projected-surface/notch fixtures. Additional route bytes
are frozen in each manifest before solving:

| Scenario | Supplied geometry and assertion |
| --- | --- |
| S0 | Circle, direction/origin controls and an affine ellipse with 8 m/5 m axes; correct metric/sign conventions and same-input equations. |
| S1 | Explicit gapped wall segments hash to partial physical-map coverage; original legal occurrence ribbons/portals remain exactly unchanged. Required physical coverage must remain INCONCLUSIVE. |
| S2 | Independently selected upper/lower cycles plus a .9 m/s selected-branch cap; compare complete-lap retiming on the same original selected geometry. |
| S3 | Existing disconnected projected crossing and occurrence-local notch; no nearest-XY surface reassignment. |
| S4 | Two projected coincident laps with identical XY/heading but independent occurrence and repeat-deck identities; supplied progress distinguishes them. No online association claim. |
| S5 | Explicit ground/ramp-up/upper-deck/ramp-down labels, portal support, caps and weaker surface model. Vertical clearance, contact and grade remain unsupported. |
| S6 | Approximately 240 m variable-curvature ellipse, fixed .7/.9 m legal widths, four portals and nonuniform 128-point seed; bounded whole-lap resource investigation. |

A01 validates all original polygons and selected topology before optimization.
Numeric original-owned directed portal controls also precede optimization;
fixture errors cannot be attributed to the optimizer. Independent continuous
geometry and dynamics acceptance remain required for every claimed final PASS.
The .5 m S6 mesh is tested before .4/.2/.1 m. Coarser retries change only the
explicit spacing policy; certificates and resource limits are never relaxed.
Fine .1 m metric queries/export evaluate the retained coefficients without a refit.

The .52/.53 m new-adapter retries are separate resource-policy investigations.
They are not matched quality/speed comparisons to the .5 m legacy row. Independent
review required an additional manifest, declared before its execution, containing
four repaired-legacy jobs at exactly .52/.53 m and two repeats each. This supplement
uses the unchanged frozen worker, original route, model, body and every other
solver/proof/resource setting. The original 92-job primary manifest is preserved.
Only matching mesh/model rows may be compared, and no globally optimal curvature
or lap-time claim follows from these diagnostic objectives.

All three tracked archives (`GLC_smile_small`, `glc_ot_ez`, `hangar_1905_v0`)
are checked for original byte hashes, nine-group shape, terminal closure and
stored-station/linear-u arithmetic. Their saved trajectories have no supplied
approved legal-route/physical/calibrated-model authority. Archive diagnostics
are compatibility evidence, not accepted physical routes. The known GLC main
closing acceleration below -19 m/s² remains visible; no archive is repaired.

## Executed evidence

Executable commands, frozen source identities and fresh-run instructions are in
[evidence/w3-benchmarks/REPRODUCE.md](evidence/w3-benchmarks/REPRODUCE.md). The
[campaign summary](evidence/w3-benchmarks/campaign-summary.json), complete manifests,
append-only ledgers, exact authority and independent reports are retained alongside
all exploratory failures. Concurrent development timings are descriptive and are
excluded from isolated performance claims.

Development probes are failure history, not exact-head acceptance evidence.
Ancillary harness code evolved between their workers: an inactive publication
path, progress logging, a corruption-control path and docstrings. The initial
pilot source snapshots match its original manifest and are retained; subsequent
worker hashes are recorded, but not every intermediate source snapshot survives.
The first pilot also used parent-contained legacy fits; the final worker uses
fresh fits with exactly the same 20 s wall/20 s CPU/2 GiB containment as A04. One early .52 m
corruption control rejected a wrong load path rather than parsing corrupt bytes;
the final control mutates the actual `reference.json` and is repeated in the
primary campaign. These limitations are explicitly recorded in
`evidence/w3-benchmarks/development-provenance.json`. The primary campaign and
matched-mesh supplement freeze source bytes before every declared attempt and
repeat the final numerical, artifact and ROS results.

Initial fixture preflight in pinned Python3.10 passed A01 and owned directed
portal controls for all 13 scenarios. The first S6 fixture has seed coefficient
length 239.999997994 m and N128. Its .5 m anchored mesh has N490. The first bounded
pilot correctly rejected the initial QP as ill-conditioned under the unchanged
1e12 limit; no candidate or geometric PASS was exposed. This measured failure is
retained and motivates separately declared coarser-mesh investigation. The pilot
overlapped A07 unit suites; its wall times are descriptive only.

The retained-matrix diagnostic measured condition 9.72380961479247e18 for the .5 m
new-adapter failure. The valid fixture's semantic anchors lie almost on uniform
quarter-lap metric stations, producing a nearly degenerate remesh interval; this
is a measured conditioning failure rather than a memory failure. No bound was
raised. Pilot .52 m and .53 m runs each completed three solver iterations, both
continuous validators, atomic persisted-byte replay, fine metric queries and
artifact rejection controls. Their maximum conditions were about 2.145e4 and
3.895e10 respectively. The .52 m mesh is the preferred demonstrated coarse policy
because it is much better conditioned. These pilot successes are repeated in the
isolated primary campaign before final resource numbers are reported.


## Frozen primary outcomes

The isolated primary completed all 92 predeclared jobs on A07 source
`0c2d7c35fc50051a2ae96b9260de636610e280f4`: 54 PASS, 28 stock-preparation
failures, eight resource-limit rejections and two numerical-conditioning
rejections. There were no harness failures or undeclared retries. Worker wall
times total 2087.432 s; manifest controls and orchestration add separate overhead.
All 54 successful rows completed continuous geometry and dynamics proofs,
atomic persisted-byte replay, fine metric queries and actual ROS export through
the existing nine-group reader and CDR serialization. Both repeated new S4 and
S5 full paths passed. The supplement is recorded separately below.

Every stock attempt retains the original `ValueError: Input vector should be 1-D.`
from pinned preparation. The repaired column means its explicit algebraically
adapted binary64 output with common W2 retiming; raw native geometry and native
continuous speed authorization remain UNSUPPORTED. Both repeats have the stated
outcome. Times are model predictions in seconds; energies are actual-coefficient
curvature integrals in 1/m, not solver surrogate values.

| Scenario | New / adapted repaired outcome | Model time, new / repaired (s) | Curvature energy, new / repaired (1/m) |
| --- | --- | ---: | ---: |
| S0-circle | PASS / PASS | 8.593510 / 8.560933 | 1.162781873 / 1.152869696 |
| S0-reverse | PASS / PASS | 8.593510 / 8.560933 | 1.162781873 / 1.152869696 |
| S0-rotated | PASS / PASS | 8.593510 / 8.560933 | 1.162781873 / 1.152869696 |
| S0-ellipse | PASS / PASS | 10.258308 / 10.154661 | 1.046232878 / 1.052529225 |
| S1-wall-gaps | PASS / PASS | 8.593510 / 8.560933 | 1.162781873 / 1.152869696 |
| S2-upper | PASS / PASS | 9.411624 / 8.221256 | 1.307405160 / 1.347016419 |
| S2-lower | PASS / PASS | 8.587344 / 8.311644 | 1.392424741 / 1.391435494 |
| S2-upper-cap | PASS / PASS | 16.775399 / 16.560617 | 1.307405160 / 1.347016419 |
| S3-surfaces | PASS / PASS | 16.419263 / 16.129368 | 2.567662254 / 2.565208607 |
| S3-notch | PASS / PASS | 16.419183 / 16.129368 | 2.567665725 / 2.565208607 |
| S4-coincident | PASS / PASS | 23.670517 / 22.869147 | 2.328570639 / 2.305742145 |
| S5-planar-connectors | PASS / PASS | 19.940845 / 19.834768 | 1.162781873 / 1.152869696 |

S1 changes the physical-wall coverage declaration while preserving exactly the
same legal route authority; requiring physical coverage remains INCONCLUSIVE.
S2's branch-specific .9 m/s cap increases complete-lap model time while retaining
identical geometry. The circle's seed curvature energy is 1.047197568 1/m;
new and adapted repaired results increase it by 11.0375% and 10.0909%, respectively.
The repaired S2-upper result also increases actual energy by 0.9990%. These
measured outcomes retain W2's warning that solver convergence is not minimum
curvature or minimum model time.

| S6 requested mesh | New-adapter result, both repeats | Adapted repaired result, both repeats |
| --- | --- | --- |
| .5 m | SOLVER_FAILURE: ill-conditioned TUM system, N490 initial mesh, no completed iteration/candidate | PASS; 3 iterations, final adapted N485 |
| .52 m | PASS; iteration point counts 472/474/474 | PASS; QP counts 462/462/463, raw N463, adapted N467 |
| .53 m | PASS; iteration point counts 464/465/466 | PASS; QP counts 453/454/454, raw N454, adapted N458 |
| .4 m | RESOURCE_LIMIT: N610 exceeds512 before remeshing | RESOURCE_LIMIT: legacy prepared point budget |
| .2 m | RESOURCE_LIMIT: N1210 exceeds512 before remeshing | Not declared |
| .1 m | RESOURCE_LIMIT: N2410 exceeds512 before remeshing | Not declared |

The primary also records stock-preparation failures at both .5 m and .4 m.
The supplementary .52/.53 m results provide the matching mesh comparison; the
successful .5 m repaired row is never paired with .52 m new as matched evidence.
The demonstrated .52 m policy changes only spacing. Dense numerical reformulation,
a larger point/memory allowance or a different backend was unnecessary for this
synthetic fixture. The .5 m remesh conditioning defect and default .4/.2/.1 m
point-budget limits remain explicit engineering limitations.


## Matched S6 quality and resources

All four separately declared repaired .52/.53 m jobs passed the complete path.
The primary plus matched campaign therefore has 96 jobs: 58 accepted adapted/new
paths, 28 stock failures, eight resource rejections and two conditioning failures.
All unsuccessful statuses remain in the ledgers. Exploratory history contributes
another 21 planner attempts, openly qualified by its source/interference limits.
External whole-CPU resource replays are counted separately below.

| Matching mesh | New / adapted repaired model time (s) | New / adapted repaired energy (1/m) | New / repaired max cond(A) | New / repaired max primal violation |
| --- | ---: | ---: | ---: | ---: |
| 0.52 m | 68.009787876 / 67.912308846 | 0.189922801810 / 0.189997285064 | 21448.671 / 45.041984 | 2.537e-14 / 1.904e-14 |
| 0.53 m | 68.007221442 / 67.916702491 | 0.190096521820 / 0.189984844181 | 3.8947811e+10 / 45.040943 | 1.184e-13 / 3.664e-15 |

The preferred .52 m new reference has exact coefficient length
240.85606913925082 m, model time 68.00978787597407 s, 1,184 geometry proof leaves,
955 cyclic retiming edges and 955 dynamics bound intervals. Both repeats retain
C=`5246eda31c757ae728c7ba9deb03a40569590dd296a941aaacbaf15af2ac58da`
and H=`72e7f5449d7ec61c88f3ef71339544dd46c32a3bcc74385801075c8463caf024`.
It supports 2,409 metric .1 m lap queries and actual .1 m ROS export without
refitting. New .53 m has 1,174 geometry leaves and 947 retiming/dynamics edges.
Matched repaired .52/.53 m have 1,187/1,176 geometry leaves and 955/946 edges.
Every row uses three QP iterations; QP N and raw/adapted N are distinct above.

Campaign model-time metrics use the retimer profile nominal. The immutable main
display/export T uses the producer dynamics report nominal; for preferred .52 m
it is 68.00978787597403 s. These independently computed nominals can differ by
rounding (at most 8.53e-14 s across the 58 saved outputs), within their certified
enclosures. Historical H/C values identify these exact frozen campaign products;
a changed implementation requires fresh products. Pinned dependencies do not
promise bit-identical fresh compilation across hosts; see the
[saved-artifact portability challenge](evidence/w3-report-portability/README.md).

The two isolated .52 m repeats give these observed ranges, with no statistical
claim from a sample of two. CPU columns include self and reaped-child CPU inside
the named phase. Nested fit/corridor/QP entries are already included in the
numerical-producer phase and must not be summed again. Whole-worker CPU, including
startup/imports/unscoped work/result serialization, is collected separately.

| .52 m phase | New wall / CPU (s) | Adapted repaired wall / CPU (s) |
| --- | ---: | ---: |
| Numerical producer | 19.960–20.908 / 19.985–20.956 | 13.472–13.574 / 13.523–13.649 |
| Nested spline fits | 6.153–6.388 / 6.128–6.383 | Included in driver / no corresponding re-intersection |
| Nested original-corridor re-intersection | 1.636–1.770 / 1.625–1.759 | Included in driver / no corresponding re-intersection |
| Nested condition/QP solve | 8.364–8.999 / 8.417–9.062 | Included in driver / no corresponding re-intersection |
| Independent continuous geometry | 29.673–31.515 / 29.667–31.512 | 29.192–30.147 / 29.182–30.145 |
| Common cyclic retiming | 3.276–3.598 / 3.291–3.611 | 3.293–3.495 / 3.308–3.510 |
| Independent continuous dynamics | 2.887–2.990 / 2.886–2.987 | 2.878–3.115 / 2.875–3.115 |
| Stage/reload/both validators/atomic publish | 33.912–35.049 / 33.894–35.030 | 33.690–36.239 / 33.684–36.236 |
| Fine metric queries | 5.412–5.562 / 5.411–5.561 | 5.606–5.955 / 5.604–5.953 |
| Actual ROS export/reader/CDR | 21.195–21.268 / 21.188–21.258 | 20.855–21.317 / 20.852–21.316 |
| Whole worker wall (isolated) | 117.964–121.528 | 110.090–114.444 |

New .52 m QP peak process RSS is 266.285–267.332 MiB; its worker peak RSS is
160.277–160.578 MiB. Matched repaired QP and worker peaks are 257.977–258.129 MiB
and 191.816–191.980 MiB. These are largest-process high-water measurements, not
aggregate concurrent memory. All remain below unchanged 2 GiB numerical-child,
3 GiB worker address-space and 4 GiB container limits. The .53 m new system is
much less well conditioned (3.895e10) despite passing; .52 m remains preferred.

## Whole-worker CPU supplement

The original phase recorder excludes imports/startup and unscoped work, so its
phase sums are not called whole-process CPU. Two separately predeclared preferred
.52 m resource-only replays close that measurement boundary using external Linux
`os.wait4`: worker startup through final result serialization/exit, including
reaped numerical descendants, excluding the collector. The controlled calibration
burns .15 CPU seconds in both parent and reaped grandchild and observes .337995 s.
An initial quoted-control-source SyntaxError failed before either planner worker
launched; its original source/manifest/calibration record are retained separately.
The repaired collector uses explicit parent/grandchild files and a new manifest.

| .52 m resource replay | User CPU (s) | System CPU (s) | Total CPU (s) | Largest process RSS (MiB) | Non-isolated wall (s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| New | 129.654783 | .973753 | 130.628536 | 265.805 | 130.854 |
| Adapted repaired | 123.489289 | 1.004897 | 124.494186 | 258.094 | 124.729 |

These two workers ran concurrently, so these wall times do not replace the
isolated primary/matched ranges. CPU accounting is per worker and its reaped
children. Both complete paths PASS under identical source, math, model and policy,
without a HOME override. Both match the corresponding original .52 m C, H,
coefficients, q, owners, model, footprint, profile, metadata and proof reports
byte-exactly in preserved JSON representation. Raw wait4 fields, exact collector
source, calibration files and identity matches are in `cpu-replay/`. The two CPU
replays are outside the 96-job primary/matched outcome matrix. The complete
retained numerical history therefore contains 119 attempts: 96 final campaign,
21 exploratory and two resource-only replays; collector controls are separate.

## Independent saved-output challenge

The unchanged W2 independent trace oracle replays every accepted new A04 history
from its original approved seed, including actual final coefficients, q lineage,
semantic anchors and periodic-fit equations. All 28 new rows pass its existing
1e-10 m fit tolerance; the worst shifted-coefficient error is 2.936e-13 m and
worst source-point error is 7.106e-15 m. The repaired rows pass saved source-index,
t, q-transition arithmetic checks; this does not authorize their raw geometry.
The independent Gaussian96 oracle checks arclength of the saved actual polynomials,
per-edge distance enclosures and affine-squared-speed model time, plus actual
curvature energy. Across all 58 accepted outputs the largest model-time difference
is 8.527e-14 s, length error 7.106e-15 m and energy48/96 difference 2.221e-16 1/m.
Every repeated pair has byte-exact coefficient/q/model/report/H authority.

All 151 post-run diagnostics pass: 141 primary and ten matched-supplement checks.
S0 signed polynomial-area integrals reverse sign and retain absolute area;
model-time spread is below 5.4e-11 s for new and 3e-14 s for repaired controls.
S1 retains exactly the same legal curve while physical coverage stays INCONCLUSIVE;
S2 cap-only variants retain exact geometry and change complete-lap retiming.
Independent arithmetic diagnostics supplement both continuous certificates and
do not replace them. Full oracle sources, source hashes, outputs and errors are
retained under `evidence/w3-benchmarks/`.

The final A08 regression suite also passes 13/13 tests in 8.41 s from a copied
package location under `/work`, with only the explicitly declared test source
context pointing to `/src`. This exercises the colcon path-layout correction.
Strict 99-column flake8 and pep257 pass all three new benchmark/test sources.
The collector/audit reproduction helpers and exact test logs/XML are retained.

## Supported scope and next engineering work

A complete approximately 240 m synthetic offline result is demonstrated under
unchanged proof and resource limits, including fresh coefficients, both checkers,
cyclic retiming, immutable publication, metric queries and legacy ROS projection.
This establishes feasibility for this validated planar fixture. It does not prove
feasibility for arbitrary course complexity or the default .4 m mesh. Robust
near-coincident semantic-anchor/uniform-grid handling remains future numerical
engineering requiring adversarial review; changing original-border constraints,
certificate tolerances or silently raising point limits is not an accepted fix.
No measured evidence requires a sparse backend or a larger memory limit here.

Supported geometry remains explicitly supplied selected planar legal ribbons,
occurrences and portals. Ramps/connectors carry annotations and planar limits;
3D clearance, grade/contact/tire behavior, calibrated physical models, localization,
state estimation and controller tracking remain unverified. Archived maps remain
software data. Neither a successful comparator nor these internal tests authorize
physical vehicle operation. Final W3 acceptance requires the separate adversarial
review with direct PR remediation authority.
