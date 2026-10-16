# W1 legal-route geometry contract

These modules are offline and ROS-independent. `route_input.load_route(path)`
accepts the synthetic examples under `planner/global_planner/test/fixtures/project_a`.
No output is an accepted optimized trajectory. A04–A09 remain future work.

## Input v1

All fields in the examples are required; unknown fields, JSON duplicate keys,
nonfinite numbers, booleans and nulls are rejected. Coordinates are metres in the
named frame, |XY| <= 100000 m. Numerical predicates use 1e-9 m; annotations near
that resolution are unsupported. Provenance records contain author, source,
revision and approval strings. They record an assertion, not authenticated truth.
Physical map SHA-256, SE2 registration `[x,y,yaw]`, coverage and provenance are
separate from legal geometry. Missing measured coverage never enlarges a ribbon.

The occurrence array is the manually selected cycle, with unique occurrence IDs
and declared surface IDs. Each occurrence has travel-ordered seed, left and right
polylines; the closed polygon is right forward + left reversed. Holes are
unsupported and rejected. Seeds meet the end caps and cannot touch legal sides.
Local seed-metric caps start at 0 and increase strictly; each applies until the
next knot (or occurrence end). Surface kind is an annotation only.

Each consecutive pair, including closure, has one ordered directed portal. v1
requires `shared_endcap`: coincident seed endpoints and shared original cap
endpoints. The gate runs right to left. `support` is a simple polygon delimiting
where the union of those two original ribbons may be consulted; it is **never**
additional legal area. `before_m` / `after_m` delimit its inherited progress
bracket. Arbitrary disconnected connector geometry is rejected; a connector must
be a separately declared occurrence with its own borders and two portals.

`gate_sequence` lists those portal IDs in cyclic order; `finish` is the closing
portal. Initialization declares the first occurrence, a bounded local seed
interval, a simple zone and an increasing heading interval in [-pi,pi]. W1 records
these anchors; future continuous validation must prove actual directed passage
and initialization applicability on the final curve.

Canonical input identity is SHA-256 over UTF-8 JSON with sorted keys, compact
separators, ensure_ascii=False and allow_nan=False. NFC-normalize strings and keys;
reject normalized key/ID collisions. Convert numbers to finite binary64 (absolute
value <= 1e12), canonicalize integral values to integers and negative zero to 0.
No wall-clock fields or digest field are supported in v1. Any provenance, legal,
physical-map, route, cap or surface mutation changes identity. Records/point
chains are frozen tuples; `Route.payload` returns a fresh copy.

Fixed fixtures include S0, reversed direction with swapped sides and transformed
gates, rotated origin, independent S2 upper/lower selections with common return,
and S3 with disconnected projected crossing occurrences on ground/upper-deck.
They describe synthetic software geometry only.

## A02 coefficient and metric kernel

`Curve.interpolate(points,q=...)` fits a periodic ordered cubic once, without
smoothing. `Curve(coefficients, owners, policy)` consumes exact `(N,2,4)` ascending
coefficients on normalized t in [0,1]. Segment owners are explicitly supplied
`(occurrence_id,surface_id)` pairs; equality in XY has no role. Public records and
all coefficient/length/owner arrays are immutable tuples. Artifact I/O is A07.

Every join including closure checks position, unit tangent and signed curvature
within 1e-8 (metres, dimensionless, 1/metre respectively). Parameter derivatives
need not have equal magnitudes across normalized segments. Quadratic derivative
Bézier boxes prove a conservative nonzero lower bound >1e-7 metres per normalized
t; ambiguous near-zero cases fail closed. Rounding allowance is 128 binary64 eps
scaled by coefficient magnitude, which is limited to 1e8. Subdivision is limited
to depth 24 and 10000 boxes per segment. These are software numerical assumptions,
not a continuous legal/footprint certificate.

QUADPACK adaptive Gauss-Kronrod integrates speed with total-lap absolute estimated
error budget 1e-10 m, divided among segments; relative request 5e-14, 100 interval
limit. QUADPACK's estimates are numerical error control, not formal interval
arithmetic. Nonconvergence or excess estimate rejects. Compensated sums accumulate
lengths. Brent inversion uses physical station tolerance 1e-8 m and verifies the
residual plus two partial integration allowances; the regression acceptance is
<=1e-7 m as required by the roadmap. No chord approximation is substituted.

`locate`, `station`, `sample` and `window` share these exact coefficients. Queries
wrap negative/multiple-lap progress; knots and seam use the right-hand segment.
Reject nonfinite progress and lap counts whose binary64 resolution exceeds 1/16
of the station budget. Windows include endpoints and have at most 100000 samples.
Heading is +X-zero/CCW, curvature is signed, normal is left-positive. There is no
speed profile, tracking state or XY association in W1.

Independent oracles use the analytic parabola integral, fixed-order
Gauss-Legendre integration of coefficients, polynomial differentiation and the
complete elliptic integral for an ellipse. Reconstructing from stored coefficients
performs no refit. The unchanged W0 defect test remains green alongside the new
true-metric inverse test.

## A03 owned corridor and lineage

`seed_curve(route)` returns `OrderedCurve` with q at every original seed knot.
q is unwrapped piecewise-linear seed arclength, distinct from current spline
metric s. `resample_ordered` uses A02 inverse arc and inherits q by segment/t;
it adds exact occurrence, cap and portal bracket anchors. `refit_ordered` accepts
shifted ordered knots plus those source records, checks source lineage and
occurrence anchors, and interpolates with the inherited monotone q. No XY
projection occurs. Cap values use the inherited local seed metric (right-hand
knots with a 1e-9 m annotation allowance).

`prepare_route` checks actual polynomial/gate intersections in the inherited
portal brackets, requires unique forward crossings and ordered gates, resamples,
and computes `Corridor` records. At each sample, intersect the full normal line
with the original owning polygon. Use only the connected interval containing the
reference; disjoint intervals are never bridged. Signed a is left-positive;
TUM alpha=-a, `[x,y,right,left]` uses `right=-lower`, `left=upper`.

Adjacent ownership is consulted only inside both the declared q bracket and
portal support polygon. The permitted interval is `(original source UNION
original target) INTERSECT support`. At a shared end cap, that cap may be removed
as an ownership separator. Other endcaps cannot masquerade as legal side walls.
Support enlargement cannot add legal area. Surface/occurrence changes, unsupported
cap intersections, collinear boundary ambiguity and off-route samples reject.
Portal roots use cubic polynomial roots with residual/direction/segment checks;
near-real uncertain roots and tangent/collinear passages reject.

Every interval is inset 1e-9 m for numerical allowance; widths are never inflated.
Require `1-kappa*a >= .05` throughout the entire returned interval; reject rather
than truncate a folded chart. Nonadjacent prepared normals inside the **same
occurrence** cannot intersect. Crossings on unrelated occurrences/surfaces do not
supply adjacency or cause a global normal-crossing rejection. Pair comparisons
have a 1000000 budget; exhaustion rejects. Samples are limited by the A02 policy.

Preparation verifies the solver mesh and directed portals; it is **not** the A05
continuous spline/footprint certificate. Narrow restrictions between solver nodes
still require W2 independent continuous validation. The fixed S3 notch test uses
an explicit seed-metric cap anchor to exercise restriction transport through
repeated resampling and independently solves ray/edge 2x2 systems against the
actual fitted normal. Its generating analytic normal is a distinct approximation.
