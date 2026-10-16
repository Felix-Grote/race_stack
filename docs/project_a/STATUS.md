# Project A status — 2026-10-16

**W0 COMPLETE. W1 IN PROGRESS: A01 COMPLETE; A02/A03 NEXT.**
No accepted E1 trajectory or physical vehicle result exists.

W1 starts from exactly `6370d0436aabd011d1b885fe1f500644b957b536`,
on new durable branch `project-a/w1-geometry`; no upstream rebase was performed
because the user explicitly required that verified W0 base. A01 adds the strict
v1 manifest, frozen records, canonical identity and six fixed synthetic fixtures.
`verify.sh all work/w1-a01-final`: exit 0, 39 A01 + 7 W0 numerical + 4 installed
ROS tests; three packages built. Legacy now collects 51 tests (39 new functional
tests + original 12), with the same 10 failures / 2 skips and no added W1 lint
diagnostics. See `evidence/w1-a01` and [W1 contract](W1_GEOMETRY.md).
Checkpoint commit is the commit introducing this section; exact source bytes
and tested parent are recorded in its evidence. A02 follows only after this commit.

## Source and durable review route

- Upstream/fork `ros2-humble`: `67981ed7964a6d35e1da48f0c22bbd9f6d123d5e` at task
  start, verified with `git ls-remote`. Started on clean local branch `work`.
- Implementation + tests + first evidence commit:
  **`73afd1f95600da8aac1a29a0aa871aed227b4e49`**.
- Durable branch: [Felix-Grote/race_stack:project-a/w0-cloud-foundation](https://github.com/Felix-Grote/race_stack/tree/project-a/w0-cloud-foundation).
  The subsequent W0 closeout commit contains docs/evidence only; its identity is
  available with `git log -1 --format=%H` on that branch. Executable files are
  unchanged from tested commit `73afd1f` (hash ledger retained).
- All seven recursive submodules match pinned gitlinks, are clean and unchanged;
  [full identities](evidence/source-baseline.json). Optimizer:
  `b1b38ecfefec7200d5bcb243f115af1d795b3766`.
- Upstream API permission: pull=true, push=false. Existing fork: push=true;
  actual feature-branch push succeeded. Draft upstream PR creation via `gh pr
  create --repo ForzaETH/race_stack --base ros2-humble --head
  Felix-Grote:project-a/w0-cloud-foundation --draft ...` was denied:
  `GraphQL: Resource not accessible by integration (createPullRequest)`.
  Review the branch; [prepared PR text](REVIEW.md) and a comparison link are saved.
  PR creation permission is a limitation, **not a blocker to the requested branch
  delivery**. No upstream merge occurred.

## Executed W0 exit checks

| Check | Result |
|---|---|
| Host / supported test path | Debian 13 x86_64, Python 3.12.14, no native ROS/colcon; Docker 28.4.0 local daemon/vfs works; **Path D** |
| Isolated test platform | Ubuntu 22.04.5, Humble, Python 3.10.12; UID 1000 Cloud / nonroot hosted runner; no network, devices, capabilities or writable source/root |
| Pinned build/setup | PASS, exit 0; dependency/apt pins, CA secret mount, pip check |
| Numerical suite | **7 passed**, 0 failure/error/skip; two real single ordered QPs, no legal certificate |
| Selected colcon build | **3 passed**: f110_msgs, frenet_conversion, global_planner |
| Installed ROS suite | **4 passed**, 0 failure/error/skip; actual CDR + nine-group JSON + installed imports/Frenet |
| Fresh remote clone | PASS at 73afd1f, recursive gitlinks; setup/functional runner exit 0; source clean after execution |
| Independent GitHub Actions | **SUCCESS** at 73afd1f; logs independently show 7 numerical + 4 ROS + 3-package build |
| Original colcon baseline | **FAIL**, 12 reports / 0 errors / 10 failures / 2 skipped; test and summary exits 1; preserved lint/XML logs |
| Original planner/config/maps/gitlinks | Unchanged, verified against base |
| W1/A01–A03 through W3/A09 | **NOT IMPLEMENTED / NOT ACCEPTED** |

[CI run 38862974185](https://github.com/Felix-Grote/race_stack/actions/runs/38862974185)
completed successfully on the GitHub Ubuntu 22.04 runner. Logs and artifact
metadata are committed. Downloading its artifact ZIP in Cloud returned HTTP 403;
job logs were fetched successfully and confirm counts. The original artifact is
retained on that run; no unavailable artifact values were invented.

Fresh-clone commands executed:

```bash
git clone --branch project-a/w0-cloud-foundation --recurse-submodules https://github.com/Felix-Grote/race_stack.git work/clean-checkout
cd work/clean-checkout
scripts/project_a/setup.sh
scripts/project_a/verify.sh all work/clean-verify-final
git status --porcelain
git submodule status --recursive
```

Setup and verification exit 0; final source status empty. Initial console logs
were briefly outside `work/` in the first clean-clone invocation; moved into
scratch before the final clean run. The committed `evidence/clean-clone` is the
final run and records clean source, not the transient scratch files.

Every command, tolerance, source/helper/dependency identity, failure and output
ledger is linked in [RESULTS](RESULTS.md). Reproduce with [RUNBOOK](RUNBOOK.md).
No W0 technical/verification blocker remains. PR permission and artifact-ZIP
retrieval are the recorded external limitations; branch, CI logs and local full
raw evidence are durable.

## Exact next instruction

**Resume W1 from `Felix-Grote/race_stack:project-a/w0-cloud-foundation` (or its
reviewed merge). Read `docs/project_a/{EXECUTION_PLAN,STATUS,DECISIONS,RESULTS}.md`
and the canonical references; verify HEAD, all recursive gitlinks and passing CI
at `73afd1f`. Reconcile upstream `ros2-humble`, run the committed W0 runner, then
implement A01 strict legal-route input, A02 periodic metric curve/stateless
queries, and A03 occurrence-owned corridor preparation. Execute the analytic and
adversarial acceptance tests, commit each checkpoint with fixtures, tolerances,
evidence and status, and publish a reviewable branch. Preserve legacy behavior;
do not proceed to or claim A04 solver/continuous-footprint acceptance in W1.**
