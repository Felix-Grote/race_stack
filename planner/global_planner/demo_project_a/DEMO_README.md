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
One scripted step creates the whole environment from a clean machine:

```bash
scripts/setup_project_a_demo.sh   # creates .venv-demo, ends with a QP self-check
```

Prerequisites: bash, curl, tar, sha256sum, a C compiler, and
[uv](https://astral.sh/uv) (or set `PYTHON_BIN` to any CPython 3.10.12).
The script additionally pins matplotlib 3.10.9, pytest 8.3.4 and
Cython 0.29.37. quadprog 0.1.7 is fetched as an sdist whose SHA-256 is
verified in the script, then built locally with two documented patches
(`language='c++'`→`'c'`, which otherwise mangles the Fortran `qpgen2_`
symbol, and a `/`→`//` work-array size fix that newer Cython semantics
require); version and algorithm sources are unchanged.

No ROS 2 runtime, vehicle, LiDAR or actuation is required; the planner
core is pure Python + numpy/scipy. `PYTHONPATH=planner/global_planner` is
required because the IQP child process re-imports `global_planner`.

## Commands

```bash
PYTHONPATH=planner/global_planner .venv-demo/bin/python scripts/run_project_a_demo.py --all
PYTHONPATH=planner/global_planner .venv-demo/bin/python scripts/run_project_a_demo.py --scenario s2
PYTHONPATH=planner/global_planner .venv-demo/bin/python scripts/run_project_a_demo.py --scenario s3
PYTHONPATH=planner/global_planner .venv-demo/bin/python scripts/run_project_a_demo.py --scenario s4
PYTHONPATH=planner/global_planner .venv-demo/bin/python -m pytest planner/global_planner/test/test_project_a_demo.py -q
```

`--scenario s3` is standalone: it compiles its S0 prerequisite
internally, then runs every adversarial case. The exit status is 0 only
when all requested positive scenarios compile PASS **and** (for `--all`
and `s3`) every adversarial case rejects exactly as specified —
exception class and reason, or non-PASS status with no artifact. An
empty or partially-run suite exits nonzero.

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
| S3 | Five negative cases across four stages | A1 whole-occurrence translation → input validation `RouteError: disconnected portal seeds`; A2 reversed gate → `RouteError: invalid portal end caps` (the validator checks end caps before direction, so this case is named for the check that fires); B valid-JSON tampered artifact → `ArtifactError: externally trusted artifact H mismatch`; C tight hairpin (a=3, b=1.1) → optimizer-prep geometry failure `GEOMETRY_FAILURE: folded/degenerate local chart`, no artifact; D valid S0 route vs oversized footprint → independent geometry-validator `FAIL`, no artifact. Every case is enforced in the exit status |
| S4 | Eccentric ellipse (a=12, b=4) in a narrow 0.35 m corridor | Braking/acceleration-rich circuit: κmax=0.75/m gives a lateral bound of ≈2.31 m/s at the ends vs the 3.0 m/s static cap on the straights, producing a non-flat cyclic v(s) with real braking and acceleration zones |

## Interpreting the figures

- `fig1_track`: legal corridor boundaries + seed (dotted) from the input
  manifest; black curve, arrows, portals and start/finish sampled from the
  **accepted reference** via `Reference.window`.
- `fig2_split_comparison`: Routes A/B overlaid with measured length, model
  lap time, runtime, validation status.
- `fig3_bridge_topology`: XY overlap (left) plus occurrence-vs-arclength
  ownership (right) — overlapping surfaces are ordered occurrences, not
  inferred connections.
- `fig4_velocity`: `v(s)` vs true metric arclength, occurrence
  transitions (drawn where ownership changes between samples),
  accel/braking shading, lap seam. The dashed limit is the **static
  model maximum only — not the full feasibility envelope** (the retimer
  also enforces speed_min, ax, ay, motor and drag); the dotted
  `sqrt(ay/|κ|)` curve is a curvature/lateral-acceleration diagnostic.
- `fig5_curvature`: top panel optimized `κ(s)` on true arclength;
  bottom panel seed vs optimized on **normalized progress** (equal x =
  equal relative location, which raw arclength cannot show after
  optimization changes the length), annotated with the measured
  curvature-energy delta from the solver trace.
- `fig6_validation_report`: measured compile/geometry/dynamics status,
  length, lap time, runtime, solver iteration count, curvature-energy
  delta and artifact identity `H` (short form). Metrics the
  implementation does not expose are shown as `-`, never invented.
  Full per-scenario diagnostics (phase timings, per-iteration curvature
  energies, retimer stats) are persisted in `summary.json` under each
  scenario's `run_report`.

## Capability boundaries

- Verified: synthetic software correctness under the declared synthetic
  planar vehicle models (`config/project_a/models`), within the pinned
  numerical runtime.
- Not verified: real-car behaviour, physical/3D clearance, ROS node
  integration, autonomous branch selection, perception-derived maps.
  Approval/provenance strings in fixtures are annotations, not physical
  evidence (mirroring the planner's own contract).
