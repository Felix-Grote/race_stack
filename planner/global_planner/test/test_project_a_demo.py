"""Project A demo tests: real numerical implementations, no mocks.

Run with the pinned environment:
  PYTHONPATH=planner/global_planner .venv-demo/bin/python -m pytest \
    planner/global_planner/test/test_project_a_demo.py -q
Compile tests are marked slow because each real IQP compile takes ~10-20 s.
"""
import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "planner" / "global_planner"))

from demo_project_a import fixtures as fx  # noqa: E402
from global_planner.route_artifact import ArtifactError, load_reference  # noqa: E402
from global_planner.route_compile import (  # noqa: E402
    compile_reference, load_policy, load_vehicle_config)
from global_planner.route_input import RouteError, validate_route  # noqa: E402

CONFIG = ROOT / "planner/global_planner/config/project_a"
POLICY = CONFIG / "policies" / "synthetic_policy.json"


@pytest.fixture(scope="module")
def manifests(tmp_path_factory):
    out = tmp_path_factory.mktemp("fixtures")
    return fx.generate_all(str(out))


def test_fixture_determinism(manifests, tmp_path):
    again = fx.generate_all(str(tmp_path / "again"))
    for name, path in manifests.items():
        assert Path(path).read_bytes() == again[name].read_bytes(), name


def test_all_manifests_validate(manifests):
    for name, path in manifests.items():
        route = validate_route(json.loads(Path(path).read_text()))
        assert [o.id for o in route.occurrences] == ["o0", "o1", "o2", "o3"], name
        assert len(route.portals) == 4


def test_s2_overlapping_xy_distinct_surfaces(manifests):
    route = validate_route(json.loads(Path(manifests["s2"]).read_text()))
    owners = [(o.id, o.surface_id) for o in route.occurrences]
    assert ("o2", "upper-deck") in owners
    # o0 and o2 both pass through the lemniscate crossing near the origin
    def near_origin(occ):
        return min((abs(x) + abs(y)) for x, y in occ.seed) < 1.5
    assert near_origin(route.occurrences[0]) and near_origin(route.occurrences[2])


def test_disconnected_and_wrong_direction_rejected(manifests):
    base = json.loads(Path(manifests["s0"]).read_text())
    bad = copy.deepcopy(base)
    for pt in bad["occurrences"][1]["seed"]:
        pt[0] += 5.0
    with pytest.raises(RouteError):
        validate_route(bad)
    bad = copy.deepcopy(base)
    bad["transitions"][0]["gate"] = bad["transitions"][0]["gate"][::-1]
    with pytest.raises(RouteError):
        validate_route(bad)


@pytest.mark.slow
def test_s0_compile_reload_query(manifests, tmp_path):
    policies, context, spacing = load_policy(str(POLICY))
    model, footprint = load_vehicle_config(
        str(CONFIG / "models" / "s0_route_model.json"))
    route = validate_route(json.loads(Path(manifests["s0"]).read_text()))
    res = compile_reference(route, model, footprint, policies,
                            output_dir=str(tmp_path / "out"),
                            retime_spacing_m=spacing, validation_context=context)
    assert res.status == "PASS", res.reason
    ref = load_reference(res.artifact_path, expected_H=res.H,
                         validation_context=context)
    assert ref.geometry_report.status == "PASS"
    assert ref.dynamics_report.status == "PASS"
    assert ref.length == pytest.approx(41.287, abs=0.05)
    assert ref.lap_time_s > 0
    a, b = ref.sample(0.0), ref.sample(ref.length)
    assert a.xy == pytest.approx(b.xy, abs=1e-6)  # cyclic closure
    speeds = [s.speed_mps for s in ref.window(0.0, ref.length, 0.5)]
    assert all(0 < v <= 3.0 + 1e-9 for v in speeds)
    # tampered copy under original H must be rejected by trusted loading
    import shutil
    dst = tmp_path / "tampered"
    shutil.copytree(Path(res.artifact_path).parent, dst)
    target = dst / "reference.json"
    target.chmod(0o644)
    target.write_text(target.read_text()[:-30] + "x" + target.read_text()[-29:])
    with pytest.raises(ArtifactError):
        load_reference(str(dst), expected_H=res.H, validation_context=context)
