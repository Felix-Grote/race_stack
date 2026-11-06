"""Deterministic synthetic route-manifest generation for Project A demo.

Geometry is generated from analytic parametric curves, split into four
ordered occurrences (o0..o3) matching the curated synthetic vehicle models
in config/project_a/models. Every manifest is built to satisfy the strict
schema in global_planner.route_input.validate_route: directed shared-endcap
portals, seed-on-cap, ribbon-contained seeds and a closed directed cycle.
No connectivity is inferred from XY proximity anywhere in this module.
"""
import hashlib
import json
import math
from pathlib import Path

HALF_WIDTH = 1.0
PROV = {"author": "project-a-demo", "source": "synthetic-parametric",
        "revision": "1", "approval": "demo-synthetic-not-physical-evidence"}
MAP_HASH = hashlib.sha256(b"project-a-demo-synthetic-map").hexdigest()


def _pt(p):
    return [round(float(p[0]), 9), round(float(p[1]), 9)]


def _chain(points, half=HALF_WIDTH):
    """Return (seed, left, right) chains for one occurrence point list."""
    seed, left, right = [], [], []
    n = len(points)
    for i, (x, y, tx, ty) in enumerate(points):
        norm = math.hypot(tx, ty)
        tx, ty = tx / norm, ty / norm
        lx, ly = -ty, tx  # left of travel (x-forward, y-left, heading CCW)
        seed.append(_pt((x, y)))
        left.append(_pt((x + lx * half, y + ly * half)))
        right.append(_pt((x - lx * half, y - ly * half)))
    return seed, left, right


def _occurrence(oid, surface, points):
    seed, left, right = _chain(points)
    return {"id": oid, "surface_id": surface, "seed": seed, "left": left,
            "right": right, "caps": [{"at_m": 0, "max_speed_mps": 3.0}],
            "provenance": dict(PROV)}


def _support(gate, travel):
    gx = gate[1][0] - gate[0][0]
    gy = gate[1][1] - gate[0][1]
    gl = math.hypot(gx, gy)
    tx, ty = travel[0], travel[1]
    tl = math.hypot(tx, ty)
    tx, ty = tx / tl, ty / tl
    d = 0.8
    return [_pt((gate[0][0] - tx * d, gate[0][1] - ty * d)),
            _pt((gate[1][0] - tx * d, gate[1][1] - ty * d)),
            _pt((gate[1][0] + tx * d, gate[1][1] + ty * d)),
            _pt((gate[0][0] + tx * d, gate[0][1] + ty * d))]


def build_manifest(course_id, route_id, occ_points, surfaces):
    """Assemble a schema-v1 manifest from per-occurrence (x,y,tx,ty) points."""
    occs = [_occurrence(f"o{i}", surfaces[i], pts)
            for i, pts in enumerate(occ_points)]
    transitions = []
    count = len(occs)
    for i in range(count):
        a, b = occs[i], occs[(i + 1) % count]
        gate = [a["right"][-1], a["left"][-1]]
        travel = (b["seed"][1][0] - a["seed"][-2][0],
                  b["seed"][1][1] - a["seed"][-2][1])
        transitions.append({
            "id": f"p{i}", "from": a["id"], "to": b["id"], "gate": gate,
            "support": _support(gate, travel), "before_m": 0.5, "after_m": 0.5,
            "continuity": "shared_endcap", "provenance": dict(PROV)})
    first = occ_points[0][0]
    heading = math.atan2(first[3], first[2])
    # Zone must strictly contain optimized points over the initial seed
    # interval with footprint clearance (route_validate.py), so give it
    # generous metric extent around the start point along travel.
    tn = math.hypot(first[2], first[3])
    tx, ty = first[2] / tn, first[3] / tn
    lx, ly = -ty, tx
    zone = [_pt((first[0] - tx * 1.0 + lx * s * 1.2,
                 first[1] - ty * 1.0 + ly * s * 1.2)) for s in (1, -1)]
    zone += [_pt((first[0] + tx * 2.5 + lx * s * 1.2,
                  first[1] + ty * 2.5 + ly * s * 1.2)) for s in (-1, 1)]
    return {
        "schema_version": 1, "course_id": course_id, "route_id": route_id,
        "frame_id": "map", "units": "m",
        "conventions": "x-forward_y-left_heading-ccw",
        "physical_map": {"sha256": MAP_HASH, "frame_id": "map",
                         "registration": [0, 0, 0], "coverage": "unknown",
                         "provenance": dict(PROV)},
        "provenance": dict(PROV),
        "surfaces": [{"id": s, "kind": ("bridge" if s != "ground" else "planar"),
                      "provenance": dict(PROV)} for s in dict.fromkeys(surfaces)],
        "occurrences": occs, "transitions": transitions,
        "gate_sequence": [t["id"] for t in transitions],
        "finish": transitions[-1]["id"],
        "initialization": {
            "occurrence_id": "o0", "seed_interval_m": [0, 1.0], "zone": zone,
            "heading_interval_rad": [heading - 0.5, heading + 0.5]}}


def _sample(fn, angles):
    return [fn(t) for t in angles]


def ellipse_points(a=8.0, b=5.0, per=14):
    def fn(t):
        return (a * math.cos(t), b * math.sin(t),
                -a * math.sin(t), b * math.cos(t))
    bounds = [i * math.pi / 2 for i in range(5)]
    return [_sample(fn, [bounds[i] + (bounds[i + 1] - bounds[i]) * k / per
                         for k in range(per + 1)]) for i in range(4)]


def lemniscate_points(a=10.0, b=7.5, per=16):
    """Gerono lemniscate: XY self-crossing at origin, crossed by o0 and o2."""
    def fn(t):
        return (a * math.cos(t), b * math.sin(t) * math.cos(t),
                -a * math.sin(t), b * math.cos(2 * t))
    off = 0.6
    bounds = [0.0, math.pi / 2 + off, math.pi, 3 * math.pi / 2 + off,
              2 * math.pi]
    return [_sample(fn, [bounds[i] + (bounds[i + 1] - bounds[i]) * k / per
                         for k in range(per + 1)]) for i in range(4)]


def split_points(variant):
    """Two smooth whole laps sharing o0 (S->E) and o3 (W->S) exactly.

    o1/o2 form the selected branch E->N->W: route A uses a compact northern
    arc (b=5.5), route B a taller/wider northern arc (a=9, b=7.5). Portal
    joints E/N/W/S have quadrant tangents, so shared end caps match exactly.
    These are two manually selected routes; the planner does not choose.
    """
    b_branch, a_branch = (5.5, 8.0) if variant == "A" else (7.5, 8.0)
    arcs = [(8.0, 5.0), (a_branch, b_branch), (a_branch, b_branch),
            (8.0, 5.0)]
    quads = [(3 * math.pi / 2, 2 * math.pi), (0.0, math.pi / 2),
             (math.pi / 2, math.pi), (math.pi, 3 * math.pi / 2)]
    per = 14
    out = []
    for (a, b), (t0, t1) in zip(arcs, quads):
        out.append([(a * math.cos(t), b * math.sin(t),
                     -a * math.sin(t), b * math.cos(t))
                    for t in (t0 + (t1 - t0) * k / per
                              for k in range(per + 1))])
    return out


SCENARIOS = {}


def generate_all(out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    specs = {
        "s0": build_manifest("demo-s0", "s0-ellipse", ellipse_points(),
                             ["ground"] * 4),
        "s1_route_a": build_manifest("demo-s1", "s1-route-a",
                                     split_points("A"), ["ground"] * 4),
        "s1_route_b": build_manifest("demo-s1", "s1-route-b",
                                     split_points("B"), ["ground"] * 4),
        "s2": build_manifest("demo-s2", "s2-lemniscate", lemniscate_points(),
                             ["ground", "ground", "upper-deck", "ground"]),
    }
    paths = {}
    for name, manifest in specs.items():
        path = out / f"{name}.json"
        path.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
        paths[name] = path
    return paths


if __name__ == "__main__":
    import sys
    for name, path in generate_all(sys.argv[1]).items():
        print(name, path)
