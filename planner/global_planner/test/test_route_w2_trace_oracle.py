"""Independent A04 history control using periodic second-derivative equations.

No optimizer, corridor, reference interpolation or hash helper is called. The
received approved route records anchor the seed. Numerical fit comparisons are
regression controls; the production validators still certify the actual curve.
"""
from bisect import bisect_right
import math

import numpy as np


def _periodic_coefficients(points, q):
    """Solve directly for knot second derivatives, then form local cubics."""
    points = np.asarray(points, dtype=float)
    intervals = np.diff(q)
    count = len(points)
    matrix = np.zeros((count, count))
    rhs = np.zeros((count, 2))
    for index in range(count):
        before, after = (index - 1) % count, (index + 1) % count
        matrix[index, before] += intervals[before]
        matrix[index, index] += 2 * (intervals[before] + intervals[index])
        matrix[index, after] += intervals[index]
        rhs[index] = 6 * ((points[after] - points[index]) / intervals[index]
                          - (points[index] - points[before]) / intervals[before])
    second = np.linalg.solve(matrix, rhs)
    coefficients = []
    for index in range(count):
        after = (index + 1) % count
        square = intervals[index] ** 2
        first = points[after] - points[index] - square * (
            2 * second[index] + second[after]) / 6
        coefficients.append(np.stack((points[index], first, square * second[index] / 2,
                                      square * (second[after] - second[index]) / 6), axis=1))
    return np.asarray(coefficients)


def _evaluate(coefficients, parameter, derivative=False):
    value = np.asarray(coefficients)
    if derivative:
        return value[:, 1] + 2 * parameter * value[:, 2] + 3 * parameter ** 2 * value[:, 3]
    return value[:, 0] + parameter * (
        value[:, 1] + parameter * (value[:, 2] + parameter * value[:, 3]))


def _trusted_seed(route):
    points, progress, ends = [], [], [0.]
    for occurrence in route.occurrences:
        local = 0.
        for first, second in zip(occurrence.seed, occurrence.seed[1:]):
            points.append(first)
            progress.append(ends[-1] + local)
            local += math.hypot(second[0] - first[0], second[1] - first[1])
        ends.append(ends[-1] + occurrence.length)
    progress.append(ends[-1])
    anchors = set(ends[:-1])
    for index, occurrence in enumerate(route.occurrences):
        anchors.update(ends[index] + cap[0] for cap in occurrence.caps)
        anchors.add(ends[index + 1] - route.portals[index].before)
        anchors.add(ends[(index + 1) % len(route.occurrences)] + route.portals[index].after)
    return _periodic_coefficients(points, progress), progress, ends, anchors


def _record_error(stats, field, actual, expected, tolerance):
    error = float(np.max(np.abs(np.asarray(actual) - np.asarray(expected))))
    assert math.isfinite(error) and error < tolerance, (field, error)
    stats[field] = max(stats[field], error)


def verify_trace_lineage(route, traces, final_coefficients, final_q, policy):
    """Replay complete A04 history from approved seed without candidate hashes.

    Inputs are validated route records, dataclass-asdict traces and solver policy,
    and the actual final coefficient/q authority. Return numerical audit maxima.
    """
    source, source_q, ends, anchors = _trusted_seed(route)
    stats = dict(iterations=0, max_source_point_error_m=0.,
                 max_reference_coefficient_error_m=0., max_normal_error=0.,
                 max_shifted_coefficient_error_m=0.)
    assert traces, 'missing A04 history'
    for iteration, trace in enumerate(traces, 1):
        assert trace['number'] == iteration
        assert tuple(source_q) == tuple(trace['source_q']), 'source q history changed'
        lineage, progress = trace['lineage'], trace['q']
        assert progress[0] == 0 and progress[-1] == ends[-1]
        assert all(first < second for first, second in zip(progress, progress[1:]))
        assert len(lineage) == len(progress) - 1 == len(trace['samples'])
        assert all(anchor in progress for anchor in anchors), 'semantic anchor lost'
        points = []
        for index, (segment, parameter, inherited) in enumerate(lineage):
            assert type(segment) is int and 0 <= segment < len(source)
            assert 0 <= parameter <= 1 and inherited == progress[index]
            assert source_q[segment] <= inherited < source_q[segment + 1]
            if inherited in anchors:
                # Known semantic anchors use their direct inverse parameter;
                # their forward floating roundtrip need not reproduce q exactly.
                assert parameter == ((inherited - source_q[segment])
                                     / (source_q[segment + 1] - source_q[segment]))
            else:
                expected = ((1 - parameter) * source_q[segment]
                            + parameter * source_q[segment + 1])
                expected = max(source_q[segment], min(expected, math.nextafter(
                    source_q[segment + 1], source_q[segment])))
                assert inherited == expected, 'lineage q formula changed'
            point = _evaluate(source[segment], parameter)
            points.append(point)
            sample = trace['samples'][index]
            owner = route.occurrences[min(bisect_right(ends, inherited) - 1, len(ends) - 2)]
            assert (sample['occurrence_id'], sample['surface_id']) == (owner.id, owner.surface_id)
            assert sample['q'] == inherited
            _record_error(stats, 'max_source_point_error_m', point, sample['xy'], 1e-10)
        reference = np.asarray(trace['coefficients'])
        _record_error(stats, 'max_reference_coefficient_error_m', reference,
                      _periodic_coefficients(points, progress), 1e-10)
        factor = min(1., iteration / policy['min_iterations'])
        assert (len(trace['normals_right']) == len(trace['qp']['alpha'])
                == len(trace['applied_alpha']) == len(trace['corridors']) == len(points))
        moved = []
        for index, (normal, alpha, applied, corridor) in enumerate(zip(
                trace['normals_right'], trace['qp']['alpha'], trace['applied_alpha'],
                trace['corridors'])):
            derivative = _evaluate(reference[index], 0., derivative=True)
            expected = np.array((derivative[1], -derivative[0])) / math.hypot(*derivative)
            _record_error(stats, 'max_normal_error', normal, expected, 1e-12)
            assert applied == alpha * factor, 'damped step changed'
            assert (-corridor['upper'] + policy['vehicle_width_m'] / 2
                    - policy['offset_tolerance'] <= applied)
            assert (applied <= -corridor['lower'] - policy['vehicle_width_m'] / 2
                    + policy['offset_tolerance'])
            moved.append(reference[index, :, 0] + applied * np.asarray(normal))
        source, source_q = np.asarray(trace['shifted_coefficients']), progress
        _record_error(stats, 'max_shifted_coefficient_error_m', source,
                      _periodic_coefficients(moved, progress), 1e-10)
        stats['iterations'] = iteration
    assert tuple(source_q) == tuple(final_q), 'final q differs from checked history'
    assert np.array_equal(source, final_coefficients), 'final coefficients differ from history'
    return stats
