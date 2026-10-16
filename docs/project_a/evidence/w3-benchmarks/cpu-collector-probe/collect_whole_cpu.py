#!/usr/bin/env python3
"""Collect whole-worker Linux wait4 resources around an unchanged frozen A08 worker."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
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
    """Keep deterministic telemetry JSON separate from artifact authority."""
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def wait_bounded(process, seconds):
    """Reap this worker exactly once and retain its whole descendant resource usage."""
    deadline = time.perf_counter() + seconds
    timeout = False
    while True:
        pid, status, usage = os.wait4(process.pid, os.WNOHANG)
        if pid:
            process.returncode = os.waitstatus_to_exitcode(status)
            return timeout, usage
        if time.perf_counter() >= deadline and not timeout:
            timeout = True
            os.killpg(process.pid, signal.SIGKILL)
        time.sleep(.05)


def one(job, worker, outer):
    """Execute one declared full path without touching worker equations or reports."""
    output = Path(job['output'])
    job_path = output / (job['id'] + '.job.json')
    bootstrap = ('import resource,runpy;'
                 f"resource.setrlimit(resource.RLIMIT_AS,({outer['address_space_bytes']},)*2);"
                 f"resource.setrlimit(resource.RLIMIT_CPU,({outer['cpu_seconds']},)*2);"
                 f'runpy.run_path({str(worker)!r},run_name="__main__")')
    began = time.perf_counter()
    with (output / (job['id'] + '.stdout')).open('wb') as stdout:
        with (output / (job['id'] + '.stderr')).open('wb') as stderr:
            process = subprocess.Popen([sys.executable, '-c', bootstrap, '--worker', str(job_path)],
                                       stdout=stdout, stderr=stderr, start_new_session=True)
            timed_out, usage = wait_bounded(process, outer['wall_seconds'])
    raw = {key: getattr(usage, key) for key in dir(usage) if key.startswith('ru_')}
    resource_record = {'collector': 'Linux os.wait4(worker_pid, WNOHANG)',
                       'boundary': 'worker startup/imports through result serialization/exit, '
                                   'including reaped numerical children; collector excluded',
                       'wall_scope': 'non-isolated concurrent resource-only replay',
                       'timed_out': timed_out, 'worker_exit_code': process.returncode,
                       'whole_worker_user_seconds': usage.ru_utime,
                       'whole_worker_system_seconds': usage.ru_stime,
                       'whole_worker_cpu_seconds': usage.ru_utime + usage.ru_stime,
                       'whole_worker_peak_process_rss_bytes': usage.ru_maxrss * 1024,
                       'outer_wall_seconds': time.perf_counter() - began,
                       'raw_wait4_rusage': raw}
    (output / (job['id'] + '.resources.json')).write_bytes(encode(resource_record))
    result = output / (job['id'] + '.json.gz')
    report = json.loads(gzip.decompress(result.read_bytes())) if result.exists() else {}
    summary = {key: report[key] for key in (
        'id', 'scenario', 'variant', 'repeat', 'status', 'reason', 'route_sha256',
        'expected_curve_digest', 'H', 'segments', 'iterations', 'geometry_status',
        'dynamics_status', 'length_m', 'lap_time_s') if key in report}
    summary.update(resource_record)
    summary.update(result_file=result.name,
                   result_sha256=hashlib.sha256(result.read_bytes()).hexdigest()
                   if result.exists() else None)
    return summary


def calibration(output):
    """Demonstrate that wait4 includes CPU consumed by an explicitly reaped grandchild."""
    # Constructing this control as ordinary source avoids shell interpretation.
    child = '''import subprocess
import sys
import time
start = time.process_time()
while time.process_time() - start < .15:
    pass
subprocess.run([sys.executable, '-c',
                'import time\nstart=time.process_time()\n'
                'while time.process_time()-start<.15:\n    pass'], check=True)
'''
    process = subprocess.Popen([sys.executable, '-c', child], start_new_session=True)
    timed_out, usage = wait_bounded(process, 10.)
    passed = not timed_out and process.returncode == 0 and usage.ru_utime + usage.ru_stime >= .3
    record = {'scope': 'collector calibration, not a numerical-planner attempt',
              'status': 'PASS' if passed else 'FAIL',
              'parent_burn_cpu_seconds': .15, 'reaped_grandchild_burn_cpu_seconds': .15,
              'observed_wait4_user_seconds': usage.ru_utime,
              'observed_wait4_system_seconds': usage.ru_stime,
              'raw_wait4_rusage': {key: getattr(usage, key) for key in dir(usage)
                                   if key.startswith('ru_')}}
    (output / 'collector-calibration.json').write_bytes(encode(record))
    if not passed:
        raise RuntimeError('wait4 descendant CPU calibration failed')


def main():
    """Freeze exact worker identities and collect the two predeclared resource replays."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--worker', required=True)
    args = parser.parse_args()
    worker = Path(args.worker).resolve()
    manifest = json.loads(Path(args.manifest).read_bytes())
    for path, key in ((worker, 'script_sha256'),
                      (worker.with_name('w3_benchmark_support.py'), 'support_sha256'),
                      (Path(__file__), 'collector_sha256')):
        if hashlib.sha256(path.read_bytes()).hexdigest() != manifest[key]:
            raise ValueError('resource replay source differs from frozen manifest')
    output = Path(manifest['jobs'][0]['output'])
    for job in manifest['jobs']:
        path = output / (job['id'] + '.job.json')
        if path.exists():
            raise ValueError('fresh resource-only replay outputs required')
        with path.open('xb') as stream:
            stream.write(encode(job))
            stream.flush()
            os.fsync(stream.fileno())
    calibration(output)
    rows = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(one, job, worker, manifest['outer_policy_predeclared'])
                   for job in manifest['jobs']]
        for future in as_completed(futures):
            row = future.result()
            rows.append(row)
            with (output / 'attempts.jsonl').open('ab') as stream:
                stream.write(encode(row) + b'\n')
                stream.flush()
                os.fsync(stream.fileno())
            print(json.dumps(row), flush=True)
    (output / 'summary.json').write_bytes(encode({'attempts': rows}))
    return int(any(row.get('status') != 'PASS' or row['worker_exit_code'] != 0 for row in rows))


if __name__ == '__main__':
    raise SystemExit(main())
