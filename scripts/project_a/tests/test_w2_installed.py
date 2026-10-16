"""Execute the numerical W2 core from the actual non-symlink Humble install."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path


def test_installed_w2_pipeline():
    import global_planner.iqp_route_adapter as optimizer
    import global_planner.cyclic_retime as retimer
    import global_planner.route_validate as geometry
    import global_planner.route_validate_dynamics as dynamics
    from global_planner.route_input import load_route

    modules = optimizer, retimer, geometry, dynamics
    identities = {}
    for module in modules:
        path = Path(module.__file__).resolve()
        assert str(path).startswith('/work/install/')
        identities[module.__name__] = {'path': str(path),
                                       'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    route = load_route('/src/planner/global_planner/test/fixtures/project_a/s0_route.json')
    numerical = optimizer.optimize(route)
    assert numerical.status == 'CANDIDATE', numerical.reason
    ordered = numerical.ordered
    body = geometry.Footprint(front_m=.10, rear_m=.10, width_m=.12, margin_m=.01)
    geometric = geometry.validate_geometry(ordered, route, body)
    assert geometric.status == 'PASS', geometric.reason
    limits = retimer.RegionLimits(
        speed_min_mps=.05, speed_max_mps=3., ax_pos_mps2=2., ax_neg_mps2=3.,
        ay_mps2=4., motor_mps2=2.5, drag_over_mass=.02,
        provenance='Explicit synthetic installed-package software test')
    model = retimer.DynamicsModel(
        regions=tuple(retimer.ModelRegion(o.id, o.surface_id, limits)
                      for o in route.occurrences),
        provenance='Synthetic planar model; no physical calibration or vehicle claim')
    timed = retimer.retime(ordered, model)
    assert timed.status == 'CANDIDATE', timed.message
    dynamic = geometry.validate_dynamics(ordered, timed.profile, model, metadata=timed.metadata)
    assert dynamic.status == 'PASS', dynamic
    Path('/work/w2-installed.json').write_text(json.dumps({
        'scope': 'Installed numerical software acceptance; no W3 artifact/export claim',
        'modules': identities, 'route_sha256': route.digest,
        'coefficients': ordered.curve.coefficients, 'q': ordered.q,
        'owners': ordered.curve.owners, 'footprint': asdict(body), 'model': asdict(model),
        'solver_policy': asdict(numerical.policy), 'iterations': len(numerical.traces),
        'numeric_policy': asdict(ordered.curve.policy),
        'geometry_policy': asdict(geometry.GeometryValidationPolicy()),
        'retime_policy': asdict(retimer.RetimePolicy()),
        'dynamics_policy': asdict(dynamics.DynamicsValidationPolicy()),
        'geometry': asdict(geometric), 'retimer': asdict(timed), 'dynamics': asdict(dynamic),
    }, indent=2, allow_nan=False))
