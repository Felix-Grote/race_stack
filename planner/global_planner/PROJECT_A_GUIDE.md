# Offline global planner: developer and downstream handoff

Project A compiles one explicitly selected legal cyclic route into an immutable
reference, independently checks its actual final coefficients and cyclic speed
profile, and projects it into the existing ROS waypoint format. It is an offline
planning subsystem; independent W3 adversarial review is required for acceptance.

Start with the [artifact and CLI specification](../../docs/project_a/W3_ARTIFACT.md),
[installed runtime instructions](../../docs/project_a/W3_RUNTIME.md),
[benchmark protocol and outcomes](../../docs/project_a/W3_BENCHMARKS.md), and
[review instructions](../../docs/project_a/W3_REVIEW.md). Current evidence is
indexed in [STATUS](../../docs/project_a/STATUS.md) and
[RESULTS](../../docs/project_a/RESULTS.md). Historical W0–W2 records remain intact.

## Reproduce an exact candidate

Use the literal candidate SHA recorded in the release evidence, never a moving
default branch. The safe environment is Ubuntu 22.04 / ROS 2 Humble /
Python 3.10.12 with the checked-in hash-locked numerical dependencies. The
optimizer remains at `b1b38ecfefec7200d5bcb243f115af1d795b3766`.

```bash
git clone --recursive https://github.com/Felix-Grote/race_stack.git
cd race_stack
git checkout --detach EXACT_W3_CANDIDATE_SHA
git submodule update --init --recursive
scripts/project_a/setup.sh
scripts/project_a/verify.sh all work/release-verification
```

The final runner builds only `f110_msgs`, `frenet_conversion` and
`global_planner` without symlink installation, then starts a separate runtime
container containing installed products and a small copied test harness. It
mounts no repository or build tree. The same installed console entry performs
compile, validate, query and export in separate processes. Explicit installed
synthetic fixtures/models/policies and build provenance are used. The actual
legacy reader and generated ROS CDR serialization are exercised. Output records
preserve failures; the ten inherited lint/XML failures remain separately visible
and are checked against their exact baseline identities.

Never use the root hardware Compose file or start vehicle nodes for this work.
The standalone `docker-compose.test.yaml` and source-free runtime launcher are
the supported test paths. Keep all generated products under explicit output
directories. Consult the benchmark protocol before running the full resource
campaign; primary timings require a controlled workload.

## Static downstream interface

```python
from global_planner.route_artifact import load_reference
from global_planner.route_compile import load_policy

policies, context, spacing = load_policy('/inputs/synthetic_policy.json')
reference = load_reference('/results/references/TRUSTED_H/reference.json',
                           expected_H=trusted_identity,
                           validation_context=context)
state = reference.sample(progress_metres, occurrence_id=supplied_occurrence)
preview = reference.window(progress_metres, progress_metres + 5.0, 0.1)
```

`trusted_identity` must come from a controlled compile or approved release
manifest retained before transport. Reading H from received bytes does not
authorize those bytes. The independently selected validation context defines
supported numerical implementation, proof policy and required coverage.

The planner team owns schema/codec, actual coefficient and speed authorities,
source q lineage, original legal geometry, numerical policies, independent
offline checks, metric queries and the lossy waypoint projection. It supplies
frame/units, H, occurrence/surface identities, gates/initialization metadata,
model/footprint/margins, provenance and coverage limitations.

Localization and state-estimation teams own metric progress/occurrence
association and freshness. Controllers own preview use, tracking error,
actuation limits and operating permission. Physical-course and vehicle owners
must supply approved geometry, calibrated traction/steering/contact models,
tracking margins and physical evidence. Planar ramps and bridge surface labels
establish neither 3D clearance nor contact/grade feasibility.

Use the immutable coefficients directly. Re-fitting waypoint XY, replacing
physical station with index-times-step, or inferring surface from nearest XY
does not preserve the certificate. Existing messages omit H, occurrence/surface
and proof authority. Optional centerline/shortest-path groups are explicitly
unavailable; consumers requiring them need separate integration work.

The S6 result is a full approximately 240 m synthetic variable-curvature course,
with disclosed mesh failures and coarse-mesh alternatives. It does not establish
performance on every tighter or more complex course, physical-car readiness,
minimum curvature or minimum lap time.
