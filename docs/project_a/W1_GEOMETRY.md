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
