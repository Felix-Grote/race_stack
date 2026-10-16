"""A04 actual pinned-equation solves and fail-closed bounded-driver regressions."""
from dataclasses import asdict, replace
import json
import math
from pathlib import Path

import numpy as np
import pytest
import trajectory_planning_helpers as tph

import global_planner.iqp_route_adapter as adapter
from global_planner.route_corridor import OrderedCurve, seed_curve
from global_planner.route_input import load_route, validate_route
from global_planner.route_reference import Curve

FIX = Path(__file__).parent / 'fixtures' / 'project_a'


def route(name='s0_route'):
    return load_route(FIX / (name + '.json'))


def system(name='ellipse'):
    t = np.linspace(0, 2 * np.pi, 64, endpoint=False)
    xy = np.column_stack((8 * np.cos(t), 5 * np.sin(t))) if name == 'ellipse' else np.column_stack(
        (8 * np.sin(t), 5 * np.sin(2 * t)))
    track = np.column_stack((xy, np.full((64, 2), .75)))
    _, _, matrix, normals = tph.calc_splines.calc_splines(np.vstack((xy, xy[0])))
    return track, normals, matrix


@pytest.mark.parametrize('name', ['ellipse', 'crossing'])
def test_exact_64_knot_direct_pinned_equation_oracle(name):
    track, normals, matrix = system(name)
    originals = tuple(a.copy() for a in (track, normals, matrix))
    direct, error = tph.opt_min_curv.opt_min_curv(track, normals, matrix, 1., .30)
    result = adapter.solve_qp(track, normals, matrix)
    np.testing.assert_allclose(result.alpha, direct, rtol=0, atol=1e-8)
    assert result.curvature_error == pytest.approx(error, abs=1e-10)
    assert result.max_violation <= 1e-7
    assert result.linear_curvature_max <= 1 + 1e-7
    assert result.peak_rss_bytes > 0
    assert result.peak_rss_bytes < adapter.SolverPolicy().qp_memory_bytes
    assert result.helper_sha256 == adapter._HASHES['opt_min_curv.py']
    for actual, original in zip((track, normals, matrix), originals):
        np.testing.assert_array_equal(actual, original)


@pytest.fixture(scope='module')
def candidates():
    results = {}
    for name in ('s0_route', 's0_reverse_route', 's0_rotated_route',
                 's2_upper_route', 's2_lower_route', 's3_surfaces_route', 's3_notch_route'):
        r = route(name)
        before = r.payload
        result = adapter.optimize(r)
        assert result.status == 'CANDIDATE', (name, result.status, result.reason)
        assert r.payload == before
        results[name] = result
    Path('/work/a04-candidates.json').write_text(json.dumps({
        name: {'status': value.status, 'fixture_sha256': value.ordered.route.digest,
               'policy': asdict(value.policy), 'length_m': value.ordered.curve.length,
               'iterations': len(value.traces),
               'traces': [asdict(t) for t in value.traces],
               'final_coefficients': value.ordered.curve.coefficients,
               'final_q': value.ordered.q,
               'scope': 'NUMERICAL_CANDIDATE_ONLY; A05/A06 NOT YET ACCEPTED'}
        for name, value in results.items()}, indent=2, allow_nan=False))
    return results


def test_whole_lap_candidates_and_original_intersections_every_qp(candidates):
    for name, result in candidates.items():
        assert len(result.traces) >= result.policy.min_iterations
        assert result.ordered.q == result.traces[-1].q
        assert result.ordered.curve.coefficients == result.traces[-1].shifted_coefficients
        for trace in result.traces:
            assert all(a < b for a, b in zip(trace.q, trace.q[1:]))
            assert {s.occurrence_id for s in trace.samples} == {'o0', 'o1', 'o2', 'o3'}
            for q, (segment, t, inherited) in zip(trace.q, trace.lineage):
                assert inherited == q
                expected = ((1 - t) * trace.source_q[segment]
                            + t * trace.source_q[segment + 1])
                assert inherited == pytest.approx(expected, abs=1e-12)
            rebuilt = OrderedCurve(result.ordered.route, Curve(trace.coefficients,
                                   [(s.occurrence_id, s.surface_id) for s in trace.samples]),
                                   trace.q)
            samples, corridors = adapter._geometry(rebuilt, result.policy)
            assert samples == trace.samples and corridors == trace.corridors
            for sample, corridor in zip(trace.samples, trace.corridors):
                assert sample.occurrence_id in corridor.support_occurrences
                assert sample.q == corridor.q
            factor = min(1., trace.number / result.policy.min_iterations)
            np.testing.assert_allclose(trace.applied_alpha, np.array(trace.qp.alpha) * factor,
                                       rtol=0, atol=1e-15)
            assert trace.qp.max_violation <= result.policy.qp_residual
            assert math.isfinite(trace.qp.objective)
        if name.startswith('s0'):
            sign = -1 if 'reverse' in name else 1
            assert all(math.copysign(1, s.curvature) == sign for s in result.traces[-1].samples)


def test_final_exact_tum_shifted_coefficients_are_authority(candidates):
    for result in candidates.values():
        trace = result.traces[-1]
        xy = np.array([s.xy for s in trace.samples])
        shifted = xy + np.array(trace.applied_alpha)[:, None] * np.array(trace.normals_right)
        x, y, _, _ = tph.calc_splines.calc_splines(
            np.vstack((shifted, shifted[0])), el_lengths=np.diff(trace.q), use_dist_scaling=True)
        expected = np.stack((x, y), axis=1)
        np.testing.assert_array_equal(result.ordered.curve.coefficients, expected)


def test_actual_curvature_energy_diagnostic_does_not_claim_improvement(candidates):
    # A radius-six circle has integral kappa^2 ds = 2*pi/6. Its small cubic
    # interpolation discrepancy is separate from metric kernel tolerances.
    result = candidates['s0_route']
    assert result.traces[0].source_curvature_energy == pytest.approx(math.pi / 3, abs=5e-6)
    assert result.traces[-1].shifted_curvature_energy > result.traces[0].source_curvature_energy
    final = result.ordered.curve
    roots, weights = np.polynomial.legendre.leggauss(96)
    diagnostic = 0.
    for segment in final.segments:
        for t, weight in zip((roots + 1) / 2, weights / 2):
            d, dd = segment.evaluate(float(t), 1), segment.evaluate(float(t), 2)
            diagnostic += weight * (d[0] * dd[1] - d[1] * dd[0]) ** 2 / math.hypot(*d) ** 5
    assert diagnostic == pytest.approx(result.traces[-1].shifted_curvature_energy, abs=1e-10)


def test_asymmetric_notch_uses_its_original_occurrence_after_rotating_normals(candidates):
    result = candidates['s3_notch_route']
    r = result.ordered.route
    notch_q = r.occurrences[0].caps[1][0]
    normals = []
    for trace in result.traces:
        index = min(range(len(trace.samples)), key=lambda i: abs(trace.samples[i].q - notch_q))
        sample, corridor = trace.samples[index], trace.corridors[index]
        assert sample.q == notch_q and sample.occurrence_id == 'o0'
        assert corridor.support_occurrences == ('o0',)
        # Independent 2x2 line/edge intersections with the original left border.
        left_normal = np.array((-sample.tangent[1], sample.tangent[0]))
        hits = []
        for a, b in zip(r.occurrences[0].left, r.occurrences[0].left[1:]):
            matrix = np.column_stack((left_normal, np.array(a) - np.array(b)))
            if abs(np.linalg.det(matrix)) <= 1e-12:
                continue
            offset, edge_t = np.linalg.solve(matrix, np.array(a) - np.array(sample.xy))
            if offset > 0 and 0 <= edge_t <= 1:
                hits.append(offset)
        assert corridor.left == pytest.approx(min(hits) - 1e-9, abs=2e-9)
        normals.append(left_normal)
        assert all(c.surface_id == 'upper-deck' for c in trace.corridors
                   if c.occurrence_id == 'o2')
    assert np.linalg.norm(normals[-1] - normals[0]) > 1e-5


def test_nonuniform_semantic_anchor_and_q_scaled_spline_equivalence():
    raw = route().payload
    raw['occurrences'][0]['caps'].append({'at_m': 1.2345, 'max_speed_mps': 1.7})
    r = validate_route(raw)
    result = adapter.optimize(r, adapter.SolverPolicy(spacing_m=.37))
    assert result.status == 'CANDIDATE', result.reason
    for trace in result.traces:
        assert 1.2345 in trace.q
        assert max(np.diff(trace.q)) > 2 * min(np.diff(trace.q))
        interpolated = Curve.interpolate([s.xy for s in trace.samples], trace.q,
                                         [(s.occurrence_id, s.surface_id) for s in trace.samples])
        np.testing.assert_allclose(interpolated.coefficients, trace.coefficients,
                                   rtol=0, atol=1e-10)


def test_cyclic_occurrence_origin_shift_preserves_topology_and_identical_qp(candidates):
    raw = route().payload
    raw['occurrences'] = raw['occurrences'][2:] + raw['occurrences'][:2]
    raw['transitions'] = raw['transitions'][2:] + raw['transitions'][:2]
    raw['gate_sequence'] = [p['id'] for p in raw['transitions']]
    raw['finish'] = raw['gate_sequence'][-1]
    raw['initialization']['occurrence_id'] = raw['occurrences'][0]['id']
    raw['initialization']['zone'] = raw['transitions'][-1]['support']
    shifted = adapter.optimize(validate_route(raw))
    assert shifted.status == 'CANDIDATE', shifted.reason
    original = candidates['s0_route'].ordered
    assert shifted.ordered.curve.length == pytest.approx(original.curve.length, abs=1e-7)
    # Full remeshing can change discretization. Test exact cyclic algebra on
    # identical knots, rather than conflate q lineage with metric station.
    trace = candidates['s0_route'].traces[0]
    index = next(i for i, sample in enumerate(trace.samples) if sample.occurrence_id == 'o2')
    track = np.array([s.xy + (c.right, c.left)
                      for s, c in zip(trace.samples, trace.corridors)])
    track = np.roll(track, -index, axis=0)
    lengths = np.roll(np.diff(trace.q), -index)
    _, _, matrix, normals = tph.calc_splines.calc_splines(
        np.vstack((track[:, :2], track[0, :2])), el_lengths=lengths, use_dist_scaling=True)
    qp = adapter.solve_qp(track, normals, matrix)
    np.testing.assert_allclose(qp.alpha, np.roll(trace.qp.alpha, -index), rtol=0, atol=1e-8)
    assert qp.curvature_error == pytest.approx(trace.qp.curvature_error, abs=1e-10)
    offset = sum(o.length for o in original.route.occurrences[:2])
    discrepancies = []
    for fraction in np.linspace(0, .99, 40):
        q = fraction * original.period
        original_q = (q + offset) % original.period
        i, t = original._parameter_at_q(original_q)
        j, u = shifted.ordered._parameter_at_q(q)
        discrepancies.append(math.dist(shifted.ordered.curve.segments[j].evaluate(u),
                                       original.curve.segments[i].evaluate(t)))
    Path('/work/a04-origin-shift.json').write_text(json.dumps({
        'route_sha256': shifted.ordered.route.digest,
        'status': shifted.status, 'fixed_qp_offset_tolerance_m': 1e-8,
        'length_difference_m': shifted.ordered.curve.length - original.curve.length,
        'max_inherited_q_position_difference_m': max(discrepancies),
        'interpretation': 'q is lineage, not metric; remeshing is seam-dependent',
        'traces': [asdict(t) for t in shifted.traces],
    }, indent=2, allow_nan=False))


def fake_qp(track, normals, matrix, policy, remaining):
    return adapter.QPResult((0.,) * len(track), 10., 0., 0., .5, 1., 1, .01,
                            adapter._HASHES['opt_min_curv.py'])


def test_nonconvergence_is_bounded_without_candidate(monkeypatch):
    monkeypatch.setattr(adapter, 'solve_qp', fake_qp)
    result = adapter.optimize(route(), adapter.SolverPolicy(max_iterations=3))
    assert result.status == 'NONCONVERGENCE'
    assert result.ordered is None and len(result.traces) == 3


@pytest.mark.parametrize('failure', ['exception', 'nonfinite', 'residual', 'offset'])
def test_solver_failures_never_expose_candidate(monkeypatch, failure):
    def broken(*args):
        if failure == 'exception':
            raise adapter.OptimizationError('injected QP exception', 'SOLVER_FAILURE')
        result = fake_qp(*args)
        if failure == 'nonfinite':
            return replace(result, alpha=(math.nan,) + result.alpha[1:])
        if failure == 'residual':
            return replace(result, max_violation=.01)
        return replace(result, alpha=(100.,) + result.alpha[1:])
    monkeypatch.setattr(adapter, 'solve_qp', broken)
    result = adapter.optimize(route())
    assert result.status != 'CANDIDATE' and result.ordered is None
    assert not result.traces


def test_actual_subprocess_wall_memory_condition_and_infeasibility_limits():
    args = system()
    with pytest.raises(adapter.OptimizationError, match='wall budget'):
        adapter.solve_qp(*args, policy=adapter.SolverPolicy(qp_wall_seconds=1e-6))
    with pytest.raises(adapter.OptimizationError, match='child failed/resource limit'):
        adapter.solve_qp(*args, policy=adapter.SolverPolicy(qp_memory_bytes=16 * 1024 ** 2))
    with pytest.raises(adapter.OptimizationError, match='ill-conditioned'):
        adapter.solve_qp(*args, policy=adapter.SolverPolicy(max_condition=1.))
    narrow = args[0].copy()
    narrow[:, 2:] = .01
    with pytest.raises(adapter.OptimizationError, match='not solvable'):
        adapter.solve_qp(narrow, *args[1:])


def test_whole_lap_point_wall_and_chart_pair_budgets():
    for policy in (adapter.SolverPolicy(max_points=10),
                   adapter.SolverPolicy(wall_seconds=1e-9),
                   adapter.SolverPolicy(chart_pair_budget=1)):
        result = adapter.optimize(route(), policy)
        assert result.status == 'RESOURCE_LIMIT', result.reason
        assert result.ordered is None


def test_tiny_spacing_is_rejected_before_metric_remeshing(monkeypatch):
    def forbidden(*args):
        raise AssertionError('budget preflight must precede resampling')
    monkeypatch.setattr(adapter, 'resample_ordered', forbidden)
    result = adapter.optimize(route(), adapter.SolverPolicy(spacing_m=1e-100))
    assert result.status == 'RESOURCE_LIMIT' and result.ordered is None


def test_actual_dense_fit_has_hard_subprocess_limit():
    r = route()
    ordered = seed_curve(r)
    with pytest.raises(adapter.OptimizationError, match='wall budget'):
        adapter._fit(r, [s.evaluate(0.) for s in ordered.curve.segments], ordered.q,
                     ordered.curve.owners, ordered.curve.policy,
                     adapter.SolverPolicy(qp_wall_seconds=1e-6))


def test_initial_identity_and_invalid_policies():
    initial = seed_curve(route('s0_reverse_route'))
    result = adapter.optimize(route(), initial=initial)
    assert result.status != 'CANDIDATE' and result.ordered is None
    for change in ({'max_iterations': 2}, {'max_points': True}, {'spacing_m': math.nan},
                   {'qp_cpu_seconds': .5}, {'curvature_bound': 0}):
        with pytest.raises(adapter.OptimizationError):
            adapter.SolverPolicy(**change)
