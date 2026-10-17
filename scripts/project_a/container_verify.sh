#!/usr/bin/env bash
set -eo pipefail
mode=${1:-all}
source /opt/ros/humble/setup.bash
# Test-only helper/archive paths are explicit; never inherited by the source-free container.
export PROJECT_A_TEST_REPO=/src
printf 'ROS_DISTRO=%s\n' "$ROS_DISTRO"
cat /etc/os-release
id
python --version
python -m pip freeze --all > /work/dependencies.txt
dpkg-query -W > /work/os-packages.txt
python -m pip check
# Evidence of actual execution isolation (not just YAML intent).
python /src/scripts/project_a/identity.py > /work/runtime-identity.json
if [[ "$mode" == all || "$mode" == numerical ]]; then
  export PYTHONPATH="/src/planner/global_planner:${PYTHONPATH:-}"
  python -m flake8 --max-line-length=99 /src/planner/global_planner/global_planner/*route*.py /src/planner/global_planner/test/test_route*.py
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q -p no:cacheprovider /src/planner/global_planner/test/test_route_input.py --junitxml=/work/a01.xml
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q -p no:cacheprovider /src/planner/global_planner/test/test_route_reference.py --junitxml=/work/a02.xml
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q -p no:cacheprovider /src/planner/global_planner/test/test_route_corridor.py --junitxml=/work/a03.xml
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q -p no:cacheprovider /src/planner/global_planner/test/test_route_w2_shared_cap.py --junitxml=/work/w2-shared-cap.xml
  python -m flake8 --max-line-length=99 /src/planner/global_planner/test/test_iqp_route_adapter.py
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q -p no:cacheprovider /src/planner/global_planner/test/test_iqp_route_adapter.py --junitxml=/work/a04.xml
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q -p no:cacheprovider /src/planner/global_planner/test/test_route_validate_geometry.py --junitxml=/work/a05.xml
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q -p no:cacheprovider /src/planner/global_planner/test/test_route_validate_bounds_oracle.py --junitxml=/work/a05-oracle.xml
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q -p no:cacheprovider /src/planner/global_planner/test/test_route_w2_numerical_oracle.py --junitxml=/work/w2-numerical-oracle.xml
  python -m flake8 --max-line-length=99 /src/planner/global_planner/global_planner/cyclic_retime.py /src/planner/global_planner/test/test_cyclic_retime.py /src/planner/global_planner/test/test_w2_pipeline.py /src/scripts/project_a/tests/test_w2_installed.py /src/scripts/project_a/source_manifest.py
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q -p no:cacheprovider /src/planner/global_planner/test/test_cyclic_retime.py --junitxml=/work/a06.xml
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q -p no:cacheprovider /src/planner/global_planner/test/test_route_validate_dynamics.py --junitxml=/work/a06-independent.xml
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q -p no:cacheprovider /src/planner/global_planner/test/test_route_dynamics_oracle.py --junitxml=/work/a06-oracle.xml
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q -p no:cacheprovider /src/planner/global_planner/test/test_route_ellipse_dynamics.py --junitxml=/work/a06-ellipse.xml
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q -p no:cacheprovider /src/planner/global_planner/test/test_route_w2_handoff.py --junitxml=/work/w2-handoff.xml
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q -p no:cacheprovider /src/planner/global_planner/test/test_w2_pipeline.py --junitxml=/work/w2-pipeline.xml
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q -p no:cacheprovider /src/planner/global_planner/test/test_route_w2_novel_pipeline.py --junitxml=/work/w2-novel-pipeline.xml
  # W3 additions have their own strict gates; inherited package lint stays visible.
  python -m flake8 --max-line-length=99 /src/scripts/project_a/source_manifest.py /src/scripts/project_a/legacy_identity.py /src/scripts/project_a/tests/test_w3_installed.py
  ament_pep257 --convention pep257 /src/planner/global_planner/global_planner/route_artifact.py /src/planner/global_planner/global_planner/route_compile.py /src/planner/global_planner/global_planner/route_legacy_export.py /src/planner/global_planner/test/test_route_artifact.py /src/planner/global_planner/test/test_route_compile.py /src/planner/global_planner/test/test_route_legacy_export.py
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q -p no:cacheprovider /src/planner/global_planner/test/test_route_artifact.py --junitxml=/work/a07-artifact.xml
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q -p no:cacheprovider /src/planner/global_planner/test/test_route_compile.py --junitxml=/work/a07-cli.xml
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q -p no:cacheprovider /src/planner/global_planner/test/test_route_legacy_export.py -k 'not actual_nine_group_reader_and_generated_ros_cdr and not corrupt_staged_ros_serialization_is_never_published' --junitxml=/work/a07-export-pure.xml
  python -m flake8 --max-line-length=99 /src/planner/global_planner/test/test_w3_benchmarks.py /src/scripts/project_a/benchmark_w3.py /src/scripts/project_a/w3_benchmark_support.py /src/scripts/project_a/w3_query_probe.py /src/scripts/project_a/tests/test_w3_scenario_installed.py
  ament_pep257 --convention pep257 /src/planner/global_planner/test/test_w3_benchmarks.py
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q -p no:cacheprovider /src/planner/global_planner/test/test_w3_benchmarks.py --junitxml=/work/a08-regressions.xml
  python -m flake8 --max-line-length=99 /src/scripts/project_a/tests/test_w3_harness.py
  # The pinned /tmp is noexec; these local Git fixtures intentionally execute shell scripts.
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q -p no:cacheprovider /src/scripts/project_a/tests/test_w3_harness.py --basetemp=/work/a09-harness-tmp --junitxml=/work/a09-harness.xml
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q -p no:cacheprovider /src/scripts/project_a/tests/test_numerical.py --junitxml=/work/numerical.xml
fi
if [[ "$mode" == all || "$mode" == ros || "$mode" == legacy ]]; then
  # Copy only selected packages: colcon/setuptools must never write into /src.
  mkdir -p /work/src
  cp -a /src/planner/global_planner /work/src/
  cp -a /src/utilities/libraries/f110_msgs /src/utilities/libraries/frenet_conversion /work/src/
  python /src/scripts/project_a/source_manifest.py --repository /src \
    --build-identity /work/src/global_planner/config/project_a/build_identity.json
  cp /work/src/global_planner/config/project_a/build_identity.json /work/build-identity.json
  python /usr/bin/colcon --log-base /work/log build --base-paths /work/src \
    --build-base /work/build --install-base /work/install \
    --packages-select f110_msgs frenet_conversion global_planner --parallel-workers 2
  optimizer=/work/src/global_planner/global_planner/global_racetrajectory_optimization
  (cd "$optimizer" && python setup.py bdist_wheel --dist-dir /work/wheels) > /work/optimizer-wheel.log 2>&1
  python -m pip install --no-index --no-deps --target /work/python /work/wheels/*.whl
  export PYTHONPATH="/work/python"
  source /work/install/setup.bash
  cd /work
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q -p no:cacheprovider /src/scripts/project_a/tests/test_ros.py --junitxml=/work/ros.xml
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q -p no:cacheprovider /src/scripts/project_a/tests/test_w1_installed.py --junitxml=/work/w1-installed.xml
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q -p no:cacheprovider /src/scripts/project_a/tests/test_w2_installed.py --junitxml=/work/w2-installed.xml
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q -p no:cacheprovider /src/scripts/project_a/tests/test_w3_installed.py --junitxml=/work/w3-installed.xml
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q -p no:cacheprovider /src/planner/global_planner/test/test_route_legacy_export.py -k 'actual_nine_group_reader_and_generated_ros_cdr or corrupt_staged_ros_serialization_is_never_published' --junitxml=/work/a07-export-ros.xml
fi
if [[ "$mode" == all || "$mode" == legacy ]]; then
  # Legacy failures remain visible in a separate result; never used to mask functional failure.
  set +e
  python /usr/bin/colcon --log-base /work/legacy-log test --base-paths /work/src \
    --build-base /work/build --install-base /work/install \
    --packages-select f110_msgs frenet_conversion global_planner --return-code-on-test-failure \
    --event-handlers console_direct+ > /work/legacy.log 2>&1
  legacy_rc=$?
  python /usr/bin/colcon test-result --test-result-base /work/build --verbose > /work/legacy-results.txt 2>&1
  summary_rc=$?
  set -e
  printf 'colcon_test=%s\ncolcon_test_result=%s\n' "$legacy_rc" "$summary_rc" > /work/legacy-exit-codes.txt
  cat /work/legacy-results.txt
  python /src/scripts/project_a/legacy_identity.py \
    --baseline /src/docs/project_a/evidence/pinned-run/legacy-results.txt.gz \
    --actual /work/legacy-results.txt --build-root /work/build \
    --output /work/legacy-identity-comparison.json
  # Baseline lint is recorded, not a passing acceptance check.
  if [[ "$mode" == legacy ]]; then exit "$legacy_rc"; fi
fi

python - <<'PY_SUMMARY'
import json
from pathlib import Path
import xml.etree.ElementTree as ET
out = {'scope': 'W0_THROUGH_A08_SOURCE_AND_A07_INSTALLED',
       'source_free_a09': 'SEPARATE_HOST_RUN_FOR_ALL_OR_ROS',
       'legal_planner_acceptance': 'SYNTHETIC_PLANAR_OFFLINE',
       'independent_w3_adversarial_review': 'REQUIRED'}
for kind in ('numerical', 'ros', 'a01', 'a02', 'a03', 'a04', 'a05', 'a05-oracle',
             'a06', 'a06-independent', 'a06-oracle', 'a06-ellipse', 'w2-handoff',
             'w2-numerical-oracle', 'w2-shared-cap', 'w2-pipeline', 'w2-novel-pipeline',
             'w1-installed',
             'w2-installed', 'a07-artifact', 'a07-cli', 'a07-export-pure', 'a07-export-ros',
             'w3-installed', 'a08-regressions', 'a09-harness'):
    path = Path('/work', kind + '.xml')
    if path.exists():
        suite = ET.parse(path).getroot().find('testsuite')
        out[kind] = {key: suite.attrib[key] for key in ('tests', 'failures', 'errors', 'skipped')}
legacy = Path('/work/legacy-exit-codes.txt')
if legacy.exists():
    out['legacy_baseline'] = legacy.read_text().strip().splitlines()
Path('/work/summary.json').write_text(json.dumps(out, indent=2))
print(json.dumps(out, indent=2))
PY_SUMMARY
