#!/bin/bash
set -eo pipefail
source /opt/ros/humble/setup.bash
export PYTHONPATH=/work/python
source /work/install/setup.bash
exec python /harness/verify.py
