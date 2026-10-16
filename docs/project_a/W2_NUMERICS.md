# W2 numerical contracts and limits

W2 starts directly from corrected W1 commit
`9440c2ce68e3dee549de7efacff1cf723fe830df`, on
`project-a/w2-optimization`. User instructions fix this base and supersede older
branch names or rebase guidance. The source remains an offline planner; no
vehicle system, legacy planner, original map or optimizer gitlink is changed.

## A04: unchanged TUM equations with original-border preparation

`iqp_route_adapter.optimize` returns an unaccepted numerical `CANDIDATE` or an
explicit failure with no usable curve. It solves the complete selected lap in
one QP per iteration, including closure. Only independent A05/A06 checks on that
same final coefficient authority can establish W2 acceptance.

Each mesh carries the W1 monotone seed coordinate q, source segment/t and
occurrence/surface. Equal **metric** resampling preserves exact cap, occurrence
and portal-support anchors. These anchors make the mesh nonuniform. The existing
TUM `calc_splines` distance-scaling equations therefore use the inherited knot
intervals `diff(q)`, matching the periodic q-interpolant. q is never substituted
for metric arc length. A fixed-input direct-helper control checks the unchanged
QP independently of preparation.

The returned TUM coefficients and their right normals define the current
authority. The driver re-intersects those normals against the original owned
boundaries before every QP and after every shifted fit. Only explicitly supported
adjacent portals permit a union. It retains the full-width Jacobian and
same-occurrence normal-intersection checks, with bounded pair comparisons.
TUM alpha is right-positive, the negative of W1's left-positive signed offset.
Widths are never accumulated, inflated or reassigned by nearest XY.

The final shifted TUM coefficients are retained verbatim; no export refit becomes
a second curve. Stock early damping and the raw curvature-linearization error
criterion are preserved. A damped offset must also satisfy the eroded nodal
interval. A failed geometry, numerical, residual, resource or convergence check
returns failure rather than weakening constraints.

Default synthetic solver policy: 0.4 m requested spacing, 0.30 m solver width,
1/m curvature bound, 0.1/m linearization-error threshold, minimum 3 / maximum 8
iterations, maximum 512 points, 120 s driver budget, and 1,000,000 chart pairs.
Dense spline fits and QPs execute in fresh children with a 20 s wall limit,
20 CPU seconds and 2 GiB address-space limit; the remaining driver budget further
limits each child. Numerical imports follow resource-limit setup. Mesh sizes are
checked before expensive preparation and geometry phases check the deadline.
The driver deadline is cooperative across the W1 metric/geometry and diagnostic
phases, so one bounded phase may overshoot it; the child process limits are hard.
The maximum accepted spline-system condition number is 1e12, primal residual
1e-7 and offset residual 1e-8 m. Traces report actual constraints, objective,
conditioning, runtime, peak resident memory, original intersections and lineage.
These are explicit software policies, not physical vehicle parameters.

### Optimization limitation

The unchanged TUM QP minimizes a local curvature surrogate, using frozen
derivative terms. Its convergence criterion does not prove global optimality,
stationarity of the exact geometric objective, or even monotonic reduction of
actual integrated squared curvature. The circle regression measures this
limitation rather than hiding it. Unweighted sums over different meshes are not
comparable curvature energies; any measured energy comparison must integrate
the actual coefficients and remains a diagnostic, not a continuous certificate.

## Synthetic acceptance inputs

The planned W2 integration footprint is an explicitly supplied rectangle with
front/rear extents 0.10 m each, width 0.12 m and separate legal margin 0.01 m.
The 0.30 m solver width provides conservative nodal clearance for that smaller
footprint. All geometric and dynamic checks still use the supplied footprint
and original legal area. No value is asserted to describe a real car.

Simple owned ribbons and declared shared-cap portal supports are the v1 domain.
Holes, missing physical clearance coverage, 3D bridge clearance, contact,
traction and physical vehicle safety cannot be silently inferred from planar
geometry, labels or successful numerical optimization.
