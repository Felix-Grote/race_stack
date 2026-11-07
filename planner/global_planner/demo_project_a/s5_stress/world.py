"""S5 Grand Challenge world (deterministic, 24 occs, ~180m, 38x18 target)."""
import math, hashlib, json

ENVELOPE_X = (-19.0, 19.0)
ENVELOPE_Y = (-9.0, 9.0)
TARGET_W, TARGET_H = 38.0, 18.0
MAX_W, MAX_H = 40.0, 20.0

# Lap origin (finish straight). Set so the A1 dip clears o0's start cap
# while the closure still dives underneath the chicane band.
START_X, START_Y = -11.0, -4.5
# East hairpin radius (o3/o4): keeps walls inside x<=19.
R_EAST = 1.8
# West closure hairpin radius (o22): inner wall radius stays >1.0.
R_WEST = 1.7
# o22 westbound altitude: matches the shallow dive-turn exit (pt4.y - 1.2).
RET_Y = -9.1
# Bridge-B deck altitude: the o5 northern loop passes underneath it.
Y_DECK_B = 5.8
# Northern-loop hairpin (o5 top): legs at +/-R_LOOP around x=0.
R_LOOP = 1.2
LOOP_TOP_Y = 6.6
# Sidecar-only deck heights (m, NOT schema): low-deck hypothesis giving
# 10%-grade straight ramps without breaking the envelope. No physical
# clearance certification is claimed; the planner is planar.
DECK_H_A = 0.35
DECK_H_B = 0.4

PROV = {"author": "project-a-s5", "source": "synthetic-s5-world-v1",
        "revision": "1", "approval": "demo-synthetic-not-physical-evidence"}

def _half_at(u, h0, h1, hm=None):
    if hm is None:
        hm = 0.5 * (h0 + h1)
    a = (1 - u) ** 2; b = 2 * (1 - u) * u; c = u ** 2
    return a * h0 + b * hm + c * h1

def straight_points(p0, heading_rad, length, n, half0, half1, half_mid=None):
    tx, ty = math.cos(heading_rad), math.sin(heading_rad)
    pts = []
    for i in range(n + 1):
        s = length * i / n
        x = p0[0] + tx * s
        y = p0[1] + ty * s
        half = _half_at(i / n, half0, half1, half_mid)
        pts.append((x, y, tx, ty, half))
    return pts

def arc_points(center, radius, a0, a1, ccw, n, half0, half1, half_mid=None):
    pts = []
    if ccw:
        while a1 <= a0:
            a1 += 2 * math.pi
    else:
        while a1 >= a0:
            a1 -= 2 * math.pi
    for i in range(n + 1):
        t = a0 + (a1 - a0) * i / n
        x = center[0] + radius * math.cos(t)
        y = center[1] + radius * math.sin(t)
        if ccw:
            tx, ty = -math.sin(t), math.cos(t)
        else:
            tx, ty = math.sin(t), -math.cos(t)
        half = _half_at(i / n, half0, half1, half_mid)
        pts.append((x, y, tx, ty, half))
    return pts

def bezier_points(p0, t0, p3, t3, d1, d2, n, half0, half1, lat1=0.0, lat2=0.0, half_mid=None):
    n0 = math.hypot(*t0); n1 = math.hypot(*t3)
    t0 = (t0[0] / n0, t0[1] / n0); t3 = (t3[0] / n1, t3[1] / n1)
    n0v = (-t0[1], t0[0]); n3v = (-t3[1], t3[0])
    p1 = (p0[0] + t0[0] * d1 + n0v[0] * lat1, p0[1] + t0[1] * d1 + n0v[1] * lat1)
    p2 = (p3[0] - t3[0] * d2 + n3v[0] * lat2, p3[1] - t3[1] * d2 + n3v[1] * lat2)
    pts = []
    for i in range(n + 1):
        u = i / n
        a = (1 - u) ** 3; b = 3 * (1 - u) ** 2 * u; c = 3 * (1 - u) * u ** 2; d = u ** 3
        x = a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0]
        y = a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]
        dx = 3 * ((1 - u) ** 2 * (p1[0] - p0[0]) + 2 * (1 - u) * u * (p2[0] - p1[0]) + u ** 2 * (p3[0] - p2[0]))
        dy = 3 * ((1 - u) ** 2 * (p1[1] - p0[1]) + 2 * (1 - u) * u * (p2[1] - p1[1]) + u ** 2 * (p3[1] - p2[1]))
        nl = math.hypot(dx, dy)
        if nl < 1e-12:
            raise ValueError("degenerate bezier")
        pts.append((x, y, dx / nl, dy / nl, _half_at(i / n, half0, half1, half_mid)))
    return pts

def build_obstacles():
    # Hand-placed deterministic sidecar islands; the diag script verifies each
    # corner lies outside every legal corridor with a positive clearance gap.
    # 1. rectangular barrier between Split-A branches (A1 sags south of it).
    # Surveyed slot: A1's north wall stays below the bottom edge, A2's
    # south wall stays above the top edge (both with documented margin).
    # Placed west of the A2 climb knee: the climb's outer wall passes just
    # east of the island's NE corner, so the island sits fully west of it.
    obs1 = [[-12.5, -1.5], [-11.9, -1.5], [-11.9, -1.1], [-12.5, -1.1]]
    # 2. concave asymmetric polygon east of B1 (B1 threads tight, B2 swings west).
    obs2 = [[-16.0, 2.7], [-15.2, 2.7], [-15.2, 4.4], [-15.6, 4.4], [-15.6, 3.7], [-16.0, 3.7]]
    # 3. narrow elongated chicane island south of the o1 leg.
    obs3 = [[8.3, -6.1], [10.7, -5.9], [10.7, -5.5], [8.3, -5.7]]
    # 4. cluster near split-A entry/o6 (two small rects).
    obs4a = [[-9.3, -1.05], [-8.5, -1.05], [-8.5, -0.45], [-9.3, -0.45]]
    obs4b = [[-7.8, -1.0], [-7.0, -1.0], [-7.0, -0.4], [-7.8, -0.4]]
    return {"central_barrier": obs1, "concave_detour": obs2,
            "chicane_island": obs3, "split_cluster_a": obs4a, "split_cluster_b": obs4b}

def _concat(*segs):
    """Join primitive point lists into one occurrence, dropping duplicate joints."""
    out = []
    for s in segs:
        if out:
            s = s[1:]
        out.extend(s)
    return out


def _walls_simple(pts):
    """Local ribbon-simplicity check mirroring the route validator semantics."""
    left = []
    right = []
    for (x, y, tx, ty, half) in pts:
        nl = math.hypot(tx, ty) or 1.0
        lx, ly = -ty / nl, tx / nl
        left.append((x + lx * half, y + ly * half))
        right.append((x - lx * half, y - ly * half))
    poly = list(map(tuple, right)) + list(map(tuple, left[::-1]))
    es = [(poly[i], poly[(i + 1) % len(poly)]) for i in range(len(poly))]
    for i, (a, b) in enumerate(es):
        for c, d in es[i + 2:]:
            if i == 0 and (c, d) == es[-1]:
                continue
            # Proper intersection of open segments (shared endpoints allowed).
            def _cross(o, p, q):
                return (p[0] - o[0]) * (q[1] - o[1]) - (p[1] - o[1]) * (q[0] - o[0])
            d1, d2 = _cross(a, b, c), _cross(a, b, d)
            d3, d4 = _cross(c, d, a), _cross(c, d, b)
            if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)):
                return False
    return True


def _smooth_pieces(occs_in, passes=6):
    """Cyclic Laplacian smoothing of the full-lap centerline, joints pinned.

    Coarse bezier sampling and independently chosen piece end-tangents
    leave 5-14 degree polyline corners, concentrated at portal joints.
    The optimizer refits seeds with a periodic cubic spline, which
    overshoots at such corners (portal anchor knots sit ~0.05-0.1m apart,
    so even a 10-degree corner spikes curvature past the chart-fold limit
    in narrow corridors). Per-occurrence smoothing cannot round a corner
    owned by two sides, and pinning joints while smoothing neighbors only
    sharpens the corner at the joint, so this smooths the concatenated
    cyclic centerline with every joint free to move (shared joints are
    single entries, hence C0 is automatic; each joint stays the midpoint
    of its own rebuilt end cap by construction). Only the seam closure
    pair is constrained (kept equal to its smoothed midpoint each pass).
    Point counts are unchanged and straight sections stay exactly straight.
    Tangents are recomputed by central differences per occurrence, then
    shared joint tangents are averaged cyclically so portal caps stay
    near-identical. Each pass count is accepted only if every ribbon
    stays simple; otherwise fewer passes are used. Deterministic.
    """
    # Concatenate cyclically, merging shared joints (kept once, carrying the
    # incoming occurrence's half-width, matching the identical-cap
    # construction). Gaps above 1e-6, or a lap that does not close, are a
    # builder bug, not smoothing input.
    C, halves, joints = [], [], []
    for i, (oid, surf, kind, pts) in enumerate(occs_in):
        for k, p in enumerate(pts):
            if k == 0 and C:
                d = math.hypot(p[0] - C[-1][0], p[1] - C[-1][1])
                if d > 1e-6:
                    raise ValueError(f'portal joint gap at {oid}: {d}')
                joints.append(len(C) - 1)
                continue
            C.append([p[0], p[1]])
            halves.append(p[4])
    d = math.hypot(C[-1][0] - C[0][0], C[-1][1] - C[0][1])
    if d > 1e-6:
        raise ValueError(f'lap does not close: {d}')
    npts = len(C)
    # joints[k] (k<n-1) is shared between occ k and occ k+1; the seam joint
    # is the closure pair (C[-1], C[0]). No absolute pinning: every joint
    # moves with its neighbors. Only the closure pair is constrained, to
    # their smoothed midpoint, so the lap stays closed.
    tried = None
    for attempt in (passes, 4, 2, 0):
        P = [list(c) for c in C]
        for _ in range(attempt):
            Q = [None] * npts
            for i in range(npts):
                a = P[i - 1]
                b = P[i]
                c = P[(i + 1) % npts]
                Q[i] = [0.25 * a[0] + 0.5 * b[0] + 0.25 * c[0],
                        0.25 * a[1] + 0.5 * b[1] + 0.25 * c[1]]
            mx = (Q[0][0] + Q[-1][0]) / 2
            my = (Q[0][1] + Q[-1][1]) / 2
            Q[0] = [mx, my]
            Q[-1] = [mx, my]
            P = Q
        # Split per occurrence: occ i spans joint[i-1]..joint[i] inclusive
        # (occ 0 starts at the seam C[0]; occ n-1 ends at C[-1]; the seam
        # pair stays equal because both entries are pinned to equal anchors).
        after = joints + [npts - 1]
        ok = True
        cand = {}
        nocc = len(occs_in)
        for i, (oid, surf, kind, _) in enumerate(occs_in):
            start = after[i - 1] if i > 0 else 0
            end = after[i]
            span = list(range(start, end + 1))
            xy = [tuple(P[k]) for k in span]
            n = len(xy)
            sm = []
            for k in range(n):
                a = xy[max(0, k - 1)]
                b = xy[min(n - 1, k + 1)]
                tx, ty = b[0] - a[0], b[1] - a[1]
                nl = math.hypot(tx, ty) or 1.0
                sm.append((xy[k][0], xy[k][1], tx / nl, ty / nl, halves[span[k]]))
            if attempt > 0 and not _walls_simple(sm):
                ok = False
                break
            cand[oid] = sm
        if ok or attempt == 0:
            tried = cand
            break
    assert tried is not None
    out = [(oid, surf, kind, tried[oid]) for (oid, surf, kind, _) in occs_in]
    # Unify shared joint tangents cyclically (identical caps portal-wise).
    for i in range(len(out)):
        a = out[i][3]
        b = out[(i + 1) % len(out)][3]
        tx = a[-1][2] + b[0][2]
        ty = a[-1][3] + b[0][3]
        nl = math.hypot(tx, ty) or 1.0
        tx, ty = tx / nl, ty / nl
        a[-1] = (a[-1][0], a[-1][1], tx, ty, a[-1][4])
        b[0] = (b[0][0], b[0][1], tx, ty, b[0][4])
    return out


def build_lap(branch_a="A1", branch_b="B1"):
    occs = []
    # o0 finish straight: narrow 0.55 at the seam (demanding cyclic
    # transition), widening to 0.8 before the chicane.
    o0 = straight_points((START_X, START_Y), 0.0, 17.5, 35, 0.55, 0.8)
    occs.append(("o0", "ground", "planar", o0))
    p1 = (o0[-1][0], o0[-1][1])
    o1 = bezier_points((p1[0], p1[1]), (1, 0), (p1[0] + 5, p1[1] + 2.0), (1, 0), 2.5, 2.5, 14, 0.8, 0.8)
    occs.append(("o1", "ground", "planar", o1))
    p2 = (o1[-1][0], o1[-1][1])
    o2 = bezier_points((p2[0], p2[1]), (1, 0), (p2[0] + 5, p2[1] - 2.0), (1, 0), 2.5, 2.5, 14, 0.8, 0.6)
    occs.append(("o2", "ground", "planar", o2))
    sx, sy = o2[-1][0], o2[-1][1]
    cx, cy = sx, sy + R_EAST
    o3 = arc_points((cx, cy), R_EAST, -math.pi / 2, 0.0, True, 14, 0.6, 0.6)
    occs.append(("o3", "ground", "planar", o3))
    o4 = arc_points((cx, cy), R_EAST, 0.0, math.pi / 2, True, 14, 0.6, 0.6)
    occs.append(("o4", "ground", "planar", o4))
    p5 = (o4[-1][0], o4[-1][1])
    # Pin the west end so downstream blocks (o6..o21) stay fixed across edits.
    # Paperclip infield loop: run west low, hairpin H1 up, run east mid,
    # hairpin H2 up (passing under bridge-B deck: two transverse XY
    # crossings, distinct surfaces), run west high, plunge south, join o6.
    # Entry and exit are vertically stacked with clearance; no leg crosses
    # another leg's level inside its span (single occurrence, no ambiguity).
    e5a = bezier_points(p5, (-1, 0), (p5[0] - 3.5, p5[1] + 0.35), (-1, 0),
                        1.2, 1.2, 8, 0.6, 0.85)
    L1 = straight_points(((p5[0] - 3.5, p5[1] + 0.35)), math.pi, 8.0, 8,
                         0.85, 0.8)
    # H1: west -> north -> east via two r=1.5 quarter arcs plus a straight
    # riser (keeps the upper legs at bridge-deck crossing altitude while the
    # low leg threads between the o1 corridor below and o17 above).
    h1a = arc_points((5.0, 0.95), 1.5, 3 * math.pi / 2, math.pi, False, 8,
                     0.8, 0.8)
    h1r = straight_points((3.5, 0.95), math.pi / 2, 1.45, 3, 0.8, 0.8)
    h1b = arc_points((5.0, 2.4), 1.5, math.pi, math.pi / 2, False, 8,
                     0.8, 0.75)
    L2 = straight_points(((5.0, 3.9)), 0.0, 1.0, 2, 0.75, 0.7)
    # H2: east -> west 180° via east, r=1.8, passing under bridge-B deck.
    H2 = arc_points((6.0, 5.7), 1.8, -math.pi / 2, math.pi / 2, True, 16,
                    0.7, 0.7)
    L3 = straight_points(((6.0, 7.5)), math.pi, 7.0, 7, 0.7, 0.75)
    # Rounded west->south turn (arc, constant curvature, clean miter).
    turn5 = arc_points((-1.0, 6.3), 1.2, math.pi / 2, math.pi, True, 8,
                       0.75, 0.75)
    plunge = straight_points(((-2.2, 6.3)), -math.pi / 2, 7.5, 15,
                             0.75, 0.7)
    # Rounded south->west turn, then a straight stub to the portal.
    turn5b = arc_points((-3.4, -1.2), 1.2, 0.0, -math.pi / 2, False, 8,
                        0.7, 0.7)
    stub = bezier_points(((-3.4, -2.4)), (-1, 0), ((p5[0] - 22, -2.0)),
                         (-1, 0), 0.8, 0.8, 7, 0.7, 0.75)
    o5 = _concat(e5a, L1, h1a, h1r, h1b, L2, H2, L3, turn5, plunge, turn5b,
                 stub)
    occs.append(("o5", "ground", "planar", o5))
    p6 = (o5[-1][0], o5[-1][1])
    o6 = straight_points((p6[0], p6[1]), math.pi, 4.0, 8, 0.75, 0.65)
    occs.append(("o6", "ground", "planar", o6))
    p7 = (o6[-1][0], o6[-1][1])
    # Split A: every joint keeps exact west tangents (no lateral control
    # offsets at boundaries), so portal caps match and walls stay simple.
    # A1 dips south/narrow, A2 swings north/wide, leaving a surveyed slot
    # for the central barrier island. A1 rejoins lower (p8 depends on branch;
    # o8 chains from it, so downstream blocks adapt automatically).
    if branch_a == "A1":
        p8 = (p7[0] - 5, p7[1] + 1.0)
        # Interior joints share exact tangents (C1); only the two portal
        # boundary tangents are constrained to west for cap matching.
        # Dip, then a flat west run SOUTH of the barrier island, then rise
        # only once fully west of it: no wall ever enters the barrier band.
        e7a = bezier_points(p7, (-1, 0), (p7[0] - 1.4, p7[1] - 0.35),
                            (-1, -0.2), 0.55, 0.55, 6, 0.65, 0.60)
        m7a = bezier_points((p7[0] - 1.4, p7[1] - 0.35), (-1, -0.2),
                            (p7[0] - 3.1, p7[1] - 0.32), (-1, 0),
                            0.7, 0.7, 10, 0.60, 0.60)
        # Crux rise: exact arc/straight/arc (R=0.95, 56deg) from the flat
        # run back to the shared rejoin. The flat-run height is chosen so
        # the straight meets both arcs tangentially (exact C1, no kink).
        _F = (p7[0] - 3.1, p7[1] - 0.32)
        _R, _th = 0.95, math.radians(56)
        _C1 = (_F[0], _F[1] + _R)
        _arc1 = arc_points(_C1, _R, -math.pi / 2, -math.pi / 2 - _th,
                           False, 8, 0.60, 0.55)
        _C2 = (p8[0], p8[1] - _R)
        _arc2 = arc_points(_C2, _R, math.pi / 2 - _th, math.pi / 2,
                           True, 8, 0.55, 0.60)
        _E1, _S2 = _arc1[-1], _arc2[0]
        _dx, _dy = _S2[0] - _E1[0], _S2[1] - _E1[1]
        _L = math.hypot(_dx, _dy)
        _st = straight_points(((_E1[0]), (_E1[1])), math.atan2(_dy, _dx),
                                _L, 6, 0.55, 0.55)
        m7b = _concat(_arc1, _st, _arc2)
        o7 = _concat(e7a, m7a, m7b)
    else:
        p8 = (p7[0] - 5, p7[1] + 1.0)
        # Two long C1 pieces bowing north of the barrier island: an early
        # climb started well east of the island, then a high crest settling
        # to the shared rejoin. k~0.25 throughout; wider and decisively
        # longer than A1: the speed-vs-distance tradeoff.
        # Climb crux: easement arc (R=1.6, 30deg) + exact main arc (R=0.9,
        # 28deg) + straight + exact soften arc (R=1.5), then descent to the
        # shared rejoin. The portal arrives straight (k=0); jumping straight
        # onto R=0.85 spikes the refit spline past the chart-fold limit, so
        # the easement splits the curvature step 0 -> 0.625 -> 1.11.
        # Constant-curvature joints throughout, no bezier overshoot.
        _eR0, _eth0 = 1.6, math.radians(30)
        _D0 = (p7[0], p7[1] + _eR0)
        _ease = arc_points(_D0, _eR0, -math.pi / 2, -math.pi / 2 - _eth0,
                           False, 6, 0.65, 0.66)
        _E = _ease[-1]
        _eTx, _eTy = _E[2], _E[3]
        _R1, _th1 = 1.0, math.radians(28)
        _rn = (_eTy, -_eTx)  # right normal of travel: turn center side
        _D1 = (_E[0] + _R1 * _rn[0], _E[1] + _R1 * _rn[1])
        _b0 = math.atan2(_E[1] - _D1[1], _E[0] - _D1[0])
        _climb = arc_points(_D1, _R1, _b0, _b0 - _th1,
                            False, 6, 0.66, 0.68)
        _A = _climb[-1]
        _aTx, _aTy = _A[2], _A[3]
        # Short run: the crest stays low (~0.0) so the descent chord to the
        # shared rejoin is shallow; a high crest forces a severe S (left
        # 51deg then right 44deg) whose walls overlap at the inflection.
        _L1 = 0.9
        _B = (_A[0] + _L1 * _aTx, _A[1] + _L1 * _aTy)
        _run = straight_points((_B[0] - _L1 * _aTx, _B[1] - _L1 * _aTy),
                               math.atan2(_aTy, _aTx), _L1, 10, 0.68, 0.70)
        _R2, _th2 = 1.5, math.radians(63)
        _blx, _bly = -_aTy, _aTx
        _D2 = (_B[0] + _R2 * _blx, _B[1] + _R2 * _bly)
        _b0 = math.atan2(_B[1] - _D2[1], _B[0] - _D2[0])
        _soft = arc_points(_D2, _R2, _b0, _b0 + _th2, True, 6, 0.70,
                           0.62)
        _C = _soft[-1]
        # Descent: three C1-matched beziers from the crest to the shared
        # rejoin (B2's proven recipe: intermediate joints on the chord with
        # shared tangents, control distances a third of each sub-chord).
        # The descent sits west of the island in open ground; the earlier
        # arc/straight/arc left tangent kinks at both straight joints and
        # the refit spline whipped past the chart-fold limit there.
        _cTx, _cTy = _C[2], _C[3]
        _dx8, _dy8 = p8[0] - _C[0], p8[1] - _C[1]
        _Lc = math.hypot(_dx8, _dy8)
        _ux, _uy = _dx8 / _Lc, _dy8 / _Lc
        # Single cubic for the whole descent: one C1 piece, no interior
        # joints, curvature distributed naturally. The three-piece version
        # concentrated the chord-to-west turn inside _d3 and kinked its
        # arrival; the arc/straight/arc version left tangent kinks at both
        # straight joints that whipped the refit spline.
        _desc = bezier_points((_C[0], _C[1]), (_cTx, _cTy), p8, (-1, 0),
                             _Lc / 3, _Lc / 3, 24, 0.62, 0.60)
        o7 = _concat(_ease, _climb, _run, _soft, _desc)
    occs.append(("o7", "ground", "planar", o7))
    cx8, cy8 = p8[0], p8[1] + 2.5
    o8 = arc_points((cx8, cy8), 2.5, -math.pi / 2, math.pi, False, 14, 0.6, 0.675)
    occs.append(("o8", "ground", "planar", o8))
    pe = (o8[-1][0], o8[-1][1])
    # Split B: B1 is the tight straight (narrow mid); B2 detours west/wide.
    # Stubs hold exact north tangents at both portals for B2.
    if branch_b == "B1":
        o9 = straight_points((pe[0], pe[1]), math.pi / 2, 3.0, 6, 0.675, 0.7,
                             half_mid=0.5)
    else:
        # Subtle west bulge: per-piece heading steps stay under ~5 degrees so
        # bezier mid-piece overshoot cannot tighten the tip below the wall
        # offset. Control distances equal a third of each chord. The tip
        # runs at 0.62 (portal caps unchanged): the optimizer otherwise
        # cuts the wide 0.75 bulge and the refit overshoots past the
        # curvature limit downstream.
        e9a = bezier_points(pe, (0, 1), (pe[0] - 0.06, pe[1] + 0.75),
                            (-0.09, 0.996), 0.25, 0.25, 4, 0.675, 0.62)
        qe = (pe[0] - 0.06, pe[1] + 0.75)
        m9a = bezier_points(qe, (-0.09, 0.996),
                            (pe[0] - 0.19, pe[1] + 1.5), (-0.14, 0.99),
                            0.25, 0.25, 8, 0.62, 0.62)
        qm = (pe[0] - 0.19, pe[1] + 1.5)
        # Single piece from the bulge to the exit portal: no interior joint
        # kink near the rejoin, control distances match a third of the chord.
        m9b = bezier_points(qm, (-0.14, 0.99), (pe[0], pe[1] + 3.0), (0, 1),
                            0.5, 0.5, 12, 0.62, 0.7)
        o9 = _concat(e9a, m9a, m9b)
    occs.append(("o9", "ground", "planar", o9))
    q9 = (o9[-1][0], o9[-1][1])
    # Sweeping hop up to the bridge-B deck altitude, ending heading east.
    o10 = bezier_points(q9, (0, 1), (q9[0] + 2.5, Y_DECK_B), (1, 0),
                        1.1, 1.0, 14, 0.7, 0.7)
    occs.append(("o10", "ground", "planar", o10))
    pt = (o10[-1][0], o10[-1][1])
    bB_app = straight_points((pt[0], pt[1]), 0.0, 3.0, 6, 0.7, 0.7)
    occs.append(("o11", "ground", "planar", bB_app))
    p = (bB_app[-1][0], bB_app[-1][1])
    bB_rup = straight_points((p[0], p[1]), 0.0, 4.0, 8, 0.7, 0.6)
    occs.append(("o12", "bridge_b_ramp_up", "ramp", bB_rup))
    p = (bB_rup[-1][0], bB_rup[-1][1])
    bB_deck = straight_points((p[0], p[1]), 0.0, 17.0, 34, 0.6, 0.6)
    occs.append(("o13", "bridge_b_deck", "bridge", bB_deck))
    p = (bB_deck[-1][0], bB_deck[-1][1])
    bB_rdn = straight_points((p[0], p[1]), 0.0, 4.0, 8, 0.6, 0.7)
    occs.append(("o14", "bridge_b_ramp_down", "ramp", bB_rdn))
    p = (bB_rdn[-1][0], bB_rdn[-1][1])
    bB_exit = straight_points((p[0], p[1]), 0.0, 1.5, 3, 0.7, 0.7)
    occs.append(("o15", "ground", "planar", bB_exit))
    pt2 = (bB_exit[-1][0], bB_exit[-1][1])
    # Dive from the bridge-B exit altitude toward the bridge-A line. A single
    # occurrence cannot host the east-entry hook (its seed would recross its
    # own entry cap), so the dive is two occurrences: a constant-curvature
    # 90-degree arc (no bezier whip, no S, x-monotone) followed by a nearly
    # straight south setter onto the bridge-A line.
    o16a = arc_points((pt2[0], pt2[1] - 1.4), 1.4, math.pi / 2, 0.0,
                      False, 20, 0.7, 0.7)
    qt = (pt2[0] + 1.4, pt2[1] - 1.4)
    # The diagonal is two x- and y-monotone gentle pieces (no S-fold, no
    # whip, no hook, no cap return). The interior joint shares its exact
    # tangent; the exit leans slightly southwest so the end does not whip,
    # leaving a mild documented kink into the straight bridge approach.
    # First control distance matches the arc's end curvature (C2 joint, so
    # the inner wall continues without a miter spike). The diagonal runs
    # at 0.62 mid-piece (portal caps unchanged) so the optimizer cannot
    # cut inside the bend and refit past the curvature limit.
    mid = (pt2[0] + 0.8, pt2[1] - 2.55)
    o16b1 = bezier_points(qt, (0, -1), mid, (-0.7, -0.7), 0.6, 0.55, 8,
                          0.7, 0.62)
    west = (pt2[0] - 0.9, pt2[1] - 2.9)
    o16b2 = bezier_points(mid, (-0.7, -0.7), west, (-1, 0), 0.7, 0.7, 8,
                          0.62, 0.7)
    o16b = _concat(o16b1, o16b2)
    occs.append(("o16a", "ground", "planar", o16a))
    occs.append(("o16b", "ground", "planar", o16b))
    pt3 = (o16b[-1][0], o16b[-1][1])
    # Rejoin bend west->south as a true constant-curvature arc (R=1.6, inner
    # wall radius 1.0 at 0.6 half width: no inner-wall fold), followed by the
    # straight bridge-A approach run.
    bA_arc = arc_points((pt3[0], pt3[1] - 1.6), 1.6, math.pi / 2, math.pi,
                        True, 10, 0.7, 0.6)
    bA_run = straight_points((pt3[0] - 1.6, pt3[1] - 1.6), -math.pi / 2, 0.4,
                             4, 0.6, 0.7)
    o17 = _concat(bA_arc, bA_run)
    occs.append(("o17", "ground", "planar", o17))
    p = (o17[-1][0], o17[-1][1])
    # Bridge A crosses the o1/o2 chicane band on its deck (XY overlap with
    # ground occurrences, distinct surfaces, no portal between them).
    bA_rup = straight_points((p[0], p[1]), -math.pi / 2, 3.0, 6, 0.7, 0.6)
    occs.append(("o18", "bridge_a_ramp_up", "ramp", bA_rup))
    p = (bA_rup[-1][0], bA_rup[-1][1])
    bA_deck = straight_points((p[0], p[1]), -math.pi / 2, 3.0, 6, 0.6, 0.6)
    occs.append(("o19", "bridge_a_deck", "bridge", bA_deck))
    p = (bA_deck[-1][0], bA_deck[-1][1])
    bA_rdn = straight_points((p[0], p[1]), -math.pi / 2, 1.8, 4, 0.6, 0.7)
    occs.append(("o20", "bridge_a_ramp_down", "ramp", bA_rdn))
    p = (bA_rdn[-1][0], bA_rdn[-1][1])
    bA_exit = straight_points((p[0], p[1]), -math.pi / 2, 1.0, 4, 0.7, 0.7)
    occs.append(("o21", "ground", "planar", bA_exit))
    pt4 = (bA_exit[-1][0], bA_exit[-1][1])
    # o22 closing leg: short dive off the exit cap line, turn west, join
    # the westbound, 90-degree sweeper, single-direction rise to the seam.
    # The ramp-down/exit are shortened (deck untouched, crossings kept) so
    # the dive stays inside the 40x20m envelope: with pt4 higher, a shallow
    # R=1.2 turn reaches the westbound directly. The old deep dive looped
    # 1.3m below the exit and broke the southern envelope edge.
    jx, jy = pt4[0] - 4.5, RET_Y
    # Dive turn south->west as a true constant-radius clockwise arc
    # (R=1.2): no interior curvature jump, so no wall kink.
    f_turn = arc_points((pt4[0] - 1.2, pt4[1]), 1.2, 0.0, -math.pi / 2,
                        False, 10, 0.65, 0.65)
    # Flat west run from the turn onto the westbound (C1: west tangents).
    _fE = (pt4[0] - 1.2, pt4[1] - 1.2)
    _fL = _fE[0] - jx
    f2 = straight_points((_fE[0], _fE[1]), math.pi, _fL, 8, 0.65, 0.55)
    o22a = _concat(f_turn, f2)
    hx0 = jx - 21.0  # sweeper entry x
    o22b = straight_points(((jx, jy)), math.pi, 21.0, 21, 0.55, 0.55)
    hcx, hcy = hx0, jy + R_WEST  # turn center (hx0, -7.3)
    # Closing turn: a 90-degree sweeper (bottom to west side) followed by a
    # long single-direction rise to the seam. The full 180-degree hairpin
    # cannot host a fold-free return in the available run, so the severe
    # direction reversal lives in o4/H1/H2 instead.
    o22c = arc_points((hcx, hcy), R_WEST, -math.pi / 2, -math.pi,
                      False, 10, 0.55, 0.55)
    hwx, hwy = hx0 - R_WEST, jy + R_WEST  # side exit, heading north
    # Riser to the seam in three gentle single-turn pieces (30deg each):
    # the single cubic bowed 0.6m off-chord and forced the optimizer onto
    # the margin. Exact-tangent joints, modest widths, E arrival at seam.
    _M1 = (hwx + 0.6, hwy + 1.04)
    _M2 = (-13.0, -5.3)
    _p1 = bezier_points((hwx, hwy), (0, 1), _M1, (0.5, 0.866),
                        0.6, 0.6, 6, 0.55, 0.62)
    _p2 = bezier_points(_M1, (0.5, 0.866), _M2, (0.866, 0.5),
                        0.55, 0.55, 8, 0.62, 0.68)
    _p3 = bezier_points(_M2, (0.866, 0.5), (START_X, START_Y), (1, 0),
                        0.8, 0.8, 10, 0.68, 0.55)
    o22d = _concat(_p1, _p2, _p3)
    o22 = _concat(o22a, o22b, o22c, o22d)
    occs.append(("o22", "ground", "planar", o22))
    return _smooth_pieces(occs)


def world_digest():
    obs = build_obstacles()
    # deterministic digest of obstacle sidecar + lap params
    payload = json.dumps({"obstacles": obs, "revision": 1}, sort_keys=True).encode()
    return hashlib.sha256(payload).hexdigest()
