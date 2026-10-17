# ForzaETH ICRA27 — Project A Codex Cloud execution plan

Version 2026-10-16 | Independent review update 2026-10-17
Owner: Global-planner subsystem | Acceptance specification below remains authoritative.

W3 independent review has reproduced and corrected publication ancestry,
installed timeout evidence and initial legacy-fit classification findings.
[The review](W3_INDEPENDENT_ADVERSARIAL_REVIEW.md), STATUS and RESULTS record exact
source checks, failures, numerical limits and the lossless evidence disposition.
The completed literal-head clean/hosted/source-free gates and release verdict
are recorded in the separate companion publication manifest linked there;
no historical implementation checkpoint substitutes for those gates.

# 1\. Executive decision and supersession

This document supersedes the execution policy, sequencing, and “A01 only” authorization in the 2026-10-10 Project A roadmap and 2026-10-15 archive index. It does NOT supersede GLOBAL\_PLANNER\_PROJECT\_A\_ARCHITECTURE.md's engineering contracts, the A01–A09 acceptance requirements, or the recorded numerical findings. The original nine PR descriptions remain the implementation specification; A01–A09 are now sequential acceptance checkpoints, not necessarily nine manually commissioned Codex Cloud tasks or nine individual pull requests.

No new calendar deadline was specified; drive by verified milestone exits rather than a fixed schedule. Do not silently expand the ownership boundary into a full autonomous-driving system.

The objective is full software implementation and independent validation of standalone offline E1 global planning: manually selected directed legal route / occurrence / surface / portal input; ordered original-boundary corridor; accurate periodic metric geometry; small TUM minimum-curvature IQP adapter; continuously bounded footprint/border validation; cyclic speed model and validation; immutable reference and compatible existing ROS waypoint export; reproducible S0–S6 benchmark and handoff.

Out of scope without separate authorization: online route graph and branch switching; live localization or occurrence tracking; perception, carstate, local planning, controller or actuation changes; on-car launch; physical safety certification; any privileged device access. Overlapping XY surfaces must remain distinct in the planner data model. Ramp information is annotated, not inferred proof of 3D clearance, tire/contact or grade feasibility.

# 2\. Observed source baseline and evidence hierarchy (16 October 2026\)

The GitHub ForzaETH/race\_stack ros2-humble ref resolved to 67981ed7964a6d35e1da48f0c22bbd9f6d123d5e. The prior indexed research had read 41c8e768415537cd8505ed107d61c7cb32267643, following merge PR \#43 (state-estimation rewrite and planner TF integration). The source study and pinned optimizer experiments refer to parent 00a166de963134746540c1971c7d888203c5ac46 and optimizer b1b38ecfefec7200d5bcb243f115af1d795b3766. Treat every research SHA as evidence provenance, not a safe patch base; Codex must inspect the live branch and actual gitlinks at its task start.

Verified GitHub ros2-humble lacks docker-compose.test.yaml, docs/development/ROS\_HUMBLE\_BASELINE.md, and the planned planner route\_input.py; the P01 isolated files were reported created on a workstation, not pushed to this branch. The remote repository still exposes hardware-oriented docker-compose.yaml (host networking, privileged, /dev mount), which must never be used by a coding agent. The current ROS global\_planner\_node.py remains an existing legacy entry point; do not replace it by default. Current connected GitHub integration reports pull access but not push to ForzaETH/race\_stack; Codex’s separate GitHub authorization may differ, so verify and use a properly permissioned personal fork and upstream PR workflow if upstream write is unavailable.

P01 built a subset of ROS 2 Humble packages twice in a local isolated Docker image; selected pre-existing lint / XML schema checks failed. Direct small ordered TUM QP solves on synthetic ellipse / figure-eight succeeded, but neither output had certified legal swept containment. Existing spline preparation has an observed SciPy shape error; existing arc-length interpolation has an observed station discrepancy. Never upgrade this evidence to “full planner working.”

Source priority: actual checkout \+ executed logged tests \> 2026-10-10 Project A architecture/roadmap and pinned probes \> Pro research \> legacy README. Do not invent ICRA2027 rules, full-course track approval, car parameters, or physical proof.

# 3\. Cloud campaign: autonomy, persistence, and review policy

Use ONE reusable published Codex Cloud environment for this repo, and execute four dependency-ordered waves. Within each wave Codex can work autonomously through A-checkpoints, refactor, test, review and correct faults without asking for routine approval. Preferred default: one cloud task per wave (W0–W3), yielding at most three substantive review/merge gates; small individual commits preserve A01–A09 auditability. A task may continue to the next checkpoint within its wave once the prior checkpoint's automated acceptance passes. Do not demand user approval after each old nine-PR item.

Cloud tasks have isolated workspaces. Codex must make small coherent git commits and persist meaningful changes to a remote feature branch or PR; task history / temporary workspace alone is not a durable transfer. Never assume starting a fresh task restores an uncommitted earlier task. The next wave begins from the tested, merged previous wave, or from an explicitly named feature branch if upstream review is pending. Rebase against ros2-humble at each wave start; reconcile changed interfaces before coding.

Keep repo-local control documents, created in W0:  
  docs/project\_a/EXECUTION\_PLAN.md — copy of this decision and links to the full reference specs.  
  docs/project\_a/STATUS.md — checkpoints, evidence, test commands, pass/fail/unsupported, current base and commits, blockers, exact next executable task.  
  docs/project\_a/DECISIONS.md — only meaningful deviations, rejected shortcuts, model/tolerance choices and tradeoffs.  
  docs/project\_a/RESULTS.md — compiled final validation matrix with hashes and limitations (populated throughout, finalized W3).  
  Scoped AGENTS.md guidance in the planner tree or root, preserving any existing instructions.  
  scripts/project\_a/verify.sh (or equivalent documented test entry point), plus ROS2 CI workflow when necessary.

After EACH checkpoint A01–A09, Codex updates STATUS and commits its change together with tests. A “PASS” must include the command, exit code, test count, source SHA, dependency/fixture identities, numerical tolerances and output path/artifact; do not present “not run,” a mocked result, a lint failure, or a synthetic scenario as empirical vehicle evidence. A blocking result is recorded honestly and fixed or escalated; no silent constraint relaxation.

Autonomy rules: investigate root causes, attempt bounded repairs, seek existing library capabilities, write regression-first tests, and prefer minimal targeted abstractions. Auto-continue on ordinary failures that can be resolved within E1 architecture. Stop and request human decision ONLY for: loss of repository write/PR capability; inability to build any credible independent verification environment; architecture B failing a demonstrated feasible case and forcing a consequential C-backend redesign; conflicts with parallel team ownership; safety-critical runtime/hardware action; unavailable required input for a claimed real-course result; or any proposal to weaken legal/continuous/dynamic release criteria. Never run, simulate authorization for, or modify real actuator commands. Do not auto-merge to the upstream branch.

# 4\. W0 — Repository and ROS cloud bootstrap (first cloud task)

W0 is newly mandatory because workstation P01 evidence/files are not available to a fresh cloud checkout. Establish GitHub fetch, recursive submodules and gitlink pinning, usable branches/fork/PR permission, exact current source identity, and a clean baseline of tests. Read and vendor only the two canonical Project A design documents into docs/project\_a/references as clearly dated planning inputs (or attach them directly to the first task and commit normalized copies); do not rely on Codex reaching a private Google Drive link.

Probe Codex Cloud OS/architecture, Python, presence of ROS 2 Humble, docker client AND daemon permissions, colcon, and submodules. ROS 2 Humble binary packages target Ubuntu 22.04 / Python 3.10. Do not attempt to install Jammy ROS binaries into a Noble Python 3.12 environment or assume Docker-in-Docker works. Determine and prove ONE of these testing paths:  
  Path D — usable isolated Docker daemon: port/repair P01's nonprivileged Humble test image and reproducible compose target with no host/devices/net privileges.  
  Path C — Docker not available in cloud: run Python numerical and topology tests in a pinned compatible isolated environment; create GitHub Actions CI on Ubuntu 22.04 / ROS 2 Humble with exact dependencies for ROS serialization, colcon, installation and integration. Do not label Cloud pure-Python tests as ROS validation. If no reliable ROS CI path exists, W0 must stop as BLOCKED rather than claim full completion.

Create a lightweight setup/maintenance script suitable for the actual published environment, cache/pin numerical dependencies, and a verification entry point that reports environment identity. Avoid writing to user hardware, relying on GUI displays or compiling the whole racing stack. Test a clean clone and an isolated planner build; do not hide existing legacy lint/network XML failures. Prefer use of ROS\_PACKAGE\_PATH/source, colcon, and import smoke over a privileged hardware Compose profile. Network should be allowed for setup/submodule/dependency fetch but restricted for execution where practical. No deployment secrets are needed.

W0 exit: accessible cloud source and durable branch, documented permission route, exact gitlinks, successful reproducible numerical smoke and credible ROS 2 Humble validation in Docker or CI, and committed repo-local plan/runner/status. A bare import is not proof of IQP feasibility.

# 5\. W1 — Legal topology, metric curve, and corridor (A01–A03)

A01: strict canonical JSON manifest and semantic validator for manually approved selected directed cyclic routes, explicit occurrence/surface/portal support, side/boundary/gate provenance, versions/units, duplicate-key/nonfinite rejection, fixed S0/S2/S3 fixtures. Do not invent legal edges or infer adjacency from coincident XY. No ROS runtime additions.

A02: ROS-independent periodic cubic, physical metric station s by controlled arc-length integration and inverse, periodic derivative/tangent/curvature, stateless queries carrying supplied route occurrence; avoid global-XY history inference and approximated index×.1. Numeric oracle catches x=t,y=t² station error.

A03: occurrence-owned legal corridor prep; signed left/right normal intersections with original connected legal region and explicit adjacent portal support; monotone inherited q/order and surfaces across resampling; reject off-route, folded, degenerate charts and unsupported geometry rather than inflating widths. No nearest-XY boundary reassignment.

W1 exit: A01/A02/A03 unit suites, analytic oracle, adversarial equality/split/bridge/notch/illegal portal tests and repeatability; commit fixtures and reports. Geometry has no accepted “optimized trajectory” at this point.

# 6\. W2 — Numerical solver and independent acceptance (A04–A06)

A04: bounded optimizer adapter using the pinned TUM ordered minimum-curvature IQP mathematics; bypass unsafe stock preprocessing; re-intersect ORIGINAL occurrence-owned borders after every shifted spline iteration and carry q lineage. Bound iteration/time/memory, expose failure/infeasible; do not edit TPH globally to disguise an error. Run S0 matched-equation and S3 asymmetric boundary/notch stress.

A05: independent, fail-closed continuous planar geometry/footprint validator on the ACTUAL final spline coefficients. Verify all joins/seam, gate passage, original legal area/holes, nonadjacent crossing independence, between-node excursions, footprint swept clearance, and justified numerical error bounds. PASS cannot be based solely on dense sampling or optimizer-reported widths; exhausted budgets \=\> INCONCLUSIVE. Labels/caps not evidence of 3D contact or bridge clearance.

A06: static caps before cyclic squared-speed retiming, closing segment acceleration, lateral limits and supported longitudinal/ggv/motor envelope, optional steering constraints only if model supplied; independently check between-sample residuals and final metadata. Explicit unsupported model terms fail rather than inferred tire performance; measured synthetic constraints are not car certification.

W2 exit: actual compiled whole-lap candidate solves and independent validator PASS on designed feasible S0/S2/S3 fixtures; adversarial false-positive tests rejected; A04–A06 suite green with declared numerical tolerances and resource limits. If B cannot achieve feasible certified solutions for S3, diagnose chart/annotation/conditioning, then escalate with a reproducible failing case and alternative C rationale; do not quietly replace architecture.

# 7\. W3 — Complete artifact, ROS integration, benchmarks, handoff (A07–A09)

A07: versioned immutable hash-addressed offline reference; exact coefficient/profile load, validation, stateless query; canonical deterministic identity; atomic write only on PASS; pure compile/verify/export CLI; installed-resource test; compatibility with existing f110\_msgs Wpnt/WpntArray, accurate main time, closing edge and no fabricated shortest-path profile. Keep legacy runtime path operational as separate opt-in selection.

A08: a fair repaired legacy comparator and S0–S6 campaign. If modifying the optimizer git submodule, commit changes in the submodule repository/fork and update parent gitlink in its own reviewable change; alternatively a reproducible test-local patch, clearly declared. Document unmodified stock errors separately from repaired comparator, preserve original maps and use legal synthetic annotations for complex fixtures. S6 \~240m resource/memory/iteration scaling. No invented lap-time benefit claim or unexecuted numerical thresholds. All benchmark scripts and raw result manifests reproducible.

A09: execute a fresh clean clone/install → compile → independent validate → artifact read/query → legacy ROS serialization roundtrip without GUI or hardware. Publish exact CLI, source+gitlink+dependency/model+fixture hashes, numeric/tolerance ledger, PASS/FAIL/UNSUPPORTED reports, known limitations, supported downstream contract and ownership boundaries. Revalidate both the generated product and installed package—not only source tree imports.

W3 exit: all A01–A09 acceptance checks pass for stated supported synthetic cases; the runbook can be reproduced independently with the same input pins; S0–S6 outcomes are truthful and evidence-backed; no regressions in the legacy entry point; publish a reviewable PR and explicit offline-only release verdict. Missing approved real race data/vehicle calibration is documented as UNSUPPORTED for real-course racing, not quietly called PASS.

# 8\. Nonnegotiable release matrix

S0: simple cyclic curve, direction/side conventions, true arc, reverse/rotated origin, legacy comparison.  
S1: wall gap never enlarges annotated legal corridor.  
S2: independently chosen split alternatives and legal complete cycles.  
S3: disconnected projected bridge XY crossing with occurrence-owned borders and portal order.  
S4: coincident XY/heading sections remain distinguishable with supplied progress/surface label; no runtime inference claim.  
S5: ramp/connector labels and supplied caps; 3D/contact/grade unvalidated unless measured evidence exists.  
S6: representative competition-scale (\~240 m) memory/time/solver scaling, all failed attempts included.  
Adversarial geometry: interior curve/footprint escape despite legal samples, polygon hole, narrow notch, crossing wrong deck, invalid topology, seam mismatch, budget exhaustion.  
Adversarial dynamics/artifact: closing acceleration, caps at seam, curvature interior extrema, infeasible limits, stale metadata, corrupt hashes, inconsistent coefficient/profile identity.

Requirements are inherited from the full A01–A09 roadmap. Do not weaken measured input tolerances or reinterpret incomplete tests as accepted behavior. Source-level reproducibility and mathematical software validity are the promised outcome; localization, vehicle following, traction and physical safety are separate.

# 9\. Codex Cloud initial dispatch prompt (paste into a new task)

You are the implementation owner for ForzaETH Project A: a standalone, safe, fully tested offline global planner for ICRA27. Operate on ForzaETH/race\_stack, branch ros2-humble; start by confirming live HEAD and submodule gitlinks. I have attached the authoritative GLOBAL\_PLANNER\_PROJECT\_A\_ARCHITECTURE.md, GLOBAL\_PLANNER\_PROJECT\_A\_ROADMAP.md, and this 2026-10-16 Codex Cloud execution plan. They are reference design/acceptance contracts; actual code and tests override historical assumptions.

Goal: deliver W0 first, with minimal requests for my attention. Investigate and implement a reproducible safe Codex Cloud development and verification path: recursive pinned checkout, environment/platform/ROS2/Docker capability probe, P01 isolation parity or a viable Ubuntu 22.04 ROS 2 Humble CI alternative, pinned pure numerical dependency smoke, reproducible planner build, repo-local docs/project\_a/EXECUTION\_PLAN.md and STATUS.md and test runner. The older workstation P01 files were NOT pushed; do not assume they exist in GitHub. Do not use privileged hardware docker-compose.yaml, launch ROS driving stack, access devices, or edit actuator/control code. Preserve the existing planner. Confirm push permissions and use my permissioned fork if upstream push is unavailable. Commit all W0 evidence/docs/config as a reviewable branch or PR, with exact commands, revisions, failures and a one-line next-wave instruction in STATUS.md. Do not claim the full planner is implemented. Autonomously resolve ordinary environment faults, but fail closed if no independent ROS validation route is possible.

# 10\. Standard continuation prompt for W1, W2 and W3

Resume ForzaETH Project A using docs/project\_a/EXECUTION\_PLAN.md, STATUS.md, the canonical architecture and nine-checkpoint roadmap, and the committed test runner. Verify current branch/HEAD, gitlinks, latest passing CI and remaining checklist; do not redo completed, verified work. Execute the next unfinished wave (W1 A01–A03, W2 A04–A06, or W3 A07–A09), including tests, adversarial cases, self-review, status/evidence updates and a reviewable PR. Work autonomously inside Project A ownership. Fix ordinary defects, keep previous acceptance gates passing, persist commits, stop only at the specified technical/permission/safety hard blockers. Report exact tests, independent validation status, limitations and the next short continuation instruction. Never self-merge upstream.

# 11\. Human intervention: deliberately limited

Before first cloud task: create/publish Codex Cloud environment; select authorized ForzaETH/race\_stack or writable fork and branch; attach/download once the architecture, roadmap and current execution plan. Approve needed GitHub authorization/PR publishing. Thereafter prefer three continuation task launches after wave results, not nine separate implementation briefs; each can use the standard prompt above and repo-local plans. Review the final evidence and approve any team merge or physical deployment separately.

If GitHub permission fails: grant suitable repo write permission or fork/PR access first. If cloud lacks Docker: accept reproducible ROS 2 Humble CI rather than trying to install the wrong ROS distribution into the base image. If a wave hits an architectural stop: provide the exact reproducer and a minimal decision request, not a vague status summary.

# 12\. Source links

Project A architecture: https\://drive.google.com/file/d/1iP4L5NStTYr7krc7ADBwKicY4o-OhfSt/view  
Project A detailed nine-checkpoint roadmap: https\://drive.google.com/file/d/1LShBecCxzfpxS7yDA\_hXFOvWyJ\_OM4sF/view  
P01 report: https\://drive.google.com/file/d/1Iwl5zXzENT1eb-itYgTyD15kNxzfzc3f/view  
Project A archive/index (research baseline): https\://drive.google.com/file/d/1lP2QNvYbKBsOm0Fd5fbBSyd\_Zbt46tfF/view  
Repository: https\://github.com/ForzaETH/race\_stack/tree/ros2-humble  
Official Codex Cloud help: https\://help.openai.com/en/articles/20001545-using-codex-cloud  
