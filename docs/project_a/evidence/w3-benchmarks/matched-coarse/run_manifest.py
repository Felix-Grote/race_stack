#!/usr/bin/env python3
"""Replay predeclared A08 supplemental jobs through the unchanged bounded worker."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def encode(value):
    """Encode deterministic run telemetry without authority normalization."""
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def main():
    """Verify the frozen worker and execute every separately declared matched job."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--worker', required=True)
    args = parser.parse_args()
    manifest = json.loads(Path(args.manifest).read_bytes())
    worker = Path(args.worker).resolve()
    for path, key in ((worker, 'script_sha256'),
                      (worker.with_name('w3_benchmark_support.py'), 'support_sha256')):
        if hashlib.sha256(path.read_bytes()).hexdigest() != manifest[key]:
            raise ValueError('supplement worker bytes differ from predeclared primary identity')
    outer = manifest['outer_policy_predeclared']
    bootstrap = ('import resource,runpy;'
                 f"resource.setrlimit(resource.RLIMIT_AS,({outer['address_space_bytes']},)*2);"
                 f"resource.setrlimit(resource.RLIMIT_CPU,({outer['cpu_seconds']},)*2);"
                 f'runpy.run_path({str(worker)!r},run_name="__main__")')
    summaries = []
    for job in manifest['jobs']:
        output = Path(job['output'])
        job_path = output / (job['id'] + '.job.json')
        if job_path.exists():
            raise ValueError('fresh supplemental job outputs required')
        job_path.write_bytes(encode(job))
        began = time.perf_counter()
        process = subprocess.Popen([sys.executable, '-c', bootstrap, '--worker', str(job_path)],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   start_new_session=True)
        timed_out = False
        try:
            stdout, stderr = process.communicate(timeout=outer['wall_seconds'])
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGKILL)
            stdout, stderr = process.communicate()
        (output / (job['id'] + '.stdout')).write_bytes(stdout)
        (output / (job['id'] + '.stderr')).write_bytes(stderr)
        result_path = output / (job['id'] + '.json.gz')
        if result_path.exists() and process.returncode == 0:
            report = json.loads(gzip.decompress(result_path.read_bytes()))
        else:
            report = {**job, 'status': 'RESOURCE_LIMIT' if timed_out else 'HARNESS_FAILURE',
                      'reason': 'outer wall bound' if timed_out else 'worker failed/no result'}
            progress = output / (job['id'] + '.progress.jsonl')
            if progress.exists():
                report['phase_progress_at_failure'] = [
                    json.loads(line) for line in progress.read_bytes().splitlines()]
            result_path.write_bytes(gzip.compress(encode(report), mtime=0))
        keys = ('id', 'scenario', 'variant', 'repeat', 'status', 'reason', 'route_sha256',
                'expected_curve_digest', 'model_sha256', 'length_m', 'segments', 'iterations',
                'geometry_status', 'geometry_leaves', 'retime_edges', 'dynamic_bound_intervals',
                'qp_condition_max', 'qp_primal_residual_max', 'qp_peak_rss_bytes',
                'curvature_energy_initial_per_m', 'curvature_energy_final_per_m', 'lap_time_s',
                'H', 'artifact_path', 'fine_query_count', 'solver_policy', 'phases',
                'parent_peak_rss_bytes', 'child_peak_rss_bytes')
        summary = {key: report[key] for key in keys if key in report}
        summary.update(outer_wall_seconds=time.perf_counter() - began,
                       worker_exit_code=process.returncode, result_file=result_path.name,
                       result_sha256=hashlib.sha256(result_path.read_bytes()).hexdigest())
        summaries.append(summary)
        with (output / 'attempts.jsonl').open('ab') as stream:
            stream.write(encode(summary) + b'\n')
            stream.flush()
            os.fsync(stream.fileno())
        print(json.dumps({key: summary.get(key) for key in
                          ('id', 'status', 'reason', 'outer_wall_seconds')}), flush=True)
    output = Path(manifest['jobs'][0]['output'])
    (output / 'summary.json').write_bytes(encode({'attempts': summaries}))
    return int(any(row['status'] == 'HARNESS_FAILURE' for row in summaries))


if __name__ == '__main__':
    raise SystemExit(main())
