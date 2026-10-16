#!/usr/bin/env python3
"""Challenge saved A08 authority through existing independent W2 oracles."""
import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys
import traceback

import numpy as np


def encode(value):
    """Preserve numeric JSON representations during exact repeated-authority checks."""
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def energy96(coefficients):
    """Integrate actual geometric curvature energy without helper surrogate values."""
    roots, weights = np.polynomial.legendre.leggauss(96)
    t, weights = (roots + 1) / 2, weights / 2
    values = []
    for c in coefficients:
        c = np.asarray(c)
        first = c[:, 1, None] + 2 * c[:, 2, None] * t + 3 * c[:, 3, None] * t * t
        second = 2 * c[:, 2, None] + 6 * c[:, 3, None] * t
        numerator = first[0] * second[1] - first[1] * second[0]
        values.append(float(weights @ (numerator * numerator /
                                        np.sum(first * first, axis=0) ** 2.5)))
    return math.fsum(values)


def signed_area(coefficients):
    """Integrate signed enclosed area directly on the saved actual polynomials."""
    values = []
    for x, y in coefficients:
        dx = [i * value for i, value in enumerate(x)][1:]
        dy = [i * value for i, value in enumerate(y)][1:]
        integrand = np.polynomial.polynomial.polysub(
            np.polynomial.polynomial.polymul(x, dy),
            np.polynomial.polynomial.polymul(y, dx))
        values.append(math.fsum(value / (i + 1) for i, value in enumerate(integrand)) / 2)
    return math.fsum(values)


def main():
    """Replay exact recorded histories and preserve every independent diagnostic failure."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', required=True)
    parser.add_argument('--run', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    repo, run = Path(args.repo), Path(args.run)
    sys.path.insert(0, str(repo / 'planner/global_planner'))
    sys.path.insert(0, str(repo / 'planner/global_planner/test'))
    from global_planner.route_input import load_route
    from test_route_ellipse_dynamics import _gaussian_arc
    from test_route_w2_trace_oracle import verify_trace_lineage
    manifest = json.loads((run / 'manifest.json').read_bytes())
    summary = json.loads((run / 'summary.json').read_bytes())
    jobs = {job['id']: job for job in manifest['jobs']}
    output = {'scope': 'independent saved-output diagnostics; no replacement certificate',
              'trace_fit_tolerance_m': 1e-10, 'metric_time_tolerance': 1e-8,
              'oracle_source_sha256': {name: hashlib.sha256((
                  repo / 'planner/global_planner/test' / name).read_bytes()).hexdigest()
                  for name in ('test_route_ellipse_dynamics.py', 'test_route_w2_trace_oracle.py')},
              'attempts': {}, 'repeat_authority': [], 'scenario_controls': {}}
    accepted = {}
    for row in summary['attempts']:
        if row['status'] != 'PASS':
            continue
        data = json.loads(gzip.decompress((run / row['result_file']).read_bytes()))
        accepted[row['id']] = data
        job = jobs[row['id']]
        if encode(job['solver_policy']) != encode(data['solver_policy']):
            raise AssertionError('reported solver policy differs from predeclared job')
        route = load_route(run / 'inputs' / (row['scenario'] + '.json'))
        if route.digest != row['route_sha256']:
            raise AssertionError('saved route identity differs from frozen inputs')
        audit = {}
        if row['variant'] == 'new':
            try:
                audit['independent_a04_history'] = {'status': 'PASS', **verify_trace_lineage(
                    route, data['traces'], data['coefficients'], data['q'],
                    data['solver_policy'])}
            except Exception as exc:
                audit['independent_a04_history'] = {
                    'status': 'FAIL', 'reason': repr(exc), 'traceback': traceback.format_exc()}
        else:
            legacy = data['legacy']
            try:
                assert legacy['lineage'][0]['source_q'] == legacy['preparation_q']
                previous = None
                for transition in legacy['lineage']:
                    source = transition['source_q']
                    if previous is not None:
                        assert source == previous, 'legacy source q history changed'
                    expected = [(1 - t) * source[i] + t * source[i + 1]
                                for i, t in zip(transition['segment'], transition['t'])]
                    expected.append(expected[0] + sum(o.length for o in route.occurrences))
                    assert expected == transition['inherited_q'], 'legacy q formula changed'
                    previous = transition['inherited_q']
                assert legacy['actual_final_q'] == legacy['lineage'][-1]['source_q']
                audit['legacy_index_t_lineage'] = {'status': 'PASS',
                    'raw_geometry_authorization': legacy['raw_legacy_geometry_authorization'],
                    'composition_roundoff_bound_m': legacy['composition_roundoff_bound_m']}
            except Exception as exc:
                audit['legacy_index_t_lineage'] = {'status': 'FAIL', 'reason': repr(exc)}
        try:
            coefficients = data['coefficients']
            arcs = [_gaussian_arc(c) for c in coefficients]
            length = math.fsum(arcs)
            knots = data['retime']['profile']['knots']
            distances, times = [], []
            for index, first in enumerate(knots):
                following = knots[(index + 1) % len(knots)]
                end = following['t'] if following['segment'] == first['segment'] else 1.
                distance = _gaussian_arc(coefficients[first['segment']], first['t'], end)
                edge = data['dynamics']['edges'][index]
                assert edge['distance_lower_m'] <= distance <= edge['distance_upper_m'], (
                    'distance enclosure', index, distance, edge)
                distances.append(distance)
                times.append(2 * distance / (math.sqrt(first['u']) + math.sqrt(following['u'])))
            time_s = math.fsum(times)
            assert (data['dynamics']['lap_time_lower_s'] <= time_s <=
                    data['dynamics']['lap_time_upper_s']), 'model time enclosure'
            errors = {'length_m': length - data['length_m'],
                      'profile_distance_sum_m': math.fsum(distances) - length,
                      'model_time_s': time_s - data['lap_time_s'],
                      'energy48_vs96_per_m': energy96(coefficients) -
                                             data['curvature_energy_final_per_m']}
            assert max(abs(x) for x in errors.values()) < 1e-8, errors
            audit['independent_gauss96_metric_time_energy'] = {'status': 'PASS',
                                                              'errors': errors}
        except Exception as exc:
            audit['independent_gauss96_metric_time_energy'] = {'status': 'FAIL',
                                                              'reason': repr(exc)}
        output['attempts'][row['id']] = audit
        if row['repeat'] == 2:
            first = accepted.get(row['id'].replace('-r2', '-r1'))
            fields = ('coefficients', 'owners', 'q', 'model', 'footprint',
                      'expected_curve_digest', 'H', 'geometry', 'dynamics')
            matches = first is not None and all(encode(first[k]) == encode(data[k])
                                                for k in fields)
            output['repeat_authority'].append({'id': row['id'], 'status':
                                               'PASS' if matches else 'FAIL'})
    for variant in ('new', 'repaired'):
        circle = accepted.get(f'S0-circle-{variant}-0.4-r1')
        reverse = accepted.get(f'S0-reverse-{variant}-0.4-r1')
        rotated = accepted.get(f'S0-rotated-{variant}-0.4-r1')
        gap = accepted.get(f'S1-wall-gaps-{variant}-0.4-r1')
        upper = accepted.get(f'S2-upper-{variant}-0.4-r1')
        capped = accepted.get(f'S2-upper-cap-{variant}-0.4-r1')
        if circle is not None and reverse is not None and rotated is not None:
            values = (circle, reverse, rotated)
            times = [value['lap_time_s'] for value in values]
            energies = [energy96(value['coefficients']) for value in values]
            areas = [signed_area(value['coefficients']) for value in values]
            passed = (max(times) - min(times) < 1e-8 and
                      max(energies) - min(energies) < 1e-8 and
                      areas[0] > 0 > areas[1] and areas[2] > 0 and
                      max(abs(area) for area in areas) -
                      min(abs(area) for area in areas) < 1e-8)
            output['scenario_controls']['S0-' + variant] = {
                'status': 'PASS' if passed else 'FAIL',
                'circle_reverse_rotated_model_time_s': times,
                'circle_reverse_rotated_energy_per_m': energies,
                'circle_reverse_rotated_signed_area_m2': areas}
        if circle is not None and gap is not None:
            same = all(encode(circle[k]) == encode(gap[k]) for k in ('coefficients', 'q', 'owners'))
            coverage = gap['required_physical_coverage']['status']
            output['scenario_controls']['S1-' + variant] = {
                'status': 'PASS' if same and coverage == 'INCONCLUSIVE' else 'FAIL',
                'same_legal_curve_authority': same, 'required_physical_coverage': coverage}
        if upper is not None and capped is not None:
            same = all(encode(upper[k]) == encode(capped[k]) for k in ('coefficients', 'q', 'owners'))
            output['scenario_controls']['S2-' + variant] = {
                'status': 'PASS' if same and capped['lap_time_s'] > upper['lap_time_s'] else 'FAIL',
                'same_geometry': same, 'base_time_s': upper['lap_time_s'],
                'capped_time_s': capped['lap_time_s']}
    Path(args.output).write_bytes(encode(output))
    statuses = [item['status'] for attempt in output['attempts'].values()
                for item in attempt.values()]
    statuses.extend(item['status'] for item in output['repeat_authority'])
    statuses.extend(item['status'] for item in output['scenario_controls'].values())
    print(json.dumps({'independent_checks': len(statuses),
                      'passes': statuses.count('PASS'), 'failures': statuses.count('FAIL')}))
    return int('FAIL' in statuses)


if __name__ == '__main__':
    raise SystemExit(main())
