"""Check new pure geometry modules from the actual non-symlink ROS install."""
from pathlib import Path

import numpy as np


def test_installed_geometry_modules():
    import global_planner.route_input as ri
    import global_planner.route_reference as rr
    for module in (ri, rr):
        assert str(Path(module.__file__).resolve()).startswith('/work/install/')
    r = ri.load_route('/src/planner/global_planner/test/fixtures/project_a/s0_route.json')
    points = [p for o in r.occurrences for p in o.seed[:-1]]
    c = rr.Curve.interpolate(points)
    assert abs(c.length - 12 * np.pi) < 1e-6
    assert c.locate(c.length) == (0, 0.)
    assert np.isfinite(c.sample(-.1).curvature)
