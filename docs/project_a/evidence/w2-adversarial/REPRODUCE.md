# Independent W2 review evidence and reproduction

Final implementation: `37b36ccc1f33300ce50e6c120c886147db11b4a7`, initial reviewed
implementation `e852641849b2497efea51dfca5ead38ad4476235`, corrected W1 base
`9440c2ce68e3dee549de7efacff1cf723fe830df`. The containing documentation commit
has its own publication SHA and exact-head CI recorded afterward in the companion
publication manifest; this archive does not pretend to know that future literal
SHA or issue an ACCEPT verdict before that CI completes.

The [self-contained review](../../W2_INDEPENDENT_ADVERSARIAL_REVIEW.md) records
findings F1 P1 and F2 P2, separate red/correction commits, mathematical contracts,
independent geometry/dynamics/history oracles, quality/resource limitations and
all executed commands. Historical phase-i and f2-red archives are immutable.

## Retained evidence

- `review-evidence.zip`: investigator reports/source probes and scripts; complete
  original failing and corrected experiments; pinned source/fixture/image/runtime/
  dependency identity, logs/JUnit/exit codes; initial and F1-only full checkpoints;
  external geometric/numerical/quality/resource experiments. Cached/virtualenv,
  copied source, build/install/wheel trees and duplicate lower-level colcon logs
  are excluded. Complete top-level verification and legacy logs remain. The
  pure-Python mpmath dependency and standalone CI artifact verifier are retained.
- `final-local.zip`: every top-level output of the final isolated complete run,
  including all 19 functional-group JUnit files, source hashes, environment/package
  inventories, full logs, raw legacy results and complete actual seven-case,
  novel-case and installed-pipeline numerical authorities/certificates.
- `final-dynamics-evidence.zip`: independently checksummed combined functional/
  retained actual-output snapshots, both successful 70-digit oracle runs, source,
  frozen environment and exact full-mathematical-payload equality proof.
- `code-final-ci-artifact.zip`: exact downloaded GitHub artifact 12049420387 from
  implementation 37b36ccc push run 38906194264/job 116990251430; SHA256
  c980acf5f5df4234914276e4de6d70818554c2285d4324634a0f650645de6aa7.
- `code-final-ci-job.log.gz`: full actual job log, compressed without editing.
- `review-index/`: complete initial and final implementation inventories,
  independently parsed functional/source/installed/legacy ledgers, API identity
  and artifact checks, original uploaded-input SHA256, source AST preservation,
  final oracle/quality comparison and retained archive-member hashes.

Final implementation full result is 373 functional passes across 19 groups, strict
99-column new-source lint, three package builds, ROS 4, installed W1/W2 and stable
exact 92-file manifests. Separate legacy: 372 tests/0 errors/the exact inherited 10
failures/2 skips. No legacy failure is represented as a passing functional test.
Final push and PR implementation workflows both completed SUCCESS. Publication
of the report-containing commit still independently requires exact-head CI.

## Integrity and extraction

From this directory, verify every retained artifact before using it:

```bash
sha256sum -c SHA256SUMS
```

Extract archives into a separate scratch directory for inspection. For rerunning
probes that use repository-relative work paths, extract `review-evidence.zip`,
`final-local.zip` and `final-dynamics-evidence.zip` into a disposable exact-source
checkout using Python's standard ZIP CLI. The dynamics bundle also includes
original fixture copies; their committed hashes are independently pinned.

```bash
python3 -m zipfile -e docs/project_a/evidence/w2-adversarial/review-evidence.zip .
python3 -m zipfile -e docs/project_a/evidence/w2-adversarial/final-local.zip .
python3 -m zipfile -e docs/project_a/evidence/w2-adversarial/final-dynamics-evidence.zip .
```

Every member path is relative and was checked for path traversal; every ZIP's CRC
was verified. `review-index/archive-members.json` retains raw hashes for selected
review/local members. The exact downloaded code artifact and independently
assembled dynamics bundle retain their own package source identities; outer
SHA256SUMS binds the complete archive bytes. Excluded build/install products are
reproducible; their installed module hashes and actual numerical run remain.

## Fresh complete reproduction

Use a nonroot account, recursive unchanged submodules and the pinned Docker
Compose test runner. Setup needs dependency network access; execution is nonroot,
network disabled, root/source read-only, no effective capabilities and
no-new-privileges. Do not run the root hardware Compose, device access or a stack
launch. Use a new output path, because verification rejects stale directories.

```bash
git checkout --detach 37b36ccc1f33300ce50e6c120c886147db11b4a7
git submodule update --init --recursive
scripts/project_a/setup.sh
scripts/project_a/verify.sh all work/adversarial/final-repeat
```

This reexecutes every permanent W0-W2 gate, all seven original fresh pipelines,
new independently generated varying-width ellipse, original W1 regressions,
49 shared-cap/gap/tangent controls and actual installed numerical pipeline.
The source/fixture/harness manifests before/after must agree. Compare raw legacy
failure identities, not merely the warning/nonzero aggregate count. Full exact
focused commands and original output identities are in the main report; use
fresh destinations when repeating them.

The final actual dynamics oracle is rerun after extracting its dependency/source:

```bash
scripts/project_a/unit.sh work/adversarial/dynamics/retained-repeat work/adversarial/dynamics/test_final_retained.py -x -s
```

It consumes the retained final-full pipeline. If that path is absent, restore it
from `work/adversarial/dynamics/final-actual-retained-pipeline.json`, as documented
in the dynamics component report. The external GEOS/Decimal oracle deliberately
uses a separate environment: Python 3.12.14, Shapely 2.1.2/GEOS 3.13.1,
mpmath 1.3.0 and NumPy 2.3.5; production acceptance remains Python 3.10/Humble.
Its no-production-import source and complete version/input ledger are retained.
This sampled oracle supplements the exact production certificates.

Reproduce original F1/F2 red tests at their documented pre-fix source commits,
using their immutable original archives. Old historical evidence scripts without
the now-required independent expected digest are replayed at the original SHA or
copied into scratch with an explicitly approved handoff migration. Do not edit
the original evidence, infer a trusted expectation from corrupted received data,
or weaken any tolerance/margin to make a replay pass.
