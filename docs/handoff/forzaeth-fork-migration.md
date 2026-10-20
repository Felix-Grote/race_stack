# ForzaETH fork migration — final report (global planner sub-team)

Date: 2026-10-20. Worker: firstmate crewmate (`fm/forzaeth-fork-migration`).

## 1. Final repository state

- Public fork: [Felix-Grote/race_stack](https://github.com/Felix-Grote/race_stack),
  fork of [ForzaETH/race_stack](https://github.com/ForzaETH/race_stack) (`fork=true`,
  parent `ForzaETH/race_stack`; never detached, never recreated).
- Public branch (exactly one): `ros2-humble`
  → `41e339320d52e23a78a41c73fe579e6a312472d9`
  (3 commits on upstream `6a2900ac06de2a767f1d1b818a8dec8f8b9c59aa`,
  fast-forward from the previous tip, no force-push).
- Upstream `ForzaETH/race_stack` untouched (read-only `ls-remote` checks only).
- Private archive: [Felix-Grote/forzaeth-planner-private](https://github.com/Felix-Grote/forzaeth-planner-private),
  standalone repo (`fork=false`, `parent=null`), visibility `private`,
  sole collaborator `Felix-Grote`, no pending invitations.

Private repo branches (all tips SHA-identical to the fork pre-cleanup state):

| branch | tip |
|---|---|
| `ros2-humble` | `6a2900a` |
| `audit/upstream-baseline-6a2900a` | `a31886b` |
| `project-a/w0-cloud-foundation` | `3056e78` |
| `project-a/w1-geometry` | `4bfcf35` (PR #1 + PR #2 + PR #3 merge) |
| `project-a/w2-optimization` | `fe53365` |
| `project-a/w3-reference-benchmarks` | `b961d20` (accepted W3 HEAD, tag `project-a/w3-accepted-b961d20`) |
| `project-a/w3-independent-final-benchmarks` | `7fcecd9` |
| `project-a/w3-scout` | `68e301c` |
| `w3-evidence-17e4ec4` | `326aa37` |
| `w3-independent-final-b961d20` | `f1827cd` (tag `project-a/w3-research-archive-final-b961d20`) |
| `w3-independent-review-20261017` | `676e59a` |
| `archive/metadata` | PR #1–#3 bodies/checks/API records, 45 CI run records, key logs |

Public fork branches after cleanup: only `ros2-humble` (10 obsolete
`project-a/*`, `w3-*`, `audit/*` branches deleted from the fork only).

## 2. Archival verification (Phase B gate — PASSED before any deletion)

- `Felix-Grote/forzaeth-planner-private` created private, confirmed
  `private=true`, `fork=false`, `parent=null` via API.
- All 11 fork branches + 2 annotated tags pushed; tip SHAs match the fork.
- Per-tip tree IDs match on all 11 branches; history depth matches
  (e.g. `project-a/w1-geometry` 165 commits, `project-a/w3-reference-benchmarks`
  164 commits, both sides).
- Blob SHA-256 spot checks match; `docs/` file count 2403 = 2403.
- Independent clone + readback from a clean directory; `git fsck` clean.
- PR #1, #2, #3: full bodies, check conclusions (`isolated-humble` pass),
  API records, and (empty) comment/review listings exported — there were no
  PR comments or reviews to lose.
- CI: all 45 workflow runs exported (42 success, 3 cancelled); job/step
  records for 6 key runs; full step logs for 5 acceptance runs
  (W1/W2/W3 merges, final benchmark replay, upstream-baseline audit).
- Access: sole collaborator `Felix-Grote`; no invitations; visibility private.
- Local recovery bundle `/tmp/mig/fork-backup.bundle` (382 MB, all refs + tags,
  `git bundle verify` clean) — scratch copy; the durable archive is the
  private repo.
- Nothing inaccessible: cancelled runs have no logs by nature (recorded as
  `cancelled` in metadata); PR conversations were empty; W1–W3 reviews,
  manifests, benchmark outputs, failure reproductions all live in-branch
  (`docs/`, `scripts/project_a`) and were pushed verbatim.

## 3. Production delta (Phase C — file-level vs upstream `6a2900a`)

True Project A delta was measured `67981ed..b961d20` (Project A branched at
`67981ed`, two commits behind upstream tip). Every
controller/perception/state-machine/utilities/stack-master/local-planner
difference vs `6a2900a` is upstream's own `67981ed..6a2900a` work, which
Project A never touched — reconstruction from fresh upstream keeps all of it.

Retained on public `ros2-humble` (25 files, byte-identical to accepted W3):

- 11 modules under `planner/global_planner/global_planner/`:
  `route_input`, `_route_geometry`, `route_reference`, `route_corridor` (W1);
  `iqp_route_adapter`, `cyclic_retime`, `route_validate`,
  `route_validate_dynamics` (W2);
  `route_artifact`, `route_compile`, `route_legacy_export` (W3).
- `package.xml`: +6 `exec_depend` (`python3-numpy`, `python3-scipy`,
  `f110_msgs`, `std_msgs`, `visualization_msgs`, `rosidl_runtime_py`).
  All used: numpy/scipy directly; the message packages via lazy imports in
  `route_legacy_export._write_ros_product`; `rosidl_runtime_py` alongside
  the pre-existing `readwrite_global_waypoints` CDR path.
- `setup.py`: `compile_route` console entry + installed
  `config/project_a/{models,policies}` data files.
- 12 curated offline inputs: `config/project_a/models/*.json` (10),
  `config/project_a/policies/*.json` (2) — explicit inputs the accepted
  `setup.py` installs; the compiler takes all inputs as explicit CLI args.

Excluded to the private archive only: `test/` (31 files, incl. byte-duplicate
fixtures), `config/project_a/fixtures/` (9, byte-identical to test fixtures),
`build_identity.json` (stale research provenance), `AGENTS.md`,
`PROJECT_A_GUIDE.md`, `docs/` (2403 research files), `scripts/project_a`
(24 harness files), `.github/workflows/project-a.yml`, `docker-compose.test.yaml`,
`.gitignore` `/work/` addition. Public diff: 25 files, +~6.8 k lines,
nothing outside `planner/global_planner/`.

Submodule note: Project A never moved `global_racetrajectory_optimization`
(stayed `b1b38ec`); upstream moved it to `ace99a4`. Reconstruction keeps
upstream's `ace99a4`. The new code does not consume the submodule: the IQP
adapter pins the *pip* package `trajectory-planning-helpers==0.79`
(`opt_min_curv.py`/`calc_splines.py` hashes) plus exact
numpy/scipy/quadprog versions, enforced at runtime. The ROS build does build
the optimizer wheel from the submodule — covered by the installed tests.

## 4. Public reconstruction (Phase D)

From freshly fetched upstream `ros2-humble` (`6a2900a`, re-verified via
`ls-remote` at reconstruction time), three wave-grouped commits applying
final accepted file states (no merge/squash of development branches):

- `0ad233a` W1 geometry kernel (4 modules)
- `06da9fc` W2 optimization + validation (4 modules)
- `41e3393` W3 artifacts/CLI/export + models/policies + package integration

Checks: `merge-base` with upstream is `6a2900a` (true descendant);
`git diff 6a2900a..41e3393 --name-only` is exactly the 25 files;
those 25 files are byte-identical (`git diff` empty) to accepted `b961d20`.
No fork `ros2-humble` history rewritten except by verified fast-forward
(see §6); no shared files (`package.xml`/`setup.py` of other packages,
launch/waypoint interfaces, controller, perception, localization,
simulation) touched.

## 5. Verification (Phase E)

Method: archived harness run verbatim against the production tree.
Verification tree `/tmp/mig/prod` = `git archive` of production
`41e3393` (all production paths SHA-256-identical to the pushed tip)
plus archived harness overlay from accepted `b961d20`
(`scripts/project_a`, `planner/global_planner/test`,
`docs/project_a/evidence/pinned-run`, `docker-compose.test.yaml`) plus the
optimizer submodule cloned at the production pin `ace99a4` (other
submodules are not consumed by any verified test). Image rebuilt from the
archived Dockerfile (digest-pinned `ros:humble-ros-base-jammy`, hash-pinned
pip requirements incl. `trajectory-planning-helpers==0.79`,
numpy 1.26.4, scipy 1.11.4, quadprog 0.1.7).
Driver: `container_verify.sh all` (numerical → ROS-installed → legacy),
then `isolated_runtime.sh` (source-free A09), same as CI.
Baseline: accepted-merge CI run `39302290392` on `4bfcf35`
(607 functional tests green; legacy colcon 597 tests / 10 pre-existing
failures: code-style, recorded separately, never gating).

Results (production `41e3393`; `summary.json` in verification outputs):

- Functional suites: **602/607 green, 0 errors.** All W0–W3 acceptance green:
  a01 (60), a02 (47), a03 (38), a04 IQP (18), a05 geometry (40) + oracle (13),
  a06 retime (21) + dynamics (41) + oracles (8+1), w2 handoff (10) / numerical
  oracle (3) / shared-cap (49) / pipeline (10) / novel (1), a07 artifact (114)
  / cli (68) / export-pure (27) / export-ros (2), a09 harness (5),
  numerical (7), ros (4), w1-installed (1), w2-installed (1). Positive and
  negative cases included (fail-closed CLI, corruption, timeout budgets).
- `a08-regressions` 13/14: the single failure
  (`test_archives_remain_software_data_with_original_closing_acceleration`)
  asserts research-era bytes of upstream-owned
  `stack_master/maps/GLC_smile_small/global_waypoints.json`
  (`closing_acceleration_mps2 < -19`). Upstream commit `6a2900a`
  ("update stored maps") changed it to `-1.70`; value at research era was
  `-19.52` (two-route corroboration). Control rerun of the same suite with
  only those 3 map files restored: **14/14 pass** — product code unaffected.
  Legacy colcon surfaces the same test (597 tests, 11 failures = 10
  pre-existing style failures + this one; baseline was 10).
- `w3-installed` (4) and source-free (5): blocked in `_inputs` by the
  archived hardcoded `_GITLINKS` (optimizer `b1b38ec…`, old gym pins) vs
  production (`ace99a4…`, new gym pins from upstream `6444d2a`/`6a2900a`) —
  research-era pins that fail before any planner code executes. The colcon
  build, optimizer wheel build from `ace99a4`, install, and `test_ros` /
  `test_w1/w2_installed` all pass on production pins. Direct supplement on
  the installed product: installed `compile_route` binary + installed share
  models/policies → compile PASS, validate PASS, query PASS, export PASS
  (isolated, network-none container).
- Verdict: **no product regression** — every test exercising planner code
  passes identically to the accepted baseline; the two failing assertions
  pin obsolete upstream bytes (maps, submodule SHAs) outside the production
  delta and fail on any fresh-upstream tree. Promotion gate: PASS with the
  documented drift items (private tests stay private; nothing ships).

## 6. Publish and cleanup (Phase F)

Preconditions (all re-verified immediately before any push/delete):

- `git ls-remote` upstream `ros2-humble` still `6a2900a` (no upstream drift
  to silently overwrite);
- fork `ros2-humble` still `6a2900a` (fast-forward applies cleanly);
- Phase B gate evidence intact (private repo refs unchanged);
- Phase E gate: summary shows zero functional failures/errors.

Publish (executed 2026-10-20, all preconditions held: upstream and fork
tips both `6a2900a`, ancestry `6a2900a` → `41e3393`, private refs intact,
Phase E gate PASS): pushed `41e3393` as **fast-forward**
`6a2900a..41e3393` of fork `ros2-humble` (no force-push); remote tip and
tree independently confirmed identical to the verified reconstruction;
`fork=true`, parent `ForzaETH/race_stack`, default branch `ros2-humble`.
Cleanup (fork only, never upstream; zero open PRs on the fork): deleted the
ten obsolete branches
`audit/upstream-baseline-6a2900a`,
`project-a/w0-cloud-foundation`, `project-a/w1-geometry`,
`project-a/w2-optimization`, `project-a/w3-reference-benchmarks`,
`project-a/w3-independent-final-benchmarks`, `project-a/w3-scout`,
`w3-evidence-17e4ec4`, `w3-independent-final-b961d20`,
`w3-independent-review-20261017`.
Confirmed: fork has exactly one branch (`ros2-humble` @ `41e3393`);
upstream `ros2-humble` still `6a2900a`; private archive intact (12 refs).
The two pre-existing annotated tags remain on the fork (tags, not branches;
they anchor merged PRs #1–#3 and the archive).
Note: this report itself ships on worker branch
`fm/forzaeth-fork-migration` (pushed per task delivery contract for firstmate
review/cleanup); the production end-state above refers to long-lived branches.

## 7. Future workflow commands

Public fork tracks upstream; production work happens locally; experiments,
tests, research and evidence stay private; verify privately against exact
SHAs before publishing; only functional planner changes go public;
`ros2-humble` stays the only long-lived public branch.

```bash
# add upstream once, sync (never merge dev branches into ros2-humble)
git remote add upstream https://github.com/ForzaETH/race_stack.git
git fetch upstream
git checkout ros2-humble && git merge --ff-only upstream/ros2-humble

# stage a production change from a local work branch, then fast-forward
git checkout -b feat/<scope> ros2-humble   # edit only planner/global_planner
git push origin feat/<scope>               # review; rebase onto fresh upstream
git checkout ros2-humble && git merge --ff-only feat/<scope>
git push origin ros2-humble

# private verification of an exact SHA (adapted Phase E recipe)
git archive <SHA> | tar -x -C /tmp/verify-tree
git archive <accepted-research-SHA> -- scripts/project_a \
  planner/global_planner/test docs/project_a/evidence/pinned-run \
  docker-compose.test.yaml | tar -x -C /tmp/verify-tree
# place optimizer submodule at the SHA recorded in <SHA>, then:
docker build -f scripts/project_a/Dockerfile -t project-a-humble:w0 /tmp/verify-tree
PROJECT_A_OUTPUT=/tmp/verify-out docker compose -f docker-compose.test.yaml run --rm test all
```

