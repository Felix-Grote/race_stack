# Project A — Reproducible Global Planner Demonstration

Demonstrates the **existing** W1–W3 offline global planner on synthetic
tracks: strict route input → TUM IQP-derived geometry optimization →
cyclic retiming → independent geometry/dynamics validation → immutable
artifact publication → trusted reloading and metric queries. No planner
algorithm, tolerance, or safety check was modified for this demo.

## Environment (exact, pinned by the planner itself)

`route_artifact._supported_context` only accepts CPython **3.10.12** with
numpy 1.26.4, scipy 1.11.4, quadprog 0.1.7 and
trajectory-planning-helpers 0.79 (it also hash-checks the helper sources).
Setup used for the verified run:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv python install 3.10.12
~/.local/share/uv/python/cpython-3.10.12-linux-x86_64-gnu/bin/python3.10 -m venv .venv-demo
.venv-demo/bin/pip install "numpy==1.26.4" "scipy==1.11.4" \
  "trajectory-planning-helpers==0.79" matplotlib pytest
# quadprog 0.1.7's sdist is declared language='c++', which mangles the
# Fortran qpgen2_ symbol on modern toolchains; build it locally as C
# (version and sources unchanged; the planner re-hashes helpers itself):
.venv-demo/bin/pip download quadprog==0.1.7 --no-binary :all: -d /tmp/qp --no-deps
tar xzf /tmp/qp/quadprog-0.1.7.tar.gz -C /tmp/qpx
sed -i "s/language='c++'/language='c'/" /tmp/qpx/quadprog-0.1.7/setup.py
.venv-demo/bin/pip install --no-build-isolation --no-deps /tmp/qpx/quadprog-0.1.7
```

No ROS 2 runtime, vehicle, LiDAR or actuation is required; the planner
core is pure Python + numpy/scipy. `PYTHONPATH=planner/global_planner` is
required because the IQP child process re-imports `global_planner`.

## Commands

```bash
PYTHONPATH=planner/global_planner .venv-demo/bin/python scripts/run_project_a_demo.py --all
PYTHONPATH=planner/global_planner .venv-demo/bin/python scripts/run_project_a_demo.py --scenario s2
PYTHONPATH=planner/global_planner .venv-demo/bin/python -m pytest planner/global_planner/test/test_project_a_demo.py -q
```

Each run writes a **new** `demo_project_a/output/run-<timestamp>/`
(fixtures, immutable `<H>/reference.json` artifacts, `figures/*.png|svg`,
`summary.json`). Existing artifacts are never overwritten (publication
itself refuses existing targets).

## Scenarios

| Scenario | Construction | Proves |
|---|---|---|
| S0 | Ellipse (a=8, b=5), 4 occurrences, varied curvature | Full compile → validate → reload → query; corridor adherence; cyclic speed profile |
| S1 | Two whole laps sharing o0/o3, differing northern branch o1/o2 | Two **manually selected** routes independently optimized and compared. The E1 planner does **not** select branches; no shortest-path claim is made |
| S2 | Gerono lemniscate; o0 (ground) and o2 (**upper-deck**, 2.5 m/s limit) both cross the origin in XY | Distinct surface/occurrence ownership at overlapping XY, ordered directed transitions, surface-dependent speed limit. XY overlap is not a connection and proves **no 3D bridge clearance** |
| S3 | Mutated inputs / tampered artifact / tight hairpin (a=3, b=1.1) | Three distinct rejections: input validation (`RouteError`), trusted-loading integrity (`ArtifactError: externally trusted artifact H mismatch`), geometry-stage failure (`GEOMETRY_FAILURE`, no artifact) |

## Interpreting the figures

- `fig1_track`: legal corridor boundaries + seed (dotted) from the input
  manifest; black curve, arrows, portals and start/finish sampled from the
  **accepted reference** via `Reference.window`.
- `fig2_split_comparison`: Routes A/B overlaid with measured length, model
  lap time, runtime, validation status.
- `fig3_bridge_topology`: XY overlap (left) plus occurrence-vs-arclength
  ownership (right) — overlapping surfaces are ordered occurrences, not
  inferred connections.
- `fig4_velocity`: `v(s)` vs true metric arclength, static model limits,
  occurrence transitions, accel/braking shading, lap seam.
- `fig5_curvature`: optimized `κ(s)` vs seed `κ(s)` over the full lap.
- `fig6_validation_report`: measured compile/geometry/dynamics status,
  length, lap time, runtime and artifact identity `H`. Metrics the
  implementation does not expose are shown as `-`, never invented.

## Capability boundaries

- Verified: synthetic software correctness under the declared synthetic
  planar vehicle models (`config/project_a/models`), within the pinned
  numerical runtime.
- Not verified: real-car behaviour, physical/3D clearance, ROS node
  integration, autonomous branch selection, perception-derived maps.
  Approval/provenance strings in fixtures are annotations, not physical
  evidence (mirroring the planner's own contract).
