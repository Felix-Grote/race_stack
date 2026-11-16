# Geometric legality of exported routes

Independent investigation and implementation record for the
annotation editor's vector-legality mechanism (Document 22, Rank 1).
Base: PR #11 at `8edbdf8`; this branch: `felix/annotation-legality`.
Environment for all measurements: CPython 3.14.9, OpenCV 5.0.0,
NumPy 2.5.4, SciPy 1.18.1, Shapely 2.2.0, Ryzen 5 5600X.

## What was wrong (reproduced, not theoretical)

The raster identity `Flegal ⊆ Fpatched ⊆ Foriginal` always held; it
says nothing about the exported polygons. Two 3×3 dilations (the
simplification chord gate and the final checker) defined acceptance
as "every exported pixel centre within one cell of legal", with gain
reported but never capped. An independent exact oracle (row
run-length union of closed legal cell squares, Shapely difference —
no production rasterizer) reproduces Document 22's numbers to the
digit on the old generator: illegal area 0.052228 m² (test, 322
fragments), 0.068544 (baku, 406), 0.080819 (spa), 0.084003 (zuri),
0.067259 / 0.055893 (baku 1-/4-cut, excluded-pocket overlap 0),
sampled max intrusion ≈0.015–0.016 m, largest fragment ≈0.00054 m².
The old 4× supersampled "gain" (0.32–0.65 m²) overstates the true
continuous gain ~7×. So: generated geometry was good, the
acceptance guarantee was not — the checker provably accepted
1-cell islands, restored pockets and 1–2-cell gap bridging in
hand-made payloads, and +0.01…0.049 m wall shifts end-to-end.

## Correctness contract (implemented)

Semantics: a pixel is a closed square of side `resolution` centred
on its registered world coordinate (`TrackMap.pixel_to_world`).
Let `L` be the union of the selected legal cells' squares and `P`
the union of the emitted section polygons (`right + reversed(left)`
per section, PR #10's outline).

**Invariant: `area(P \ L) = 0`.** Boundary contact (zero area)
is legal. Corollaries, not separate checks: no occupied island,
excluded pocket or narrow gap inside `L`'s complement can be
covered or bridged (any such coverage has positive area); deleted
operator exclusions cannot reappear; topology separation imposed
by the bucket selection is preserved. Shape fidelity is separate
and weaker: deviation bounds (0.6-cell floor + wall epsilon) keep
exported walls within ~1.2 cells of the extracted dense wall, but
legality never depends on them — chords may deviate arbitrarily
far *inside* `L`.

Enforced, twice, by different code paths:

1. **By construction.** The dense pixel-centre contour already
   satisfies the invariant (measured exactly 0 on all real maps;
   diagonal steps only touch occupied squares at points). Both
   simplification stages accept a chord only when the *ear* — the
   region between chord and replaced subchain — has exactly zero
   area over occupied squares (`_ear_annexed_m2`, exact cell-box
   intersections, self-crossing ears measured lobe by lobe after
   `make_valid`). Zero-annexation ears compose across stages.
2. **By certification.** `_vector_legality` differences each final
   section polygon against the exact run-length union of `L`
   (`_legal_union`) and rejects any positive area, reporting
   section, area and location. This also catches hand-edited
   payloads and any future generator regression.

Numeric zero is `1e-9 m²` for GEOS predicate residue — not a policy
allowance; genuine fragments are ≥ ~1e-6 m² and accepted candidates
measure exactly 0.0 here. Out of scope and unchanged: continuous
spline/body containment (still `NOT_CHECKED`), and the start-zone
check (see integration notes).

## Alternatives considered

| Family | Guarantee | Why not chosen |
|---|---|---|
| Bounded tolerance (depth/area caps over exact measurement) | `P ⊆ L ⊕ k·res` with caps | Needs owner-ratified thresholds that distinguish slivers from erased pockets by size alone; a 1-cell exclusion is indistinguishable from staircase noise by area. Zero is achievable, so a tolerance buys nothing. |
| 1-cell erosion (build on `erode(L)`, deviation ≤1 cell) | `P ⊆ L` via margin | Measured: exact zero, but shrinks every road 5–8 % (0.05 m per side), can disconnect narrow necks, and broke baku 4-cut route validation (`walls cross or touch`). Changes operator-visible geometry everywhere. |
| Cell-edge (crack) contours + inward simplification | `P ⊆ L`, walls on true cell boundary | Rewrites extraction/joints/caps; diagonal walls stay dense staircases under inward-only chords; no benefit over the ear gate, which lets chords use the full half-cell margin of pixel-centre contours. |
| Simplify-then-repair vs exact checker | `P ⊆ L` after loop | Same outcome with more machinery (segment→subchain bookkeeping); the ear predicate inside RDP *is* the repair, at the moment the chord is chosen. |
| Topology-preserving simplification (Saalfeld / de Berg / TopoVW / shapely `preserve_topology`) | No self-intersections, feature topology | None of these imply containment against a raster `L`; the ear area predicate is the missing piece in all of them. |
| **Exact ear gate + exact certifier (chosen)** | `P ⊆ L` exactly, full road width | Smallest change to the existing two-stage chain: predicate signature `(pts, a, b)`, one exact primitive shared by gate and certifier semantics, checker replaced. |

## Evidence

Oracle = the run-length union above, implemented independently in
the investigation scripts and as test-local code in
`test/test_annotation_legality.py` (production checker not reused).

| Case | Old illegal | New illegal | Lap (m) old → new | Wall verts old → new |
|---|---|---|---|---|
| test | 0.052228 | **0.0** | 85.868 → 85.852 | 531 → 840 |
| baku | 0.068544 | **0.0** | 122.770 → 122.773 | 752 → 1169 |
| spa | 0.080819 | **0.0** | 111.228 → 111.186 | 761 → 1276 |
| zuri | 0.084003 | **0.0** | 119.449 → 119.441 | 749 → 1338 |
| baku 1-cut | 0.067259 | **0.0** (pocket overlap 0) | 121.844 → 121.849 | 743 → 1172 |
| baku 4-cut | 0.055893 | **0.0** (pocket overlap 0) | 120.071 → 120.082 | 712 → 1054 |

Reproduce: `pytest test/test_annotation_legality.py` (includes the
oracle) plus `test_annotation_{core,ui,route}.py` — 144 passed,
1 skipped (ROS-only) at this branch head. A real-browser flow
(open baku → suggest → preview `annex 0.000000 m²` → approve →
export → reload digest match) was executed with Playwright;
screenshot attached to the draft PR.

Adversarial coverage (`test_annotation_legality.py`): hand-mutated
payloads (1-cell island coverage, +5/10/49 mm outward wall shifts,
restored excluded pocket) all rejected at `VECTOR_LEGAL`;
generator-reachable cases exact-zero: diagonal-staircase diamond
ring, corner cuts with 1/3/13-px bands (1-px diagonal leaks under
8-connectivity and fails closed at extraction, by design), wall
tooth detour, road island (extraction topology rejection), pinch
slit (builds exact or fails closed), thinnings 0/0.02/0.03,
resolutions 0.02/0.05/0.1; primitive semantics (edge contact = 0,
0.99-cell spike > 0, hairline expansion > 0, collinear/backtracking
ears = 0).

## Performance

Full candidate (build + all checks), warm, this machine:
test 1.7 s, baku 2.6 s, spa 2.3 s, zuri 2.4 s; peak Python heap
≈3 MB over baseline. Breakdown (baku, cProfile): route checks it
shares with PR #10 ≈0.5 s, ear gate ≈0.4 s (~2900 ear tests, small
bounding boxes), exact certifier ≈0.2 s (one run-length union +
4 differences). Scaling: ear tests are local (ear bbox), certifier
is O(rows + runs + section vertices); synthetic 800² annulus
0.38 s. No global per-cell geometry is built. Suite wall time
45 s → ~95 s (many builds per suite); per-preview latency is the
operator-relevant number and is unchanged in kind.

## Self-review / limitations

- The ear composition argument assumes each stage's input polygon
  is contained; the certifier exists precisely so this argument is
  not load-bearing — it measures the final coordinates.
- `make_valid` on bowtie ears: signed-area cancellation was a real
  bug found during the spike (zero-area fast path skipped lobes);
  the production primitive validates before measuring and the
  diagonal-ear unit test pins a self-crossing case.
- Vertex counts grow ~1.6× (diagonals must keep more staircase
  vertices). Manifests get larger; PR #10 validation time grows
  mildly. If that ever matters, a min-vertex ear-constrained
  optimizer (Imai–Iri style) is the upgrade path, not a tolerance.
- Exact digests remain environment-specific (float pipeline);
  geometry (lap lengths, zero annexation) is the stable contract.
- 1-px diagonal strokes leak under 8-connectivity and narrow
  (≤2-cell) corridors can still fail downstream route/car checks;
  both fail closed and are orthogonal to annexation.
- `_AREA_EPS_M2 = 1e-9` could in principle pass a sub-nanometre
  sliver on a future GEOS version; accepted candidates measure
  exactly 0.0 in every environment tested.

## Owner policy decision (the one this rests on)

**Cell-square semantics with zero permitted expansion**: a free
cell means its full closed square is drivable, an occupied/
excluded cell means no positive area of its square may be covered.
Consequences: walls may run exactly along cell edges (boundary
contact), and the road is up to half a cell narrower per side than
the square union wherever diagonal chords must stay inside —
i.e. the export is conservative relative to `L`, never larger.
The alternative (pixel centres as points with an interpolation
kernel, or any `k·res` expansion budget) would make "excluded"
fuzzy precisely where operators draw exclusions. I recommend
ratifying cell-square/zero-expansion; it is the standard
occupancy-grid meaning, it needs no tuned thresholds, and this
branch demonstrates ordinary tracks remain practical under it.
It is implemented here as a candidate, **not** as owner approval:
Document 22's gate G1 still wants explicit sign-off.

## Integration (done: start-zone + source-identity branches merged)

- **Start zone** (`felix/start-zone-containment`): containment is
  canonical — `validate_route` requires the whole zone within the
  union of the section polygons, which chained with the exact
  section containment above puts it inside the legal squares too.
  The editor's former centre test and weaker raster-proximity check
  were deleted as duplicates. Zone *generation* verifies
  containment in that union and falls back ribbon → shrinking
  quads → actionable refusal, after rotation sweeps showed a
  single quad escapes on tight bends (worst outside area is now
  0.0 across 24 rotations × 4 real maps, sharp diamond corners,
  and hairpins down to 0.15 m inner radius; beyond that it fails
  closed at generation with a move-the-start message).
- **Source identity** (`fix/source-identity-approval`): adopted
  as-is, plus the same `check_source_current` guard on
  `op_validate`/`op_suggest` so no candidate-building server op
  mints a PASS against a stale snapshot.
- `GENERATOR_VERSION` is `route-v2` (geometry changed for identical
  input; old approvals correctly stop authorizing).
  `build_route` gained a required `legal_mask` keyword;
  `build_candidate` signature is unchanged.

Known residuals, ranked: (1) zuri joint placement can still choose
cuts whose sections share wall along a narrow isthmus (pre-existing,
fail-closed with a route-package message; operator redraws the
guide); (2) start zone may sit anywhere in the union with unchecked
heading coherence, and the 2D union can splice across surfaces in
hand-edited multi-surface manifests — future multi-surface work,
editor emits one surface; (3) source-drift guarantee is
check-instant only (documented in ANNOTATION_TOOL.md).

## Recommendation

Ready for PR #11 merge qualification once the owner ratifies the
cell-square/zero-expansion policy above. The Document 22 gates
G1–G3 are implemented and tested on this stack; G4–G6 are
qualification activities (browser campaign breadth, ROS Humble
roundtrip) rather than code changes.
