"""Bind independent W2 acceptance to a trusted, retained A04 handoff identity."""
from dataclasses import replace
import gzip
import hashlib
import json
import math
from pathlib import Path

import pytest

from global_planner.cyclic_retime import (
    DynamicsModel, ModelRegion, RegionLimits, SpeedKnot, SpeedProfile,
    curve_digest, model_digest, retime)
from global_planner.route_corridor import OrderedCurve
from global_planner.route_input import load_route, validate_route
from global_planner.route_reference import Curve
from global_planner.route_validate import Footprint, validate_geometry
from global_planner.route_validate_dynamics import validate_dynamics
import global_planner.route_validate as geometry_api

FIX = Path(__file__).parent / 'fixtures' / 'project_a'
BODY = Footprint(.1, .1, .12, .01)


def _model(route):
    limits = RegionLimits(.05, 4., 2., 3., 4., 3., .02,
                          'explicit synthetic independent handoff test')
    return DynamicsModel(tuple(ModelRegion(o.id, o.surface_id, limits)
                               for o in route.occurrences),
                         'independent W2 handoff regression; no physical evidence')


def _constant_profile(ordered, model):
    # Chosen strictly feasible constant velocity; independently reconstructed
    # metric/time and model checks remain the validator's responsibility.
    return SpeedProfile(tuple(SpeedKnot(i, 0., .25)
                              for i in range(len(ordered.curve.segments))),
                        curve_digest(ordered), model_digest(model),
                        ordered.curve.length / .5)


@pytest.fixture(scope='module')
def handoff():
    raw = (FIX / 'w2_a04_candidates.json.gz').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == (
        '2a506953026b75fc5be4defb1b018577faa46cebdbdfcd767c0103e733b2279b')
    record = json.loads(gzip.decompress(raw))['candidates']['s0_route']
    route = load_route(FIX / 's0_route.json')
    approved = OrderedCurve(route, Curve(record['coefficients'], record['owners']), record['q'])
    # This independent expected authority is captured once before any downstream
    # mutation. A candidate-provided self-hash is not a replacement for it.
    expected = curve_digest(approved)
    model = _model(route)
    return approved, expected, model, _constant_profile(approved, model)


def test_missing_independent_handoff_cannot_receive_either_pass(handoff):
    approved, _, model, profile = handoff
    geometry = validate_geometry(approved, approved.route, BODY)
    dynamics = validate_dynamics(approved, profile, model)
    assert geometry.status == dynamics.status == 'INCONCLUSIVE'


@pytest.mark.parametrize('expected', ['', 'f' * 63, 'g' * 64, 123, False])
def test_malformed_independent_handoff_fails_closed(expected, handoff):
    approved, _, model, profile = handoff
    geometry = validate_geometry(approved, approved.route, BODY,
                                 expected_curve_digest=expected)
    dynamics = validate_dynamics(approved, profile, model, expected_curve_digest=expected)
    assert geometry.status == dynamics.status == 'FAIL'


def test_mismatched_independent_handoff_fails_despite_valid_self_hashes(handoff):
    approved, expected, model, profile = handoff
    wrong = ('0' if expected[0] != '0' else '1') + expected[1:]
    assert profile.curve_digest == expected
    geometry = validate_geometry(approved, approved.route, BODY, expected_curve_digest=wrong)
    dynamics = validate_dynamics(approved, profile, model, expected_curve_digest=wrong)
    assert geometry.status == dynamics.status == 'FAIL'


def test_valid_independent_handoff_is_shared_by_both_reports_and_wrapper(handoff):
    approved, expected, model, profile = handoff
    geometry = validate_geometry(approved, approved.route, BODY, expected_curve_digest=expected)
    dynamics = validate_dynamics(approved, profile, model, expected_curve_digest=expected)
    forwarded = geometry_api.validate_dynamics(approved, profile, model,
                                               expected_curve_digest=expected)
    assert geometry.status == dynamics.status == forwarded.status == 'PASS'
    assert geometry.curve_digest == dynamics.curve_digest == profile.curve_digest == expected
    assert forwarded == dynamics


def test_rehashed_monotone_q_warp_cannot_move_an_original_cap(handoff):
    base, _, _, _ = handoff
    raw = base.route.payload
    raw['occurrences'][0]['caps'] = [
        {'at_m': 0., 'max_speed_mps': 4.},
        {'at_m': 3., 'max_speed_mps': .1},
        {'at_m': 3.01, 'max_speed_mps': 4.}]
    route = validate_route(raw)
    approved = OrderedCurve(route, base.curve, base.q)
    expected = curve_digest(approved)
    q = tuple(v + 1.5 * math.sin(math.pi * (v - 1.) / 7.) ** 2
              if 1. < v < 8. else v for v in approved.q)
    altered = OrderedCurve(route, approved.curve, q)
    model = _model(route)
    model = replace(model, regions=tuple(replace(
        r, limits=replace(r.limits, ax_pos_mps2=1000., ax_neg_mps2=1000.,
                          ay_mps2=1000., motor_mps2=1000., drag_over_mass=0.))
        for r in model.regions))
    timed = retime(altered, model)
    assert timed.status == 'CANDIDATE', timed.message
    assert altered.curve == approved.curve and timed.profile.curve_digest != expected
    geometry = validate_geometry(altered, route, BODY, expected_curve_digest=expected)
    dynamics = validate_dynamics(altered, timed.profile, model,
                                 metadata=timed.metadata, expected_curve_digest=expected)
    assert geometry.status == dynamics.status == 'FAIL'
    assert 'authority' in geometry.reason.lower() and 'authority' in dynamics.reason.lower()


def test_dynamics_of_a_different_curve_cannot_complete_geometry_handoff(handoff):
    approved, expected, model, _ = handoff
    # A regular monotone alternate correspondence retains exact occurrence
    # anchors and the complete same planar geometry. The full authority differs.
    q = tuple(v + .05 * math.sin(math.pi * (v - 1.) / 7.) ** 2
              if 1. < v < 8. else v for v in approved.q)
    other = OrderedCurve(approved.route, approved.curve, q)
    profile = _constant_profile(other, model)
    geometry = validate_geometry(approved, approved.route, BODY, expected_curve_digest=expected)
    dynamics = validate_dynamics(other, profile, model, expected_curve_digest=expected)
    assert geometry.status == 'PASS' and dynamics.status == 'FAIL'
    assert geometry.curve_digest == expected != profile.curve_digest
    assert not (geometry.status == dynamics.status == 'PASS' and
                geometry.curve_digest == dynamics.curve_digest == expected)
