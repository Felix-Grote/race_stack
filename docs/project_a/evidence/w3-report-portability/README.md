# Historical report replay and cross-host portability

This records an additional adversarial failure found after complete local and
hosted verification of `811bd708b32d4d61c2c3db69964bfd78c804caa6`. A green
552-test suite did not establish portable replay of a saved artifact. Independent
W3 adversarial review remains required after remediation.

## Original failures

`red/hosted-original-ci.zip` is the original push-run 38934109447 artifact
12063605159, 9,280,836 bytes, SHA256
`05bc2b23b3e5f71bdea3cc9d729f779549af66e0cfe8674de59c1d6c2fb0b3d9`.
Both that exact-head push and PR run 38934117548 succeeded. Local and hosted
verification each passed 552 functional tests in 27 groups and all nine installed
cases. Legacy remained 541 tests, zero errors, the exact ten inherited failures
and two skips; all 1,173 diagnostic rows and multiplicities matched baseline.

Nevertheless, comparing fresh local and hosted compilations gives different H
and C values for all nine cases. The original assertion script, stdout, stderr
and exit code 1 are retained. Build manifest, source/helper/dependency/OS-package
inventories and original route/model/footprint/policy/provenance are identical.
Differences begin in the first numerical spline fit and propagate through the
unchanged three-iteration solve. Across these cases the maximum coefficient
difference is 2.790e-9 and maximum model-time difference is 6.015e-7 s. These
are different exact binary64 authorities, not interchangeable identities.
The detailed audit includes all per-case comparisons. CPU/BLAS dispatch was not
captured; different kernel/image identities do not establish a numerical cause.
No general bit-identical fresh-compilation guarantee follows from pinned package
versions. No coefficient, q, digest or model value is rounded to hide this result.

A separate nonroot, source-free, network-disabled, read-only-root container then
loaded the unchanged hosted S0 artifact with its separately retained CI H and
independently selected local installed policy. Both validators ran, but the old
loader rejected the accepted authority with
`dynamics stored proof differs from independent replay`. The old loader demanded
exact bytes for the historical and newly regenerated numerical reports. The
real failed harness, controlled catalog, console and exit code 1 are under
`red/failed-saved-artifact-replay`. This is a false rejection, not a successful
portability result or evidence that a validator rejected the curve.

## Retained reproduction inputs

`red/local-references/*/reference.json.gz` preserves each original local product
losslessly with deterministic gzip metadata. Decompress a selected file to a
directory containing `reference.json`; decompressed bytes retain its original H.
The original hosted ZIP preserves all hosted products and their compile/replay/
query/export receipts. Each side has its own controlled scenario catalog.
Do not exchange the local and hosted H values.

The original failed equality script uses its actual `work/w3` paths. A standalone
comparison from this evidence directory is:

```python
import json
from pathlib import Path
a = json.loads(Path('red/local-scenario-campaign.json').read_text())
b = json.loads(Path('red/hosted-scenario-campaign.json').read_text())
for x, y in zip(a['outcomes'], b['outcomes']):
    assert x['case'] == y['case']
    assert x['H'] == y['H']  # Expected FAIL for the retained host pair.
```

To reproduce the original loader failure, build and install literal 811bd708 in
the recorded local context, extract the hosted ZIP, and invoke installed
`compile_route validate` on hosted S0 with expected H
`4bf3a0995829b6ecc77258cb52b6ed7daa09308e8b683d49472a2c5604453909` and the
independently installed synthetic policy. The retained harness shows the exact
mounts and additional checks. The particular host-dependent arithmetic difference
need not occur on every machine; deterministic outward-bound and genuine refined
partition regressions additionally reproduce the old comparison defect.

## Remediation contract

Historical reports remain exact H-bound audit snapshots. Strict typed decoding,
authority/identity/coverage/assumption checks and internal snapshot coherence
remain mandatory. Snapshot checks do not independently recertify the historical
numerical bounds. The two actual validators must independently PASS on the same
saved coefficients, q, route, profile, model and selected policies. Only those
fresh replay reports authorize and populate the Reference's validation fields.
Its saved producer main time is checked separately as described below. Numerical
report bytes and adaptive geometry partitions need not equal the historical run.
No generic closeness tolerance, refit, numerical-policy relaxation or substituted
curve approval is introduced.

Every payload edit under the original expected H still fails. A separately
controlled new expected H is a new external approval: a legal changed footprint
may pass fresh validation, while an unsafe footprint must fail the actual
geometry validator. Historical numerical fields under a new H are audit claims,
not independent certificates. Tests never accept a hash merely supplied by the
received artifact itself.

The main binary64 lap T remains the exact producer dynamics nominal, validated
inside both historical and fresh time enclosures. This prevents valid replay
rounding from changing the legacy Float32 field. A genuine constant-speed
regression puts producer T `16.000000953674313` below the Float32 midpoint
`16.000000953674316`, while an independently recomputed nominal
`16.00000095367433` remains inside the same unchanged proven enclosure but lies
above the midpoint. Correct immutable projection is `16.0`; using fresh nominal
would produce `16.000001907348633`. Profile bytes and metric prefix queries are
unchanged. Prefix time is never rescaled to force equality with the display T.

Implementation identity includes the repaired module hash. Old 811bd708 artifacts
remain unsupported by a different implementation identity; no identity bypass is
used to demonstrate a fix. Complete post-fix acceptance must create a fresh
hosted product, then load its unchanged bytes in the matching locally installed
implementation under its actual hosted H. The containing candidate's literal SHA,
full exact-head CI and final controlled H catalogs are recorded externally in
[PR #3](https://github.com/Felix-Grote/race_stack/pull/3), avoiding self-reference.

## Focused verification before candidate freeze

| Recorded run | Actual outcome |
| --- | --- |
| Original loader, deterministic numeric/partition controls | 2 failures / 2 tests, 33.869 s; intended old exact-report rejection |
| Original installed loader, deterministic replay control | 1 failure / 1 test, 29.615 s; intended old exact-report rejection |
| First repaired full artifact suite | 96 PASS / 1 failure, 222.124 s; outdated expectation for a separately approved legal footprint |
| Corrected full artifact suite | 98 PASS / no failures/errors/skips, 230.79 s |
| Repaired ordinary install and separate source-free runtime | 3 package builds, then 4 PASS / no failures/errors/skips, 112.974 s |
| Genuine constant-speed Float32 midpoint control | 1 PASS, 32.355 s |

These focused runs overlap and must not be summed as a release-suite count.
The initial full-suite failure is preserved under `initial-retry-unit`; it was
not a failed geometry certificate. The test now uses a truly unsafe body and
requires actual geometry FAIL. A separate positive case explicitly approves the
small legal body under a controlled new H and requires both real fresh proofs.
Original-H and frozen-producer body-mutation rejection controls are unchanged.

The green installed run truthfully records dirty `811bd708` provenance, not a
clean release claim. All 138 source-manifest entries are byte-identical before
build, after build and after runtime. Its 94 curated files include manifests,
all 15 negative controls, accepted bytes, CLI receipts, reader/CDR checks, raw
JUnit and the isolated minimal harness. The positive proof-variation control
calls each real validator once before conservatively varying its report; file
bytes, H, C, coefficients, q, owners, profile, model, policies and main T remain
unchanged. Forged categorical metadata and missing fresh required coverage
reject for their intended reasons. Strict active-source flake8 (99 columns) and
module/test pep257 pass. Full clean-candidate verification remains the next gate.

`files-sha256.json` inventories every other regular file in this evidence tree.
Historical logs/source snapshots retain their original bytes and are not active
lint targets. Physical-operation, 3D/contact, localization and controller
evidence remain outside this offline planar software contract.
