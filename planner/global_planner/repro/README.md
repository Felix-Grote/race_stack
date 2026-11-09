# Annotation MVP — independent reproduction package

All commands run from the repository root. Two Python environments are
used on purpose; the manifest is the env-independent handoff:

- **generation** (system `python3.12` + repo deps, opencv 5.0): map
  extraction, seeds, strict validation. `ridge_seed` follows cv2
  distance-transform numerics, which differ from opencv 4.8.1 by up to
  ~2.5 m — generation is therefore recorded on the system env, and the
  manifest digest is the reproducible handoff.
- **compilation** (pinned env below): Project A optimization,
  independent validation, query.

## 1. Pinned optimizer environment

```bash
planner/global_planner/repro/pinned_setup.sh ~/venvs/forza-pinned
~/venvs/forza-pinned/bin/python -m pip freeze | \
  diff planner/global_planner/repro/requirements-pinned.txt -
```

Expected pins: CPython 3.10.12, numpy 1.26.4, scipy 1.11.4,
quadprog 0.1.7, trajectory-planning-helpers 0.79. Build subtlety (also
in the script): quadprog 0.1.7's unconstrained `setup_requires` pulls
Cython 3.x under isolation, whose extern-C `qpgen2_` does not link;
the script pre-installs Cython 0.29.37 and builds only quadprog
without isolation.

## 2. Full chains (deterministic, hash-asserted)

```bash
planner/global_planner/repro/repro_test.sh ~/venvs/forza-pinned/bin/python
planner/global_planner/repro/repro_baku.sh ~/venvs/forza-pinned/bin/python
```

Each script regenerates its manifest (asserts byte-identical to the
committed `manifests/` copy), compiles, and asserts the documented
artifact hash:

- `test` (suggested seed, defaults): strict PASS, 345 prepared
  samples → compile PASS `H=e80c49b6…` → geometry PASS →
  dynamics PASS → query PASS.
- `baku` (ridge seed, `chain_dp_epsilon_m=0.03`): strict PASS, 479
  prepared samples → compile PASS `H=f96db7b9…` → geometry PASS →
  dynamics PASS → query PASS.

Re-running either script must print the same H (determinism); any
divergence is a release-blocking defect, not a tolerance.

Machine-readable identities: `receipts.json` (manifest digests,
artifact H, statuses).

## 3. Test suite

```bash
PYTHONPATH=planner/global_planner python3.12 -m pytest \
  planner/global_planner/test/test_annotation_core.py -q
```

49 passed. Covers frame-gap rejection, gated-RDP fixtures and the
end-to-end wall-containment measurement, the eps/res envelope,
same-stem persistence isolation, HTTP hardening, and the full
preview→approve→export lifecycle.

## 4. Geometry contract (enforced in `build_manifest`)

Wall simplification may annex at most epsilon of occupied space, and
only across features narrower than the chord gate resolves (~3 cells
wide, ~4 diagonal). `chain_dp_epsilon_m / resolution > 0.6` is
rejected before any geometry work; inside the envelope intrusion is
bounded to ~0.5 raster cells (measured worst case; diagonal
stair-step corners up to ~0.62). This is raster-constrained bounded
approximation, not strictly inward simplification.

## 5. Browser and ROS (operator interfaces)

- Browser: `ui_flow.py` harness (headless Chromium) — 11/11 checks.
- ROS 2 Humble + Foxglove Bridge in Docker (`annot:humble-foxglove`
  image, repo mounted read-only): open → edit → duplicate →
  reconnect → failed command → same-ID retry → canonical state →
  persistence — 8/8 checks. See `ANNOTATION_TOOL.md`.

## 6. Persistence naming

Drafts/exports are namespaced per source map:
`{parentdir}__{stem}__{sha8}_annotation.json` /
`{parentdir}__{stem}__{sha8}_legal_route.json`. A legacy bare-stem
draft is adopted in place on open and written forward on save (never
deleted by the tool).
