# Project A final independent W3 research archive

**W3_RESEARCH_ACCEPTED** for implementation
`b961d20ce4a803e55336fb5590c30574e23b2fad`, initially reviewed at
`17e4ec4e8fedfa736467d02f6204b04e8552decb`.

Read [the independent acceptance report](W3_ACCEPTANCE.md) and its
[raw-evidence binding receipt](W3_ACCEPTANCE.json). The release gate passed 612
functional tests in 27 groups, including five separate source-free tests and
nine installed scenario compile/validate/query/export/CDR paths. All 30 intended
negative-control instances passed. Ten inherited legacy failures and two copyright
skips remain separately identified. The scope is synthetic planar offline software;
physical vehicle, calibrated model, real course and controller behavior are not
validated.

The source tag is
[`project-a/w3-accepted-b961d20`](https://github.com/Felix-Grote/race_stack/tree/project-a/w3-accepted-b961d20).
This archive branch adds evidence only. **Its HEAD is not the accepted build SHA.**
Use literal b961d20 for reproduction; fresh build provenance legitimately changes H.

## Verification and retained histories

- [Exact accepted-source push CI39110306747](https://github.com/Felix-Grote/race_stack/actions/runs/39110306747),
  [PR CI39110310707](https://github.com/Felix-Grote/race_stack/actions/runs/39110310707).
- [Complete final96 run39110811058](https://github.com/Felix-Grote/race_stack/actions/runs/39110811058):
  workflow harness7fcecd9 separately checks out literal b961d20; 58PASS,
  28stock preparation failures, 8resource limits and 2conditioning failures.
- [Original evidence326aa378](https://github.com/Felix-Grote/race_stack/tree/326aa3783ac2d757b6e714eadd14fdba96f595fd),
  [earlier independent evidence676e59ab](https://github.com/Felix-Grote/race_stack/tree/676e59ab101e8209840e566e36c5daf0fd624381)
  remain intact. Original failures, interrupted attempts and unsupported outcomes
  are preserved rather than relabeled as success.
- [Research PR3](https://github.com/Felix-Grote/race_stack/pull/3): premerge source
  accepted; publication precedes its authorized merge. The subsequent closure
  record will identify the actual merge commit/tree and its CI.

The full96 records distinguish raw stock failures, adapted repaired legacy
geometry and the new planner. Adapted certificates do not approve native legacy
geometry. S6's0.52m case succeeds under its explicit policy, while0.50m fails
conditioning and finer requests exceed point budgets. Mesh/origin/scale sensitivity,
curvature-energy limitations and lack of optimum/general robustness claims remain.
[S6 telemetry](S6_FINAL_TELEMETRY.json) distinguishes outer wall, inclusive and
nonoverlapping phases, separate CPU observations and separate RSS maxima.

## Durable files and integrity

[The bundle index](control/final-bundle-index.json),
[coverage audit](control/final-coverage-audit.json),
[full selected/excluded inventory](control/final-selection-inventory.json),
[duplicate accounting](control/final-duplication-accounting.json) and
[archive report](control/final-ARCHIVE_REPORT.md) identify all retained bytes.
Eight deterministic bundles preserve 5,240 unique source paths. Each bundle has
an internal MANIFEST.json, a published manifest and receipt sidecar. Every member
and selected original was hash-checked; the two final bundles were independently
serialized twice to identical bytes. All 401 decisive acceptance inputs are covered.
Reconstructible checkout/build/install/wheel/cache state is excluded explicitly;
actual JUnit/Testing originals are salvaged before build exclusion. Every source-free
scenario's raw product and producer/validator/export receipts remain.

The first three convenience bundles duplicate already Git-retained committed
research bytes (98,702,652 compressed bytes). They do not represent unique new
experiments. The remaining bundles retain external investigations, authenticated
original CI ZIPs, final96, current official upstream baseline, failed local attempts,
complete fresh/runtime products and metadata. Full duplicate accounting separates
repeated file bytes from unique content. No historical commits or only evidence
copies were deleted or rewritten.

From this directory, verify published files before extraction:

```bash
sha256sum -c PUBLICATION_SHA256SUMS
```

Extract selected bundles into a new private empty directory; internal paths match
`/workspace/forza-audit-records` relative names used by retained scripts. Source-specific
READMEs and exact raw commands identify the required historical source/mounts. The
original external H/C catalogs are approval inputs; an artifact's own H is not an
independent approval. Initial17 probes, finalb961 probes and hosted/fresh compilation
products remain separately identified. Authenticated unchanged hosted replay is
separate from fresh recompilation, which is not promised bit-identical across hosts.

## Reproduce the accepted implementation

Use a nonroot account with ordinary Docker/Git access; never run the vehicle Compose
or stack launch. Clone the personal fork, detach at the accepted source and initialize
all recursive gitlinks:

```bash
git clone https://github.com/Felix-Grote/race_stack.git accepted-research
cd accepted-research
git checkout --detach b961d20ce4a803e55336fb5590c30574e23b2fad
git submodule update --init --recursive
scripts/project_a/fresh_verify.sh b961d20ce4a803e55336fb5590c30574e23b2fad work/fresh-independent
```

The output destination must be absent. Tooling builds the digest-pinned Humble image
and hashed dependencies; no host-global numerical dependency replacement is required.
It performs a normal non-symlink install, generates actual staged build provenance,
then starts a separate network-disabled, nonroot, read-only source-free container.
Literal source hashes and clean state are checked before and after. The compiler
captures original curve/q authority before retiming; both independent validators
rerun on persisted bytes under externally retained H. No loader/query/export refit
is permitted. Fresh failed or uncertain proof dominates a historical PASS.

The full96 harness, commands, manifest and literal source verification are in bundle03;
its numerical checkout SHA differs deliberately from the workflow harness SHA.
Independent 65-digit query oracles and filesystem/trust fault scripts are in bundle02.
Follow each source-specific README when recreating an initial17 experiment, rather
than substituting current source or manufacturing its old H under a new identity.

The [predeclared production equivalence protocol](PRODUCTION_EQUIVALENCE_PROTOCOL.md)
is a later integration test plan, not a production acceptance declaration. Lean
production extraction must start from actual current official ros2-humble, retain its
optimizer/QoS/node/launch behavior, and link this archive without importing its history.
