"""Query a checked installed reference in a new, source-free interpreter."""
from dataclasses import asdict
import json
import math
import sys

from global_planner.route_artifact import load_reference
from global_planner.route_compile import load_policy


def main():
    """Replay shuffled metric, seam, owner and multiple-lap queries after one load."""
    artifact, expected_h, policy = sys.argv[1:]
    _, context, _ = load_policy(policy)
    reference = load_reference(artifact, expected_H=expected_h, validation_context=context)
    length = reference.length
    stations = [2 * length + .137, -.137, 0., length, .137, length / 2,
                math.nextafter(length, 0.), math.nextafter(0., 1.)]
    stations.extend(reference.ordered.curve.station(i, 0.)
                    for i in reversed(range(len(reference.ordered.curve.segments))))
    states = [reference.sample(station) for station in stations]
    assert all(state.H == expected_h and 0 <= state.s < length for state in states)
    assert states[2] == states[3]
    assert abs(states[0].s - .137) < reference.policies.numeric.station_abs
    assert abs(states[1].s - (length - .137)) < reference.policies.numeric.station_abs
    owners = {}
    for i, (occurrence, surface) in enumerate(reference.ordered.curve.owners):
        if occurrence not in owners:
            station = reference.ordered.curve.station(i, .5)
            state = reference.sample(station, occurrence_id=occurrence)
            assert state.occurrence_id == occurrence and state.surface_id == surface
            owners[occurrence] = asdict(state)
    expected_owners = {o.id for o in reference.ordered.route.occurrences}
    assert set(owners) == expected_owners
    print(json.dumps({'status': 'PASS', 'H': expected_h, 'length_m': length,
                      'lap_time_s': reference.lap_time_s, 'samples': len(states),
                      'owner_samples': owners}, allow_nan=False))


if __name__ == '__main__':
    main()
