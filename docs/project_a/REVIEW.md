W0 restores the missing repository-local ROS development foundation for Project A. It adds a digest-pinned Ubuntu 22.04/ROS 2 Humble test image, hash-locked numerical dependencies, a nonroot/read-only/network-disabled Compose target, reproducible setup/verification scripts, planner-specific CI, and the execution/status/decision/results documents with canonical inputs and raw evidence.

Verification in Codex Cloud: 7 numerical checks passed (including two real ordered synthetic QPs); `f110_msgs`, `frenet_conversion` and `global_planner` built and installed; 4 actual ROS/install checks passed (generated message CDR, existing nine-group JSON, installed utilities/optimizer and Frenet). The published branch was recursively cloned and the checks repeated. Existing colcon baseline remains red: 12 aggregate reports, 0 errors, 10 failures, 2 skipped; complete lint/XML logs are preserved separately. `verify.sh all` gates functional checks and reports baseline failures explicitly; `verify.sh legacy` returns their failure status.

Base is live `ros2-humble` at `67981ed7964a6d35e1da48f0c22bbd9f6d123d5e`; all seven recursive gitlinks match. Production planner, maps, configs, messages, submodules and vehicle-facing code are unchanged. No hardware Compose, host networking, nodes or devices were used. W0 is infrastructure only: A01–A09, continuous legal/footprint validation, cyclic dynamics and real-course/vehicle acceptance are not implemented or claimed.

See `docs/project_a/STATUS.md` for exact commit/run identities and the W1 A01–A03 continuation instruction, `RESULTS.md` for measured values/tolerances, and `RUNBOOK.md` for reproduction. Please review; no automatic upstream merge.

Upstream draft PR creation was attempted and denied by the GitHub integration.
The durable branch is ready for review:
https://github.com/Felix-Grote/race_stack/tree/project-a/w0-cloud-foundation

Prepared upstream comparison:
https://github.com/ForzaETH/race_stack/compare/ros2-humble...Felix-Grote:project-a/w0-cloud-foundation?expand=1

Confirmed hosted CI:
https://github.com/Felix-Grote/race_stack/actions/runs/38862974185
