# ForzaETH ICRA27 — W1 Adversarial Review Report

Independent verification of A01–A03 · 16 October 2026 · READ-ONLY investigation

## A. Executive verdict

**CHANGES REQUIRED. W2 cannot safely rely on this W1 revision as its accepted mathematical and topological foundation.**

The reviewed implementation is `Felix-Grote/race_stack`, branch `project-a/w1-geometry`, commit **`133a96fd6653e4d3b16d71c38e1c70fc38585101`**, published in [draft PR #1](https://github.com/Felix-Grote/race_stack/pull/1). Its base and merge base are exactly the required W0 commit **`6370d0436aabd011d1b885fe1f500644b957b536`** on `project-a/w0-cloud-foundation`. This verdict concerns the final CI-tested SHA, not an earlier provisional revision.

Two P1 defects block acceptance: an explicitly sampled corridor bridges a tangent contact with its original legal boundary, and the metric kernel accepts regular periodic geometry whose actual station error exceeds its advertised tolerance by more than two orders of magnitude. Three P2 defects affect cap-event transport, exact boundary queries and scale-dependent gate validation. All five reproduce on the pinned Humble numerical stack. No P0 finding is asserted: disconnected-surface reassociation and illegal branch connectivity were not demonstrated; the corridor counterexample concerns an unsupported tangent contact, not a proved finite-width exterior strip.

Existing tests pass: 48 A01, 12 A02, 18 A03, seven W0 numerical, four actual ROS and one installed W1 test. An independent replay reproduced these results and the three-package build. The ten pre-existing legacy failures and two skips retain the same identities as W0. Passing hosted CI therefore does not resolve the defects below.

No implementation, tracked repository file, branch, PR state, map or hardware system was changed. New probes and their outputs were confined to scratch. All 859 tracked non-gitlink W1 blobs remained identical after the experiments. The original environment checkout stayed clean at its initial legacy HEAD.

## B. Verified implementation inventory

### Identity, history and complete diff

W1 is six commits ahead of W0, zero behind, in this order:

| Commit | Purpose |
|---|---|
| `6dc2b38dd7862ed81410f474161c53dc68ab2c77` | A01 strict directed route input |
| `cd6749d88139222bd6d4016bee5bb160feb19405` | A01 source-style test/evidence |
| `61c320e0b5551dc983d5b866460900a3f8428de2` | A02 periodic metric kernel |
| `f4048adac1471c4db03616d5292f06aa83f78a13` | A03 owned corridor preparation |
| `129c28100cd060d155cafb4a1a4e0469e0855cae` | Schema/gate hardening |
| `133a96fd6653e4d3b16d71c38e1c70fc38585101` | W1 closeout, evidence and two final regressions |

The entire W0–W1 diff contains 211 changed leaves: four production modules, three source test files, seven JSON fixtures, one package manifest, three CI/runner integration files, seven documentation files and 186 retained evidence files. All 211 changed snapshot blobs were checked against GitHub blob hashes. Full recursive tree comparison confirmed the inventory and unchanged gitlinks; no legacy planner, map, interface, controller, localization or actuator change is present.

All seven recursive gitlinks are preserved:

| Path | Exact SHA |
|---|---|
| `base_system/f110_simulator/f1tenth_gym` | `f8f8c9d4781d44a2959bae013f276410cb4e9da0` |
| `base_system/f110_simulator/f1tenth_gym_ros` | `163020c0b631a5bdd9ddc59e6132337cec04cc27` |
| `base_system/f1tenth_system` | `5d6490fc6426deb1254198020133a85c0614f183` |
| its nested `ackermann_mux` | `ed4eac7284d13cae66628688e6fd32e585a96a62` |
| its nested `teleop_tools` | `09938461991ec2260ddab6db8ac962f46d205669` |
| `planner/global_planner/global_planner/global_racetrajectory_optimization` | `b1b38ecfefec7200d5bcb243f115af1d795b3766` |
| `sensors/vesc` | `2fd19be756544693752d3e5b36c128e6157e4bd3` |

The execution plan, STATUS, DECISIONS, RESULTS, canonical architecture and roadmap, scoped AGENTS, geometry contract, self-review, runbook and review documentation were inspected. Source and executed experiments determine this verdict; the implementing agent's completion claims were not treated as acceptance evidence.

### What the code actually provides

Paths below use `GP = planner/global_planner/global_planner`.

| Component | Implemented behavior | Important boundary |
|---|---|---|
| A01 `GP/route_input.py` | Strict UTF-8 JSON loading, duplicate-key rejection, NFC/binary64 normalization, canonical digest, frozen loaded route records; ordered occurrences, surfaces, caps, consecutive portals and closing gate validation | One selected cycle; simple ribbon polygons; shared endcaps. Holes and arbitrary connectors reject. Approval is recorded text, not authentication. Initialization applicability is not proved. |
| A02 `GP/route_reference.py` | Exact normalized cubic coefficients; periodic interpolation; join/seam checks; derivative regularity subdivision; adaptive speed integration and Brent inverse; stateless metric/frame queries with explicit segment owners | No ROS, TUM lookup, runtime association, speed profile or artifact loader. Error control has the demonstrated failure in F2. |
| A03 `GP/route_corridor.py` | Original seed-metric q lineage, anchored metric resampling/refits, occurrence-owned normal intersections, explicitly adjacent portal masks, polynomial gate roots, Jacobian and sampled chart-pair rejection, TUM row/right-normal views | Ephemeral solver preparation. F1 and F3 violate returned-interval/event guarantees. It is not continuous final-curve or swept-body certification. |
| `GP/_route_geometry.py` | Private planar polygon/segment predicates and open normal-line interior intervals | Fixed 1e-9 m predicate policy; no formal robust-predicate proof supplied. |

Only `python3-numpy` and `python3-scipy` execution dependencies were added to `package.xml`; the pinned image, numerical lockfiles, optimizer gitlink and legacy entry points are unchanged. The new code does not introduce a geometry framework or duplicate the legacy extraction path.

A04 IQP iteration, A05 independent continuous containment, A06 dynamics, A07 artifact/export and A08–A09 benchmark/handoff remain unimplemented. Their absence is a legitimate W1 boundary. It does not excuse an incorrect width or event already returned by A03.

### What CI actually checked

The exact-head [push run 38867639532](https://github.com/Felix-Grote/race_stack/actions/runs/38867639532) succeeded on `133a96fd…`; its completed run metadata was updated 16 October at 09:32:45 Europe/Zurich. The [PR run 38867646470](https://github.com/Felix-Grote/race_stack/actions/runs/38867646470) also succeeded, but checked out synthetic merge `ece844a570ff9dcbd77bbd0051d79f92140d1e5f`. The push run is the exact-head evidence. Initially running CI was allowed to complete before this verdict. A final remote check at 09:47 Europe/Zurich still found the same head SHA and completed successful CI.

Both CI logs confirm the stated W1/W0 tests, installed checks and selected three-package build. `all` deliberately records legacy colcon failures as a warning; it does not prove legacy lint/XML success or automatically compare their identities. The independent W0/W1 replay performed that comparison.

## C. Findings ordered by severity

All source links below are pinned to the reviewed SHA. P1 findings require correction before acceptance. P2 findings are bounded but should also be repaired before their APIs become W2 dependencies.

| ID | Severity | Demonstrated defect |
|---|---|---|
| F1 | **P1 — High** | A sampled corridor joins separate open interiors across an original-side tangent contact |
| F2 | **P1 — High** | Accepted regular periodic cubic exceeds arc/inversion error budgets |
| F3 | **P2 — Moderate** | Mandatory cap anchor can be returned with the upstream cap |
| F4 | **P2 — Moderate** | Seam/endpoint rounding violates half-open query and owner conventions |
| F5 | **P2 — Moderate** | Collinear seed subdivision turns an unambiguously forward gate into a rejection |

### F1 — Tangent legal-side contact is bridged in a returned corridor

**Locations:** [GP/route_corridor.py:160–174](https://github.com/Felix-Grote/race_stack/blob/133a96fd6653e4d3b16d71c38e1c70fc38585101/planner/global_planner/global_planner/route_corridor.py#L160-L174), called at [181–202](https://github.com/Felix-Grote/race_stack/blob/133a96fd6653e4d3b16d71c38e1c70fc38585101/planner/global_planner/global_planner/route_corridor.py#L181-L202); open-interval construction in [GP/_route_geometry.py:84–109](https://github.com/Felix-Grote/race_stack/blob/133a96fd6653e4d3b16d71c38e1c70fc38585101/planner/global_planner/global_planner/_route_geometry.py#L84-L109).

**Violated contract:** select the original owner's connected normal interior containing the reference; do not bridge disconnected intervals or accept unsupported tangent/ambiguous normal geometry. This is a returned mesh interval, not a between-node containment claim.

**Minimal reproduction:** load fixed `s0_route.json`, build `seed_curve`, take occurrence 0's seed knot 16 and its fitted left normal. Insert `sample.xy + 0.2 * left_normal` at index 19 of occurrence 0's original left chain. Add a cap at the queried q so the point is an explicit preparation anchor. The seeds, surfaces, portals and spline remain otherwise unchanged. The full manifest is `evidence/a03_tangent_prepare_route.json`; executable construction is `probes/a03_tangent_prepare.py` plus `a03_tangent_public.py`.

Pinned execution, through the wrapper recorded in section D:

```text
python3 suites/run_probe_humble.py a03_tangent_prepare
```

Observed at q `4.711915876399159`, XY `(4.242640687119286, 4.242640687119285)`:

```text
raw open interiors: (-0.9000000000000002, 0.19999999999999957)
                    (0.19999999999999957, 0.6999999999999998)
notch tip:          (4.101219330881976, 4.1012193308819755)
tip is interior:    False
returned left:     0.6999999989999999 m
returned right:    0.8999999990000003 m
owner/support:     o0 / (o0,), no portal
prepare_route:     ACCEPTED, 107 samples, including this exact query
```

**Expected:** reject this unsupported tangent contact, or retain the origin-containing strict interior ending at approximately 0.2 m with its inward allowance. Returning 0.7 m across the side contact is inconsistent with the stated interior/component policy.

**Root cause:** `line_intervals` correctly splits at the boundary vertex. `_merge` uses `a <= previous_upper` without contact provenance, treating touching open intervals as connected. `_component` therefore sees an already joined interval. The later endpoint-side test checks the far endpoint, not the discarded internal contact. Insetting only the final ends by 1e-9 m cannot remove an interior boundary point. The Jacobian also passes, so no later preparation check catches it.

**Correction:** preserve contact/cut provenance or explicitly reject tangent/uncertain non-gate side contacts. Permit removal of a touching separator only when it is the declared shared portal endcap. Merely changing every `<=` to `<` risks rejecting legitimate adjacent portal unions; fix the contact semantics rather than globally forbidding authorized gate joins.

**Regression:** use the full accepted route and explicit sampled cap anchor above; assert rejection or an upper interval no greater than the first interior boundary, never 0.7 m. Repeat under rigid transforms, near-tangent perturbations and authorized shared-cap cases. The standalone notch experiment reproduces the same failure under eight rigid transforms. A resolved finite gap is retained correctly; this finding does not claim a macroscopic illegal strip is bridged. P1 reflects a false usable chart at a sampled contact without claiming vehicle certification or disconnected-deck reassociation.

### F2 — Adaptive integration silently misses a regular low-speed feature

**Locations:** [GP/route_reference.py:114–121](https://github.com/Felix-Grote/race_stack/blob/133a96fd6653e4d3b16d71c38e1c70fc38585101/planner/global_planner/global_planner/route_reference.py#L114-L121) and [133–149](https://github.com/Felix-Grote/race_stack/blob/133a96fd6653e4d3b16d71c38e1c70fc38585101/planner/global_planner/global_planner/route_reference.py#L133-L149).

**Violated contract:** true metric integration/inversion must meet the stated numerical accuracy or fail closed. Default policy is whole-lap `arc_abs=1e-10 m`, `station_abs=1e-8 m`, minimum normalized derivative norm `1e-7`. Documentation honestly calls QUADPACK's number an estimate; that qualification does not make the demonstrated actual station error satisfy the query tolerance.

**Minimal input:** ascending normalized coefficients, with no resampling:

```python
seg = CubicSegment(((0., .0899, -.3, 1/3),
                    (0., 2e-7, 0., 0.)))
s = .75 * seg.length
t = seg.parameter(s)
```

Here `x'=(t-.3)^2-.01^2`, `y'=2e-7`; the derivative norm is everywhere at least `2e-7`, so this is regular under the accepted policy. Its brief x reversal lies between t=0.29 and 0.31. Independently,

`integral hypot(x',y') >= integral |x'| = 0.123236 m`.

The latter is a piecewise polynomial integral. Binary64 coefficient/root effects are immaterial at this scale; even subtracting 1e-14 m from the lower bound leaves the violation intact. A split 64/128/256-point Gaussian oracle independently agrees on approximately `0.123236000035081 m`.

```text
python3 suites/run_probe_humble.py a02_adversarial
```

Actual pinned results:

| Quantity | Observed |
|---|---:|
| Accepted segment length | 0.12323333334188319 m |
| Reported quadrature error | 1.5271498741260836e-13 m |
| Proven length undercount, approximately | at least 2.6666581e-6 m |
| Inverse target | 0.09242500000641239 m |
| Returned t | 0.9304256195843263 |
| Residual using production arc | −4.6183e-13 m |
| Proven true station residual | at least 2.6666628e-6 m |
| Independent true station residual | approximately 2.6666979e-6 m |

The actual length error exceeds the default arc budget by over 26,000 times; the inverse error exceeds the station budget by over 266 times. Both calls return successfully.

**Periodic reachability:** `a02_adversarial.py` includes eight explicit XY knots and q=0…8 forming an accepted periodic `Curve.interpolate`. Its first segment is the same counterexample within roundoff, with derivative norm lower bound `1.99999999796e-7`. Its per-segment arc budget is tighter, `1.25e-11 m`, yet the same false estimate passes. `Curve.sample(0.75 * first_segment.length)` has true station error at least `2.6666628e-6 m`. Accepted lap length is `10.545359470552732 m`, versus approximately `10.545362137245931 m` from the converged independent oracle. The complete knots and query are retained in the script and JSON. No claim is made that this periodic example also passes A03.

A supplementary **non-retracing** cubic also fails: x coefficients `(0,.211669921876,-.3984375,.25)`, y `(0,4e-6,0,0)`. Its x derivative is strictly positive, approximately `.75*(t-17/32)^2+1e-12`. An analytic projection lower bound still proves arc undercount above `1.20666e-8 m` and inverse residual above `1.19122e-8 m`. Thus the failure is not confined to exact cusps or x backtracking.

**Root cause:** whole-interval adaptive quadrature can miss the localized speed feature and underestimate its own error. Regularity subdivision checks nonzero derivative but does not supply feature partitions to integration. Brent then solves the same inaccurate arc function; checking its residual with that same function accepts a self-consistent, physically wrong station.

**Correction:** make integration sensitive to polynomial speed features, at minimum isolating derivative/speed-squared extrema or reusing regularity partitions. Back acceptance with conservative error control for the supported domain; unresolved low-speed features must reject. Budget partial integrals and inversions consistently. Repeating the same unconstrained quadrature or merely increasing sample density is insufficient.

**Regression:** retain the analytic projection lower bound, split independent oracle, accepted periodic embedding and non-retracing supplement. Sweep feature positions/widths, segment scales and partial queries. Require actual arc/station errors within policy or explicit `GeometryError`; retain the original parabola, continuity and budget-exhaustion tests.

### F3 — A declared cap event is numerically reclassified as upstream

**Locations:** [GP/route_corridor.py:105–114](https://github.com/Felix-Grote/race_stack/blob/133a96fd6653e4d3b16d71c38e1c70fc38585101/planner/global_planner/global_planner/route_corridor.py#L105-L114) and [117–143](https://github.com/Felix-Grote/race_stack/blob/133a96fd6653e4d3b16d71c38e1c70fc38585101/planner/global_planner/global_planner/route_corridor.py#L117-L143).

**Violated contract:** mandatory cap/ownership/portal anchors survive resampling with their inherited q and right-hand semantics. Approximate physical station inversion must not change a known semantic event.

**Input and command:** `probes/a03_anchor_legal_reparam.py` loads S0, keeps its original legal borders and changes first-occurrence knot angles using the monotone map `f(u)=u + .99*sin(2*pi*u)/(2*pi)`. Its derivative is at least .01. It fits the resulting ordered curve using the original q knots and adds a 1 m/s cap at q `4.805954193927142`, after an upstream cap of 4 m/s. `prepare_route(..., spacing=.25, ordered=...)` succeeds. The full route and knot array are retained in `evidence/a03_anchor_legal_reparam_{route,points}.json`.

```text
python3 suites/run_probe_humble.py a03_anchor_legal_reparam
```

```text
declared cap q:      4.805954193927142
returned q:         4.80595419066715
q error:           −3.2599913879494125e-9 m
expected cap:       1 m/s
actual cap:         4 m/s
physical residual: −3.895372913120809e-11 m, within station_abs=1e-8
preparation:        ACCEPTED, 163 samples
```

**Expected:** the mandatory cap sample retains the exact declared event and receives 1 m/s. This is a discontinuous metadata error, even though its coordinate discrepancy is small. It is not evidence of an existing unsafe speed profile; A06 is absent.

**Root cause:** resampling converts known q anchors to s, discards their event identity, then reconstructs q through approximate s inversion. `_sample` compensates cap selection with only 1e-9 m in q, unrelated to the physical station tolerance and local dq/ds. Here valid inversion accuracy still crosses that classification threshold. The comment promising exact anchors is therefore false.

**Correction:** preserve authoritative `(segment,t,q,event)` for mandatory anchors and derive their station; do not recover those known events through a lossy roundtrip. Keep sample consistency checks and refit lineage coherent with that representation. Increasing a global EPS would not solve the arbitrary q/s conditioning or preserve closely spaced events.

**Regression:** the exact accepted reparameterized case must return the 1 m/s event, and repeated refit/resample cycles must retain it. Add nonuniform q/s ratios, nearby cap changes, occurrence/seam and portal-bracket anchors. Distinguish event semantics from ordinary approximate s queries.

### F4 — Endpoint station and wrapping conventions are inconsistent

**Locations:** compensated cumulative sums at [GP/route_reference.py:210–219](https://github.com/Felix-Grote/race_stack/blob/133a96fd6653e4d3b16d71c38e1c70fc38585101/planner/global_planner/global_planner/route_reference.py#L210-L219); [station/wrap/locate at 254–273](https://github.com/Felix-Grote/race_stack/blob/133a96fd6653e4d3b16d71c38e1c70fc38585101/planner/global_planner/global_planner/route_reference.py#L254-L273).

**Violated contract:** finite negative progress wraps into a defined half-open periodic domain; an exact segment endpoint maps to the canonical next knot and its right-hand owner.

**Minimal reproductions, in `a02_adversarial.py`:**

1. Interpolate 64 equally spaced points on a radius-6 circle; call `sample(-1e-20)`. `wrap` returns **L itself**, `37.69910696841439`, because floating-point modulo rounds upward. `sample` raises `GeometryError: segment station outside arc`.
2. Interpolate five points `(6*cos(theta),4*sin(theta))` with distinct per-segment owners. `station(2,1)` is `18.232675003474927`, whereas canonical `cumulative[3]` is `18.23267500347493`. `sample(station(2,1))` returns segment 2, t=1 and owner **o2**, rather than right-hand **o3**.

The same pinned command as F2 executes these cases. In a fixed-seed stress run over 100 periodic curves and 36,616 queries, 1,045 endpoint-anchor segment mismatches occurred; ordinary random/nextafter queries in that run did not otherwise fail. Position discrepancies are only a few ulps. This is adjacent-boundary metadata inconsistency, not demonstrated disconnected-deck switching.

**Root cause:** `station` re-adds segment length rather than returning the compensated canonical cumulative knot for exact endpoints; `wrap` assumes `%` always produces a representable value strictly below L. Subtraction in `locate` can then exceed the stored last-segment length by roundoff.

**Correction:** return canonical cumulative values for t=0/1, normalize modulo results to a representable half-open interval with a documented boundary-side policy, and handle bounded subtraction roundoff consistently. Do not broadly snap distinct nearby stations across ownership boundaries.

**Regression:** every `(segment,0/1)` must roundtrip to the canonical half-open owner; test last-to-first closure, tiny negative progress, exact ±integer laps and `nextafter` around every cumulative knot on nonuniform curves.

### F5 — Gate acceptance depends on irrelevant seed sampling scale

**Location:** [GP/route_input.py:217–218](https://github.com/Felix-Grote/race_stack/blob/133a96fd6653e4d3b16d71c38e1c70fc38585101/planner/global_planner/global_planner/route_input.py#L217-L218).

**Violated contract:** inserting collinear points preserves the same directed seed polyline, legal gate and topology. Well-resolved segment subdivision must not change a forward passage into a direction error.

**Reproduction:** `a01_gate_scale.py` makes a radius-6 circular route with border radii `6 ± 0.00005 m`, updates shared gate endpoints and successfully validates it. It then inserts collinear seed points 1e-6 m before and after portal p0. No existing point moves, and seed-polyline length change is exactly 0. The full rejected manifest is `evidence/a01_gate_scale_input.json`.

```text
python3 suites/run_probe_humble.py a01_gate_scale

before subdivision:      ACCEPTED
after subdivision:       RouteError: wrong directed gate
gate length:             9.999999999799059e-5 m
travel length:           1.999397637392408e-6 m
cross(gate,travel):      −1.9993976373522318e-10 m²
normalized cross:       −1.0
```

**Expected:** both manifests validate as the same forward-directed geometric polyline, subject to later chart validation. All new lengths are above the 1e-9 m geometric tolerance. The 0.1 mm synthetic width makes this a bounded supported-domain false rejection; no vehicle-fit claim is made.

**Root cause:** a cross product in m² is compared directly to `-EPS`, specified in metres. Gate width and neighboring point spacing therefore control rejection despite an unambiguous direction.

**Correction:** use a dimensionally consistent signed-distance or normalized-direction predicate, with independently checked nondegenerate vectors. Dividing by gate length before applying a metre ambiguity allowance is one surgical option. Do not loosen global EPS.

**Regression:** preserve acceptance under collinear subdivision around portals at several widths, point spacings and rigid transforms; reversed/tangent directions must still reject.

## D. Independent adversarial experiments and reproducibility

### Environment and executed commands

The environment initially contained legacy checkout `67981ed…`, not W1. The final W1/W0 objects were fetched without moving its branch. Separate archives were extracted under `/workspace/work/w1-review`; matching optimizer contents were supplied read-only at the unchanged pin.

```bash
git -C /workspace/race_stack fetch --no-tags origin \
  133a96fd6653e4d3b16d71c38e1c70fc38585101 \
  6370d0436aabd011d1b885fe1f500644b957b536
git -C /workspace/race_stack archive 133a96fd6653e4d3b16d71c38e1c70fc38585101 \
  | tar -x -C /workspace/work/w1-review/source
```

The prescribed W0 Dockerfile/locks were reused; the existing daemon and proxy/CA configuration were retained:

```bash
env -u DOCKER_HOST -u DOCKER_CONTEXT -u DOCKER_TLS -u DOCKER_TLS_VERIFY -u DOCKER_CERT_PATH \
  docker --host=unix:///var/run/docker.sock build \
  --secret id=system_ca,src=/etc/ssl/certs/ca-certificates.crt \
  -f scripts/project_a/Dockerfile -t project-a-humble:w1-review .
bash /workspace/work/w1-review/suites/run_suites.sh w0
bash /workspace/work/w1-review/suites/run_suites.sh w1
python3 /workspace/work/w1-review/suites/compare_legacy.py
```

The direct runner replay was necessary because an archive has no `.git`, and invoking setup would initialize submodules in source. It executes each unchanged `container_verify.sh all` under the same isolation policy as standalone test Compose. No hardware Compose, stack launch, controller or hardware device was used.

Actual image ID: `sha256:8c9c36d25927e34e03ab3e9978bd1a1a56ab4f60a7ec57ce90c17c053c7ab8d3`. Base: `ros:humble-ros-base-jammy@sha256:860e53793ccf575e5369b5e9a19939de2bfcfb46a299954d06f54f2af54fed19`. Runtime: Ubuntu 22.04.5, ROS Humble, Python 3.10.12, NumPy 1.26.4, SciPy 1.11.4, pytest 8.3.5, TPH 0.79, quadprog 0.1.7. Tests/probes ran UID 1000, no effective capabilities, no-new-privileges, read-only source/root and loopback-only networking. `pip check` passed. Initial host exploration used SciPy 1.12.0; final findings were replayed on the CI stack and do not depend on that host version.

`suites/run_probe_humble.py NAME` runs a named independent probe inside this image, mounting the snapshot read-only. Example actual wrapper command:

```bash
python3 /workspace/work/w1-review/suites/run_probe_humble.py a02_adversarial
```

For every final probe, `evidence/*_humble_execution.json` records full Docker argv, image, script SHA-256 and exit status; `*_humble_runtime.json` records runtime/isolation; `.log` and `.stderr` retain output. All 12 final probe hashes match the executed scripts. **Probe exit 0 means the expected observations, including defects, reproduced; it is not implementation acceptance.**

### Executed experiment ledger

| Probe / invariant or oracle | Coverage and result |
|---|---|
| `required_metric_midpoint` — analytic parabola | Reproduced the architecture's exact old discrepancy **0.16557464142413925 m** at nominal t=.5. Target s=L/2=0.7394714287722988; W1 returns t=0.6107386829580599 with zero measured analytic residual. One coefficient segment, no resampling. The original error is genuinely fixed here. |
| `a02_adversarial` — analytic and split Gaussian arc/differential oracles | F2 periodic/segment/non-retracing failures; F4 endpoint failures. Parabola 201-query maximum residual 1.31286e-10 m. Analytic global nominal-fraction maximum .16703482227 m; mesh-dependent legacy maxima differ from the midpoint example. |
| A02 rigid motion, reversal and cyclic-origin shift | Nonuniform 35-knot ellipse: metric length preserved within 3.56e-15 m; XY covariance within 1.43e-14 m, curvature rotation within 2.28e-13 /m, reversal sign within 6.11e-15 /m; cyclic-origin geometry matched. |
| A02 stress and fail-closed probes | Seed 1631, 100 curves/36,616 queries; F4 endpoint mismatches as reported. Zero/uncertain derivatives, explicit integration/regularity exhaustion and a below-minimum short segment reject. A small set of 15 nextafter queries around the five-knot ellipse did not otherwise fail. |
| `a03_tangent_notch`, `a03_tangent_public`, `a03_tangent_prepare` | Isolated polygon, valid full manifest/public query, then actual prepared anchor all demonstrate F1. |
| `a03_geometry_metamorphic` | Tangent flaw persists over eight rigid transforms. Resolved finite-gap perturbation chooses the first component; sub-EPS gap perturbations do not establish correctness and should fail closed if uncertain. |
| `a03_anchor_legal_reparam` | Accepted unchanged-border candidate demonstrates F3 while its physical inverse residual stays within policy. Dense radius diagnostic is exploratory mesh evidence, not a continuous certificate. |
| `cross_module_metamorphic` | Five S0/S2/S3 fixtures × three rigid transforms, 120 queries. Preserve owners, portal support, metric length, signed widths and curvature. Worst width change 1.47138e-11 m; worst length change 5.11591e-12 m; worst curvature change 5.66581e-10 /m, below chosen 1e-8 /m threshold. |
| `mixed_choices` | All four upper/lower pairs across two separately annotated split/remerge visits prepare, with eight distinct occurrences and eight gates. Coincident return geometry retains ownership; injected switching to the other visit rejects. |
| `a01_adversarial` — strict metadata and exact integer predicates | Fifteen malformed manifests, six duplicate/NFC/nonfinite JSON cases reject. Recursive key reordering preserves digest; caller mutation does not affect validated output; physical coverage changes identity without changing occurrences/portals. Twelve rigid transforms preserve topology and seed lengths, worst 2.92e-12 m. |
| A01 bounded random polygon/segment tests | Seed 20261016: 4,000 eight-vertex polygons, 3,902 exact proper-crossing cases rejected plus translated copies; 2,329 proper crossings among 10,000 segment pairs detected. |
| `a01_neardegenerate` — exact Fraction binary64 oracle | Seed 2026101601; 20,000 candidates, 15,917 exact proper crossings at lengths 1e-7…1e4 m and angles 1e-14…1 rad; zero misses. The suspected near-parallel predicate flaw was **not substantiated**. |
| `a01_gate_scale` | Collinear-subdivision invariant fails as F5. |

Additional compressed-circle cap exploration is retained as `a03_anchor_transport.py` and its host log; it supported the same F3 mechanism but is not needed for the finding. The unchanged-border reparameterized candidate above is the final pinned evidence. No unexecuted experiment is presented as a verified failure.

### Existing suites and legacy separation

| Independent replay | Functional checks | Build | Legacy aggregate |
|---|---|---|---|
| W0 exact baseline | 7 numerical + 4 ROS passed | 3 packages passed | 12 reports, 0 errors, 10 failures, 2 skipped |
| W1 exact review SHA | 48 A01 + 12 A02 + 18 A03 + 7 numerical + 4 ROS + 1 installed W1 passed | 3 packages passed | 90 reports, 0 errors, 10 failures, 2 skipped |

Packages: `f110_msgs`, `frenet_conversion`, `global_planner`. Installed checks used non-symlink `/work/install`; ROS tests used generated messages without launching driving nodes. Scoped new-file flake8 passed.

`suites/comparison.json` independently confirms equal failing/skipped identities. Eight failing leaf cases are three `f110_msgs` CMake formatting cases, its XML-schema check, and flake8/pep257 checks in Frenet/global planner; two failing CTest wrappers produce the aggregate ten. Both legacy return codes remain 1. They are pre-existing failures, not W1 regressions. CI does not itself enforce identity equality, so this independent comparison matters.

Evidence includes full CI logs/metadata, W0/W1 trees and diff inventory, raw local suite logs/JUnit, runtime/dependency inventories, probes and complete counterexample fixtures, with a bundle SHA-256 manifest. The evidence is reproducible software verification, not physical validation.

## E. Test-coverage gaps and residual uncertainty

The following are **actual failures** absent from existing coverage: tangent legal-side contact at a solver node; localized regular low-speed integration features; exact anchor metadata after a nonuniform q/s roundtrip; compensated endpoint canonicalization; and scale/subdivision-invariant portal orientation. Their regressions are specified individually above.

Other boundaries remain **unproved risks or API limitations**, not additional demonstrated blockers:

- Bounded random predicates do not prove robust classification for every supported binary64 polygon. Near-parallel false acceptance was investigated without success; it must not be reported as a found defect.
- Loaded route/curve outputs use frozen tuples and show no caller mutation, mutable cache, runtime association or ROS dependency. However public `Route(occurrences,portals,encoded)` has no invariant check: direct construction/replacement can mismatch geometry and digest or supply mutable fields. The supported validator factory returns consistent immutable objects. A04 should retain that validated original; document a factory-only boundary or guard construction if direct construction is meant to be supported. This is a trust-boundary caution, not evidence that JSON loading silently switches surfaces.
- Approval/provenance strings are structurally required but do not define an approved/rejected policy vocabulary or authenticity mechanism. Initialization zone/heading applicability is recorded, not proved on a final curve. These limitations are explicitly declared; no physical approval was inferred.
- q lineage and local directed gate checks do not prove every intervening point follows a physical surface. Continuous ownership/containment, holes/footprint handling, curvature extrema and swept margins belong to A05. A03 correctly labels its output as preparation. A05 still must independently reject between-node escapes, including a smoothed/refitted curve whose sampled points remain legal.
- Holes are explicitly rejected rather than silently filled; this is permitted by the architecture. Arbitrary disconnected connectors require explicit occurrences. These are supported-domain restrictions, not missing W2 implementations hidden as W1 success.
- No representative 240 m/S6 solver scaling, optimizer iteration, optimized footprint clearance, dynamic profile, measured course, 3D deck clearance, tire/contact/grade feasibility or vehicle certification was established. Those claims were not made by this review.

## F. Architectural assessment for A04–A06

The main decomposition is suitable after surgical repair. One selected cyclic route, original occurrence/surface ownership and monotone inherited q are substantially better foundations than global nearest-XY association. Distinct projected bridge decks and repeated identical XY/heading visits remain distinguishable in the inspected and executed cases. The four small pure modules avoid ROS/runtime coupling and preserve legacy behavior. Signed left-positive a, TUM right-positive alpha=-a, right/left row order, heading and curvature conventions agree in the tested transformations.

One coefficient authority drives geometry, derivatives and metric queries; reconstruction does not refit. The original parabola error is genuinely removed through integration/inversion. F2 nevertheless prevents accepting the metric contract generally. Self-consistency against one inaccurate integrator is insufficient verification.

A03 already re-intersects original owned borders after refit, rejects off-route samples and invalid full-width Jacobians, limits chart comparisons, and preserves explicit portal adjacency. Its full-width check takes the minimum of `1-kappa*a` at both interval ends and requires at least .05; using endpoints is mathematically sufficient for this affine expression. Widths are inset 1e-9 m rather than inflated or clamped to pass. These are sampled chart checks, not a continuous chart certificate. No demonstrated nearest-distance reassociation or width-inflation fallback was found. F1 shows the intersection representation loses boundary-contact topology; F3 shows numeric coordinates and semantic events are not consistently separated. Both can be repaired within the current representation.

`PreparedRoute.reftrack`, right normals, exact curve and lineage can support a small A04 adapter without an architectural rewrite. A04 must retain original route authority and recompute intervals after every shifted fit; A05 must independently certify final coefficients rather than trust A03/optimizer acceptance; A06 must split at exact semantic cap events and include closing dynamics. No alternate backend, generalized graph framework or wholesale rewrite is justified by this evidence.

## G. Dependency-ordered remediation plan

1. **Repair F2 metric acceptance.** Add feature-aware, conservatively controlled integration or explicit rejection of unresolved cases. Make partial arc/inverse acceptance share a valid budget. Add analytic lower-bound, periodic and non-retracing regressions before claiming metric accuracy.
2. **Repair F4 canonical query boundaries.** Make endpoint anchors agree exactly with cumulative knots and handle modulo/subtraction roundoff under an explicit half-open policy. Exercise every join/seam and adjacent owner.
3. **Repair F1 interval contact topology.** Preserve/reject non-gate tangent contacts while retaining legitimate declared shared-cap union. Add the complete route/actual mesh-anchor regression and transformed variants.
4. **Repair F3 semantic anchor transport.** Preserve known source anchors/events through resampling/refit rather than reclassifying them after approximate inversion. Test cap, occurrence, portal and seam events under nonuniform progress conditioning.
5. **Repair F5 dimensional gate orientation.** Normalize the directed predicate and add collinear-subdivision/scale regressions; keep reversed/tangent rejection.
6. **Publish a fresh exact-head verification result.** Run all existing and new regressions in pinned Humble, installed checks and the W0 legacy-identity comparison; preserve source/fixture/policy hashes and CI checkout identity. Update W1 completion/limitations documents to the repaired contracts. Clarify factory-only route construction without expanding the architecture.

No W1 repair was implemented during this investigation. These are narrow corrections to existing contracts, not requests to implement A04–A06 early or weaken acceptance tolerances.

## H. Final W2 readiness decision

**Can W2 safely begin using this W1 implementation as its mathematical and topological foundation? No.**

F1 and F2 are demonstrated acceptance blockers at the reviewed final CI-tested SHA. The metric kernel can return the wrong physical station while reporting success, and a sampled original-border interval can include an unsupported internal legal-side contact. W2 must not treat either result as an accepted foundation.

To lift the block, the corrected SHA must reject or correctly resolve both counterexamples within the original tolerances, pass independent periodic/partial-arc and transformed tangent/portal regressions, and preserve the existing suites. F3–F5 should be corrected in the same W1 repair so W2 inherits exact event/owner conventions and stable portal validation. A new exact-head CI result, installed-package replay and unchanged legacy-failure identities must accompany that revision.

A04/A05 design or test-oracle work can proceed independently, but solver results that rely on the present W1 outputs must remain provisional. Acceptance of a repaired W1 will still be mathematical software acceptance; continuous final-trajectory certification and physical vehicle evidence remain separate obligations.
