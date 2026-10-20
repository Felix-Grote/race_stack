"""Bounded, original-border IQP candidates using the unchanged pinned TUM QP.

The helper's distance scaling uses inherited q because semantic anchors make the
mesh nonuniform. q remains lineage, never physical station. Only A05/A06 may
accept a candidate; numerical convergence here is deliberately not a certificate.
"""
from dataclasses import dataclass
import hashlib
import importlib.metadata as metadata
import io
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

import numpy as np

from ._route_geometry import segments_touch
from .route_corridor import (CorridorError, OrderedCurve, _sample_at_q, normal_interval,
                             portal_crossings, resample_ordered, seed_curve)
from .route_reference import Curve, GeometryError, NumericPolicy

_HASHES = {
    'opt_min_curv.py': 'a2ce75c33498426a5276e5b3455f2059040e8c5e5e54734aee3dde0436bef46d',
    'calc_splines.py': '2943a4cb0c614a541551a8c6d031cf43b18b81b701221ac02ae51337fbf075a8',
}


class OptimizationError(ValueError):
    """An explicit numerical, infeasibility or resource failure without candidate."""

    def __init__(self, reason, status='NUMERICAL_FAILURE'):
        super().__init__(reason)
        self.status = status


@dataclass(frozen=True)
class SolverPolicy:
    """Predeclared synthetic numerical limits; no physical vehicle calibration."""

    spacing_m: float = .4
    vehicle_width_m: float = .30
    curvature_bound: float = 1.
    curvature_error: float = .1
    min_iterations: int = 3
    max_iterations: int = 8
    max_points: int = 512
    wall_seconds: float = 120.
    qp_wall_seconds: float = 20.
    qp_cpu_seconds: int = 20
    qp_memory_bytes: int = 2 * 1024 ** 3
    max_condition: float = 1e12
    qp_residual: float = 1e-7
    offset_tolerance: float = 1e-8
    chart_pair_budget: int = 1000000

    def __post_init__(self):
        for x in (self.spacing_m, self.vehicle_width_m, self.curvature_bound,
                  self.curvature_error, self.wall_seconds, self.qp_wall_seconds,
                  self.max_condition, self.qp_residual, self.offset_tolerance):
            if (isinstance(x, bool) or not isinstance(x, (int, float))
                    or not math.isfinite(x) or x <= 0):
                raise OptimizationError('invalid solver tolerance/resource policy')
        for x in (self.min_iterations, self.max_iterations, self.max_points,
                  self.qp_cpu_seconds, self.qp_memory_bytes, self.chart_pair_budget):
            if type(x) is not int or x < 1:
                raise OptimizationError('invalid integer solver resource policy')
        if self.min_iterations > self.max_iterations or self.max_points < 3:
            raise OptimizationError('inconsistent solver iteration/point policy')


@dataclass(frozen=True)
class QPResult:
    """Observed actual helper/quadprog output, including primal residuals."""

    alpha: tuple
    curvature_error: float
    objective: float
    max_violation: float
    linear_curvature_max: float
    condition: float
    peak_rss_bytes: int
    elapsed_seconds: float
    helper_sha256: str


@dataclass(frozen=True)
class IterationTrace:
    """Exact current coefficients, inherited lineage and original intersections."""

    number: int
    source_q: tuple
    lineage: tuple
    q: tuple
    coefficients: tuple
    samples: tuple
    corridors: tuple
    normals_right: tuple
    matrix_sha256: str
    qp: QPResult
    applied_alpha: tuple
    shifted_coefficients: tuple
    source_curvature_energy: float
    reference_curvature_energy: float
    shifted_curvature_energy: float
    shifted_curvature_max: float
    reference_fit_resources: tuple
    shifted_fit_resources: tuple


@dataclass(frozen=True)
class OptimizationResult:
    """CANDIDATE is numerical only; failed runs expose no usable candidate."""

    status: str
    ordered: object
    traces: tuple
    reason: str
    policy: SolverPolicy


def _helpers():
    import trajectory_planning_helpers as tph
    for name, version in (('numpy', '1.26.4'), ('scipy', '1.11.4'),
                          ('quadprog', '0.1.7'), ('trajectory-planning-helpers', '0.79')):
        if metadata.version(name) != version:
            raise OptimizationError('unrecognized pinned kernel: ' + name)
    root = Path(tph.__file__).parent
    for name, digest in _HASHES.items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != digest:
            raise OptimizationError('unrecognized helper source: ' + name)
    return tph


def curvature_energy(coefficients):
    """Diagnostic 48-point Gaussian integral of kappa squared ds, not a bound.

    This recomputes derivatives directly from the actual coefficient authority.
    It does not authorize convergence, containment or any dynamic acceptance.
    Unlike an unweighted nodal sum it is comparable across numerical meshes.
    """
    roots, weights = np.polynomial.legendre.leggauss(48)
    t, weights = (roots + 1) / 2, weights / 2
    values = []
    for coefficient in coefficients:
        a = np.asarray(coefficient)
        d = a[:, 1, None] + 2 * a[:, 2, None] * t + 3 * a[:, 3, None] * t ** 2
        dd = 2 * a[:, 2, None] + 6 * a[:, 3, None] * t
        numerator = d[0] * dd[1] - d[1] * dd[0]
        values.append(float(weights @ (numerator ** 2 / np.sum(d * d, axis=0) ** 2.5)))
    return math.fsum(values)


def _fit(route, xy, q, owners, numeric_policy, policy, remaining=None):
    if len(xy) > policy.max_points:
        raise OptimizationError('point budget exhausted', 'RESOURCE_LIMIT')
    points = np.asarray(xy, dtype=float)
    if (points.shape != (len(q) - 1, 2) or not np.isfinite(points).all()
            or min(np.diff(q)) <= 0):
        raise OptimizationError('nonfinite/nonmonotone solver mesh')
    if min(np.linalg.norm(np.diff(np.vstack((points, points[0])), axis=0), axis=1)) <= 1e-9:
        raise OptimizationError('degenerate consecutive shifted mesh')
    request = io.BytesIO()
    np.savez(request, operation=np.array('fit'), points=points, q=np.array(q))
    response = _run_child(request.getvalue(), policy, remaining)
    try:
        fitted = np.load(io.BytesIO(response), allow_pickle=False)
        x, y, matrix, normals = (fitted[n] for n in ('x', 'y', 'matrix', 'normals'))
    except (ValueError, KeyError) as exc:
        _child_error(response)
        raise OptimizationError('invalid bounded spline response') from exc
    if not np.isfinite(matrix).all() or not np.isfinite(normals).all():
        raise OptimizationError('nonfinite TUM system')
    coefficients = tuple((tuple(a), tuple(b)) for a, b in zip(x, y))
    ordered = OrderedCurve(route, Curve(coefficients, owners, numeric_policy), tuple(q))
    usage = tuple(float(z) for z in fitted['resources'])
    return ordered, matrix, tuple(tuple(float(z) for z in row) for row in normals), usage


def _geometry(ordered, policy, check=lambda: None):
    """Current TUM knot normals against the original declared legal geometry."""
    check()
    portal_crossings(ordered)
    check()
    samples = tuple(_sample_at_q(ordered, q) for q in ordered.q[:-1])
    corridors = []
    for sample in samples:
        check()
        corridors.append(normal_interval(ordered, sample))
    corridors = tuple(corridors)
    pairs = 0
    for i, (v, c) in enumerate(zip(samples, corridors)):
        n = (-v.tangent[1], v.tangent[0])
        a = tuple(v.xy[j] + c.lower * n[j] for j in range(2))
        b = tuple(v.xy[j] + c.upper * n[j] for j in range(2))
        for w, d in zip(samples[i + 2:], corridors[i + 2:]):
            if v.occurrence_id != w.occurrence_id:
                continue
            pairs += 1
            if pairs % 256 == 0:
                check()
            if pairs > policy.chart_pair_budget:
                raise OptimizationError('chart pair budget exhausted', 'RESOURCE_LIMIT')
            m = (-w.tangent[1], w.tangent[0])
            e = tuple(w.xy[j] + d.lower * m[j] for j in range(2))
            f = tuple(w.xy[j] + d.upper * m[j] for j in range(2))
            if segments_touch(a, b, e, f):
                raise CorridorError('ambiguous intersecting charts within occurrence')
    return samples, corridors


def _worker():
    """One resource-limited child; observe and preserve the helper equations."""
    import resource
    import quadprog
    began = time.monotonic()
    try:
        request = np.load(io.BytesIO(sys.stdin.buffer.read()), allow_pickle=False)
        if 'operation' in request and request['operation'].item() == 'fit':
            points, q = request['points'], request['q']
            x, y, matrix, normals = _helpers().calc_splines.calc_splines(
                np.vstack((points, points[0])), el_lengths=np.diff(q), use_dist_scaling=True)
            response = io.BytesIO()
            usage = (resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
                     time.monotonic() - began)
            np.savez_compressed(response, x=x, y=y, matrix=matrix, normals=normals,
                                resources=np.array(usage))
            sys.stdout.buffer.write(response.getvalue())
            return
        track, normals, matrix = (request[n] for n in ('track', 'normals', 'matrix'))
        bound, width, condition_limit = request['limits']
        condition = float(np.linalg.cond(matrix))
        if not math.isfinite(condition) or condition > condition_limit:
            raise OptimizationError('ill-conditioned TUM system')
        observation = {}
        original = quadprog.solve_qp

        def observed(hessian, linear, constraints, bounds, *args, **kwargs):
            solved = original(hessian, linear, constraints, bounds, *args, **kwargs)
            alpha = solved[0]
            residuals = bounds - constraints.T @ alpha
            n = len(alpha)
            # TUM supplies C=-G.T, b=-h, d=-f to quadprog.
            g, h = -constraints.T, -bounds
            linear_kappa = g[2 * n:3 * n] @ alpha + bound - h[2 * n:3 * n]
            observation.update(objective=float(.5 * alpha @ hessian @ alpha - linear @ alpha),
                               max_violation=float(max(0., np.max(residuals))),
                               linear_curvature_max=float(np.max(np.abs(linear_kappa))))
            return solved

        quadprog.solve_qp = observed
        try:
            alpha, error = _helpers().opt_min_curv.opt_min_curv(
                track.copy(), normals.copy(), matrix.copy(), float(bound), float(width),
                print_debug=False, plot_debug=False)
        finally:
            quadprog.solve_qp = original
        answer = dict(status='OK', alpha=alpha.tolist(), curvature_error=float(error),
                      condition=condition, peak_rss_bytes=int(
                          resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024),
                      elapsed_seconds=time.monotonic() - began,
                      helper_sha256=_HASHES['opt_min_curv.py'], **observation)
    except Exception as exc:
        status = 'RESOURCE_LIMIT' if isinstance(exc, MemoryError) else 'SOLVER_FAILURE'
        if 'inconsistent' in str(exc) or 'not solvable' in str(exc):
            status = 'INFEASIBLE'
        answer = dict(status=status, reason=type(exc).__name__ + ': ' + str(exc))
    sys.stdout.write(json.dumps(answer, allow_nan=False))


def _run_child(request, policy, remaining):
    """Bound both dense spline fitting and the QP before numerical imports."""
    bootstrap = (
        'import resource,runpy; '
        f'resource.setrlimit(resource.RLIMIT_AS,({policy.qp_memory_bytes},'
        f'{policy.qp_memory_bytes})); '
        f'resource.setrlimit(resource.RLIMIT_CPU,({policy.qp_cpu_seconds},'
        f'{policy.qp_cpu_seconds})); '
        "runpy.run_module('global_planner.iqp_route_adapter',run_name='__main__')")
    env = dict(os.environ)
    env.update(OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1',
               NUMEXPR_NUM_THREADS='1')
    timeout = policy.qp_wall_seconds if remaining is None else min(
        policy.qp_wall_seconds, remaining)
    if timeout <= 0:
        raise OptimizationError('whole-lap wall budget exhausted', 'RESOURCE_LIMIT')
    try:
        completed = subprocess.run([sys.executable, '-c', bootstrap], input=request,
                                   capture_output=True, timeout=timeout, env=env, check=False)
    except subprocess.TimeoutExpired as exc:
        raise OptimizationError('QP subprocess wall budget exhausted', 'RESOURCE_LIMIT') from exc
    if completed.returncode:
        detail = completed.stderr.decode(errors='replace')[-500:]
        raise OptimizationError('QP child failed/resource limit: ' + detail, 'RESOURCE_LIMIT')
    return completed.stdout


def _child_error(response):
    try:
        answer = json.loads(response)
    except (ValueError, UnicodeError) as exc:
        raise OptimizationError('invalid QP subprocess response') from exc
    status = answer.pop('status', 'SOLVER_FAILURE')
    if status != 'OK':
        raise OptimizationError(answer.get('reason', 'QP subprocess failure'),
                                status)
    return answer


def solve_qp(track, normals, matrix, policy=SolverPolicy(), remaining=None):
    """Run one unchanged QP under actual wall, CPU and address-space limits."""
    track, normals, matrix = (np.asarray(a, dtype=float) for a in (track, normals, matrix))
    n = len(track) if track.ndim else 0
    if (n < 3 or n > policy.max_points or track.shape != (n, 4)
            or normals.shape != (n, 2) or matrix.shape != (4 * n, 4 * n)
            or not all(np.isfinite(a).all() for a in (track, normals, matrix))):
        raise OptimizationError('invalid/budget-exhausted QP input')
    request = io.BytesIO()
    np.savez(request, track=track, normals=normals, matrix=matrix,
             limits=np.array((policy.curvature_bound, policy.vehicle_width_m,
                              policy.max_condition)))
    answer = _child_error(_run_child(request.getvalue(), policy, remaining))
    answer['alpha'] = tuple(answer['alpha'])
    result = QPResult(**answer)
    _check_result(result, track, policy)
    return result


def _check_result(result, track, policy):
    numbers = result.alpha + (result.curvature_error, result.objective, result.max_violation,
                              result.linear_curvature_max, result.condition,
                              result.elapsed_seconds)
    if (len(result.alpha) != len(track) or not all(math.isfinite(v) for v in numbers)
            or result.curvature_error < 0 or result.max_violation < 0
            or result.condition > policy.max_condition):
        raise OptimizationError('nonfinite/invalid QP output')
    alpha = np.array(result.alpha)
    lo = -track[:, 3] + policy.vehicle_width_m / 2
    hi = track[:, 2] - policy.vehicle_width_m / 2
    if (np.max(lo - alpha) > policy.offset_tolerance
            or np.max(alpha - hi) > policy.offset_tolerance
            or result.max_violation > policy.qp_residual
            or result.linear_curvature_max > policy.curvature_bound + policy.qp_residual):
        raise OptimizationError('QP primal/offset/linear-curvature residual exceeded')


def optimize(route, policy=SolverPolicy(), numeric_policy=NumericPolicy(), initial=None):
    """Solve the complete directed lap jointly; return only an unaccepted candidate."""
    began, traces = time.monotonic(), []

    def remaining():
        value = policy.wall_seconds - (time.monotonic() - began)
        if value <= 0:
            raise OptimizationError('whole-lap wall budget exhausted', 'RESOURCE_LIMIT')
        return value

    try:
        remaining()
        if (sum(len(o.seed) - 1 for o in route.occurrences) > policy.max_points
                or (initial is not None and len(initial.curve.segments) > policy.max_points)):
            raise OptimizationError('initial seed point budget exhausted', 'RESOURCE_LIMIT')
        ordered = seed_curve(route, numeric_policy) if initial is None else initial
        if ordered.route.digest != route.digest:
            raise OptimizationError('initial route identity mismatch')
        for iteration in range(1, policy.max_iterations + 1):
            remaining()
            if ordered.curve.length > policy.spacing_m * policy.max_points:
                raise OptimizationError('point budget exhausted before remeshing',
                                        'RESOURCE_LIMIT')
            # A semantic event can add one knot: conservatively count all supplied
            # events before doing any metric inversion (duplicates only reduce it).
            events = (len(route.occurrences) + sum(len(o.caps) for o in route.occurrences)
                      + 2 * len(route.portals))
            count = math.ceil(ordered.curve.length / policy.spacing_m)
            if events + count > policy.max_points:
                raise OptimizationError('semantic anchor budget exhausted', 'RESOURCE_LIMIT')
            lineage = resample_ordered(ordered, policy.spacing_m)
            if len(lineage) > policy.max_points:
                raise OptimizationError('point budget exhausted', 'RESOURCE_LIMIT')
            q = tuple(v.q for v in lineage) + (ordered.period,)
            owners = tuple((v.occurrence_id, v.surface_id) for v in lineage)
            reference, matrix, normals, fit_usage = _fit(
                route, [v.xy for v in lineage], q, owners, numeric_policy, policy, remaining())
            samples, corridors = _geometry(reference, policy, remaining)
            expected = np.array([(v.tangent[1], -v.tangent[0]) for v in samples])
            if not np.allclose(normals, expected, rtol=0, atol=1e-12):
                raise OptimizationError('TUM matrix/normal/coefficient authority mismatch')
            track = np.array([v.xy + (c.right, c.left) for v, c in zip(samples, corridors)])
            qp = solve_qp(track, normals, matrix, policy, remaining())
            _check_result(qp, track, policy)
            factor = iteration / policy.min_iterations if iteration < policy.min_iterations else 1.
            applied = np.array(qp.alpha) * factor
            # Damping must not leave the legal eroded nodal interval either.
            lo = -track[:, 3] + policy.vehicle_width_m / 2
            hi = track[:, 2] - policy.vehicle_width_m / 2
            if max(np.max(lo - applied), np.max(applied - hi)) > policy.offset_tolerance:
                raise OptimizationError('damping violates eroded corridor', 'INFEASIBLE')
            shifted, _, _, shifted_usage = _fit(
                route, track[:, :2] + applied[:, None] * np.array(normals),
                q, owners, numeric_policy, policy, remaining())
            shifted_samples, _ = _geometry(shifted, policy, remaining)
            traces.append(IterationTrace(
                iteration, ordered.q, tuple((v.segment, v.t, v.q) for v in lineage),
                q, reference.curve.coefficients, samples, corridors, normals,
                hashlib.sha256(matrix.tobytes()).hexdigest(), qp, tuple(applied),
                shifted.curve.coefficients, curvature_energy(ordered.curve.coefficients),
                curvature_energy(reference.curve.coefficients),
                curvature_energy(shifted.curve.coefficients),
                max(abs(v.curvature) for v in shifted_samples), fit_usage, shifted_usage))
            remaining()
            if iteration >= policy.min_iterations and qp.curvature_error <= policy.curvature_error:
                return OptimizationResult('CANDIDATE', shifted, tuple(traces), '', policy)
            ordered = shifted
        raise OptimizationError('curvature linearization did not converge', 'NONCONVERGENCE')
    except OptimizationError as exc:
        return OptimizationResult(exc.status, None, tuple(traces), str(exc), policy)
    except (CorridorError, GeometryError, np.linalg.LinAlgError) as exc:
        return OptimizationResult('GEOMETRY_FAILURE', None, tuple(traces), str(exc), policy)


if __name__ == '__main__':
    _worker()
