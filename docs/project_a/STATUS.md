# Project A status — 2026-10-16

W0 functional preparation is implemented; final pinned-image and clean-clone
verification/publication are in progress. A01–A09 are **NOT STARTED**.

Source base: live upstream and fork `ros2-humble` both
`67981ed7964a6d35e1da48f0c22bbd9f6d123d5e`. Review branch:
`Felix-Grote/race_stack:project-a/w0-cloud-foundation`. All seven recursive gitlinks
match; see evidence manifest. Upstream is read-only, fork is writable.

Initial executed run `scripts/project_a/verify.sh all work/attempt-2`: numerical
7/7, selected colcon build 3/3, installed ROS/serialization 4/4. Existing colcon
baseline reports 12 tests / 0 errors / 10 failures / 2 skipped (test and summary
exit codes both 1). No runtime/planner production changes. Final evidence follows.

Next after W0 acceptance: **Resume W1 on the published W0 feature branch; verify
HEAD/gitlinks and run the committed runner, then implement and independently test
A01–A03 from the canonical architecture/roadmap, committing each checkpoint with
fixtures, numerical tolerances, evidence and updated status. Preserve the legacy
planner and do not claim solver/legal-footprint acceptance.**

Final pinned-image working-tree verification passed: `setup.sh` exit 0,
`verify.sh all work/final-pinned` exit 0, numerical 7/7, build 3/3, actual ROS 4/4.
Exact measurements, limitations and red legacy results: [RESULTS](RESULTS.md).
[RUNBOOK](RUNBOOK.md) is the executable reproduction procedure. Publication and a
fresh remote clone are the remaining W0 exit checks, not an A01 implementation.
