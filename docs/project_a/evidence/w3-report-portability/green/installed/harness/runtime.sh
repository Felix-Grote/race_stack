#!/usr/bin/env bash
set -eo pipefail
source /opt/ros/humble/setup.bash
export PYTHONPATH=/work/python
source /work/install/setup.bash
cd /results
python -m flake8 --max-line-length=99 /runtime-harness/test_w3_installed.py
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q -p no:cacheprovider /runtime-harness/test_w3_installed.py --junitxml=/results/installed-replay.xml
