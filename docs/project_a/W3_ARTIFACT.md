# Offline reference contract v1

The supported product is an independently checked planar offline reference. The
contract identifier is `forzaeth.offline-reference.v1`. It preserves the accepted
W2 cubic and squared-speed authorities. It supplies no live localization,
tracking, controller permission, physical clearance or vehicle safety approval.
The three production modules are `route_artifact`, `route_compile` and
`route_legacy_export`; the W2 kernel and independent validators remain authoritative.

## Inputs and installed commands

The compiler takes three explicit UTF-8 JSON documents. The route is the existing
A01 selected legal-route schema. The vehicle document has exactly
`schema_version: 1`, `model` (the complete supported `DynamicsModel` record) and
`footprint` (front/rear extent, width and separate geometric margin). These are
supplied synthetic or separately approved model inputs, not inferred car settings.

The policy document has exactly `schema_version: 1`, `contract_id`, `numeric`,
`solver`, `retime`, `geometry`, `dynamics`, `required_geometry_coverage`,
`required_dynamics_coverage` and `retime_spacing_m`. All policy records contain
every field, including the validators' separately supplied numerical policies.
Unknown fields, missing fields and booleans in numerical fields are rejected.
Typed construction must preserve the precise JSON authority; write normalized
model values as JSON floating-point numbers where W2 constructors return floats.

The installed resources are under
`share/global_planner/project_a/{fixtures,models,policies}`. They include a copy of
the accepted synthetic S0 route, `synthetic_model.json` and
`synthetic_policy.json`. The build installs a provenance manifest separately.
Example paths can be obtained with `ament_index_python`; the compiler itself
performs no package-share, map, HOME, vehicle or checkout discovery.

```bash
ros2 run global_planner compile_route compile \
  --manifest /inputs/s0_route.json \
  --vehicle-config /inputs/synthetic_model.json \
  --policy /inputs/synthetic_policy.json \
  --build-manifest /inputs/build_identity.json \
  --output /results/references --report /results/compile.json

ros2 run global_planner compile_route validate \
  --artifact /results/references/TRUSTED_H/reference.json \
  --expected-h TRUSTED_H --policy /inputs/synthetic_policy.json \
  --report /results/validate.json

ros2 run global_planner compile_route query \
  --artifact /results/references/TRUSTED_H/reference.json \
  --expected-h TRUSTED_H --policy /inputs/synthetic_policy.json --s-m 12.3

ros2 run global_planner compile_route export \
  --artifact /results/references/TRUSTED_H/reference.json \
  --expected-h TRUSTED_H --policy /inputs/synthetic_policy.json \
  --step-m 0.1 --output /results/legacy --report /results/export.json
```

`--build-manifest` is optional informational provenance from an explicit path;
the source-free release acceptance supplies the generated installed manifest.
It records the exact checkout, recursive gitlinks, source/resources and lock
hashes without invoking Git at runtime. Retain `H` from the controlled compile
receipt before transporting the artifact. A mutable adjacent receipt, an
artifact's own H, its embedded curve approval or its stored PASS is insufficient
independent approval for a received artifact. The accepted output directory and
report paths must be new. Query emits its JSON result on stdout. Other commands
also create a separate report without replacing an existing file. Non-PASS
outcomes return nonzero and expose no usable artifact path.

## Identity and exact records

Each accepted directory is named by lowercase SHA-256 `H` and contains exactly
one file, `reference.json`. The envelope is
`{schema_version: 1, H: <hex>, payload: <object>}`. H hashes the canonical payload
alone, excluding its own envelope and all run telemetry. Canonical bytes are
UTF-8 `json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
allow_nan=False)`. Arrays retain order. Floating-point numbers retain binary64
values, signed zero and float versus integer spelling. This is deliberately
different from A01's route-input normalizer. The embedded route retains A01's
canonical representation; W2 curve/model digests retain their existing algorithms.

The payload has exactly these members:

| Member | Authority |
|---|---|
| `conventions` | metres/seconds/radians, +X/CCW heading, signed left curvature, true metric progress and cyclic right-hand edge state |
| `approved_route` | complete original A01 route, surfaces, occurrences, gates/support, boundaries, caps, physical-map/annotation provenance and coverage |
| `curve` | actual ascending-power normalized-t `(N,2,4)` cubic coefficients, N occurrence/surface owner pairs and N+1 inherited seed-q values |
| `approved_curve_digest` | full W2 identity captured directly after the trusted final A04 return |
| `model`, `footprint` | complete explicit region/steering model, provenance, body and separate margin |
| `speed_profile` | exact half-open segment/t/u knots, curve/model bindings and main moving-lap time; u is squared speed |
| `policies` | complete numeric, solver, retimer and independent geometry/dynamics records |
| `implementation` | supported contract, accepted W2/gitlink identity, actual installed kernel/checker/helper content hashes and pinned numerical runtime versions |
| `validation` | immutable historical geometry interval/gate and dynamics edge reports, assumptions, coverage and model-time enclosure; fresh replay reports decide acceptance |
| `provenance` | bounded informational string values, including controlled input identities and explicit build-manifest identity when supplied |

No stored waypoint, arc table or interpolated spline replaces these coefficients.
The loader reconstructs `Curve(coefficients, owners, expected_numeric_policy)`;
it never calls interpolation or fitting. Derived metric metadata are rebuilt.
Changing any authority changes H. Volatile wall/CPU times, RSS and solver trace
diagnostics are confined to the separate compile run report.

Full encoded JSON is bounded to 64 MiB, depth 32, 2,000,000 lexical/tree nodes,
65,536 UTF-8 bytes per text value and 1,024-bit integers. Config/route inputs are
bounded to 2 MiB. Resource preflight also retains the independently selected W2
segment, polygon-work, profile-knot and certificate budgets. Duplicate keys,
invalid UTF-8, overflow/nonfinite numbers, wrong dimensions, scalar types,
unknown versions/contracts and unsupported required coverage fail closed.

## Trust and publication

Compilation freezes the full W2 curve digest immediately after the trusted A04
return, before retiming or serialization. Both independent validators receive
that same separately retained expectation. Original route/model/body/policies
and provenance are frozen before downstream work. Curve/profile/report bytes
are separately retained; encoded authority is compared with these controlled
values before the compiler freezes H. This prevents a coordinated q/profile
rehash, smaller-body substitution or more permissive model from becoming its own
approval during publication.

The publisher requires both the independently frozen expected H and original
A04 curve digest. It writes canonical bytes into a private same-parent stage,
reads those exact persisted bytes back, verifies the separate expectations,
reconstructs the original coefficients, and reruns both independent validators.
Stored reports are H-bound historical snapshots. Strict authority, identity,
coverage, assumptions and internal snapshot coherence must hold. Their numerical
values and adaptive geometry partitions need not equal a new replay bit for bit.
The two freshly regenerated PASS reports are the sole runtime validation
authority and populate the Reference's validation fields; the payload retains
the unchanged historical bytes. Snapshot coherence is not a second numerical
certificate.
No generic closeness tolerance or proof-policy relaxation is used.
The main binary64 lap-time display remains the producer's exact persisted
dynamics-report nominal T. It must lie inside both its historical enclosure and
the actual fresh replay enclosure. `Reference.lap_time_s`, terminal audit T and
legacy Float32 projection use that frozen value. Fresh nominal report time may
differ by rounding; it does not change the immutable display. Query prefix times
remain derived from actual metric arcs, without rescaling to force equality.

Every changed payload fails under the original external H. A separately
controlled new expected H is a new external approval: actual fresh validators
must still prove its saved authority, while historical numeric audit claims do
not authorize acceptance. A received self-hash is never a trusted expectation.

File and stage directories are fsynced. Linux `flock` serializes cooperative writers, while
`renameat2(RENAME_NOREPLACE)` protects against existing targets and late races.
Directory traversal uses file descriptors with no symlink following. Existing
digest directories are never replaced; final files/directories are read-only.
The parent is fsynced after publication. Private stages and locks cannot load as
accepted references.

An interruption or injected failure leaves the accepted target absent or fully
valid. A crash or fsync failure after rename can leave a complete valid reference
with no successful receipt and uncertain power-loss durability; no rollback or
hardware persistence guarantee is claimed. Orphan private stages are unaccepted.
The contract targets the pinned Linux/Humble local filesystem, with no distributed
filesystem locking claim.

Loading requires externally trusted `expected_H` and an independently selected
`ValidationContext`. H is checked before the embedded curve approval is used.
The loader rejects changed behavioral implementation, numerical dependencies or
proof policy, then reruns both validators before exposing a frozen `Reference`.
Rehashing a received mutation does not supply external approval.

Fresh compilation is not guaranteed to produce bit-identical coefficients/q/C/H
across hosts merely because source, inputs and package versions match. The final
811bd708 challenge measured this variation and exposed an overly strict
historical-report comparison; the [red/green evidence](evidence/w3-report-portability/README.md)
records the repair and its limits. Each controlled compile retains its own H and
C. Portability replays one unchanged artifact under its externally trusted H and
supported context, without refitting or changing that authority. No coefficients
or identities are rounded to conflate distinct fresh products. The exact source
of host-dependent numerical variation is unproven in the retained observations.

## Metric queries and the ROS projection

`Reference.locate`, `sample` and `window` accept supplied physical progress.
Progress wraps cyclically; exact seam/coefficient ownership is right-hand and
half-open. Negative and multiple-lap progress are supported within the W1
resolution bound. An optional supplied occurrence must agree with ordered
progress; XY never selects an occurrence. Samples contain H, true station,
segment/t, XY, tangent, left normal, +X/CCW heading, signed curvature, occurrence,
surface, speed, right-hand acceleration, accumulated wrapped model time and
applicable declared portal support.

Within an edge, `u=u0+(u1-u0)*local_true_arc/edge_true_arc`,
`v=sqrt(u)`, `a=(u1-u0)/(2*edge_true_arc)` and partial time is
`2*local_true_arc/(sqrt(u0)+sqrt(u))`. Closure uses the last knot to first knot.
Neither q, t, waypoint index nor linear velocity interpolation substitutes for
physical arclength. Query numerical accuracy inherits W1's bounded arc/inverse
policy; portal tags conservatively retain support at numerical event boundaries.

The exporter projects the accepted reference directly into unchanged
`f110_msgs/Wpnt` and `WpntArray`. It retains true s, signed curvature, original
owned signed-normal side distances (including the existing 1e-9 m inward chart
allowance), main cyclic speed/acceleration and the correctly rounded Float32
main lap time. It adds a terminal seam duplicate with unwrapped s=L. The audit
projection retains terminal time=T; the unchanged Wpnt message has no per-waypoint
time field, so that value is not carried in the legacy message.
Nominal sampling also retains semantic/profile events; actual s remains authoritative.
It uses the actual nine-group legacy writer, reader and generated CDR serializer
in a private export stage before no-replace publication. Unavailable centerline
and shortest-path groups are explicitly empty and described as unavailable.

Waypoint fields omit occurrence/surface, q and per-waypoint time. Map text
includes an informational H; it is not an independently trusted identity or
certificate for the waypoint bytes. External H and artifact replay remain
necessary. Consumers that refit samples, infer occurrence from XY or use
index-times-0.1 do not preserve
this authority. Downstream teams own supplied progress/occurrence association,
localization, tracking error budgets, controller integration and every physical
operating decision. Real-course approval, tire/contact/grade behavior and 3D
clearance require separate evidence. Independent W3 adversarial review remains
the release gate even when the implementation's own suites pass.
