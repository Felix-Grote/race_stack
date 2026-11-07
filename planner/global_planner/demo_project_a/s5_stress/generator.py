"""S5 manifest/model generator (deterministic, 4 routes)."""
import hashlib, json, math
from pathlib import Path
from .world import build_lap, build_obstacles, world_digest, PROV

HALF_EPS = 1e-9

def _pt(p):
    return [round(float(p[0]), 9), round(float(p[1]), 9)]

def _chain_pts(pts):
    seed, left, right = [], [], []
    for (x, y, tx, ty, half) in pts:
        n = math.hypot(tx, ty)
        tx, ty = tx / n, ty / n
        lx, ly = -ty, tx
        seed.append(_pt((x, y)))
        left.append(_pt((x + lx * half, y + ly * half)))
        right.append(_pt((x - lx * half, y - ly * half)))
    return seed, left, right

def _support(gate, travel, d=1.1, lat=0.25):
    tx, ty = travel
    tl = math.hypot(tx, ty) or 1.0
    tx, ty = tx / tl, ty / tl
    gx, gy = gate[1][0] - gate[0][0], gate[1][1] - gate[0][1]
    gl = math.hypot(gx, gy) or 1.0
    gx, gy = gx / gl, gy / gl
    g0 = (gate[0][0] - gx * lat, gate[0][1] - gy * lat)
    g1 = (gate[1][0] + gx * lat, gate[1][1] + gy * lat)
    return [_pt((g0[0] - tx * d, g0[1] - ty * d)),
            _pt((g1[0] - tx * d, g1[1] - ty * d)),
            _pt((g1[0] + tx * d, g1[1] + ty * d)),
            _pt((g0[0] + tx * d, g0[1] + ty * d))]

# Caps per occurrence (ground fast 7.0, etc.)
CAPS = {
    "o0": 7.0, "o1": 6.0, "o2": 6.0, "o3": 4.0, "o4": 4.0,
    "o5": 5.0, "o6": 5.0, "o7": None,  # variant dependent
    "o8": 4.0, "o9": None, "o10": 4.5,
    "o11": 5.0, "o12": 3.5, "o13": 4.0, "o14": 3.5, "o15": 5.0,
    "o16a": 4.5, "o16b": 4.5, "o17": 5.0, "o18": 3.5, "o19": 4.0,
    "o20": 3.5, "o21": 5.0, "o22": 5.0,
}
CAPS_A = {"A1": 4.0, "A2": 5.5}
CAPS_B = {"B1": 4.5, "B2": 5.0}

def caps_for(branch_a, branch_b):
    c = dict(CAPS)
    c["o7"] = CAPS_A[branch_a]
    c["o9"] = CAPS_B[branch_b]
    return c

def build_manifest(route_id, branch_a, branch_b):
    occs_in = build_lap(branch_a, branch_b)
    occs = []
    surfaces_seen = []
    caps = caps_for(branch_a, branch_b)
    for (oid, surf, kind, pts) in occs_in:
        seed, left, right = _chain_pts(pts)
        cap = caps[oid]
        occs.append({"id": oid, "surface_id": surf, "seed": seed, "left": left,
                     "right": right, "caps": [{"at_m": 0, "max_speed_mps": cap}],
                     "provenance": dict(PROV)})
        if surf not in surfaces_seen:
            surfaces_seen.append(surf)
    # kind map
    kind_map = {"ground": "planar", "bridge_b_ramp_up": "ramp", "bridge_b_deck": "bridge",
                "bridge_b_ramp_down": "ramp", "bridge_a_ramp_up": "ramp",
                "bridge_a_deck": "bridge", "bridge_a_ramp_down": "ramp"}
    surfaces = [{"id": s, "kind": kind_map.get(s, "planar"), "provenance": dict(PROV)} for s in surfaces_seen]
    count = len(occs)
    # Portal q-windows stay at the 0.5 defaults. Wider windows stack
    # resample anchors into degenerate normal intervals (anchor knots
    # within ~1e-3 of uniform stations collapse the local chart and starve
    # the QP). Support boxes are deepened to gate +/-1.1m along travel
    # (window 0.5 + body half-length 0.3 + margin 0.1 + slack 0.2) and
    # widened 0.25m beyond each gate endpoint along the gate so the swept
    # reference-aligned body stays strictly inside the support mask with
    # margin to spare: the optimized line shifts laterally from the seed
    # and straight support side edges otherwise cut across curved ribbons
    # near hairpin gates. The q-windows are unchanged and the shortest
    # occurrence (1.09m) still exceeds before+after, so no new
    # portal-ownership ambiguity is introduced.
    transitions = []
    for i in range(count):
        a, b = occs[i], occs[(i + 1) % count]
        gate = [a["right"][-1], a["left"][-1]]
        travel = (b["seed"][1][0] - a["seed"][-2][0], b["seed"][1][1] - a["seed"][-2][1])
        transitions.append({"id": f"p{i}", "from": a["id"], "to": b["id"], "gate": gate,
                            "support": _support(gate, travel),
                            "before_m": 0.5, "after_m": 0.5,
                            "continuity": "shared_endcap", "provenance": dict(PROV)})
    first_pts = occs_in[0][3]
    first = first_pts[0]
    heading = math.atan2(first[3], first[2])
    tn = math.hypot(first[2], first[3])
    tx, ty = first[2] / tn, first[3] / tn
    lx, ly = -ty, tx
    zone = [_pt((first[0] - tx * 1.0 + lx * s * 1.2, first[1] - ty * 1.0 + ly * s * 1.2)) for s in (1, -1)]
    zone += [_pt((first[0] + tx * 2.5 + lx * s * 1.2, first[1] + ty * 2.5 + ly * s * 1.2)) for s in (-1, 1)]
    return {"schema_version": 1, "course_id": "demo-s5", "route_id": route_id,
            "frame_id": "map", "units": "m", "conventions": "x-forward_y-left_heading-ccw",
            "physical_map": {"sha256": world_digest(), "frame_id": "map",
                             "registration": [0, 0, 0], "coverage": "unknown",
                             "provenance": dict(PROV)},
            "provenance": dict(PROV), "surfaces": surfaces,
            "occurrences": occs, "transitions": transitions,
            "gate_sequence": [t["id"] for t in transitions],
            "finish": transitions[-1]["id"],
            "initialization": {"occurrence_id": "o0", "seed_interval_m": [0, 1.0], "zone": zone,
                               "heading_interval_rad": [heading - 0.5, heading + 0.5]}}

# Dynamics models (synthetic S5, 7.0 hypothesis, realistic steering/footprint).
# Document shape must match the vehicle-config schema exactly: no per-field
# provenance inside footprint/steering/limits; the S5 hypothesis note lives
# once in model.provenance.
# Erosion width 0.70 = 0.35/side in the S5 solver policy. It must exceed
# body+margin (0.15+0.10 = 0.25/side) by the validator margin (0.10):
# the time-optimal line hugs the eroded wall at the R=1.2-1.7 hairpins,
# and only erosion >= 0.25 + 0.10 keeps the hugging corners' clearance
# provable. Follows the S0-S4 pattern of eroding beyond the bare body.
FOOTPRINT = {"front_m": 0.20, "rear_m": 0.20, "width_m": 0.30, "margin_m": 0.10}
STEERING = {"wheelbase_m": 0.32, "angle_max_rad": 0.45, "rate_max_radps": 3.2}

def limits_for(branch_a, branch_b):
    caps = caps_for(branch_a, branch_b)
    # ay: low-grip o5=2.5, ramps=3.0, else 4.0
    ay_map = {"o5": 2.5, "o12": 3.0, "o14": 3.0, "o18": 3.0, "o20": 3.0}
    regions = []
    # need occ/surface mapping from build_lap
    occs_in = build_lap(branch_a, branch_b)
    for (oid, surf, kind, pts) in occs_in:
        ay = ay_map.get(oid, 4.0)
        regions.append({"occurrence_id": oid, "surface_id": surf,
                        "limits": {"speed_min_mps": 0.05, "speed_max_mps": caps[oid],
                                   "ax_pos_mps2": 2.0, "ax_neg_mps2": 3.0,
                                   "ay_mps2": ay, "motor_mps2": 2.5,
                                   "drag_over_mass": 0.02,
                                   "provenance": ("synthetic-s5-planar-diamond-no-car-calibration; "
                                                  "7.0mps-synthetic-hypothesis")}})
    return regions

def build_model(branch_a, branch_b):
    return {"schema_version": 1,
            "model": {"regions": limits_for(branch_a, branch_b),
                      "provenance": ("Synthetic S5 planar offline; 7.0m/s synthetic hypothesis, "
                                     "conservative 368x296mm-center footprint approx; no physical certification"),
                      "steering": dict(STEERING)},
            "footprint": dict(FOOTPRINT)}

ROUTES = {
    "s5_p1": ("A1", "B1"),
    "s5_p2": ("A2", "B1"),
    "s5_p3": ("A1", "B2"),
    "s5_p4": ("A2", "B2"),
}

def generate_all(out_dir):
    from pathlib import Path
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    paths = {}
    for rid, (ba, bb) in ROUTES.items():
        man = build_manifest(f"demo-s5-{rid}", ba, bb)
        p = out / f"{rid}.json"
        p.write_text(json.dumps(man, indent=1), encoding="utf-8")
        paths[rid] = p
    # world sidecar (obstacles, not holes)
    w = out / "s5_world.json"
    w.write_text(json.dumps({"obstacles": build_obstacles(), "digest": world_digest(),
                             "envelope_target": {"x": [-19, 19], "y": [-9, 9]},
                             "provenance": dict(PROV)}, indent=1), encoding="utf-8")
    paths["world"] = w
    return paths
