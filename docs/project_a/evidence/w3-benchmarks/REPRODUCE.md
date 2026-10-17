# Reproduce the frozen A08 campaign

The primary run starts from A07 source `0c2d7c35fc50051a2ae96b9260de636610e280f4`.
The benchmark/support bytes are identified by `primary/manifest.json`; they are
committed with A08. All product modules remain the same accepted A07 bytes.
Primary numerical execution uses Ubuntu 22.04/ROS 2 Humble/Python 3.10.12,
NumPy 1.26.4/SciPy 1.11.4/TPH 0.79/quadprog 0.1.7. The actual image ID is recorded in
`primary/image-id.txt`, together with observed runtime isolation. All paths below
are explicit. No hardware Compose, ROS nodes, device access or network is used.

The exact historical primary and supplement invocations are retained in
`historical-invocations.txt`. They inherited `HOME=/work`; that override was
unnecessary and is omitted from every new command below. All benchmark inputs,
outputs, ROS projection paths and dependency prefixes were explicit. No `.ros`
or user configuration tree was created in either run directory. These
sourceful benchmark invocations are separate from the source-free A09 gate.

From a recursive checkout of the reviewed W3 candidate, obtain the pinned image
and a selected non-symlink install containing the existing generated ROS messages:

```bash
scripts/project_a/setup.sh
scripts/project_a/verify.sh ros work/w3/benchmark-build
```

The actual primary used the previously tested prefix
`work/w3/a07-ros-integration/install`. For a fresh reproduction, replace that
single prefix in the exact command below with `work/w3/benchmark-build/install`.
The compiler/kernel/validators are explicitly imported from the reviewed source;
the tested install provides generated ROS interfaces for export. A separate A09
campaign proves source-free installed execution. Use a fresh output directory.

Reproduce the 92-job primary protocol with the following command:

```bash
env -u DOCKER_HOST -u DOCKER_CONTEXT -u DOCKER_TLS \
  -u DOCKER_TLS_VERIFY -u DOCKER_CERT_PATH \
  docker --host=unix:///var/run/docker.sock run --rm --name w3-a08-primary \
  --network none --read-only --cap-drop ALL --security-opt no-new-privileges \
  --pids-limit 256 --memory 4g --cpus 2 --user 1000:1000 \
  --tmpfs /tmp:rw,nosuid,nodev,size=256m,mode=1777 \
  -e PYTHONDONTWRITEBYTECODE=1 \
  -e OPENBLAS_NUM_THREADS=1 -e OMP_NUM_THREADS=1 \
  --mount type=bind,src=/workspace/race_stack,dst=/src,readonly \
  --mount type=bind,src=/workspace/race_stack/work/w3,dst=/work \
  project-a-humble:w0 /bin/bash -c '
    source /opt/ros/humble/setup.bash &&
    source /src/work/w3/a07-ros-integration/install/setup.bash &&
    export PYTHONPATH=/src/planner/global_planner:/src/scripts/project_a:$PYTHONPATH &&
    python /src/scripts/project_a/identity.py > /work/a08-primary-runtime.json &&
    python /src/scripts/project_a/benchmark_w3.py \
      --repo /src \
      --fixtures /src/planner/global_planner/test/fixtures/project_a \
      --output /work/a08-primary \
      --scenarios S6-240m,S0-circle,S0-reverse,S0-rotated,S0-ellipse,S1-wall-gaps,S2-upper,S2-lower,S2-upper-cap,S3-surfaces,S3-notch,S4-coincident,S5-planar-connectors \
      --repeat 2 --artifacts --export-ros'
```

Change only the two host `src=` mount paths when the checkout is elsewhere. The
script freezes all 92 jobs before execution: two repeats for every declared
route/variant/spacing, including stock errors and expected resource failures.
S6 .5m is first; .52/.53m retries retain every other numerical/proof limit.
All attempts use fresh processes, recorded phase progress and process-group
termination under external 240 s wall/CPU and 3 GiB address-space bounds. Individual
fits/QPs retain 20 s wall/CPU and 2 GiB, unchanged from accepted A04.

The four matched-coarse repaired-legacy jobs were separately predeclared before
execution. Their exact worker/support hashes, same model/body/route/policies and
paired original primary manifest SHA are in `matched-coarse/manifest.json`.
They are replayed with the unchanged primary worker, without editing or replacing
the 92-job manifest. Restore the archived supplement into a fresh writable output:

```bash
mkdir -p work/w3/a08-matched-coarse/inputs
cp docs/project_a/evidence/w3-benchmarks/matched-coarse/manifest.json \
  work/w3/a08-matched-coarse/manifest.json
cp docs/project_a/evidence/w3-benchmarks/matched-coarse/run_manifest.py \
  work/w3/a08-matched-coarse/run_manifest.py
cp docs/project_a/evidence/w3-benchmarks/matched-coarse/inputs/S6-240m.json \
  work/w3/a08-matched-coarse/inputs/S6-240m.json
```

Reproduce the supplement protocol with the following command:

```bash
env -u DOCKER_HOST -u DOCKER_CONTEXT -u DOCKER_TLS \
  -u DOCKER_TLS_VERIFY -u DOCKER_CERT_PATH \
  docker --host=unix:///var/run/docker.sock run --rm --name w3-a08-matched-coarse \
  --network none --read-only --cap-drop ALL --security-opt no-new-privileges \
  --pids-limit 256 --memory 4g --cpus 2 --user 1000:1000 \
  --tmpfs /tmp:rw,nosuid,nodev,size=256m,mode=1777 \
  -e PYTHONDONTWRITEBYTECODE=1 \
  -e OPENBLAS_NUM_THREADS=1 -e OMP_NUM_THREADS=1 \
  --mount type=bind,src=/workspace/race_stack,dst=/src,readonly \
  --mount type=bind,src=/workspace/race_stack/work/w3,dst=/work \
  project-a-humble:w0 /bin/bash -c '
    source /opt/ros/humble/setup.bash &&
    source /src/work/w3/a07-ros-integration/install/setup.bash &&
    export PYTHONPATH=/src/planner/global_planner:/src/scripts/project_a:$PYTHONPATH &&
    python /work/a08-matched-coarse/run_manifest.py \
      --manifest /work/a08-matched-coarse/manifest.json \
      --worker /src/scripts/project_a/benchmark_w3.py'
```

For fresh reproduction use the new tested install prefix as above. New source
commit/status/output telemetry will differ from the original manifest; accepted
product module/helper bytes, route/model/policy identities and controlled numeric
authority remain independently comparable. Do not compare different mesh/model
rows as matched quality or speed results. Raw legacy geometry approval remains
UNSUPPORTED; common certificates apply only to its explicitly adapted binary64
polynomials. Native legacy continuous speed recovery is UNSUPPORTED; model times
use the declared common W2 retimer.

`files.json` indexes exact original and compressed file hashes/sizes. Bulky raw
authority, exports and corrupt products are gzip compressed with mtime=0. For an
artifact, decompress `reference.json.gz` into a private directory containing only
`reference.json`; use the independently approved H and supported validation
context when loading. A self-hash or stored PASS does not approve a reference.
The raw native coefficients/q, adapted authority, full traces, profiles, policies,
independent reports and resource/phase telemetry remain in each result JSON.gz.

All exploratory failures remain in `pilot`, `coarse-retry`, `s4-probe` and
`ros-probe`. Read `development-provenance.json` before interpreting them. They
contain exploratory source/interference limitations and are not final acceptance
or controlled performance evidence. The frozen primary and supplement determine
the final result matrix. Separate independent adversarial W3 review is still the
release gate.


## Independent replay and resource collection

Recheck the saved final primary through the unchanged W2 independent oracles in
the same pinned image (no HOME override). This diagnostic does not require
uncompressing artifacts, since it reads the exact saved coefficient/history files:

```bash
env -u DOCKER_HOST -u DOCKER_CONTEXT -u DOCKER_TLS \
  -u DOCKER_TLS_VERIFY -u DOCKER_CERT_PATH \
  docker --host=unix:///var/run/docker.sock run --rm --network none --read-only \
  --cap-drop ALL --security-opt no-new-privileges --pids-limit 256 --memory 4g \
  --cpus 2 --user 1000:1000 --tmpfs /tmp:rw,nosuid,nodev,size=256m,mode=1777 \
  -e PYTHONDONTWRITEBYTECODE=1 -e OPENBLAS_NUM_THREADS=1 -e OMP_NUM_THREADS=1 \
  --mount type=bind,src=/workspace/race_stack,dst=/src,readonly \
  --mount type=bind,src=/workspace/race_stack/work/w3,dst=/work \
  project-a-humble:w0 /bin/bash -c '
    source /opt/ros/humble/setup.bash &&
    export PYTHONPATH=/src/planner/global_planner:/src/scripts/project_a:$PYTHONPATH &&
    python /src/docs/project_a/evidence/w3-benchmarks/independent_audit.py \
      --repo /src --run /src/docs/project_a/evidence/w3-benchmarks/primary \
      --output /work/reproduced-primary-audit.json'
```

For the ten matched-supplement checks, change only the `--run` suffix from
`primary` to `matched-coarse` and select a new output filename.

The two whole-worker CPU resource replays were separately predeclared after the
96 numerical jobs. Restore the exact tested collector/manifest/fixture to a fresh
output; these manifest paths are fixed and must not contain existing job files:

```bash
mkdir -p work/w3/a08-cpu-replay-v2/inputs
cp docs/project_a/evidence/w3-benchmarks/cpu-replay/manifest.json \
  work/w3/a08-cpu-replay-v2/manifest.json
cp docs/project_a/evidence/w3-benchmarks/cpu-replay/collect_whole_cpu.py \
  work/w3/a08-cpu-replay-v2/collect_whole_cpu.py
cp docs/project_a/evidence/w3-benchmarks/cpu-replay/inputs/S6-240m.json \
  work/w3/a08-cpu-replay-v2/inputs/S6-240m.json
```

Their actual invocation, without any HOME override, was:

```bash
env -u DOCKER_HOST -u DOCKER_CONTEXT -u DOCKER_TLS \
  -u DOCKER_TLS_VERIFY -u DOCKER_CERT_PATH \
  docker --host=unix:///var/run/docker.sock run --rm --name w3-a08-cpu-replay-v2 \
  --network none --read-only --cap-drop ALL --security-opt no-new-privileges \
  --pids-limit 256 --memory 4g --cpus 2 --user 1000:1000 \
  --tmpfs /tmp:rw,nosuid,nodev,size=256m,mode=1777 \
  -e PYTHONDONTWRITEBYTECODE=1 -e OPENBLAS_NUM_THREADS=1 -e OMP_NUM_THREADS=1 \
  --mount type=bind,src=/workspace/race_stack,dst=/src,readonly \
  --mount type=bind,src=/workspace/race_stack/work/w3,dst=/work \
  project-a-humble:w0 /bin/bash -c '
    source /opt/ros/humble/setup.bash &&
    source /src/work/w3/a07-ros-integration/install/setup.bash &&
    export PYTHONPATH=/src/planner/global_planner:/src/scripts/project_a:$PYTHONPATH &&
    python /work/a08-cpu-replay-v2/collect_whole_cpu.py \
      --manifest /work/a08-cpu-replay-v2/manifest.json \
      --worker /src/scripts/project_a/benchmark_w3.py'
```

Use the fresh tested install prefix for a new checkout as described above.
`wait4` records exact user/system CPU and the largest process RSS over the worker
and reaped numerical descendants; it excludes the collector and includes imports
and final serialization. A calibration must PASS before either numerical launch.
Both workers run concurrently, so their walls are explicitly non-isolated; use
the original primary/matched run for isolated wall comparisons. Identity checks
against original .52 m records are retained in `cpu-replay/identity-match.json`.
The first malformed calibration control and its unchanged initial manifest/source
remain under `cpu-collector-probe/`; no planner worker launched on that failure.

The final copied-package acceptance and strict lint commands, exact source hashes
and exit statuses are in `tests/final-checks.json`, with test XML and full logs.
`check_a08.py` recreates that copied layout with explicit
`PROJECT_A_TEST_REPO=/src` in a sourceful test environment. This variable is never
needed by installed/source-free product execution.


Verify all archived bytes before replaying them:

```bash
cd docs/project_a/evidence/w3-benchmarks
sha256sum -c SHA256SUMS
```

Checksums establish byte integrity. They do not replace an externally trusted H,
independently selected supported validation context or either continuous validator.
