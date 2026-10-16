# Project A decision ledger

## 2026-10-16 — W0 environment and ownership

1. **Path D selected by execution**, not assumption. Host Debian 13/Python 3.12 has
   no native ROS. Managed local Docker works and runs digest-pinned Ubuntu 22.04 /
   Humble / Python 3.10 without host networking or privileged/device access. Keep
   host untouched; use isolated numerical and actual ROS suites inside that image.
2. **Writable fork route:** upstream `ForzaETH/race_stack` reports pull=true,
   push=false; `Felix-Grote/race_stack` reports push=true. Base matches upstream
   `ros2-humble` at `67981ed7964a6d35e1da48f0c22bbd9f6d123d5e`. Publish review branch
   on the existing fork; never merge upstream automatically.
3. **Re-establish P01 capabilities rather than reuse unpublished files.** Existing
   workspace-only onboarding built messages/Frenet using host network and did not
   build planner. New repo-local setup, isolated Compose, planner install/wheel,
   numerical and serialization checks replace that dependency. No original setup,
   vehicle code, configuration, map or submodule is modified.
4. **Pin kernel, retain helper equations.** NumPy 1.26.4/SciPy 1.11.4/TPH 0.79/
   quadprog 0.1.7 use declared build tools, full numerical dependency hashes and
   versioned apt venv packages. Do not follow optimizer's obsolete dependency file.
   TPH source hashes match research. No global helper patch or optimizer gitlink
   update is made. CasADi imports are not minimum-time verification.
5. **W0 smoke is deliberately limited.** Two single ordered QPs with 64 synthetic
   knots, half-width .75 m, vehicle width .30 m, curvature bound 1/m; finite output
   and nodal offset bound .60 m + 1e-8 m. No convergence, optimized legal curve,
   continuous footprint or vehicle claim. Quadprog analytic tolerance 1e-10,
   independent analytic arc oracle 1e-12 m, installed Frenet smoke 1e-6 m.
6. **Record legacy red independently.** Old selected colcon lint/XML failures stay
   red. `all` gates new functional acceptance and records baseline exit codes;
   `legacy` returns failure. CI warning/report makes this separation explicit.
   No legalization/numerical criterion is weakened to pass W0.
7. **Bounded collection repair:** Humble launch-testing auto-discovery imported ROS
   tests during numerical collection before messages were built. Disable external
   pytest plugin autoload only for explicit W0 files; legacy colcon keeps normal
   plugins. Assertions, source and generated interfaces remain unchanged.
8. **Historical references remain dated inputs.** Vendor byte-identical canonical
   architecture/roadmap and current execution plan. Their workstation paths and
   old SHAs are not fresh evidence. W0 does not act on older A01-only orchestration.
9. **Closeout evidence is separate from executable changes.** Commit `73afd1f`
   was pushed, cloned recursively, retested with clean source and independently
   passed hosted CI. The closeout commit adds documentation/raw evidence only.
   Preserve the exact tested implementation identity rather than imply a
   self-referential final evidence-commit hash.
10. **Branch satisfies publication despite PR restriction.** Actual upstream draft
    PR creation was denied by the GitHub integration. The authorized fork push
    succeeded; deliver its reviewable branch and prepared PR text, without
    requesting routine confirmation or implying that an upstream PR exists.
    CI ZIP retrieval also returned 403, while CI job logs and metadata were
    accessible; preserve those exact logs and do not infer missing artifact data.
