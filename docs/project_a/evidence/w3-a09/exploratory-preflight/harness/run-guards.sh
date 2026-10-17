#!/usr/bin/env bash
set -eo pipefail
source /opt/ros/humble/setup.bash
cd /results
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q -p no:cacheprovider /runtime-harness/tests/test_w3_harness.py --junitxml=/results/guard-preflight.xml
