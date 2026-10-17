# Independent W3 A08 investigation and correction

Initial reviewed source: `17e4ec4e8fedfa736467d02f6204b04e8552decb`.
Accepted W2 comparison base: `9fae5faed6ca62e0c943b6290babc50638477d9b`.
This report covers independent benchmark/numerical investigation; the main W3
report owns the complete release verdict and final exact-head CI.

## Confirmed P2 and minimal correction

At initial `scripts/project_a/w3_benchmark_support.py:461`, the repaired legacy
comparator's initial bounded fit was outside its existing numerical exception
handler. An actual initial fit timeout escaped to `run_worker`, which reported
`HARNESS_FAILURE` and omitted the partial comparator result. The contract requires
a retained numerical `RESOURCE_LIMIT`, no candidate, zero completed QPs, and the
explicit bounded-fit reason. Later fit/QP failures already used that handler.

Minimal reproducer: unchanged frozen S0-circle route and original SolverPolicy,
except the explicit `qp_wall_seconds=.001`. The real child times out; no mock is
used. `legacy-first-fit-limit-red/exec-run.log` and the compressed report contain
the actual result and traceback. A regression at current
`planner/global_planner/test/test_w3_benchmarks.py:133` failed before the change.

The correction moves that same initial fit into the existing `try` at current
`w3_benchmark_support.py:505`. No fit/QP equation, mathematical policy, budget,
successful-path value or certificate changes. The corrected worker reports
`RESOURCE_LIMIT` and retains the full comparator failure record. A separate
successful repaired S0 run completes both independent proofs with the original
diagnostic values: energy `1.1528696958441853 /m`, time `8.560933045401049 s`.

Verification: failing-first regression **1 failed / 13 deselected**; complete
corrected A08 suite **14 passed in 10.06 s**; strict 99-column flake8 and pep257
pass. An intermediate suite had 13 PASS and one missing optimizer-file error
because this worktree had not initialized that gitlink; that report remains.
After initializing exact optimizer `b1b38ecfefec7200d5bcb243f115af1d795b3766`,
all 14 pass. No original test was weakened or removed.

Historical helper SHA256:
`29a25360fc2ee4411fb6483ae70dffda30335cbebec1d02a0218ec3a9ae50f59`.
Corrected helper SHA256:
`6ba5f671f1152a46eaff3e25cec4979c2c2bfbf8b1b825425a2dc5d27223622b`.
The 96 historical manifests remain unchanged. Exact historical source bytes are
recoverable from the initial reviewed Git commit, and W3_BENCHMARKS explicitly
distinguishes that historical replay from a new corrected-source manifest.

## Frozen campaign: independent source and mathematical audit

`audit_saved.py` imports no planner code. It verified all **966** campaign
checksums, manifest/job coverage, result-gzip hashes, route-byte hashes, worker
and helper source identities against initial Git, and actual report outcomes.
The 92-job primary plus four-job matched supplement contain exactly **58 PASS,
28 stock preparation failures, 8 resource rejections, 2 conditioning failures**.
Their manifest SHA256s are respectively
`a0ac91282fa72287d98c1c986c4b66be7082b5d1731dc1fc844d7c4e2f1706bf`
and `b51896f8e9e044bc767a529f97da75bb87afe99e1cb05f6064803f98ef95fcf5`.
All 29 accepted repeated pairs retain identical numerical authority and reports.

All 30 repaired legacy outputs preserve raw actual `create_raceline` coefficients
and q separately. Raw legacy geometry authorization is explicitly UNSUPPORTED.
Only separately adapted binary64 polynomials receive common certificates and
the common W2 retimer. Independent Fraction arithmetic reconstructs all adapted
pieces and confirms every declared composition bound; the largest coordinate
error bound is `2.7987749448754537e-15 m`. No raw certificate transfer was found.
The source-local SciPy repair and checker-array repair are authenticated and
declared; installed TPH and the optimizer gitlink remain unmodified.

Adaptive QUADPACK integration of actual coefficients and affine-u profile edges
checks all 58 outputs. Maximum disagreement: length `3.552713678800501e-15 m`,
energy `4.440892098500626e-16 /m`, profile nominal `7.105427357601002e-14 s`,
producer nominal `1.4210854715202004e-14 s`. Every distance and time lies in the
saved independent enclosure. A separate 60-digit Decimal adaptive-Simpson oracle
integrates all 474 preferred S6 cubics: length
`240.856069139250809347677318389756297576479697546411419310223 m`, energy
`0.189922801810385769910541063647413303194689311046140916013415 /m`.
These numerical diagnostics supplement, and do not replace, continuous proofs.

The independent saved/fresh coefficient oracles ran in host Python 3.12.14,
NumPy 1.26.4 and SciPy 1.12.0; the Decimal oracle uses the standard library at
60 digits. Production and the new-process query challenge ran pinned Python
3.10.12, NumPy 1.26.4, SciPy 1.11.4, TPH 0.79 and quadprog 0.1.7.

The circle's actual curvature-energy increase is real. Convergence gives no
minimum-curvature or minimum-time guarantee. Matching mesh, common body/model,
adapted authority, and common retimer are required when comparing columns.

## Fresh bounded S6 counterexamples and sensitivity

All inputs and policies were frozen in manifests before execution. The unchanged
limits are 512 points, `1e12 cond(A)`, numerical-child 20 s wall/CPU and 2 GiB,
whole optimizer 120 s, worker 240 s wall/CPU and 3 GiB, one numerical thread.
The pinned image is
`sha256:72059c0caff2aa71e7ee9ff85d718c2e1761488d144857a42167de36ff74d246`.
Containers are nonroot, read-only, no network/capabilities/devices, capped 1 CPU
and 4 GiB. Early sensitivity timing is descriptive under concurrent review.

| Actual supplied change | Outcome | Maximum or failed cond(A) |
| --- | --- | ---: |
| Original .5 m | SOLVER_FAILURE before completed iteration | 9.7238096142e18 |
| Original .4/.2/.1 m | RESOURCE_LIMIT before remeshing, no candidate | point limit |
| .519 m | Both independent proofs PASS, N475 | 4.9007861844e8 |
| .521 m | Both independent proofs PASS, N473 | 2.6090548072e9 |
| .525 m | Both independent proofs PASS, N470 | 2.6680181650e4 |
| Quarter-lap cyclic origin, .52 m | Both independent proofs PASS, N474 | 1.2818282761e4 |
| Half seed knots, original legal boundaries | Both independent proofs PASS, N474 | 2.1109071606e4 |
| Analytic 256-knot seed, original legal boundaries | Both independent proofs PASS, N474 | 2.1536503911e4 |
| Scale .995 at fixed .52 m | SOLVER_FAILURE, no candidate | 9.7005588010e18 |
| Scale 1.005 at fixed .52 m | SOLVER_FAILURE, no candidate | 9.7040794723e18 |
| Collinear midpoint seed refinement | Third QP fails after two retained iterations | 1.0968412070e16 |
| Scale .995, explicitly scaled .5174 m mesh | Both independent proofs PASS | 2.1437833628e4 |
| Scale 1.005, explicitly scaled .5226 m mesh | Both independent proofs PASS on isolated retry | 2.1459409120e4 |

Fixed .52 m is therefore not generally robust to course scale. The quarter-anchor
and uniform-grid aliasing is a measured dense-remesh limitation. Fail-closed
rejections are correct; no tolerance or condition bound was raised. The collinear
refinement changes actual seed energy fourfold despite small coordinate changes;
it is not equivalent to analytic denser ellipse sampling. Both are retained.
The controlled mesh-covariant retries demonstrate that no new solver architecture
is needed to make these small-scale variants feasible, without erasing failures.

The 1.005 covariant case first exhausted its unchanged 10 s retimer wall budget
while my interface build shared the same 1 CPU; that INCONCLUSIVE is retained.
With the same source/input/policy and no concurrent build, it passes in 73.49 s.
The first .519 attempt lost output serialization during independently observed
host ENOSPC: phase progress, zero-length result and Docker events remain, with
ENVIRONMENT_FAILURE rather than a fabricated PASS. Failed container launches
and every retry remain. `fresh-audit.json` covers 19 completed ledger reports:
10 PASS, 4 RESOURCE_LIMIT, 4 SOLVER_FAILURE, 1 INCONCLUSIVE. The direct red worker
and partial ENOSPC attempt are two additional retained attempts.

## Corrected complete approximately 240 m path

The final .52 m run completes actual production optimization, fresh continuous
geometry/dynamics, atomic persisted-byte publication/reload, 2,409 .1 m metric
queries, and existing nine-group ROS reader/CDR export. Real f110_msgs was built
with ordinary colcon installation for this sourceful benchmark. This is distinct
from the main review's full three-package and source-free acceptance gates.

Observed isolated whole-worker wall/CPU: **123.957199 / 123.703743 s**; three
iterations, N474; QP peak process RSS **274,227,200 B**, worker peak
**166,182,912 B**. These are per-process high-water marks, not summed memory.
Actual length `240.8560691393339 m`, energy `0.1899228018108761 /m`, independent
maximum absolute curvature `0.05021455266445619 /m`. Profile model time is
`68.00978787594032 s`; immutable producer main time is `68.00978787594029 s`.

Corrected C=`21aeb6a3a4e81aa3ff072232e96e699a10fd9966d0b14e54132da74cfa359b20`;
H=`f42fe3eaab4d76a015ec18d3938a3a3ea78d5934b4316f5609079f22f5a84760`.
The reference file SHA256 is
`82a74ab447654b075bc2c9274cc9abed9baf92cafd0346a6d9d7ba8d8ee0d006`.
A new process reloads it in 34.73 s, reruns both proofs, preserves coefficients/q
bit-for-bit and producer main time, and retains the file bytes unchanged. Its
fresh time enclosure is `[68.0097878758253,68.00978787605527] s`. Independent
query maxima: arc residual `7.807443580531981e-11 m`, squared-speed error
`1.7763568394002505e-15`, time error `2.4371615836571436e-11 s`.

The fresh C differs from the historical preferred C despite almost identical
quality/length. Bit-identical cross-host fresh compilation is not promised.
Transporting the unchanged old primary H72e7f5... product correctly reports
UNSUPPORTED because it binds producer0c2d7c3 A07 source hashes, which differ from
the corrected implementation. That version rejection is not same-version
numerical portability evidence; the separate artifact lane retains hosted
same-version replay. No identity allowance, rounding or policy was weakened.

## Evidence and scope

The runnable sources, frozen inputs, append-only ledgers, raw compressed results,
red/green outputs, and exact numerical oracles are retained in this directory.
Generated `ros-interfaces/{build,install,src,log}` is reconstructible and excluded
from the compact long-term archive; `ros-interfaces-build.log` remains. No
important experimental result is deleted. Archive hashes/manifests accompany
the publication. Initial-source investigation records precede implementation
edits in `PHASE_I.md` and `LEGACY_FIT_FINDING.md`.

No demonstrated A08 blocking defect remains after the P2 correction. Scope is
explicitly supplied planar synthetic routes, supported models and fail-closed
resource outcomes. No real course approval, physical racing, contact/grade/3D,
localization, controller or actuation acceptance follows.
