#!/usr/bin/env bash
set -eo pipefail
mode=${1:-all}
source /opt/ros/humble/setup.bash
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
  python -m flake8 --max-line-length=99 /src/planner/global_planner/test/test_iqp_route_adapter.py
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q -p no:cacheprovider /src/planner/global_planner/test/test_iqp_route_adapter.py --junitxml=/work/a04.xml
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q -p no:cacheprovider /src/planner/global_planner/test/test_route_validate_geometry.py --junitxml=/work/a05.xml
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q -p no:cacheprovider /src/planner/global_planner/test/test_route_validate_bounds_oracle.py --junitxml=/work/a05-oracle.xml
  python -m flake8 --max-line-length=99 /src/planner/global_planner/global_planner/cyclic_retime.py /src/planner/global_planner/test/test_cyclic_retime.py /src/planner/global_planner/test/test_w2_pipeline.py /src/scripts/project_a/tests/test_w2_installed.py /src/scripts/project_a/source_manifest.py
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q -p no:cacheprovider /src/planner/global_planner/test/test_cyclic_retime.py --junitxml=/work/a06.xml
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q -p no:cacheprovider /src/planner/global_planner/test/test_route_validate_dynamics.py --junitxml=/work/a06-independent.xml
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q -p no:cacheprovider /src/planner/global_planner/test/test_route_dynamics_oracle.py --junitxml=/work/a06-oracle.xml
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q -p no:cacheprovider /src/planner/global_planner/test/test_w2_pipeline.py --junitxml=/work/w2-pipeline.xml
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q -p no:cacheprovider /src/scripts/project_a/tests/test_numerical.py --junitxml=/work/numerical.xml
fi
if [[ "$mode" == all || "$mode" == ros || "$mode" == legacy ]]; then
  # Copy only selected packages: colcon/setuptools must never write into /src.
  mkdir -p /work/src
  cp -a /src/planner/global_planner /work/src/
  cp -a /src/utilities/libraries/f110_msgs /src/utilities/libraries/frenet_conversion /work/src/
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
  # Baseline lint is recorded, not a passing acceptance check.
  if [[ "$mode" == legacy ]]; then exit "$legacy_rc"; fi
fi

python - <<'PY_SUMMARY'
import json
from pathlib import Path
import xml.etree.ElementTree as ET
out = {'scope': 'W0_THROUGH_A06', 'legal_planner_acceptance': 'SYNTHETIC_PLANAR_W2'}
for kind in ('numerical', 'ros', 'a01', 'a02', 'a03', 'a04', 'a05', 'a05-oracle',
             'a06', 'a06-independent', 'a06-oracle', 'w2-pipeline', 'w1-installed',
             'w2-installed'):
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
