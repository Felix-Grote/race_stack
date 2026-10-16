"""Independent full-driver regression probe; source/fixtures remain untouched."""
from fractions import Fraction
import json
import math
from pathlib import Path

import numpy as np

from global_planner.route_corridor import OrderedCurve, _sample_at_q, seed_curve
from global_planner.route_input import load_route, validate_route
from global_planner.route_reference import Curve
import global_planner.route_validate as validator


def test_hidden_original_notch_rejects_legal_knot_bodies():
    original = load_route('/src/planner/global_planner/test/fixtures/project_a/s3_notch_route.json')
    seed = seed_curve(original)
    notch_q = original.occurrences[0].caps[1][0]
    notch = _sample_at_q(seed, notch_q)
    normal = np.array((-notch.tangent[1], notch.tangent[0]))
    payload = original.payload
    left = payload['occurrences'][0]['left']
    nearest = min(range(len(left)), key=lambda i: math.dist(left[i], notch.xy))
    left[nearest] = (np.array(notch.xy) + .02 * normal).tolist()
    route = validate_route(payload)
    seed = seed_curve(route)
    selected, within = [], {}
    for i, owner in enumerate(seed.curve.owners):
        k = within.get(owner[0], 0)
        if k % 3 == 0:
            selected.append(i)
        within[owner[0]] = k + 1
    q = tuple(seed.q[i] for i in selected) + (seed.period,)
    # Keep true portal roots away from rounded interpolation joins; their
    # declared progress brackets permit this small forward displacement.
    xy = tuple(_sample_at_q(seed, (seed.q[i] + .05) % seed.period).xy for i in selected)
    owners = tuple(seed.curve.owners[i] for i in selected)
    candidate = OrderedCurve(route, Curve.interpolate(xy, q, owners), q)
    body = validator.Footprint(.10, .10, .12, .01)
    polygons = [tuple(validator._point(p) for p in o.polygon) for o in route.occurrences]
    unions = [validator._union_polygon(route.occurrences[i],
              route.occurrences[(i + 1) % len(route.occurrences)])
              for i in range(len(route.occurrences))]
    ends = [0.]
    for occurrence in route.occurrences:
        ends.append(ends[-1] + occurrence.length)
    all_knot_bodies_legal = True
    for i, (segment, owner) in enumerate(zip(candidate.curve.segments, owners)):
        coefficient = validator._coefficient_records(segment.coefficients)
        bounds = validator.interval_bounds(coefficient)
        rectangle, _ = validator._rectangle(coefficient, Fraction(0), body, bounds)
        index = next(j for j, occurrence in enumerate(route.occurrences) if occurrence.id == owner[0])
        domains = [polygons[index]]
        for j, portal in enumerate(route.portals):
            delta = validator._portal_delta(Fraction(q[i]), Fraction(ends[j + 1]),
                                            Fraction(ends[-1]))
            if -Fraction(portal.before) <= delta <= Fraction(portal.after):
                support = tuple(validator._point(p) for p in portal.support)
                if validator._rectangle_clearance2(rectangle, support) is not None:
                    domains.append(unions[j])
        if not any(validator._rectangle_clearance2(rectangle, domain) is not None
                   for domain in domains):
            all_knot_bodies_legal = False
            break
    report = validator.validate_geometry(candidate, route, body)
    Path('/work/hidden-notch-generated-route.json').write_bytes(route.encoded)
    Path('/work/hidden-notch-candidate.json').write_text(json.dumps({
        'coefficients': candidate.curve.coefficients, 'q': candidate.q,
        'owners': candidate.curve.owners,
        'footprint': {'front_m': .10, 'rear_m': .10, 'width_m': .12, 'margin_m': .01},
        'policy': {'numeric_policy': 'unchanged NumericPolicy defaults', 'max_curvature': 1.},
        'scope': 'synthetic negative geometry candidate; no optimized-reference claim',
    }, indent=2, allow_nan=False))
    Path('/work/hidden-notch-probe.json').write_text(json.dumps({
        'original_fixture_sha256': original.digest, 'generated_fixture_sha256': route.digest,
        'candidate_knot_count': len(selected), 'original_notch_q': notch_q,
        'seed_phase_q_m': .05,
        'notch_floor_m': .02, 'all_knot_bodies_legal': all_knot_bodies_legal,
        'status': report.status, 'reason': report.reason,
        'offending_interval': report.offending_interval,
        'certified_leaves_before_rejection': len(report.intervals),
    }, indent=2))
    assert all_knot_bodies_legal
    assert report.status == 'FAIL', report.reason
    assert 'rectangle' in report.reason or 'footprint' in report.reason
