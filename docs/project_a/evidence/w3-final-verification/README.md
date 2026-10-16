# Final W3 candidate verification — 17e4ec4e

This data-only publication records complete verification of implementation
`17e4ec4e8fedfa736467d02f6204b04e8552decb` on
`project-a/w3-reference-benchmarks`. Its code starts at actual accepted W2 merge
`9fae5faed6ca62e0c943b6290babc50638477d9b`, containing accepted
`fe53365f86d660b4f6d4389925f9810cf33d41b3`. All seven recursive pins and
95 protected W2/legacy/map/interface files remain unchanged. This companion
changes no production code. Build the literal implementation commit above;
the containing evidence commit has different Git provenance.

## Complete acceptance evidence

- Fresh no-hardlink recursive checkout, pinned safe setup and full verification:
  **591 functional tests / 27 groups / zero failures, errors or skips**. All
  wrapper/container exits are zero; all 138 source identities match exact Git
  before and after. Three selected packages use ordinary non-symlink installs.
- Separate nonroot source-free runtime: **5 tests PASS in 837.47 s**. All nine
  installed scenarios pass compile, new-process dual validation, metric and
  occurrence queries, original nine-group reader and actual ROS CDR export.
  No source/build/optimizer checkout, network, GUI, physical-car configuration,
  HOME .ros tree or hardware is required. All 15 content/trust negatives reject
  for their intended reasons; proof-drift/coverage controls also pass.
- Literal-head [push CI 38945204845](https://github.com/Felix-Grote/race_stack/actions/runs/38945204845)
  **SUCCESS**, again 591 / 27 / zero functional failures. Associated
  [PR merge-reference CI 38945212759](https://github.com/Felix-Grote/race_stack/actions/runs/38945212759)
  also SUCCESS. The push artifact alone supplies the trusted hosted catalog.
- Legacy: **578 tests / zero errors / exact ten inherited failures / two skips**.
  All 1,173 diagnostic identities and multiplicities match baseline; no new
  failure is relabeled inherited. Local full failure messages also match.
  Hosted message differences, if present, are retained in the audit.
- Actual hosted-to-local replay: **9/9 unchanged hosted references PASS both
  independent validators**, metric queries and S6 reader/CDR. All nine producer
  main-time binary64 values remain exact. All nine dynamics reports differ
  numerically on replay; one fresh nominal time differs by one ULP. Historical
  report equality is not required, and neither policy nor authority is weakened.

The original exact-head push ZIP is retained at
[ci/original-push-artifact.zip](ci/original-push-artifact.zip), 9,327,825 bytes,
SHA256 `5ba01962bd2cd39ce8f9742d3a2464d1f5d086cd42ad06448c6bf5bb7fe4a180`,
verified against GitHub artifact 12067848728. All extracted bytes and controlled
receipts were independently checked. Its hosted H/C catalog is
[ci/controlled-hosted-catalog.json](ci/controlled-hosted-catalog.json).

The hosted S6 artifact has trusted H
`7331d604864405e3d886744939ac54d5fd857d81942f2a60510e9d3ee0fce12d`,
C `2cbd2d35e40b9221d54204f28e4c907204215a9829801c824fe6c1de9b34e936`.
Its producer main T is 68.00978787596146 s and actual reader Float32 is
68.0097885131836 s. Keep this controlled H with these exact bytes; do not
substitute a fresh local product's H or infer approval from a received self-hash.

## Final-source S0–S6 replay

All 96 original primary/matched jobs were frozen before numerical execution and
retained exactly once. **58 PASS, 28 stock preparation failures, eight point-budget
rejections and two conditioning failures; zero timeouts/harness failures/retries**.
Independent unchanged saved-output numerical oracles pass **151/151**; output and
identity checks pass **96/96**, including every accepted actual H/C binding.

| Scenario | Accepted new/adapted outputs | Preserved unsuccessful attempts |
| --- | ---: | --- |
| S0 circle/reversal/rotated origin/ellipse | 16 | 8 stock preparation |
| S1 legal corridor and physical wall gaps | 4 | 2 stock preparation |
| S2 independent alternatives and branch cap | 12 | 6 stock preparation |
| S3 disconnected projected surfaces and notch | 8 | 4 stock preparation |
| S4 coincident XY/heading, separate occurrences | 4 | 2 stock preparation |
| S5 annotated planar connectors and limits | 4 | 2 stock preparation |
| S6 approximately 240 m synthetic course | 10 | 4 stock, 8 point-budget, 2 conditioning |

Stock failures are distinct from explicitly source-hashed test-local repairs.
Raw legacy authority and native continuous speed remain unsupported; independent
certificates cover only its approved algebraic adaptation with common W2 retiming.

The preferred new S6 .52 m mesh completes three iterations at N=472/474/474,
condition(A)=21448.6714, QP residual 2.537e-14, 1,184 geometry leaves and 955
dynamics edges, supporting 2,409 fine .1 m metric queries without refitting.
The .5 m mesh fails at condition 9.72e18 > unchanged 1e12; .4/.2/.1 m require
610/1210/2410 points > unchanged 512. No numerical budget was raised.

Original isolated A08 performance remains the performance authority: preferred
S6 end-to-end wall 117.96–121.53 s; separate complete-worker CPU 130.628536 s
and peak process RSS 278,716,416 bytes. The final 96-job replay overlaps fresh
verification with predeclared concurrency three in a two-CPU/4-GiB container;
its timings are **NONISOLATED FUNCTIONAL ONLY**, not a new speed comparison.
All original per-child/solver/worker/proof limits remain unchanged. Two collector
preparation errors before any numerical launch are preserved separately.
[Replay and exact commands](benchmarks/README.md),
[all final outcomes](benchmarks/final-summary.json),
[controlled artifact catalog](benchmarks/controlled-artifact-catalog.json).

## Raw bundles and reproduction

- [fresh-17e4ec4e.tar.gz](fresh-17e4ec4e.tar.gz) and
  [fresh-archive.json](fresh-archive.json): complete raw fresh/run/runtime/JUnit
  evidence, accepted and negative artifacts, receipts and minimal harnesses.
- [portability-17e4ec4e.tar.gz](portability-17e4ec4e.tar.gz),
  [portability-summary.json](portability-summary.json) and
  [portability-archive.json](portability-archive.json): exact incoming artifacts,
  controlled receipts, original failing harness now passing, supplemental main-T
  checks, policies, launch controls, file ledgers, reader/CDR and exit evidence.
- [benchmarks/final-functional-17e4ec4e.tar.gz](benchmarks/final-functional-17e4ec4e.tar.gz):
  all 1,056 final replay files, with its internal SHA256SUMS and reproduction
  scripts. Archive SHA256
  `cbd2cef83a15882a63a8fa682fbba37fc1484977c7979af85ac44b44e8d01b2d`.
- [audits](audits): independent read-only source, legacy, fresh, hosted and
  cross-host reviews. Integrity hashes establish bytes, not artifact approval.

From a clean recursive implementation checkout, run:

```bash
scripts/project_a/fresh_verify.sh 17e4ec4e8fedfa736467d02f6204b04e8552decb work/w3/independent-final
```

[publication-index.json](publication-index.json) maps published names to original
workspace records; raw archive receipts retain their original workspace paths.
Extract bundles into private scratch directories; their inventories preserve
original filenames, byte hashes and sizes. The portability bundle README and
launcher show exact source-free mounts and required controlled CI catalog.
Its expected CI paths can be restored by extracting the original ZIP. Use the
current installed synthetic policy and externally retained H for validation.
Historical snapshots under old implementation hashes are not migrated or bypassed.
Packaging/replay scripts are archived as execution evidence, not installed
product modules or active lint targets.
[Artifact/CLI specification](../../W3_ARTIFACT.md),
[installed handoff/ownership](../../W3_RUNTIME.md),
[independent adversarial review instructions](../../W3_REVIEW.md).

## Limits and remaining ownership

Fresh local and hosted compilations differ in all nine H/C values despite exact
static inputs/code/dependency inventories. Maximum coefficient difference is
2.790e-9 and model-time difference 6.015e-7 s. CPU/BLAS causation is unproven.
Both trusted catalogs are retained; coefficients, q and identities are never
rounded to force equality. Transported fixed products now revalidate successfully.

The frozen-derivative TUM surrogate may increase actual curvature energy; neither
convergence nor these comparisons proves minimum curvature or faster lap time.
Fine optimization meshes remain limited as above. Archived maps are software
data, not approved physical-course geometry. S1 physical completeness and S5
3D/contact coverage remain explicit limitations. Legacy projection is lossy and
does not authenticate a full reference. Localization/occurrence association, state
estimation, controller tracking, real vehicle calibration, tire/contact behavior
and physical clearance require separate integration and physical evidence.

This completes author/internal verification of an **offline planar planning
subsystem**. It does not establish physical-car readiness or W3 acceptance.
A separate independent W3 adversarial reviewer retains final acceptance and
direct PR-remediation authority. Do not auto-merge or operate a physical vehicle.
