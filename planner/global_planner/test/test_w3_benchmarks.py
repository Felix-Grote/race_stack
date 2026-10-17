"""A08 independent fixture, legacy adaptation, authority and fairness contracts."""
from dataclasses import replace
import importlib.util
import math
import os
from pathlib import Path
import sys

import numpy as np
import pytest

from global_planner import iqp_route_adapter as adapter
from global_planner.route_corridor import portal_crossings, seed_curve
from global_planner.route_reference import Curve

PACKAGE = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get('PROJECT_A_TEST_REPO', str(PACKAGE.parents[1])))
SCRIPTS = ROOT / 'scripts/project_a'
sys.path.insert(0, str(SCRIPTS))
if not (SCRIPTS / 'w3_benchmark_support.py').exists():
    sys.path.insert(0, str(Path(__file__).parent))
from w3_benchmark_support import (  # noqa: E402 - test-local harness outside package
    _bounded_legacy_fit, archive_inventory, checker_shape_control, legacy_candidate,
    scenarios, split_authority, synthetic_model)

FIX = PACKAGE / 'test/fixtures/project_a'
OPT = PACKAGE / 'global_planner/global_racetrajectory_optimization'


@pytest.fixture(scope='module')
def routes():
    """Freeze every synthetic topology before optimization."""
    return scenarios(FIX)[0]


def test_frozen_scenario_topology_and_competition_fixture_precede_solver(routes):
    """Require legal ribbons and directed owned portals before numerical attribution."""
    assert set(routes) == {'S0-circle', 'S0-reverse', 'S0-rotated', 'S0-ellipse',
                           'S1-wall-gaps', 'S2-upper', 'S2-lower', 'S2-upper-cap',
                           'S3-surfaces', 'S3-notch', 'S4-coincident',
                           'S5-planar-connectors', 'S6-240m'}
    for name, route in routes.items():
        ordered = seed_curve(route)
        assert len(portal_crossings(ordered)) == len(route.portals), name
        assert len(ordered.curve.segments) <= 512
    s6 = seed_curve(routes['S6-240m'])
    assert s6.curve.length == pytest.approx(240., abs=1e-4)
    assert all(len(o.polygon) < 512 for o in s6.route.occurrences)
    assert max(np.diff(s6.q)) > 1.1 * min(np.diff(s6.q))


def test_physical_wall_gaps_cannot_enlarge_original_legal_geometry(routes):
    """Keep legal geometry identical when physical wall segments are removed."""
    first, gapped = routes['S0-circle'], routes['S1-wall-gaps']
    assert first.occurrences == gapped.occurrences
    assert first.portals == gapped.portals
    assert first.payload['physical_map']['coverage'] == 'unknown'
    assert gapped.payload['physical_map']['coverage'] == 'partial'
    assert first.digest != gapped.digest
    walls = scenarios(FIX)[1]
    assert len(walls['segments']) < sum(2 * (len(o.seed) - 1) for o in first.occurrences)


def test_coincident_xy_heading_have_distinct_supplied_progress_and_surface(routes):
    """Distinguish repeated projections using supplied progress and owner identity."""
    ordered = seed_curve(routes['S4-coincident'])
    first, repeated = ordered.curve.sample(.5), ordered.curve.sample(ordered.curve.length / 2 + .5)
    np.testing.assert_allclose(first.xy, repeated.xy, rtol=0, atol=1e-8)
    assert first.heading == pytest.approx(repeated.heading, abs=1e-8)
    assert (first.occurrence_id, first.surface_id) == ('o0', 'ground')
    assert (repeated.occurrence_id, repeated.surface_id) == ('repeat-o0', 'repeat-deck')
    with pytest.raises(ValueError):
        ordered.curve.sample(.5, occurrence_id='repeat-o0')


def test_planar_connector_models_are_explicit_and_surface_specific(routes):
    """Require explicit connector labels and matching conservative model regions."""
    route = routes['S5-planar-connectors']
    model = synthetic_model(route)
    assert {s['kind'] for s in route.payload['surfaces']} == {'ramp', 'bridge', 'planar'}
    assert [(r.occurrence_id, r.surface_id) for r in model.regions] == [
        (o.id, o.surface_id) for o in route.occurrences]
    assert model.regions[1].limits.speed_max_mps < model.regions[0].limits.speed_max_mps
    assert 'no physical' in model.provenance.lower()


def test_s6_default_limit_and_predeclared_coarse_mesh_keep_all_other_limits(routes):
    """Preserve explicit default rejection and all nonspacing resource limits."""
    default = adapter.SolverPolicy()
    coarse = replace(default, spacing_m=.5)
    assert coarse.max_points == default.max_points == 512
    assert coarse.qp_cpu_seconds == default.qp_cpu_seconds == 20
    for spacing in (.4, .2, .1):
        result = adapter.optimize(routes['S6-240m'], replace(default, spacing_m=spacing))
        assert result.status == 'RESOURCE_LIMIT'
        assert result.ordered is None and not result.traces
    assert math.ceil(seed_curve(routes['S6-240m']).curve.length / .5) + 16 <= 512


def test_algebraic_authority_subdivision_and_seam_rotation_never_refit(routes, monkeypatch):
    """Preserve captured polynomials while rotating their cyclic representation."""
    original = seed_curve(routes['S0-circle'])
    index = 13
    coefficients = original.curve.coefficients[index:] + original.curve.coefficients[:index]
    q = original.q[index:] + tuple(x + original.period for x in original.q[1:index + 1])

    def forbidden(*args, **kwargs):
        raise AssertionError('captured legacy coefficients must never be refitted')

    monkeypatch.setattr(Curve, 'interpolate', forbidden)
    composition = []
    rebuilt = split_authority(
        original.route, coefficients, q, original.curve.policy, evidence=composition)
    np.testing.assert_allclose(rebuilt.curve.coefficients, original.curve.coefficients,
                               rtol=0, atol=1e-13)
    np.testing.assert_allclose(rebuilt.q, original.q, rtol=0, atol=1e-12)
    assert max(x['coordinate_composition_roundoff_bound_m'] for x in composition) < 1e-11
    for s in (0., .5, 10., original.curve.length - .1):
        np.testing.assert_allclose(rebuilt.curve.sample(s).xy, original.curve.sample(s).xy,
                                   rtol=0, atol=1e-10)


def test_source_authenticated_stock_failure_is_preserved_separately(routes):
    """Retain the actual pinned unmodified SciPy preparation shape failure."""
    ordered, stock = legacy_candidate(routes['S0-circle'], adapter.SolverPolicy(), repaired=False)
    assert ordered is None
    assert stock['status'] == 'STOCK_PREPARATION_FAILURE'
    assert stock['reason'] == 'ValueError: Input vector should be 1-D.'
    assert not stock['repairs']
    assert not stock['qps']


def test_initial_legacy_fit_retains_bounded_resource_failure(routes):
    """Classify an actual first-fit child timeout as a numerical resource rejection."""
    policy = replace(adapter.SolverPolicy(), qp_wall_seconds=.001)
    ordered, result = legacy_candidate(routes['S0-circle'], policy)
    assert ordered is None
    assert result['status'] == 'RESOURCE_LIMIT'
    assert result['iterations'] == 0
    assert not result['qps']
    assert 'legacy spline child wall limit' in result['reason']


def test_interior_owner_subdivision_has_independent_composition_error_bound(routes, monkeypatch):
    """Bound interior algebraic composition independently with exact fractions."""
    original = seed_curve(routes['S0-circle'])
    q = list(original.q)
    for index in (32, 64, 96):
        q[index] += .02

    def forbidden(*args, **kwargs):
        raise AssertionError('algebraic subdivision cannot call interpolate')

    monkeypatch.setattr(Curve, 'interpolate', forbidden)
    composition = []
    rebuilt = split_authority(
        original.route, original.curve.coefficients, q,
        original.curve.policy, evidence=composition)
    assert len(rebuilt.curve.segments) == len(original.curve.segments) + 3
    assert max(x['coordinate_composition_roundoff_bound_m'] for x in composition) < 1e-11
    for progress in np.linspace(0, original.curve.length, 19, endpoint=False):
        np.testing.assert_allclose(rebuilt.curve.sample(float(progress)).xy,
                                   original.curve.sample(float(progress)).xy, rtol=0, atol=1e-10)


def test_checker_fix_preserves_full_xy_arrays_and_records_both_diagnostics():
    """Discriminate the actual truncated checker arrays from the declared repair."""
    report = checker_shape_control(OPT)
    stock, repaired = report['rows']
    assert stock['bound1_shape'] == stock['bound2_shape'] == [4]
    assert repaired['bound1_shape'][1] == repaired['bound2_shape'][1] == 2
    assert min(repaired['bound1_shape'][0], repaired['bound2_shape'][0]) > 2
    assert stock['maximum_distance_m'] > 10
    assert repaired['maximum_distance_m'] < 1
    assert report['source_sha256'] != report['repaired_source_sha256']


def test_archives_remain_software_data_with_original_closing_acceleration():
    """Retain archived format and negative dynamics diagnostics without repairing data."""
    report = archive_inventory(ROOT)
    assert set(report) == {'GLC_smile_small', 'glc_ot_ez', 'hangar_1905_v0'}
    for archive in report.values():
        for profile in archive['profiles'].values():
            assert profile['terminal_duplicate_xy']
            assert profile['max_stored_acceleration_error'] < 1e-12
    assert (report['GLC_smile_small']['profiles']['global_traj_wpnts_iqp']
            ['closing_acceleration_mps2'] < -19)


def test_same_prepared_equations_use_common_track_bounds_and_solver():
    """Require matched-input numerical parity with the unchanged pinned helper."""
    spec = importlib.util.spec_from_file_location('w3_campaign_test', SCRIPTS / 'benchmark_w3.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.parity_control()
    assert result['max_alpha_difference_m'] <= 1e-8
    assert result['qp']['max_violation'] <= adapter.SolverPolicy().qp_residual


@pytest.mark.parametrize('scaling', [True, False])
def test_legacy_fit_containment_preserves_exact_original_helper_arrays(scaling):
    """Require containment to preserve every actual spline-helper output bit."""
    tph = adapter._helpers()
    t = np.linspace(0, 2 * math.pi, 64, endpoint=False)
    xy = np.column_stack((8 * np.cos(t), 5 * np.sin(t)))
    path = np.vstack((xy, xy[0]))
    expected = tph.calc_splines.calc_splines(path, use_dist_scaling=scaling)
    actual = _bounded_legacy_fit(path, scaling, adapter.SolverPolicy(), 20.)
    for left, right in zip(expected, actual):
        np.testing.assert_array_equal(left, right)
    assert actual[-1][0] < adapter.SolverPolicy().qp_memory_bytes
