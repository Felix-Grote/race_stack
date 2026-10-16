# Project A validation matrix — W0

Tested source base: `67981ed7964a6d35e1da48f0c22bbd9f6d123d5e`, with W0 changes
identified by [implementation SHA-256 manifest](evidence/implementation-files.json).
No production source or gitlink changes. Final clean-clone verification follows in
STATUS; local logs are evidence, not substitutes for a committed branch identity.

Executed commands:

```bash
scripts/project_a/setup.sh
scripts/project_a/verify.sh all work/final-pinned
bash -n scripts/project_a/setup.sh scripts/project_a/verify.sh scripts/project_a/container_verify.sh
git diff --check
git submodule foreach --recursive --quiet 'test -z "$(git status --porcelain)" || exit 1'
```

Setup and functional runner exit **0**. Image:
`sha256:cd722a05da5819643684d723d61fd59ca07687c9efe9a21ecc40443c739b2d2a`.
Base ROS manifest digest:
`sha256:860e53793ccf575e5369b5e9a19939de2bfcfb46a299954d06f54f2af54fed19`.

| Check | Executed result | Tolerance / scope |
|---|---|---|
| Numerical pytest | **7 passed**, 0 failed/errors/skipped | Synthetic dependency/QP/defect characterization only |
| Analytic active-set QP | PASS | absolute 1e-10 |
| Ordered ellipse QP | finite, max offset 0.6000000000000008 m | bound .60 + 1e-8 m; linearization error .09313225043408788 /m |
| Ordered projected-crossing QP | finite, max offset 0.600000000000008 m | same bound; linearization error .3629228282846315 /m |
| SciPy arc oracle x=t,y=t² | PASS | absolute 1e-12 m, integration estimate <1e-12 |
| Unmodified legacy prep | **FAIL characterized**, expected ValueError | `Input vector should be 1-D`; no patch applied |
| Legacy spline station | **incorrect characterized** | measured .1669380946018666 m max discrepancy at .1 m nominal sampling; differs from historical probe mesh |
| Colcon build/install | **3 packages passed** | f110_msgs, frenet_conversion, global_planner; non-symlink installation |
| Optimizer wheel/import | PASS | unchanged pinned submodule; wheel under output directory |
| Actual ROS/install pytest | **4 passed**, 0 failed/errors/skipped | generated Wpnt/WpntArray CDR, all 9 JSON groups, installed utilities, Frenet |
| Installed straight Frenet roundtrip | PASS | absolute 1e-6 m, rtol=0; no new tracker |
| Runtime isolation | PASS | nonroot; CapEff=0; NoNewPrivs=1; loopback only; readonly root/source |
| Legacy selected colcon tests | **FAIL**: 12 aggregate reports, 0 errors, 10 failures, 2 skipped | colcon test=1, test-result=1; existing lint/XML-schema access |
| A01–A09 / full IQP / continuous legal geometry / cyclic dynamics | **NOT IMPLEMENTED** | no accepted trajectory or product artifact |
| Real course, vehicle, 3D/contact/traction | **UNSUPPORTED / NOT TESTED** | no approved measurements, calibration or hardware work |

[Curated full evidence](evidence/pinned-run/SHA256SUMS) includes JUnit, helper
hashes, exact dependency/OS inventories, runtime identity, QP measurements, build
and wheel output and gzip-compressed raw logs. `run.log.gz` contains selected build
output; `legacy.log.gz` and `legacy-results.txt.gz` preserve the complete red
baseline. `exit-code.txt` refers to functional acceptance, **not** legacy success.
Numerical and ROS test counts are separate; no pure-Python check is called ROS.

TPH QP, IQP handler and preparation hashes match the canonical research values.
The W0 probes call one QP per curve, not the unbounded stock IQP wrapper. Neither
single-QP error is treated as convergence, continuous curvature feasibility or
legal footprint evidence. No margins, widths or release tolerances were weakened.

Initial setup iterations are recorded: collection failed exit 4 before message
build because launch-testing imported neighboring ROS tests. The bounded runner
repair disables plugin autoload for explicit W0 files; legacy tests keep plugins.
`evidence/initial-collection-failure.log` preserves that failure. Direct-only pins
were expanded to a hash-locked numerical/build closure before the final run.
