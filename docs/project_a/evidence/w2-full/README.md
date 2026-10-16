# Full local W0–W2 verification at committed A06

Command: `scripts/project_a/verify.sh all work/w2/full`.
Commit: `e3f94dce130cf0cee8cc0dfdbf697b57efbd7b87`.
Exit **0**, complete before/after source/fixture/harness hashes equal.
**296 functional tests** in fourteen groups, strict scoped lint and three package
builds pass. Actual installed W2 test freshly optimizes S0 and certifies the same
coefficients geometrically/dynamically; recorded `/work/install` source hashes
match the tested source manifest exactly. No W3 artifact/export claim.

Separate legacy aggregate: **295 tests, 0 errors, 10 failures, 2 skips**. All ten
failure identities exactly match W0/W1, including duplicated CTest/xUnit reports.
These existing style/schema failures remain visible; none masks a new failure.

The source remained frozen throughout this full run. Three supplemental literal
regressions (ellipse, coincident wrong deck, narrow-notch lower cap) are added and
verified separately after this immutable checkpoint; the final exact-head hosted
workflow runs the complete updated suite. Their results never rewrite this run.
