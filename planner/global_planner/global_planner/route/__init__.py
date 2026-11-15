"""
Track geometry for the global planner.

Reads a track, derives its centrelines, gates and portal zones, and builds and samples
closed curves around the lap.

Pipeline:   manifest -> track (centrelines, gates) -> lap (centre curve) -> sampling, portals;
            zones (from a car's reach) -> where both sections around a gate count as road.

Symbols used throughout:
    s:          distance along the current curve, in metres (a point's station).
    q:          lap progress along the section centrelines; fixed while the curve moves.
    t:          position inside one cubic piece, from 0 to 1.
    section:    one stretch of road between two caps.
    portal:     the join of two consecutive sections at their shared cap (the gate).
"""
