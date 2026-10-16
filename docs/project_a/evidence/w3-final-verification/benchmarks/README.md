# Final-candidate S0–S6 functional replay

This evidence executes the original 92-job primary and four matched-coarse jobs
against literal source `17e4ec4e8fedfa736467d02f6204b04e8552decb`. It is a
non-isolated functional replay during full final-candidate verification. All new
wall/CPU telemetry is functional/resource observation only; it does not replace
or compare with the original isolated A08 performance campaign.

`manifest.json` binds both submanifest hashes and all 96 unique jobs. All model,
body, solver, geometry/dynamics proof, numerical helper and resource policies
remain unchanged. Concurrency three executes within the original two-CPU/4-GiB
container; each worker retains 240 s wall/CPU and 3 GiB address space, accepted
A04 children retain 20 s wall/CPU and 2 GiB, and the whole-lap solver retains
120 s wall, 512 points and condition(A) <=1e12. Every actual outcome is retained;
there are no numerical retries or replacement records.

Image ID is
`sha256:2cc1f6ad969cdb3256f14b4b45500cb0fcdd4a3f321b4c2a1bbc7c7fb6ca0f88`.
The source tree is read-only. The actual tested installed A07 prefix provides
ROS dependencies only; explicit PYTHONPATH and all 11 source-module origin/hash
checks bind planner behavior to the final 17e4 source. No HOME override, nodes,
GUI, network, hardware or devices are used. `runtime-isolation.json`,
`host-resource-context.json`, `numpy-runtime.txt` and the manifest retain observed
resource, implementation, helper, dependency and recursive-pin identities.

Two orchestration preparation errors preceded all numerical controls/workers.
Their original code/console and partial plans remain under
`preparation-failure-{1,2}`. They are separate from the 96 executed numerical
attempts. `provenance-notes.json` also explains inherited original matched-launcher
and pairing metadata versus the current runner and root submanifest hashes.
An independent read-only manifest review found no blocker.

The actual invocation used the local Docker socket and explicit mount paths:

```bash
env -u DOCKER_HOST -u DOCKER_CONTEXT -u DOCKER_TLS \
  -u DOCKER_TLS_VERIFY -u DOCKER_CERT_PATH \
  docker --host=unix:///var/run/docker.sock run --rm --name w3-postfix-functional \
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
    python /work/postfix-benchmark-replay.py --repo /src \
      --output /work/postfix-benchmarks'
```

The exact invoked scratch runner is retained as `replay_runner.py`; committed
benchmark/support sources are unchanged. To execute a new independent run, use
an exact recursive 17e4 checkout, build the pinned image and selected ROS prefix,
copy the retained runner outside this archived directory and choose a fresh output
directory. If building the selected prefix afresh, the path above may be reused;
only generated ROS dependencies are consumed from it. All actual source origins
must still resolve to the reviewed 17e4 checkout. Existing outputs are never
reused or overwritten.

Each accepted route has actual final coefficients, occurrence owners, inherited q,
model, policy, profile and real validation reports in its gzip result and exact
immutable artifact bytes. The artifact publisher independently reloads the staged
bytes with the separately retained trusted A04 C and artifact H and requires both actual
validators to PASS. Fine true-metric queries and original nine-group reader/CDR
export must also complete for a functional PASS. The final controlled-artifact
catalog records each actual new H/C; no old historical H is substituted, and no
fresh cross-host binary-identical compilation promise follows.

After all jobs finish, the unchanged independent W2 trace and Gaussian96 oracles
check every accepted saved output at their original tolerances. Independent output
checks bind actual saved artifact coefficients/q/model/profile/implementation and
producer main T/Float32 export to the controlled result. Raw legacy geometry and
native continuous legacy speed authorization remain UNSUPPORTED; only the
explicitly adapted exact binary64 comparator authority receives common checks.

`final-summary.json` records every final outcome and independent audit result.
`source-after.json` verifies the unchanged clean final source. `SHA256SUMS` and
`files.json` provide byte-integrity inventories; these do not authorize an artifact
or replace the independently selected validation context and trusted expected H.
Physical operation, arbitrary course feasibility, 3D/contact, localization and
controller tracking remain outside this offline planar evidence. A separate
independent W3 adversarial review remains the final approval gate.
