"""Scratch-only current-behavior audit; no production/test-tree mutation."""
import gzip
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

import global_planner.cyclic_retime as timing
from global_planner.route_corridor import OrderedCurve
from global_planner.route_input import load_route
from global_planner.route_reference import Curve
from global_planner.route_validate_dynamics import validate_dynamics


@pytest.mark.parametrize('kind', ['all_zero', 'isolated_zero', 'positive_below_floor'])
def test_current_zero_motion_behavior(kind, monkeypatch):
    fixture = Path('/src/planner/global_planner/test/fixtures/project_a')
    record = json.loads(gzip.decompress((fixture / 'w2_a04_candidates.json.gz').read_bytes()))
    value = record['candidates']['s0_route']
    route = load_route(fixture / 's0_route.json')
    ordered = OrderedCurve(route, Curve(value['coefficients'], value['owners']), value['q'])
    limits = timing.RegionLimits(0., 4., 2., 3., 4., 2.5, .02, 'synthetic audit')
    model = timing.DynamicsModel(tuple(timing.ModelRegion(o.id, o.surface_id, limits)
                                      for o in route.occurrences), 'synthetic zero-floor audit')

    def injected(objective, **kwargs):
        values = np.full(len(objective), 1e-12)
        if kind == 'all_zero':
            values[:] = 0.
        elif kind == 'isolated_zero':
            values[0] = 0.
        else:
            values[:] = 1e-14
        return SimpleNamespace(success=True, x=values, nit=0)

    monkeypatch.setattr(timing, 'linprog', injected)
    result = timing.retime(ordered, model)
    checked = None if result.profile is None else validate_dynamics(ordered, result.profile, model)
    Path('/work/' + kind + '.json').write_text(json.dumps({
        'case': kind, 'retimer_status': result.status, 'retimer_message': result.message,
        'minimum_u': None if result.profile is None else min(k.u for k in result.profile.knots),
        'independent_status': None if checked is None else checked.status,
        'independent_reason': None if checked is None else checked.reason,
        'declared_floor_mps': timing.RetimePolicy().moving_speed_mps,
    }, indent=2))
    if kind == 'all_zero':
        assert result.status == 'INCONCLUSIVE' and result.profile is None
    else:
        assert result.status == 'CANDIDATE' and checked.status == 'FAIL'
