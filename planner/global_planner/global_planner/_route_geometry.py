"""Private planar predicates for annotated ribbons; no topology inference."""
import math

EPS = 1e-9  # metres; inputs restricted to |coordinate| <= 1e5 m


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1])


def cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1]


def distance(a, b):
    return math.hypot(*sub(a, b))


def on_segment(p, a, b):
    v, w = sub(b, a), sub(p, a)
    length = math.hypot(*v)
    return (length > EPS and abs(cross(v, w)) <= EPS * length
            and -EPS * length <= dot(w, v) <= dot(v, v) + EPS * length)


def segments_touch(a, b, c, d):
    v, w = sub(b, a), sub(d, c)
    den = cross(v, w)
    if abs(den) <= EPS * (math.hypot(*v) + math.hypot(*w)):
        return any((on_segment(a, c, d), on_segment(b, c, d),
                    on_segment(c, a, b), on_segment(d, a, b)))
    t, u = cross(sub(c, a), w) / den, cross(sub(c, a), v) / den
    return -EPS <= t <= 1 + EPS and -EPS <= u <= 1 + EPS


def edges(poly):
    return zip(poly, poly[1:] + poly[:1])


def inside(p, poly, boundary=True):
    if any(on_segment(p, a, b) for a, b in edges(poly)):
        return boundary
    hit = False
    for a, b in edges(poly):
        if (a[1] > p[1]) != (b[1] > p[1]):
            x = a[0] + (p[1] - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            if x > p[0]:
                hit = not hit
    return hit


def signed_area_twice(poly):
    """Translation-stable signed area, avoiding cancellation of global XY terms."""
    origin = poly[0]
    return math.fsum(cross(sub(a, origin), sub(b, origin)) for a, b in edges(poly))


def simple_polygon(poly):
    if len(poly) < 3:
        return False
    es = list(edges(poly))
    if any(distance(a, b) <= EPS for a, b in es):
        return False
    if abs(signed_area_twice(poly)) <= EPS:
        return False
    for i, (a, b) in enumerate(es):
        # Adjacent collinear reversals/overlap are invalid too.
        c = es[(i + 1) % len(es)][1]
        if abs(cross(sub(b, a), sub(c, b))) <= EPS * distance(a, b):
            if dot(sub(b, a), sub(c, b)) <= 0:
                return False
        for j in range(i + 1, len(es)):
            if j == i + 1 or (i == 0 and j == len(es) - 1):
                continue
            if segments_touch(a, b, *es[j]):
                return False
    return True


def line_intervals(p, n, poly, allowed_caps=()):
    """All open interior intervals of p+a*n. Collinear edges are ambiguous."""
    cuts = []
    for a, b in edges(poly):
        v = sub(b, a)
        den = cross(n, v)
        if abs(den) <= EPS * math.hypot(*v):
            if abs(cross(sub(a, p), n)) <= EPS:
                if not any((distance(a, c) <= EPS and distance(b, d) <= EPS) or
                           (distance(a, d) <= EPS and distance(b, c) <= EPS)
                           for c, d in allowed_caps):
                    raise ValueError('normal collinear with boundary/end cap')
                cuts.extend((dot(sub(a, p), n), dot(sub(b, p), n)))
            continue
        z = cross(sub(a, p), v) / den
        t = cross(sub(a, p), n) / den
        if -EPS <= t <= 1 + EPS:
            cuts.append(z)
    cuts.sort()
    unique = []
    for z in cuts:
        if not unique or z - unique[-1] > EPS:
            unique.append(z)
    return [(a, b) for a, b in zip(unique, unique[1:])
            if b - a > EPS and inside((p[0] + .5 * (a + b) * n[0],
                                      p[1] + .5 * (a + b) * n[1]), poly, bool(allowed_caps))]
