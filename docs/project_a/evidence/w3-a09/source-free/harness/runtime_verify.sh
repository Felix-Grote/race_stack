#!/usr/bin/env bash
# This script is copied alone with the installed-interface test, never the repository.
set -eo pipefail
source /opt/ros/humble/setup.bash
export PYTHONPATH=/work/python
source /work/install/setup.bash
cd /results
python -m pip check
python -m pip freeze --all > /results/runtime-dependencies.txt
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q -p no:cacheprovider \
  /runtime-harness/test_w3_installed.py \
  /runtime-harness/test_w3_scenario_installed.py --junitxml=/results/w3-source-free.xml
