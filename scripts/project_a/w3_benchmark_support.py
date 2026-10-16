"""
Test-only A08 fixtures and explicitly repaired, bounded legacy comparator.

The installed planner never imports this file. Vendor/helper files stay unchanged.
Candidate coefficients come directly from the legacy helper, never sampled refits.
"""
from bisect import bisect_right
import contextlib
import copy
from dataclasses import asdict
from fractions import Fraction
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import types

import numpy as np
from scipy import interpolate, optimize, spatial

from global_planner import iqp_route_adapter as adapter
from global_planner.cyclic_retime import DynamicsModel, ModelRegion, RegionLimits, SteeringLimits
from global_planner.route_corridor import OrderedCurve, _sample_at_q, normal_interval, seed_curve
from global_planner.route_input import load_route, validate_route
from global_planner.route_reference import Curve

HASHES = {
    'spline_approximation.py':
        'a1e6259858f24ba28493d1f049e88710385d2d218a5cbca1a1d2835904e81d52',
    'iqp_handler.py': 'b764ff805fd5585a6dfb30e23b1c0b3ef667c91d66129dca78d9b37a356f65ae',
    'check_traj.py': 'a7f397f1375dc8624b6e651b9fccde7017b7e00446256ee479ef498a2c8c01ed',
    'create_raceline.py': '98985622e8995f04fe38292f844b51b4fc9a1114825389eea3538279bca43fb5',
}
GROUPS = ('map_info_str', 'est_lap_time', 'centerline_markers', 'centerline_waypoints',
          'global_traj_markers_iqp', 'global_traj_wpnts_iqp', 'global_traj_markers_sp',
          'global_traj_wpnts_sp', 'trackbounds_markers')
SCOPE = 'Synthetic planar offline software only; no physical course/car certification'


def sha(data):
    """Hash exact source or fixture bytes."""
    return hashlib.sha256(data).hexdigest()


def json_bytes(value):
    """Encode deterministic diagnostic JSON without route-input normalization."""
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def synthetic_model(route):
    """One common explicit model for new/legacy geometry; no car calibration."""
    regions = []
    for o in route.occurrences:
        weak = o.surface_id != 'ground'
        limits = RegionLimits(.05, 2.5 if weak else 4., 1.5 if weak else 2.,
                              2. if weak else 3., 2. if weak else 4., 2.5, .02,
                              'W3 synthetic explicit planar diamond; no car calibration')
        regions.append(ModelRegion(o.id, o.surface_id, limits))
    return DynamicsModel(tuple(regions), SCOPE, SteeringLimits(.3, .7, 3.))


def _provenance(source):
    return {'author': 'Project A W3 fixture generator', 'source': source,
            'revision': 'w3-v1', 'approval': 'synthetic software only; no physical evidence'}


def _ellipse_course(base):
    """240 m variable-curvature ribbon, fixed physical widths, nonuniform seed."""
    p = base.payload
    # Deterministic high-order ellipse integral, used to select fixture dimensions
    # only. Acceptance still uses the actual coefficients and independent proofs.
    roots, weights = np.polynomial.legendre.leggauss(96)
    theta = math.pi * (roots + 1)
    length = math.pi * float(weights @ np.hypot(45 * np.sin(theta), 30 * np.cos(theta)))
    scale = 240 / length
    a, b = 45 * scale, 30 * scale

    def frame(t):
        c, s = math.cos(t), math.sin(t)
        if abs(c) < 1e-14:
            c = 0.
        if abs(s) < 1e-14:
            s = 0.
        x, y = a * c, b * s
        norm = math.hypot(c / a, s / b)
        return (x, y), (c / a / norm, s / b / norm)

    def point(t, offset=0.):
        xy, normal = frame(t)
        return [xy[j] + offset * normal[j] for j in (0, 1)]

    for i, o in enumerate(p['occurrences']):
        angles = [math.pi / 2 * (i + (j / 32) ** 1.05) for j in range(33)]
        o.update(seed=[point(t) for t in angles], left=[point(t, -.7) for t in angles],
                 right=[point(t, .9) for t in angles],
                 caps=[{'at_m': 0., 'max_speed_mps': 4. if i % 2 == 0 else 3.2}],
                 provenance=_provenance('240m ellipse; fixed .7/.9m legal sides; nonuniform seed'))
    for i, portal in enumerate(p['transitions']):
        t = (i + 1) % 4 * math.pi / 2
        xy, normal = frame(t)
        tangent = (-normal[1], normal[0])
        portal.update(gate=[point(t, .9), point(t, -.7)], before_m=.3, after_m=.3,
                      support=[[xy[j] + radial * normal[j] + along * tangent[j]
                                for j in (0, 1)]
                               for radial, along in ((1.3, -.5), (1.3, .5),
                                                     (-1.3, .5), (-1.3, -.5))],
                      provenance=_provenance('explicit shared endcap/support; planar only'))
    p['initialization']['zone'] = copy.deepcopy(p['transitions'][-1]['support'])
    p['course_id'] = 'w3-s6-240m-ellipse'
    p['route_id'] = 'w3_s6_route'
    p['provenance'] = _provenance('analytic approximately240m competition-scale synthetic ellipse')
    p['physical_map']['provenance'] = _provenance('no measured physical map; synthetic only')
    p['physical_map']['sha256'] = sha(json_bytes({'a': a, 'b': b, 'widths': [.7, .9]}))
    return validate_route(p)


def scenarios(fixtures):
    """Freeze explicit route payloads before the campaign starts."""
    root = Path(fixtures)
    names = {'S0-circle': 's0_route', 'S0-reverse': 's0_reverse_route',
             'S0-rotated': 's0_rotated_route', 'S2-upper': 's2_upper_route',
             'S2-lower': 's2_lower_route', 'S3-surfaces': 's3_surfaces_route',
             'S3-notch': 's3_notch_route'}
    routes = {name: load_route(root / (filename + '.json')) for name, filename in names.items()}
    base = routes['S0-circle']
    p = base.payload
    for o in p['occurrences']:
        for key in ('seed', 'left', 'right'):
            o[key] = [[4 * x / 3, 5 * y / 6] for x, y in o[key]]
    for portal in p['transitions']:
        for key in ('gate', 'support'):
            portal[key] = [[4 * x / 3, 5 * y / 6] for x, y in portal[key]]
    p['initialization']['zone'] = [
        [4 * x / 3, 5 * y / 6] for x, y in p['initialization']['zone']]
    p['route_id'] = 'w3_s0_ellipse'
    p['provenance'] = _provenance('axes8/5 affine ellipse; independent topology-preserving map')
    routes['S0-ellipse'] = validate_route(p)
    # Wall data deliberately contains physical gaps; its presence never changes
    # the original legal chains or supplies a missing physical-coverage proof.
    walls = {'schema': 'w3-synthetic-wall-segments-v1', 'scope': SCOPE, 'segments': []}
    for occurrence in base.occurrences:
        for side in (occurrence.left, occurrence.right):
            walls['segments'].extend([[a, b] for j, (a, b) in enumerate(zip(side, side[1:]))
                                      if not 10 <= j < 18])
    p = base.payload
    p['physical_map'].update(
        sha256=sha(json_bytes(walls)), coverage='partial',
        provenance=_provenance('explicit gapped walls; legal ribbon unchanged'))
    routes['S1-wall-gaps'] = validate_route(p)
    p = routes['S2-upper'].payload
    p['occurrences'][1]['caps'] = [{'at_m': 0., 'max_speed_mps': .9}]
    p['route_id'] = 'w3_s2_upper_cap'
    routes['S2-upper-cap'] = validate_route(p)
    p = base.payload
    more = copy.deepcopy(p['occurrences'])
    for o in more:
        o['id'] = 'repeat-' + o['id']
        o['surface_id'] = 'repeat-deck'
    p['surfaces'].append({'id': 'repeat-deck', 'kind': 'bridge',
                          'provenance': _provenance('coincident projected deck; no3D claim')})
    p['occurrences'] += more
    portals = copy.deepcopy(p['transitions'])
    p['transitions'][-1]['to'] = 'repeat-o0'
    for portal in portals:
        for key in ('id', 'from', 'to'):
            portal[key] = 'repeat-' + portal[key]
    portals[-1]['to'] = 'o0'
    p['transitions'] += portals
    p['gate_sequence'] = [portal['id'] for portal in p['transitions']]
    p['finish'] = p['gate_sequence'][-1]
    p['route_id'] = 'w3_s4_repeat'
    routes['S4-coincident'] = validate_route(p)
    p = base.payload
    labels = ('ground', 'ramp-up', 'upper-deck', 'ramp-down')
    p['surfaces'] = [{'id': label, 'kind': 'ramp' if 'ramp' in label else
                      'bridge' if label == 'upper-deck' else 'planar',
                      'provenance': _provenance(
                          'annotated planar connector; contact/grade unsupported')}
                     for label in labels]
    for o, label in zip(p['occurrences'], labels):
        o['surface_id'] = label
        o['caps'] = [{'at_m': 0., 'max_speed_mps': 1.4 if 'ramp' in label else 3.}]
    p['route_id'] = 'w3_s5_connectors'
    routes['S5-planar-connectors'] = validate_route(p)
    routes['S6-240m'] = _ellipse_course(base)
    return routes, walls


def _authenticated(path, expected):
    source = Path(path).read_bytes()
    if sha(source) != expected:
        raise adapter.OptimizationError('unsupported comparator source: ' + str(path))
    return source.decode()


def _module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _legacy_fit_worker():
    """Only an unchanged spline helper, after parent-applied fresh-process limits."""
    import resource
    began = time.monotonic()
    request = np.load(io.BytesIO(sys.stdin.buffer.read()), allow_pickle=False)
    x, y, matrix, normals = adapter._helpers().calc_splines.calc_splines(
        path=request['path'], use_dist_scaling=bool(request['scaling'].item()))
    response = io.BytesIO()
    np.savez_compressed(response, x=x, y=y, matrix=matrix, normals=normals,
                        resources=np.array((resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                                            * 1024, time.monotonic() - began)))
    sys.stdout.buffer.write(response.getvalue())


def _bounded_legacy_fit(path, use_dist_scaling, policy, remaining):
    """Match accepted A04 fit containment without changing legacy spline scaling."""
    if len(path) - 1 > policy.max_points or remaining <= 0:
        raise adapter.OptimizationError('legacy fit point/wall budget exhausted', 'RESOURCE_LIMIT')
    request = io.BytesIO()
    np.savez(request, path=path, scaling=np.array(use_dist_scaling))
    bootstrap = ('import resource,runpy;'
                 f'resource.setrlimit(resource.RLIMIT_AS,({policy.qp_memory_bytes},)*2);'
                 f'resource.setrlimit(resource.RLIMIT_CPU,({policy.qp_cpu_seconds},)*2);'
                 f'runpy.run_path({str(Path(__file__).resolve())!r},run_name="__main__")')
    env = dict(os.environ)
    env.update(OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1',
               NUMEXPR_NUM_THREADS='1')
    try:
        completed = subprocess.run([sys.executable, '-c', bootstrap, '--legacy-fit-worker'],
                                   input=request.getvalue(), capture_output=True,
                                   timeout=min(policy.qp_wall_seconds, remaining),
                                   env=env, check=False)
    except subprocess.TimeoutExpired as exc:
        raise adapter.OptimizationError('legacy spline child wall limit',
                                        'RESOURCE_LIMIT') from exc
    if completed.returncode:
        raise adapter.OptimizationError('legacy spline child failed/resource limit: ' +
                                        completed.stderr.decode(errors='replace')[-500:],
                                        'RESOURCE_LIMIT')
    response = np.load(io.BytesIO(completed.stdout), allow_pickle=False)
    return tuple(response[name] for name in ('x', 'y', 'matrix', 'normals', 'resources'))


def checker_shape_control(optimizer_root):
    """Run stock/repaired checker unchanged apart from two declared array fixes."""
    root = (Path(optimizer_root) / 'global_racetrajectory_optimization'
            / 'helper_funcs_glob' / 'src')
    source = _authenticated(root / 'check_traj.py', HASHES['check_traj.py'])
    interp = _module('w3_legacy_interp', root / 'interp_track.py')
    calc = _module('w3_legacy_distance', root / 'calc_min_bound_dists.py')
    rows = []

    def observe(**kwargs):
        distances = calc.calc_min_bound_dists(**kwargs)
        rows.append({'bound1_shape': list(kwargs['bound1'].shape),
                     'bound2_shape': list(kwargs['bound2'].shape),
                     'minimum_distance_m': float(min(distances)),
                     'maximum_distance_m': float(max(distances))})
        return distances

    package = types.ModuleType('global_racetrajectory_optimization')
    package.helper_funcs_glob = types.SimpleNamespace(src=types.SimpleNamespace(
        interp_track=interp,
        calc_min_bound_dists=types.SimpleNamespace(calc_min_bound_dists=observe)))
    previous = sys.modules.get(package.__name__)
    sys.modules[package.__name__] = package
    t = np.arange(64) * 2 * math.pi / 64
    track = np.column_stack((6 * np.cos(t), 6 * np.sin(t), np.full((64, 2), .75)))
    trajectory = np.column_stack((6 * t, track[:, :2], t, np.full(64, 1 / 6),
                                  np.full(64, 2.), np.zeros(64)))
    needle = 'stepsize_approx=1.0)[0]'
    if source.count(needle) != 2:
        raise ValueError('checker repair anchor mismatch')
    repaired = source.replace(needle, 'stepsize_approx=1.0)[:, :2]')
    try:
        for label, body in (('stock', source), ('repaired', repaired)):
            ns = {}
            exec(compile(body, '<w3 isolated ' + label + ' checker>', 'exec'), ns)
            with contextlib.redirect_stdout(io.StringIO()):
                ns['check_traj'](track, track[:, :2] / 6, trajectory,
                                 np.array([[0., 12., 12.], [15., 12., 12.]]),
                                 np.array([[0., 9.], [15., 1.]]), 15., .20, .12,
                                 False, .02, 1., 1.)
            rows[-1]['label'] = label
    finally:
        if previous is None:
            del sys.modules[package.__name__]
        else:
            sys.modules[package.__name__] = previous
    return {'source_sha256': sha(source.encode()),
            'repaired_source_sha256': sha(repaired.encode()),
            'repair': 'exactly2 stepsize_approx=1.0)[0] -> stepsize_approx=1.0)[:, :2]',
            'rows': rows, 'authority': 'diagnostic only; sampled unsigned warning checker'}


def split_authority(route, coefficients, q, numeric_policy, *, evidence=None):
    """
    Algebraically subdivide/rotate captured cubics at supplied owner q events.

    This is a representation change of the same exact candidate polynomials,
    subject to ordinary binary64 arithmetic; no points are interpolated or fit.
    """
    q = tuple(float(x) for x in q)
    period = sum(o.length for o in route.occurrences)
    if len(q) != len(coefficients) + 1 or any(a >= b for a, b in zip(q, q[1:])):
        raise ValueError('nonmonotone legacy coefficient lineage')
    if abs((q[-1] - q[0]) - period) > 1e-8:
        raise ValueError('legacy lineage does not cover one selected cycle')
    ends = [0.]
    for o in route.occurrences:
        ends.append(ends[-1] + o.length)
    pieces = []
    for source_segment, (c, lower, upper) in enumerate(zip(coefficients, q, q[1:])):
        cuts = [lower, upper]
        for lap in range(math.floor(lower / period) - 1, math.ceil(upper / period) + 1):
            cuts.extend(x + lap * period for x in ends[:-1]
                        if lower < x + lap * period < upper)
        for first, last in zip(sorted(set(cuts)), sorted(set(cuts))[1:]):
            start = (first - lower) / (upper - lower)
            step = (last - first) / (upper - lower)
            new = tuple(tuple(math.fsum(
                c[axis][k] * math.comb(k, j) * start ** (k - j) * step ** j
                for k in range(j, 4)) for j in range(4))
                        for axis in (0, 1))
            if evidence is not None:
                exact_start = ((Fraction(first) - Fraction(lower)) /
                               (Fraction(upper) - Fraction(lower)))
                exact_step = ((Fraction(last) - Fraction(first)) /
                              (Fraction(upper) - Fraction(lower)))
                errors = []
                for axis in (0, 1):
                    error = Fraction(0)
                    for j in range(4):
                        exact = sum(Fraction(c[axis][k]) * math.comb(k, j) *
                                    exact_start ** (k - j) * exact_step ** j
                                    for k in range(j, 4))
                        error += abs(Fraction(new[axis][j]) - exact)
                    errors.append(math.nextafter(float(error), math.inf))
                # Sum of coordinate absolute errors bounds Euclidean error too.
                bound = math.nextafter(math.fsum(errors), math.inf)
                evidence.append({'source_segment': source_segment,
                                 'source_q_interval': [first, last],
                                 'source_t_start': start, 'source_t_step': step,
                                 'coordinate_composition_roundoff_bound_m': bound})
            lap = math.floor((first + last) / (2 * period))
            a, b = first - lap * period, last - lap * period
            # Preserve original semantic endpoint float values exactly.
            a = min(ends, key=lambda x: abs(a - x)) if min(abs(a - x) for x in ends) < 1e-10 else a
            b = min(ends, key=lambda x: abs(b - x)) if min(abs(b - x) for x in ends) < 1e-10 else b
            owner_index = min(bisect_right(ends, (a + b) / 2) - 1,
                              len(route.occurrences) - 1)
            owner = route.occurrences[owner_index]
            pieces.append((a, b, new, (owner.id, owner.surface_id)))
    pieces.sort(key=lambda x: x[0])
    if pieces[0][0] != 0 or pieces[-1][1] != period:
        raise ValueError('legacy q seam could not be retained')
    return OrderedCurve(route, Curve([x[2] for x in pieces], [x[3] for x in pieces],
                                     numeric_policy), tuple(x[0] for x in pieces) + (period,))


def legacy_candidate(route, policy, *, repaired=True):
    """
    Bound unchanged TPH prep/IQP equations with explicit local adaptations.

    Stock preparation is always measured separately. Repairs scalarize SciPy's
    objective argument and contain calls; widths remain legacy transported widths.
    """
    deadline = time.monotonic() + policy.wall_seconds
    tph = adapter._helpers()
    root = Path(tph.__file__).parent
    sources = {name: _authenticated(root / name, HASHES[name])
               for name in ('spline_approximation.py', 'iqp_handler.py', 'create_raceline.py')}
    # The image/dependency pin fixes this helper. The runtime byte hash is retained
    # beside the authenticated prep and IQP source identities in every result.
    lineage = []
    result = {'scope': SCOPE, 'equations': 'unchanged authenticated pinned TPH0.79',
              'sources': {name: sha(text.encode()) for name, text in sources.items()},
              'create_raceline_sha256': sha((root / 'create_raceline.py').read_bytes()),
              'repairs': [], 'lineage': lineage, 'qps': [], 'fits': [],
              'legacy_velocity': {'status': 'UNSUPPORTED',
                                  'reason': 'geometry-only stock-equation driver; '
                                            'common W2 retiming is evaluated separately'}}
    seed = seed_curve(route)
    raw = []
    for q in seed.q[:-1]:
        sample = _sample_at_q(seed, q)
        corridor = normal_interval(seed, sample)
        raw.append(sample.xy + (corridor.right, corridor.left))
    raw = np.asarray(raw)
    result['input_track_sha256'] = sha(raw.tobytes())
    ns = {}
    exec(compile(sources['spline_approximation.py'], '<w3 isolated legacy prep>', 'exec'), ns)
    closest = []

    def fmin(*args, **kwargs):
        answer = optimize.fmin(*args, **kwargs)
        closest.append(float(np.asarray(answer).item()))
        return answer

    ns['optimize'] = types.SimpleNamespace(fmin=fmin)
    if repaired:
        ns['dist_to_p'] = lambda t, path, p: spatial.distance.euclidean(
            p, interpolate.splev(float(np.asarray(t).item()), path))
        result['repairs'].append('isolated dist_to_p scalarizes t via float(np.asarray(t).item())')
    began = time.monotonic()
    try:
        track = ns['spline_approximation'](
            raw.copy(), s_reg=1, stepsize_prep=.05,
            stepsize_reg=policy.spacing_m, debug=False)
    except (ValueError, TypeError) as exc:
        result.update(status=('STOCK_PREPARATION_FAILURE' if not repaired
                              else 'PREPARATION_FAILURE'),
                      reason=type(exc).__name__ + ': ' + str(exc),
                      preparation_seconds=time.monotonic() - began)
        return None, result
    result['preparation_seconds'] = time.monotonic() - began
    result['closest_parameters'] = closest
    if (len(closest) != len(seed.q) or not np.isfinite(closest).all()
            or any(a >= b for a, b in zip(closest, closest[1:]))
            or abs(closest[-1] - closest[0] - 1) > 1e-3):
        result.update(status='UNSUPPORTED',
                      reason='legacy preparation has no monotone cyclic q correspondence')
        return None, result
    period = seed.period
    # The B-spline is periodic. Close with first+1, retaining the observed final
    # nearest-search discrepancy explicitly; no XY association is done downstream.
    parameters = np.asarray(closest)
    result['periodic_endpoint_parameter_discrepancy'] = closest[-1] - closest[0] - 1
    parameters[-1] = parameters[0] + 1
    grid = np.arange(len(track)) / len(track)
    table_t = np.concatenate((parameters[:-1] - 1, parameters, parameters[1:] + 1))
    table_q = np.concatenate((np.asarray(seed.q[:-1]) - period, seed.q,
                              np.asarray(seed.q[1:]) + period))
    current_q = np.interp(grid, table_t, table_q)
    current_q = np.append(current_q, current_q[0] + period)
    result['preparation_q'] = current_q.tolist()
    result['repairs'].extend(('cyclic source-q map from recorded monotone prep parameters',
                              'bounded QP calls/points/wall and explicit headless output paths'))
    if len(track) > policy.max_points:
        result.update(status='RESOURCE_LIMIT', reason='legacy prepared point budget exceeded')
        return None, result

    def fit(path, use_dist_scaling=True):
        tick = time.monotonic()
        values = _bounded_legacy_fit(path, use_dist_scaling, policy,
                                     deadline - time.monotonic())
        result['fits'].append({'seconds': time.monotonic() - tick, 'n': len(path) - 1,
                               'use_dist_scaling': use_dist_scaling,
                               'child_peak_rss_bytes': float(values[-1][0]),
                               'child_seconds': float(values[-1][1])})
        return values[:4]

    x, y, matrix, normals = fit(np.vstack((track[:, :2], track[0, :2])))
    state = {'q': current_q, 'iterations': 0, 'final': None}

    def qp(**kwargs):
        state['iterations'] += 1
        if state['iterations'] > policy.max_iterations:
            raise adapter.OptimizationError('legacy QP iteration watchdog', 'RESOURCE_LIMIT')
        value = adapter.solve_qp(kwargs['reftrack'], kwargs['normvectors'], kwargs['A'],
                                 policy, deadline - time.monotonic())
        result['qps'].append(asdict(value))
        return np.asarray(value.alpha), value.curvature_error

    def create(**kwargs):
        before = state['q'].copy()
        tick = time.monotonic()
        value = create_native(**kwargs)
        if len(value[0]) > policy.max_points or time.monotonic() > deadline:
            raise adapter.OptimizationError('legacy remesh/wall watchdog', 'RESOURCE_LIMIT')
        inds, ts = value[4], value[5]
        inherited = (1 - ts) * before[inds] + ts * before[inds + 1]
        next_q = np.append(inherited, inherited[0] + period)
        if np.any(np.diff(next_q) <= 0):
            raise ValueError('legacy create_raceline reversed inherited q')
        lineage.append({'source_q': before.tolist(), 'segment': inds.tolist(),
                        't': ts.tolist(), 'inherited_q': next_q.tolist(),
                        'seconds': time.monotonic() - tick})
        state['q'] = next_q
        state['final'] = (np.stack((value[2], value[3]), axis=1), before)
        return value

    proxy = types.SimpleNamespace(**{name: getattr(tph, name) for name in dir(tph)
                                     if not name.startswith('_')})
    proxy.opt_min_curv = types.SimpleNamespace(opt_min_curv=qp)
    proxy.create_raceline = types.SimpleNamespace(create_raceline=create)
    proxy.calc_splines = types.SimpleNamespace(calc_splines=fit)
    create_ns = {}
    exec(compile(sources['create_raceline.py'], '<w3 unchanged bounded legacy raceline>',
                 'exec'), create_ns)
    create_ns['tph'] = proxy
    create_native = create_ns['create_raceline']
    ns = {}
    exec(compile(sources['iqp_handler.py'], '<w3 unchanged bounded legacy iqp>', 'exec'), ns)
    ns['tph'] = proxy
    zeros = np.zeros(track.shape)
    try:
        alpha, final_track, final_normals, *_ = ns['iqp_handler'](
            track.copy(), normals, matrix, zeros, zeros, zeros, zeros,
            policy.curvature_bound, policy.vehicle_width_m, False, False,
            policy.spacing_m, policy.min_iterations, policy.curvature_error)
        create(refline=final_track[:, :2], normvectors=final_normals, alpha=alpha,
               stepsize_interp=policy.spacing_m)
        coefficients, final_q = state['final']
        result.update(actual_final_coefficients=coefficients.tolist(),
                      actual_final_q=final_q.tolist(),
                      coefficient_source='actual final create_raceline return; no sampled refit',
                      iterations=state['iterations'])
        result['raw_curvature_energy_per_m'] = adapter.curvature_energy(coefficients)
        result['raw_legacy_geometry_authorization'] = {
            'status': 'UNSUPPORTED',
            'reason': 'raw legacy cubics omit original occurrence anchors; '
                      'common certificates apply only to the adapted binary64 authority'}
        composition = []
        ordered = split_authority(
            route, coefficients, final_q, seed.curve.policy, evidence=composition)
        result['algebraic_subdivision'] = composition
        result['composition_roundoff_bound_m'] = max(
            x['coordinate_composition_roundoff_bound_m'] for x in composition)
        result['adapted_curvature_energy_per_m'] = adapter.curvature_energy(
            ordered.curve.coefficients)
        result.update(status='CANDIDATE', reason='', split_segments=len(ordered.curve.segments))
        return ordered, result
    except (adapter.OptimizationError, ValueError) as exc:
        result.update(status=getattr(exc, 'status', 'UNSUPPORTED'),
                      reason=type(exc).__name__ + ': ' + str(exc), iterations=state['iterations'])
        return None, result


def archive_inventory(repo):
    """Check static archival compatibility and arithmetic without approving geometry."""
    result = {}
    for name in ('GLC_smile_small', 'glc_ot_ez', 'hangar_1905_v0'):
        path = Path(repo) / 'stack_master' / 'maps' / name / 'global_waypoints.json'
        raw = path.read_bytes()
        payload = json.loads(raw)
        if set(payload) != set(GROUPS):
            raise ValueError('archived nine-group schema changed: ' + name)
        profiles = {}
        for group in ('global_traj_wpnts_iqp', 'global_traj_wpnts_sp'):
            rows = payload[group]['wpnts']
            if any(not all(math.isfinite(v) for v in row.values()) for row in rows):
                raise ValueError('nonfinite archived waypoint')
            durations, errors = [], []
            for first, last in zip(rows, rows[1:]):
                ds = last['s_m'] - first['s_m']
                durations.append(2 * ds / (first['vx_mps'] + last['vx_mps']))
                errors.append(abs(first['ax_mps2'] -
                                  (last['vx_mps'] ** 2 - first['vx_mps'] ** 2) / (2 * ds)))
            profiles[group] = {'count': len(rows), 'stored_length_m': rows[-1]['s_m'],
                               'terminal_duplicate_xy': all(rows[-1][k] == rows[0][k]
                                                            for k in ('x_m', 'y_m')),
                               'stored_station_linear_u_time_s': math.fsum(durations),
                               'max_stored_acceleration_error': max(errors),
                               'closing_acceleration_mps2': rows[-2]['ax_mps2']}
        result[name] = {'file_sha256': sha(raw), 'groups': list(payload), 'profiles': profiles,
                        'stored_est_lap_time': payload['est_lap_time'],
                        'scope': ('archival software data; '
                                  'no approved legal geometry/calibrated model')}
    return result


if __name__ == '__main__' and sys.argv[1:] == ['--legacy-fit-worker']:
    _legacy_fit_worker()
