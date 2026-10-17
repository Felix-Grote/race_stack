#!/usr/bin/env bash
set -eo pipefail
source /opt/ros/humble/setup.bash
python /src/scripts/project_a/source_manifest.py --repository /src > /work/source-hashes-before.json
mkdir -p /work/src
cp -a /src/planner/global_planner /work/src/
cp -a /src/utilities/libraries/f110_msgs /src/utilities/libraries/frenet_conversion /work/src/
python /src/scripts/project_a/source_manifest.py --repository /src --build-identity /work/src/global_planner/config/project_a/build_identity.json
cp /work/src/global_planner/config/project_a/build_identity.json /work/build-identity.json
python /usr/bin/colcon --log-base /work/log build --base-paths /work/src --build-base /work/build --install-base /work/install --packages-select f110_msgs frenet_conversion global_planner --parallel-workers 2
optimizer=/work/src/global_planner/global_planner/global_racetrajectory_optimization
(cd "$optimizer" && python setup.py bdist_wheel --dist-dir /work/wheels) > /work/optimizer-wheel.log 2>&1
python -m pip install --no-index --no-deps --target /work/python /work/wheels/*.whl
python /src/scripts/project_a/source_manifest.py --repository /src > /work/source-hashes-after.json
cmp /work/source-hashes-before.json /work/source-hashes-after.json
