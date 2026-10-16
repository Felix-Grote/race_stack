# Project A ownership and execution

Read `docs/project_a/EXECUTION_PLAN.md`, `STATUS.md`, `DECISIONS.md` and the two
canonical reference specifications at the repository root before Project A work.
The 2026-10-16 execution plan supersedes the older roadmap's A01-only dispatch,
not its technical acceptance. Actual source and executed tests override historical
repository assumptions. Work only in the wave requested by the current task.

- Preserve the legacy planner, maps, configs and optimizer gitlink by default.
- Never run the root hardware `docker-compose.yaml`, stack launch, device access,
  controller, localization, perception or actuator code. The standalone
  `docker-compose.test.yaml` is the test target; do not merge Compose files.
- Keep new compiler/kernel modules ROS-independent. Overlapping XY does not imply
  connectivity or shared occurrence/surface ownership. Never inflate legal widths.
- Tests must distinguish numerical QP results, ROS serialization, continuous legal
  validation and physical evidence. Sampling alone cannot certify swept containment.
- Use `scripts/project_a/setup.sh` then `scripts/project_a/verify.sh all`.
  Add checkpoint tests under `planner/global_planner/test/` and wire them into the
  runner explicitly; existing lint failures are separately recorded, never hidden.
- Commit each completed checkpoint with tests, exact commands, tolerances, source
  and fixture identities, evidence and updated status. No upstream auto-merge.
- Normal technical repairs are autonomous. Stop only for the genuine blockers in
  the execution plan; do not silently weaken release criteria or change B to C.
- Output/builds belong in scratch (`work/`), never original maps or source modules.
