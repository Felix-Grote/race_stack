# Annotation MVP — independent reproduction package

All commands run from the repository root. Two Python environments are
used on purpose; the manifest is the env-independent handoff:

- **generation** (system `python3.12` + repo deps, opencv 5.x): map
  extraction, seeds, strict validation. `ridge_seed` follows cv2
  distance-transform numerics, which differ from opencv 4.8.1 by up to
  ~2.5 m — generation is therefore recorded on the system env, and the
  manifest digest is the reproducible handoff. Both repro scripts source
  the shared `repro/env.sh`, which resolves `SYSTEM_PY` and fails closed
  when the generator env drifts from the `generator` record in
  `receipts.json` (recorded: CPython 3.12.13, opencv 5.0.0, numpy
  2.5.4). Provision it with:
  `python3.12 -m pip install --user "opencv-python-headless==5.*"
  "numpy==2.5.4"` (suite extras: `pillow`, `pytest`).
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
committed `manifests/` copy), compiles, asserts the documented
artifact hash, and finishes with a stateless query probe (`s=5.0`)
against the reloaded artifact:

- `test` (suggested seed, defaults): strict PASS, 345 prepared
  samples → compile PASS `H=e80c49b6…` → geometry PASS →
  dynamics PASS → query PASS.
- `baku` (ridge seed, `chain_dp_epsilon_m=0.03`): strict PASS, 479
  prepared samples → compile PASS `H=82f9b533…` → geometry PASS →
  dynamics PASS → query PASS. (Previous `H=f96db7b9…` was the
  ungated-prefilter geometry; the gated prefilter reinstated
  above-floor wall features, moving the optimum. Test `H=e80c49b6…`
  is unchanged: no above-floor feature was dropped there.)

Re-running either script must print the same H (determinism); any
divergence is a release-blocking defect, not a tolerance.

Machine-readable identities: `receipts.json` (manifest digests,
artifact H, statuses).

## 3. Test suite

```bash
PYTHONPATH=planner/global_planner python3.12 -m pytest \
  planner/global_planner/test/test_annotation_core.py \
  planner/global_planner/test/test_annotation_ui.py -q
```

69 passed + 3 environment-skipped headless (1 ROS-only; 2 pinned-only
validation tests, which need the exact optimizer stack). Covers
frame-gap rejection, gated prefilter/RDP fixtures and the end-to-end
wall-containment measurement, the eps/res envelope, same-stem
persistence isolation, HTTP hardening, the full preview→approve→export
lifecycle, relative-topic namespace isolation, digest-bound thinning,
suggest fallback + direction guard, and double-click/map-refresh UI
contracts.

## 4. Geometry contract (enforced in `build_manifest`)

Wall simplification runs two bounded, gate-checked stages. The
radial pre-filter only removes deviations below the envelope's
quantization floor (0.6 raster cells: pixel staircase peaks at
~0.5 px); an eps-bounded prefilter reinstated every quantization jag
and exploded the checker's polygon budgets, while real features above
the floor survive (pinned 1x1.2-cell notch fixture: ~0 gain). RDP
then bounds the remainder within epsilon with raster-gate-checked
chords. End-to-end gain vs the extracted dense wall is bounded by
floor + epsilon (<= ~1.2 cells inside the envelope). The gate
additionally rejects crossings of occupied spans >= ~3 cells wide
(~4 diagonal). `chain_dp_epsilon_m / resolution > 0.6` is rejected
before any geometry work. This is raster-constrained bounded
approximation, not strictly inward simplification.

## 5. Browser and ROS (operator interfaces)

- Browser flows, headless Chromium, real UI: open → draw (double-click
  endpoint kept) → auto-extract → correct/remove → suggest (ridge
  fallback) → preview → explicit Validate (locks thinning) → re-preview
  → approve → export → save/reload → edit revokes → stale refused.
  Verified on `test` (0.02) and `baku` (0.03; export canonically
  identical to the committed manifest).
- ROS 2 Humble + Foxglove Bridge in Docker (`annot:humble-foxglove`
  image, repo mounted read-only, node namespaced `-r __ns:=/annot`):
  open → edit → duplicate → reconnect → failed request → same-ID retry
  → canonical state → persistence — all PASS, relative topics only.
  See `ANNOTATION_TOOL.md`.

## 6. Persistence naming

Drafts/exports are namespaced per source map:
`{parentdir}__{stem}__{sha8}_annotation.json` /
`{parentdir}__{stem}__{sha8}_legal_route.json`. A legacy bare-stem
draft is adopted in place on open and written forward on save (never
deleted by the tool).
