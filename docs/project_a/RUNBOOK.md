# W0/W1 reproducible offline development

Run from a recursive checkout of the named review branch, as a nonroot user with
access to the **local** Docker socket. Setup needs HTTPS/HTTP access to GitHub,
Docker Hub, Ubuntu/ROS apt repositories and PyPI. Tests run with no network.
No ROS or numerical package is installed on the Debian Cloud host.

```bash
git clone --branch project-a/w1-geometry --recurse-submodules https://github.com/Felix-Grote/race_stack.git
cd race_stack
git rev-parse HEAD
git submodule status --recursive
scripts/project_a/setup.sh
scripts/project_a/verify.sh all work/review-1
```

`setup.sh` is also the published environment setup/maintenance entry point. It
initializes recursive gitlinks (no `--remote`), checks pin consistency, addresses
the local managed daemon explicitly and builds the image. Preserve platform proxy
and Docker credential configuration. In Cloud the system CA bundle is mounted as
a BuildKit secret for apt/pip; it is not copied into the image. Network-policy or
registry authorization failures must be diagnosed, not bypassed. Setup does not
run hardware Compose, use host networking or change a Docker daemon.

The image uses the digest-pinned `ros:humble-ros-base-jammy`, Python 3.10.12 and
NumPy 1.26.4 / SciPy 1.11.4 / TPH 0.79 / quadprog 0.1.7. Exact direct and transitive
numerical dependencies and build tools have PyPI hashes in `requirements*.lock`.
The older quadprog is deliberately built with Cython 0.29.37 and no build isolation.
`requirements.in` documents direct intent; the locks govern builds. Do not install
the optimizer's historical requirements into this environment. CasADi/scikit-learn
are imported by the legacy optimizer package; their presence does not validate its
minimum-time backend. Apt venv packages have exact versions; if removed upstream,
setup fails rather than silently updating. Full OS/pip inventories are emitted per
run. Image digests and package versions pin inputs, not bit-identical local image
IDs: apt metadata/timestamps and compiled wheel bytes can vary between rebuilds.
A new supported dependency set requires explicit verification and updated evidence.

Use a **fresh** output path for each invocation:

```bash
scripts/project_a/verify.sh numerical work/numerical-1
scripts/project_a/verify.sh ros work/ros-1
scripts/project_a/verify.sh legacy work/legacy-1
```

- `numerical`: A01/A02/A03 suites (47/12/17), scoped new-file flake8, and the
  original seven W0 dependency/QP/oracle/legacy-characterization checks.
- `ros`: isolated non-symlink colcon install of `f110_msgs`, `frenet_conversion`,
  `global_planner`; optimizer wheel build/install; four original ROS/install tests plus one installed W1 geometry/corridor test.
- `legacy`: same build/ROS checks, then original selected colcon tests. Returns their
  failure status. No lint deletion, blanket xfail or production repair.
- `all`: numerical + ROS checks must pass; records legacy results independently.
  Exit zero means **W0 and W1 functional checks passed**, not that legacy lint is green.
  `legacy-exit-codes.txt`, `legacy-results.txt` and `summary.json` expose the red
  baseline; CI emits a warning and uploads evidence. An early functional failure
  returns nonzero, even if later reports have not been produced.

The two W0 pytest calls disable third-party plugin autoload because Humble's
`launch_testing` plugin scans neighboring files before generated messages exist.
These tests do not use launch testing. Original colcon tests retain normal plugin
loading. This is not a change to any assertion or legacy result.

Runtime is nonroot (the calling UID/GID), root/source read-only, all capabilities
dropped, no-new-privileges, network none, private IPC, no host devices, 4 GiB/2 CPU/
256-PID limits. `/tmp` and a dedicated output mount are writable. Runtime assertions
check effective UID/capabilities/network/root/source permissions. The container
copies only the three packages to `/work/src`; colcon and wheel outputs are outside
the original checkout. Installed imports run from `/work` and must resolve under
`/work/install` or `/work/python`, not the original source. ROS checks serialize
Wpnt/WpntArray and use the actual existing JSON reader/writer; no ROS node,
publisher, GUI, map extraction, controller or driving stack is started.

Run artifacts contain commands/source status/gitlinks, image ID, system and pip
inventories, runtime properties, helper hashes, JUnit, synthetic measurements,
colcon/wheel logs and legacy failures. Source document hashes and curated evidence
are under `docs/project_a/evidence`. JUnit timestamps and wall time are observations,
not release performance thresholds. Do not upload build/install directories as a
substitute for source and dependency identities.

`.github/workflows/project-a.yml` repeats Path D on an Ubuntu 22.04 GitHub runner
using the same image/scripts and read-only token permissions. It runs for planner,
interfaces, Frenet library and infrastructure changes. CI being configured is not
evidence that a run has passed; consult the exact commit's run and artifacts.
A01/A02/A03 tests are wired explicitly into the runner. A04–A09 tests must be
added when implemented; W1 does not cover the future solver or compiler. If Docker becomes unavailable,
follow the execution plan's Path C and prove Humble CI before claiming validation.

W1 implements A01–A03 only. No accepted optimized trajectory, continuous
footprint certificate, cyclic dynamics acceptance or physical vehicle result is
delivered. See W1_GEOMETRY.md for the supported geometry and numeric limits.
