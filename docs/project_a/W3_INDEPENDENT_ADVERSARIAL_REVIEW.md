# Independent W3 review and remediation — 2026-10-17

Initial review authority: `17e4ec4e8fedfa736467d02f6204b04e8552decb`, PR #3,
`Felix-Grote/race_stack:project-a/w3-reference-benchmarks`. Accepted W2 merge
`9fae5faed6ca62e0c943b6290babc50638477d9b` and accepted W2 history are retained.
Original push CI 38945204845 and PR CI 38945212759 both report SUCCESS at 17e4ec4;
these earlier runs do not validate the corrections below. No upstream write,
merge, force-push, hardware launch or numerical-policy relaxation is authorized
by this review.

This report records independently reproduced findings and corrected-source
verification. A final verdict also requires a clean recursive exact-SHA
`fresh_verify.sh` run, exact-head push CI, authenticated hosted artifacts, and
same-version saved-product replay after the last correction. The completed
literal SHA, test matrix, artifact receipts and verdict are recorded in the
[companion publication manifest](https://github.com/Felix-Grote/race_stack/blob/w3-independent-review-20261017/docs/project_a/evidence/w3-independent-review/final-publication.json),
outside the implementation commit to avoid self-referential provenance.

## Findings and corrections

| ID | Priority | Finding | Failing-first evidence | Corrected verification |
| --- | --- | --- | --- | --- |
| F1 | P2 | Publication lacked trusted control of its output ancestry | Four permanent regressions fail against original production | 16 focused PASS; 139 pure artifact/export PASS, two actual ROS tests separately covered by full/install gates |
| F2 | P2 | An installed-command timeout lost captured streams and command history | Two permanent actual-process regressions fail | Five harness regressions PASS; partial bytes, producer report and RESOURCE_LIMIT timeout receipt retained before failure |
| F3 | P2 | Initial bounded legacy fit escaped numerical failure classification | Actual child timeout and one permanent regression fail | 14 A08 tests PASS; initial fit remains RESOURCE_LIMIT with zero QPs and no candidate; successful comparator still completes |
| F4 | P3 | Loose historical numerical evidence dominates review size | Exact Git/blob/ledger audit | Two largest A09 JSONs are losslessly compressed, with raw/stored hashes and verified restoration; full history retained |

Corrective commits: F1 `4a941599ec38195936f5f2b51829cef9cfaf3db8`;
F2 `72b72c654d9569a21bb11a6f22a3ad53893d63a9`;
F3 `abdbc4ab232ebe850ec1b8c096fc89a2480c29b9`.
Raw evidence and exact commands are indexed in the [evidence receipt](evidence/w3-independent/README.md).

F1 requires every publication ancestor and stage parent to be owned by the
effective user or root and have no group/other write mode. Root-owned sticky
shared ancestry is allowed only into a trusted private child; the shared
directory itself cannot be the stage parent. A real UID1001/UID1000 ancestry
check rejects foreign ownership. Loading retains its separate external-H and
fresh dual-validation contract. Root, the effective user, privileged capabilities
and filesystem administration remain trusted; same-UID mutation and distributed
filesystem guarantees are outside the contract. The initial scoped shell-setup
failure remains retained; it was not a test pass.

F2 changes evidence retention, then reraises the original timeout. It does not
turn a failed command into acceptance. Both stdout and stderr are retained as
the actual bytes returned by the real process, with a separate timeout record;
an existing producer report is not overwritten.

F3 moves the unchanged first fit into the already existing exception boundary.
No numerical equation, successful-path value, condition limit, margin, tolerance
or resource budget changes. The frozen 96-job historical campaign remains
unchanged; a current-source rerun records the amended helper identity. The
intermediate 13-PASS/one missing-submodule run and failed Docker launches remain
separate from the final 14-PASS result.

## Independent evidence beyond implementation tests

The archive includes reproducible oracle source, frozen jobs, actual products,
controlled H/C catalogs, original red results, every failed/retried run and raw
logs/JUnit. Its member manifest and SHA256 receipt permit verification without
trusting the narrative. Archive source checkouts, build trees, bytecode and tiny
synthetic Git fixtures are excluded as reconstructible scratch; their original
failed outputs remain. The original evidence branch is preserved unchanged.

- Canonical serialization agrees on 10,009 exact finite-binary64 roundtrips and
  12 malformed-input rejections in host and pinned Python. Byte/node boundary
  and excess-node resource observations remain raw evidence, not a smaller
  unmeasured memory guarantee.
- Nine unchanged initial-head hosted products replay with externally retained
  H/C and fresh geometry/dynamics PASS. A later implementation hash requires
  newly matching products; the completed final publication receipt records
  that separate final-version replay. No bit-identical fresh compilation across
  arbitrary hosts is promised, and CPU/BLAS causation is unrecorded.
- Independent 60-digit mpmath coefficient integration checks 703 queries and
  268 side intersections across five cases, including repeated XY/heading
  occurrences; 2,145 exported waypoints are inspected. Maximum arc/time/side
  errors are 1.496e-10 m, 1.479e-10 s and 4.441e-16 m. This direct source run
  is separate from actual installed ROS acceptance. A pure export suite passes
  25 tests; it excludes actual reader/CDR tests.
- An independent audit verifies all 966 frozen campaign checksums and all 96
  jobs: 58 PASS, 28 stock preparation failures, eight resource rejections and
  two conditioning rejections. All 29 accepted repeated pairs retain complete
  mathematical authority. Independent adaptive QUADPACK checks all 58 accepted
  outputs; 30 separate exact-rational composition audits cover adapted legacy
  outputs. Raw legacy geometry/native speed remain unapproved.
- Nineteen completed fresh benchmark worker reports retain 10 PASS, four RESOURCE_LIMIT, four
  SOLVER_FAILURE and one INCONCLUSIVE; two rows are S0 controls (the 17 S6 rows
  contain nine PASS/three resource/four solver/one inconclusive). The direct failing-first worker and
  disk-partial attempt are two additional retained attempts. Nearby meshes,
  origin and analytic seed controls pass, while fixed .52 m spacing fails at
  ±0.5% geometric scale and a collinear seed refinement fails conditioning.
  Explicitly co-scaling the mesh restores feasibility under unchanged limits.
  The approximately 240 m corrected whole path passes in 123.957 s with 474
  segments, both proofs, persisted-byte replay, 2,409 metric queries and actual
  nine-group reader/CDR export. A new process preserves authority and main
  time while rerunning both proofs. Its detailed report retains all limits,
  per-process memory measurements and the 60-digit Decimal oracle.
- Script review and executable clean-commit guards verify literal-head/source
  drift rejection, ordinary installs and source-free execution. Original fresh
  attempts failed from shared Docker-vfs ENOSPC/termination; they are retained
  as environment failures. Built-in legacy comparison is strengthened for this
  review by exact ten identities/two skip reasons, complete diagnostic-text
  multiplicities and nondiagnostic block comparison. Diagnostic enumeration
  order is permitted to vary; raw-byte equality is not claimed.

The independent saved/fresh coefficient oracle uses host Python 3.12.14/SciPy
1.12.0; production and new-process query checks use pinned Python 3.10.12/SciPy
1.11.4. The 23 mutation checks merely defined in `trust_consistency.py` have no
execution receipt and are not credited as completed.

## Complete corrected-source verification

Safe setup exits 0 at immutable image
`sha256:72059c0caff2aa71e7ee9ff85d718c2e1761488d144857a42167de36ff74d246`.
The standard corrected dirty-source attempt completes **593 tests / 21 groups,
zero failures/errors/skips**, strict lint and all 138 unchanged source hashes.
Its wrapper exits 1 before colcon because this Git worktree's `.git` points
outside the Docker source mount, causing Git128 while generating build provenance.
Ordinary builds, installed ROS, legacy comparison and source-free runtime were
**NOT_RUN in this attempt**. The exact matrix and failure are retained in
[the attempt summary](evidence/w3-independent/corrected-source-attempt.json).
The required final standalone clean clone supplies visible Git metadata; no
runner check is weakened to make the worktree attempt pass.

The exact committed clean reproduction and final hosted results are separate
publication gates. Earlier checkpoint counts and CI cannot substitute for them.
The companion final manifest records their actual result and source identities,
including the hosted artifact's own checked-out source SHA and source hashes.

## Review size and evidence disposition

Physical LOC counts include comments/docstrings and blank lines; nonblank LOC
is reported separately. Git diff line totals are a different measure. The final
three W3 production modules contain 1,708 physical / 1,537 nonblank lines /
84,183 bytes; all eleven Project A production modules contain 5,412 / 4,815 /
258,328 bytes. The seven W3 test files contain 2,784 / 2,459 lines / 141,112
bytes; all thirty planner/harness test files contain 6,809 / 5,978 lines /
338,335 bytes. No production framework or numerical backend is added by these
corrections.

The original W2-to-17e4ec4 diff changes 1,826 files: 1,771 evidence files
account for 119,063,375 bytes and 695,389 added lines, versus three new production
modules with 83,008 bytes/1,685 lines. Evidence is 97.00% of added lines;
installed inputs, tests, harness and documentation are classified separately
in the audit. These original numbers are not presented as the post-compression
diff. The final companion audit records the actual delivered Git objects.

The two compressed A09 JSONs previously occupied 422,952 text lines. Restoration
must reproduce the original Git blob hashes exactly; the updated A09 ledger
binds stored gzip bytes and the raw/stored map. This reduces checkout/review bulk
without removing prior Git blobs. Main-branch clone history may be reduced only
through a later supervised integration preserving reviewed archives/history;
this release does not rewrite or force-push accepted history. Actions artifacts
expire and are not the sole archive: Git-retained companion archives remain
maintained by the fork owner.

## Supported handoff and remaining limits

The supported result is offline synthetic planar software under explicit route,
body/model, policy, provenance and resource assumptions. Preserve the existing
legacy entry point, maps, messages, archived assets, all recursive pins and
accepted W2 source. Circle curvature energy can increase after convergence;
neither path proves global minimum curvature or minimum lap time. S6 .5/finer
meshes and the disclosed seed/scale cases retain fail-closed limits. A stored
PASS or self-supplied H is never external approval.

Unapproved real-course geometry/calibration, physical coverage, S5 3D/contact,
ramp/grade/tire behavior, live occurrence selection, localization, controller
tracking, actuation and racing safety remain unsupported. No physical vehicle
or autonomous-operation approval follows. No merge is performed.
