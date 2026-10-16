#!/usr/bin/env python3
"""
Reproduce A08 with bounded subprocesses and an append-only attempt ledger.

Invoke only in the pinned project-a-humble environment; every input/output path
is explicit. No ROS node, GUI, map inference, optimizer-source edit or hardware.
"""
import argparse
import contextlib
from dataclasses import asdict
import gzip
import importlib.metadata
import io
import json
import math
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time
import traceback

import numpy as np

from global_planner import iqp_route_adapter as adapter
from global_planner.cyclic_retime import curve_digest, model_digest, retime, RetimePolicy
from global_planner.route_corridor import portal_crossings, resample_ordered, seed_curve
from global_planner.route_input import RouteError, load_route, validate_route
from global_planner.route_validate import Footprint, GeometryValidationPolicy, validate_geometry
from global_planner.route_validate_dynamics import DynamicsValidationPolicy, validate_dynamics
from w3_benchmark_support import (archive_inventory, checker_shape_control, json_bytes,
                                  legacy_candidate, scenarios, sha, synthetic_model)

BODY = Footprint(.10, .10, .12, .01)
OUTER = {'wall_seconds': 240., 'cpu_seconds': 240, 'address_space_bytes': 3 * 1024 ** 3,
         'threads': 1, 'max_attempts': 100}
CONTRACT = 'project-a-a08-v1'


class Recorder:
    """Phase wall/CPU/RSS measurements, preserving exceptions and failure context."""

    def __init__(self, progress_path=None):
        """Keep phase records and an optional durable failure-progress ledger."""
        self.phases = []
        self.progress_path = progress_path

    def emit(self, event, record):
        """Persist a phase event before expensive or interruptible work."""
        if self.progress_path is not None:
            with self.progress_path.open('ab') as stream:
                stream.write(json_bytes({'event': event, **record}) + b'\n')
                stream.flush()
                os.fsync(stream.fileno())

    @contextlib.contextmanager
    def phase(self, name):
        """Record phase wall time, CPU usage, memory and failures."""
        wall, cpu = time.perf_counter(), time.process_time()
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        record = {'name': name}
        self.phases.append(record)
        self.emit('start', record)
        try:
            yield record
        except Exception as exc:
            record['exception'] = type(exc).__name__ + ': ' + str(exc)
            raise
        finally:
            after = resource.getrusage(resource.RUSAGE_CHILDREN)
            record.update(wall_seconds=time.perf_counter() - wall,
                          parent_cpu_seconds=time.process_time() - cpu,
                          child_cpu_seconds=(after.ru_utime + after.ru_stime -
                                             before.ru_utime - before.ru_stime),
                          parent_peak_rss_bytes=(resource.getrusage(
                              resource.RUSAGE_SELF).ru_maxrss * 1024),
                          child_peak_rss_bytes=after.ru_maxrss * 1024)
            self.emit('complete', record)


def _summary(report):
    """Compact ledger projection; full witnesses remain in compressed result."""
    keys = ('id', 'scenario', 'variant', 'repeat', 'status', 'reason', 'route_sha256',
            'expected_curve_digest', 'model_sha256', 'length_m', 'segments', 'iterations',
            'geometry_status', 'geometry_reason', 'geometry_leaves', 'geometry_gates',
            'retime_status', 'retime_reason', 'retime_iterations', 'retime_edges',
            'dynamics_status', 'dynamics_reason', 'dynamic_bound_intervals',
            'qp_condition_max', 'qp_primal_residual_max', 'qp_peak_rss_bytes',
            'curvature_energy_initial_per_m', 'curvature_energy_final_per_m',
            'lap_time_s', 'H', 'artifact_path', 'fine_query_count', 'solver_policy',
            'phases', 'parent_peak_rss_bytes', 'child_peak_rss_bytes', 'worker_exit_code',
            'outer_wall_seconds', 'result_file', 'result_sha256')
    return {key: report[key] for key in keys if key in report}


def _instrument(recorder):
    """Time accepted adapter phases locally without changing their equations."""
    originals = {name: getattr(adapter, name) for name in ('_geometry', '_fit', 'solve_qp')}

    def wrapped(name):
        def invoke(*args, **kwargs):
            with recorder.phase({'_geometry': 'corridor_reintersection', '_fit': 'spline_fit',
                                 'solve_qp': 'bounded_qp_condition_and_solve'}[name]) as row:
                try:
                    value = originals[name](*args, **kwargs)
                except adapter.OptimizationError:
                    if name == 'solve_qp':
                        # The production failure response deliberately exposes no
                        # candidate. Characterize the retained input matrix only.
                        row['failed_input_matrix_condition'] = float(np.linalg.cond(args[2]))
                    raise
                if name == '_geometry':
                    row['n'] = len(value[0])
                if name == '_fit':
                    row.update(n=len(value[0].curve.segments), child_resources=value[-1])
                return value
        return invoke

    for name in originals:
        setattr(adapter, name, wrapped(name))
    return originals


def _publish(report, ordered, timed, model, geometry, dynamics, job, recorder):
    from global_planner.route_artifact import (ValidationContext, artifact_identity, build_payload,
                                               load_reference, publish_reference)
    kwargs = {'solver_policy': adapter.SolverPolicy(**job['solver_policy']),
              'retime_policy': RetimePolicy(), 'geometry_policy': GeometryValidationPolicy(),
              'dynamics_policy': DynamicsValidationPolicy(),
              'approved_curve_digest': report['expected_curve_digest'],
              'geometry_report': geometry, 'dynamics_report': dynamics,
              'provenance': {'benchmark_contract': CONTRACT, 'scenario': job['scenario'],
                             'variant': job['variant'], 'scope': report['scope']}}
    with recorder.phase('encode_stage_reload_dual_validation_atomic_publish'):
        payload = build_payload(ordered, timed.profile, model, BODY, **kwargs)
        expected_H = artifact_identity(payload)
        reference = publish_reference(payload, Path(job['output']) / 'artifacts' / job['id'],
                                      expected_H=expected_H,
                                      expected_curve_digest=report['expected_curve_digest'],
                                      validation_context=ValidationContext())
    report.update(H=reference.H, artifact_path=str(reference.path))
    with recorder.phase('fine_true_metric_queries_without_refit'):
        count = math.ceil(reference.length / .1)
        values = tuple(reference.sample(i * reference.length / count) for i in range(count))
        reference.sample(-.1)
        reference.sample(2 * reference.length + .1)
    report['fine_query_count'] = len(values)
    if job['repeat'] == 1:
        attacks = []
        with recorder.phase('corrupt_artifact_and_external_identity_negative_controls'):
            mutation_dir = Path(job['output']) / 'mutations' / job['id'] / 'corrupt'
            mutation_dir.mkdir(parents=True)
            corrupt = mutation_dir / 'reference.json'
            corrupt.write_bytes(Path(reference.path).read_bytes() + b'{')
            for label, path, expected in (('corrupt persisted bytes', corrupt, reference.H),
                                          ('wrong external H', reference.path, '0' * 64)):
                try:
                    load_reference(path, expected_H=expected,
                                   validation_context=ValidationContext())
                except ValueError as exc:
                    attacks.append({'attack': label, 'status': 'REJECTED',
                                    'reason': str(exc)})
                else:
                    raise AssertionError('artifact mutation accepted: ' + label)
        report['artifact_negative_controls'] = attacks
    if job.get('export_ros'):
        from global_planner.route_legacy_export import export_waypoints
        (Path(job['output']) / 'legacy').mkdir(exist_ok=True)
        with recorder.phase('legacy_ros_export_without_refit'):
            export_waypoints(reference, step_m=.1,
                             output_dir=Path(job['output']) / 'legacy' / job['id'])


def run_worker(job):
    """Evaluate one frozen job without exposing an unaccepted reference."""
    recorder = Recorder(Path(job['output']) / (job['id'] + '.progress.jsonl'))
    report = {'id': job['id'], 'scenario': job['scenario'], 'variant': job['variant'],
              'repeat': job['repeat'], 'scope': 'Synthetic planar offline software only',
              'solver_policy': job['solver_policy'], 'status': 'INCONCLUSIVE', 'reason': '',
              'phases': recorder.phases,
              'worker_script_sha256': sha(Path(__file__).read_bytes()),
              'worker_support_sha256': sha(Path(__file__).with_name(
                  'w3_benchmark_support.py').read_bytes())}
    try:
        policy = adapter.SolverPolicy(**job['solver_policy'])
        with recorder.phase('strict_route_topology_validation'):
            route = load_route(job['route'])
        report.update(route_sha256=route.digest, route_bytes=len(route.encoded),
                      topology='A01_VALID_SELECTED_CYCLIC_RIBBONS')
        with recorder.phase('seed_curve_and_directed_owned_portal_control') as row:
            seed = seed_curve(route)
            passages = portal_crossings(seed)
            row.update(seed_length_m=seed.curve.length, seed_segments=len(seed.curve.segments),
                       directed_owned_portals=len(passages))
        report['curvature_energy_initial_per_m'] = adapter.curvature_energy(
            seed.curve.coefficients)
        if (job['scenario'] == 'S6-240m' and job['variant'] == 'new'
                and job['repeat'] == 1 and policy.spacing_m == .5):
            with recorder.phase('mesh_count_preflight_and_actual_metric_resample') as row:
                events = (len(route.occurrences) + sum(len(o.caps) for o in route.occurrences)
                          + 2 * len(route.portals))
                row['meshes'] = [{'spacing_m': spacing,
                                  'uniform_count': math.ceil(seed.curve.length / spacing),
                                  'conservative_events': events,
                                  'actual_anchored_count': len(resample_ordered(seed, spacing)),
                                  'max_points': policy.max_points}
                                 for spacing in (.5, .4, .2, .1)]
        ordered = None
        if job['variant'] == 'new':
            originals = _instrument(recorder)
            try:
                with recorder.phase('whole_lap_optimize'):
                    numerical = adapter.optimize(route, policy)
                    # Independent expectation is captured at the trusted return,
                    # before retiming, serialization, queries or stored reports.
                    expected = (curve_digest(numerical.ordered)
                                if numerical.ordered is not None else None)
            finally:
                for name, value in originals.items():
                    setattr(adapter, name, value)
            report.update(status=numerical.status, reason=numerical.reason,
                          iterations=len(numerical.traces),
                          traces=[asdict(t) for t in numerical.traces])
            ordered = numerical.ordered
            qps = [asdict(trace.qp) for trace in numerical.traces]
        else:
            with recorder.phase('legacy_stock_preparation' if job['variant'] == 'stock' else
                                'legacy_explicitly_repaired_preparation_and_bounded_iqp'):
                ordered, legacy = legacy_candidate(
                    route, policy, repaired=job['variant'] != 'stock')
                expected = curve_digest(ordered) if ordered is not None else None
            report.update(legacy=legacy, status=legacy['status'], reason=legacy['reason'],
                          iterations=legacy.get('iterations', 0))
            qps = legacy['qps']
        if qps:
            report.update(qp_condition_max=max(q['condition'] for q in qps),
                          qp_primal_residual_max=max(q['max_violation'] for q in qps),
                          qp_peak_rss_bytes=max(q['peak_rss_bytes'] for q in qps))
        if ordered is None:
            return report
        report.update(expected_curve_digest=expected, length_m=ordered.curve.length,
                      segments=len(ordered.curve.segments),
                      coefficients=ordered.curve.coefficients,
                      owners=ordered.curve.owners, q=ordered.q,
                      curvature_energy_final_per_m=adapter.curvature_energy(
                          ordered.curve.coefficients))
        with recorder.phase('independent_continuous_geometry'):
            geometry = validate_geometry(ordered, route, BODY, expected_curve_digest=expected)
        report.update(geometry=asdict(geometry), geometry_status=geometry.status,
                      geometry_reason=geometry.reason, geometry_leaves=len(geometry.intervals),
                      geometry_gates=len(geometry.gates))
        if geometry.status != 'PASS':
            report.update(status=geometry.status, reason=geometry.reason)
            return report
        model = synthetic_model(route)
        report.update(model=asdict(model), model_sha256=model_digest(model),
                      footprint=asdict(BODY))
        with recorder.phase('common_cyclic_squared_speed_retime'):
            timed = retime(ordered, model, spacing_m=.5)
        report.update(retime_status=timed.status, retime_reason=timed.message,
                      retime_iterations=timed.iterations, retime_edges=timed.edge_count,
                      retime=asdict(timed))
        if timed.status != 'CANDIDATE':
            report.update(status=timed.status, reason=timed.message)
            return report
        with recorder.phase('independent_continuous_dynamics'):
            dynamics = validate_dynamics(ordered, timed.profile, model, metadata=timed.metadata,
                                         expected_curve_digest=expected)
        report.update(dynamics=asdict(dynamics), dynamics_status=dynamics.status,
                      dynamics_reason=dynamics.reason,
                      dynamic_bound_intervals=sum(e.bound_intervals for e in dynamics.edges),
                      lap_time_s=timed.profile.lap_time_s, status=dynamics.status,
                      reason=dynamics.reason)
        if dynamics.status == 'PASS' and job.get('artifacts'):
            _publish(report, ordered, timed, model, geometry, dynamics, job, recorder)
        if job['scenario'] == 'S1-wall-gaps':
            with recorder.phase('required_physical_coverage_negative_control'):
                coverage = validate_geometry(
                    ordered, route, BODY,
                    GeometryValidationPolicy(require_physical_coverage=True),
                    expected_curve_digest=expected)
            report['required_physical_coverage'] = asdict(coverage)
            if coverage.status != 'INCONCLUSIVE':
                raise AssertionError('partial physical wall coverage must remain INCONCLUSIVE')
    except RouteError as exc:
        report.update(status='FAIL', reason='malformed annotated route: ' + str(exc))
    except Exception as exc:
        report.update(status='HARNESS_FAILURE', reason=type(exc).__name__ + ': ' + str(exc),
                      traceback=traceback.format_exc())
    finally:
        report.update(parent_peak_rss_bytes=(resource.getrusage(
            resource.RUSAGE_SELF).ru_maxrss * 1024), child_peak_rss_bytes=(resource.getrusage(
                resource.RUSAGE_CHILDREN).ru_maxrss * 1024))
    return report


def parity_control():
    """Compare the same prepared matrix, bounds/body and unchanged QP equations."""
    tph = adapter._helpers()
    t = np.linspace(0, 2 * math.pi, 64, endpoint=False)
    xy = np.column_stack((8 * np.cos(t), 5 * np.sin(t)))
    track = np.column_stack((xy, np.full((64, 2), .75)))
    _, _, matrix, normals = tph.calc_splines.calc_splines(np.vstack((xy, xy[0])))
    direct, error = tph.opt_min_curv.opt_min_curv(
        track.copy(), normals.copy(), matrix.copy(), 1., .30)
    actual = adapter.solve_qp(track, normals, matrix)
    discrepancy = float(max(abs(direct - actual.alpha)))
    if discrepancy > 1e-8 or abs(error - actual.curvature_error) > 1e-10:
        raise AssertionError('unchanged prepared-input equation parity failed')
    return {'n': 64, 'max_alpha_difference_m': discrepancy, 'tolerance_m': 1e-8,
            'curvature_error_difference_per_m': abs(error - actual.curvature_error),
            'track_sha256': sha(track.tobytes()), 'matrix_sha256': sha(matrix.tobytes()),
            'qp': asdict(actual), 'authority': 'same-prepared-input numerical parity only'}


def campaign(args):
    """Freeze the manifest and execute every declared bounded attempt."""
    output = Path(args.output).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError('fresh output directory required; attempt evidence is never overwritten')
    output.mkdir(parents=True, exist_ok=True)
    inputs = output / 'inputs'
    inputs.mkdir()
    routes, walls = scenarios(args.fixtures)
    selected = args.scenarios.split(',') if args.scenarios else list(routes)
    if set(selected) - set(routes):
        raise ValueError('unknown scenario selection')
    (inputs / 's1_gapped_physical_walls.json').write_bytes(json_bytes(walls))
    jobs = []
    for name in selected:
        route_path = inputs / (name + '.json')
        route_path.write_bytes(routes[name].encoded)
        spacings = (.5, .52, .53, .4, .2, .1) if name == 'S6-240m' else (.4,)
        for spacing in spacings:
            variants = ['new']
            if not args.no_legacy and spacing in (.4, .5):
                variants.extend(('stock', 'repaired'))
            for variant in variants:
                for repeat in range(1, args.repeat + 1):
                    policy = asdict(adapter.SolverPolicy(spacing_m=spacing))
                    identity = f'{name}-{variant}-{spacing:g}-r{repeat}'
                    jobs.append({'id': identity, 'scenario': name, 'variant': variant,
                                 'repeat': repeat, 'route': str(route_path),
                                 'solver_policy': policy,
                                 'output': str(output), 'artifacts': args.artifacts,
                                 'export_ros': args.export_ros})
    if len(jobs) > OUTER['max_attempts']:
        raise ValueError('campaign attempt budget exceeded')

    def git(*arguments):
        return subprocess.check_output(['git', '-C', args.repo, *arguments], text=True)

    gitlinks = git('submodule', 'status', '--recursive')
    helper_root = Path(adapter._helpers().__file__).parent
    helper_names = ('calc_splines.py', 'opt_min_curv.py', 'spline_approximation.py',
                    'iqp_handler.py', 'create_raceline.py', 'calc_spline_lengths.py',
                    'interp_splines.py', 'interp_track_widths.py')
    manifest = {'contract': CONTRACT, 'scope': 'synthetic offline comparison; no race readiness',
                'source_sha': git('rev-parse', 'HEAD').strip(),
                'source_status': git('status', '--short'),
                'gitlinks': gitlinks.splitlines(), 'outer_policy_predeclared': OUTER,
                'jobs': jobs, 'footprint': asdict(BODY),
                'geometry_policy': asdict(GeometryValidationPolicy()),
                'dynamics_policy': asdict(DynamicsValidationPolicy()),
                'retime_policy': asdict(RetimePolicy()),
                'dependencies': {name: importlib.metadata.version(name) for name in
                                 ('numpy', 'scipy', 'quadprog', 'trajectory-planning-helpers')},
                'python': sys.version, 'script_sha256': sha(Path(__file__).read_bytes()),
                'helper_source_sha256': {name: sha((helper_root / name).read_bytes())
                                         for name in helper_names},
                'legacy_preparation_settings': {'s_reg': 1, 'stepsize_prep_m': .05,
                                                'stepsize_reg_m': 'same declared solver spacing',
                                                'min_width': None, 'headless': True},
                'numerical_negative_control_policy': asdict(
                    adapter.SolverPolicy(max_condition=1.)),
                'support_sha256': sha(Path(__file__).with_name(
                    'w3_benchmark_support.py').read_bytes()),
                'fixtures': {name: {'route_sha256': routes[name].digest,
                                    'model': asdict(synthetic_model(routes[name]))}
                             for name in selected},
                's6_policy_decision': ('spacing .5m first; .52/.53 declared coarser retries; '
                                       'proofs/limits unchanged; .4/.2/.1 bounded failures'),
                'unsupported': ['physical car/course approval', '3D clearance/contact/grade',
                                'minimum curvature/time optimality',
                                'localization/tracking permission']}
    with (output / 'manifest.json').open('wb') as stream:
        stream.write(json_bytes(manifest))
        stream.flush()
        os.fsync(stream.fileno())
    optimizer = (Path(args.repo) / 'planner/global_planner/global_planner'
                 / 'global_racetrajectory_optimization')
    controls = {'same_prepared_input_equation_parity': parity_control(),
                'legacy_checker_shape': checker_shape_control(optimizer),
                'archival_software_assets': archive_inventory(args.repo)}
    numerical = adapter.optimize(routes['S0-circle'], adapter.SolverPolicy(max_condition=1.))
    controls['numerical_condition_failure'] = {
        'status': numerical.status, 'reason': numerical.reason,
        'candidate_exposed': numerical.ordered is not None, 'iterations': len(numerical.traces)}
    if numerical.status != 'SOLVER_FAILURE' or numerical.ordered is not None:
        raise AssertionError('numerical conditioning failure must not expose a candidate')
    malformed = routes[selected[0]].payload
    malformed['occurrences'][0]['left'], malformed['occurrences'][0]['right'] = (
        malformed['occurrences'][0]['right'], malformed['occurrences'][0]['left'])
    try:
        validate_route(malformed)
    except RouteError as exc:
        controls['malformed_geometry'] = {'status': 'REJECTED', 'reason': str(exc)}
    else:
        raise AssertionError('inconsistent side geometry accepted')
    (output / 'controls.json').write_bytes(json_bytes(controls))
    summaries = []
    bootstrap = ('import resource,runpy;'
                 f"resource.setrlimit(resource.RLIMIT_AS,({OUTER['address_space_bytes']},)*2);"
                 f"resource.setrlimit(resource.RLIMIT_CPU,({OUTER['cpu_seconds']},)*2);"
                 f'runpy.run_path({str(Path(__file__).resolve())!r},run_name="__main__")')
    for job in jobs:
        job_path = output / (job['id'] + '.job.json')
        job_path.write_bytes(json_bytes(job))
        began = time.perf_counter()
        try:
            process = subprocess.Popen(
                [sys.executable, '-c', bootstrap, '--worker', str(job_path)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
            try:
                stdout, stderr = process.communicate(timeout=OUTER['wall_seconds'])
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                stdout, stderr = process.communicate()
                raise subprocess.TimeoutExpired(process.args, OUTER['wall_seconds'],
                                                output=stdout, stderr=stderr)
            (output / (job['id'] + '.stdout')).write_bytes(stdout)
            (output / (job['id'] + '.stderr')).write_bytes(stderr)
            result_path = output / (job['id'] + '.json.gz')
            if process.returncode or not result_path.exists():
                report = {**job, 'status': ('RESOURCE_LIMIT' if process.returncode < 0
                                            else 'HARNESS_FAILURE'),
                          'reason': 'worker failed/no result',
                          'worker_exit_code': process.returncode}
            else:
                report = json.loads(gzip.decompress(result_path.read_bytes()))
                report.update(worker_exit_code=process.returncode, result_file=result_path.name,
                              result_sha256=sha(result_path.read_bytes()))
        except subprocess.TimeoutExpired as exc:
            report = {**job, 'status': 'RESOURCE_LIMIT',
                      'reason': 'outer campaign wall bound exhausted',
                      'worker_exit_code': 'TIMEOUT'}
            (output / (job['id'] + '.stdout')).write_bytes(exc.stdout or b'')
            (output / (job['id'] + '.stderr')).write_bytes(exc.stderr or b'')
        if 'result_file' not in report:
            progress = output / (job['id'] + '.progress.jsonl')
            if progress.exists():
                events = [json.loads(line) for line in progress.read_bytes().splitlines()]
                report['phase_progress_at_failure'] = events
                report['phases'] = [row for row in events if row['event'] == 'complete']
            result_path = output / (job['id'] + '.json.gz')
            result_path.write_bytes(gzip.compress(json_bytes(report), mtime=0))
            report.update(result_file=result_path.name,
                          result_sha256=sha(result_path.read_bytes()))
        report['outer_wall_seconds'] = time.perf_counter() - began
        summary = _summary(report)
        summaries.append(summary)
        with (output / 'attempts.jsonl').open('ab') as ledger:
            ledger.write(json_bytes(summary) + b'\n')
            ledger.flush()
            os.fsync(ledger.fileno())
        print(json.dumps({key: summary.get(key) for key in
                          ('id', 'status', 'reason', 'segments', 'iterations',
                           'outer_wall_seconds')}), flush=True)
    (output / 'summary.json').write_bytes(json_bytes(
        {'contract': CONTRACT, 'attempts': summaries}))
    return 0 if all(row['status'] != 'HARNESS_FAILURE' for row in summaries) else 1


def main():
    """Run the explicit-path campaign or one contained worker."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output')
    parser.add_argument('--fixtures')
    parser.add_argument('--repo')
    parser.add_argument('--scenarios')
    parser.add_argument('--repeat', type=int, default=2)
    parser.add_argument('--no-legacy', action='store_true')
    parser.add_argument('--artifacts', action='store_true')
    parser.add_argument('--export-ros', action='store_true')
    parser.add_argument('--worker')
    args = parser.parse_args()
    if args.worker:
        job = json.loads(Path(args.worker).read_bytes())
        with contextlib.redirect_stdout(io.StringIO()):
            report = run_worker(job)
        raw = json_bytes(report)
        destination = Path(job['output']) / (job['id'] + '.json.gz')
        destination.write_bytes(gzip.compress(raw, mtime=0))
        print(json.dumps(_summary(report), allow_nan=False), flush=True)
        return 0
    if not all((args.output, args.fixtures, args.repo)) or not 1 <= args.repeat <= 2:
        parser.error('--output, --fixtures, --repo and repeat in [1,2] required')
    return campaign(args)


if __name__ == '__main__':
    raise SystemExit(main())
