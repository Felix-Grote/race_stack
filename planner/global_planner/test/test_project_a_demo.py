"""Project A demo tests: real numerical implementations, no mocks.

Run with the pinned environment (scripts/setup_project_a_demo.sh):
  PYTHONPATH=planner/global_planner .venv-demo/bin/python -m pytest \
    planner/global_planner/test/test_project_a_demo.py -q
Compile tests are marked slow because each real IQP compile takes ~10-20 s.
"""
import copy
import dataclasses
import importlib.util
import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "planner" / "global_planner"))

from demo_project_a import fixtures as fx  # noqa: E402
from demo_project_a import visualize as viz  # noqa: E402
from global_planner.route_artifact import ArtifactError, load_reference  # noqa: E402
from global_planner.route_compile import (  # noqa: E402
    compile_reference, load_policy, load_vehicle_config)
from global_planner.route_input import RouteError, validate_route  # noqa: E402

CONFIG = ROOT / "planner/global_planner/config/project_a"
POLICY = CONFIG / "policies" / "synthetic_policy.json"
COMMITTED_FIXTURES = (ROOT / "planner/global_planner/demo_project_a"
                      / "fixtures")


def _load_runner():
    spec = importlib.util.spec_from_file_location(
        "run_project_a_demo", ROOT / "scripts/run_project_a_demo.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = _load_runner()


@pytest.fixture(scope="module")
def manifests(tmp_path_factory):
    out = tmp_path_factory.mktemp("fixtures")
    return fx.generate_all(str(out))


def _compile(name, manifest_doc, out, model_name="s0_route_model.json",
             footprint=None):
    policies, context, spacing = load_policy(str(POLICY))
    model, fp = load_vehicle_config(str(CONFIG / "models" / model_name))
    route = validate_route(manifest_doc)
    res = compile_reference(route, model, footprint or fp, policies,
                            output_dir=str(out), retime_spacing_m=spacing,
                            validation_context=context)
    return res, context


def test_fixture_determinism(manifests, tmp_path):
    again = fx.generate_all(str(tmp_path / "again"))
    for name, path in manifests.items():
        assert Path(path).read_bytes() == again[name].read_bytes(), name


def test_committed_fixtures_match_generator(manifests):
    """Byte-equivalence gate: committed JSON == freshly generated JSON.

    Skipped while the fixtures data PR has not landed (logic PR alone
    carries no committed fixture files by design).
    """
    committed = sorted(COMMITTED_FIXTURES.glob("*.json"))
    if not committed:
        pytest.skip("no committed fixtures (data PR not landed)")
    assert {p.stem for p in committed} == set(manifests), (
        "committed fixture set must equal generator scenario set")
    for path in committed:
        assert path.read_bytes() == Path(manifests[path.stem]).read_bytes(), path.name


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


def test_a1_whole_occurrence_translation_is_disconnected(manifests):
    """Internally-valid o1, broken portal continuity -> disconnected seeds."""
    base = json.loads(Path(manifests["s0"]).read_text())
    bad = copy.deepcopy(base)
    for key in ("seed", "left", "right"):
        for pt in bad["occurrences"][1][key]:
            pt[0] += 5.0
    with pytest.raises(RouteError, match="disconnected portal seeds"):
        validate_route(bad)


def test_a2_reversed_gate_fires_endcap_check(manifests):
    """Gate reversal fails end-cap correspondence before the direction check.

    The direction check ('wrong directed gate') is unreachable by this
    mutation given the validator's check order and ribbon-confined
    seeds; this test pins the check that actually fires.
    """
    base = json.loads(Path(manifests["s0"]).read_text())
    bad = copy.deepcopy(base)
    bad["transitions"][0]["gate"] = bad["transitions"][0]["gate"][::-1]
    with pytest.raises(RouteError, match="invalid portal end caps"):
        validate_route(bad)


def test_report_rows_short_hash_and_missing_cells():
    rows = [{"scenario": "s0", "compile": "PASS", "geo": "PASS",
             "dyn": "PASS", "length_m": 41.287, "lap_s": 13.762,
             "runtime_s": 13.1, "solver_iters": 3,
             "curv_energy_delta_pct": -39.1,
             "H": "b26dd9942cfa1234567890abcdef"},
            {"scenario": "bad", "compile": "FAIL", "H": None}]
    table = viz.report_rows(rows)
    assert table[0][-1] == "b26dd9942cfa"
    assert table[0][viz.REPORT_COLS.index("solver_iters")] == "3"
    assert table[1][-1] == "-"


def test_occurrence_boundaries_only_on_change():
    samples = [SimpleNamespace(s=s, occurrence_id=o) for s, o in
               [(0.0, "o0"), (0.2, "o0"), (0.4, "o1"), (0.6, "o1"),
                (0.8, "o2")]]
    # No spurious boundary at the first s>0 sample of the first owner.
    assert viz.occurrence_boundaries(samples) == [0.4, 0.8]


def test_summarize_run_report_trims_bulk_traces():
    run = {"phases": {"optimization": {"wall_seconds": 1.0}},
           "wall_seconds": 2.0, "cpu_seconds": 1.5,
           "solver_iteration_count": 1,
           "solver_iterations": [{
               "number": 0, "source_curvature_energy": 2.0,
               "reference_curvature_energy": 1.8,
               "shifted_curvature_energy": 1.5,
               "shifted_curvature_max": 0.4,
               "coefficients": tuple(range(10000)),
               "corridors": tuple(range(10000))}],
           "retimer": {"status": "CANDIDATE"}}
    summary = runner.summarize_run_report(run)
    assert summary["solver_iterations"][0]["shifted_curvature_energy"] == 1.5
    assert "coefficients" not in summary["solver_iterations"][0]
    assert runner._energy_delta_pct(summary) == -25.0


def test_suite_ok_enforces_adversarial_and_nonempty():
    good_adv = {c: {"ok": True} for c in runner.ADVERSARIAL_CASES}
    rows = [{"compile": "PASS"}]
    assert runner.suite_ok(rows, good_adv, True, True)
    assert not runner.suite_ok([], good_adv, True, True)  # empty suite
    assert not runner.suite_ok(rows, {}, True, True)  # adversarial missing
    bad_adv = dict(good_adv, B_tampered_artifact={"ok": False})
    assert not runner.suite_ok(rows, bad_adv, True, True)  # wrong accept
    assert not runner.suite_ok([{"compile": "FAIL"}], good_adv, True, True)


@pytest.mark.slow
def test_s0_compile_reload_query_and_tamper(manifests, tmp_path):
    doc = json.loads(Path(manifests["s0"]).read_text())
    res, context = _compile("s0", doc, tmp_path / "out")
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
    # run_report diagnostics are actually produced by the compiler
    report = runner.summarize_run_report(res.run_report)
    assert report["solver_iteration_count"] >= 1
    assert report["solver_iterations"]
    # Valid-JSON tamper under original H must fail the trusted-H check,
    # not a parse error.
    dst = tmp_path / "tampered"
    shutil.copytree(Path(res.artifact_path).parent, dst)
    target = dst / "reference.json"
    target.chmod(0o644)
    data = target.read_text()
    mutated = data.replace('"speed_max_mps":3.0', '"speed_max_mps":9.0', 1)
    assert mutated != data
    json.loads(mutated)
    target.write_text(mutated)
    with pytest.raises(ArtifactError,
                       match="externally trusted artifact H mismatch"):
        load_reference(str(dst), expected_H=res.H, validation_context=context)


@pytest.mark.slow
def test_s1_both_routes_compile(manifests, tmp_path):
    lengths = {}
    for name in ("s1_route_a", "s1_route_b"):
        doc = json.loads(Path(manifests[name]).read_text())
        res, context = _compile(name, doc, tmp_path / name)
        assert res.status == "PASS", (name, res.reason)
        ref = load_reference(res.artifact_path, expected_H=res.H,
                             validation_context=context)
        lengths[name] = ref.length
    # Route B's taller northern branch is the longer lap.
    assert lengths["s1_route_b"] > lengths["s1_route_a"]


@pytest.mark.slow
def test_s2_compile_ownership_at_crossing(manifests, tmp_path):
    doc = json.loads(Path(manifests["s2"]).read_text())
    res, context = _compile("s2", doc, tmp_path / "s2",
                            model_name="s3_surfaces_route_model.json")
    assert res.status == "PASS", res.reason
    ref = load_reference(res.artifact_path, expected_H=res.H,
                         validation_context=context)
    samples = ref.window(0.0, ref.length, 0.1)
    near = [s for s in samples if abs(s.xy[0]) + abs(s.xy[1]) < 0.75]
    assert {s.occurrence_id for s in near} >= {"o0", "o2"}, (
        "accepted reference must show both owners at the XY crossing")
    o2_speeds = [s.speed_mps for s in samples if s.occurrence_id == "o2"]
    assert o2_speeds and max(o2_speeds) <= 2.5 + 1e-9  # upper-deck cap


@pytest.mark.slow
def test_s4_braking_rich_nonflat_profile(manifests, tmp_path):
    doc = json.loads(Path(manifests["s4"]).read_text())
    res, context = _compile("s4", doc, tmp_path / "s4")
    assert res.status == "PASS", res.reason
    ref = load_reference(res.artifact_path, expected_H=res.H,
                         validation_context=context)
    samples = ref.window(0.0, ref.length, 0.25)
    speeds = [s.speed_mps for s in samples]
    assert max(speeds) - min(speeds) > 0.3, "S4 speed profile must be non-flat"
    assert any(s.acceleration_mps2 < -0.05 for s in samples), "braking zones"
    assert any(s.acceleration_mps2 > 0.05 for s in samples), "acceleration zones"
    a, b = ref.sample(0.0), ref.sample(ref.length)
    assert a.xy == pytest.approx(b.xy, abs=1e-6)  # cyclic


@pytest.mark.slow
def test_c_tight_hairpin_optimizer_geometry_failure(tmp_path):
    doc = fx.build_manifest("demo-s3", "s3-tight-hairpin",
                            fx.ellipse_points(a=3.0, b=1.1), ["ground"] * 4)
    res, _ = _compile("tight", doc, tmp_path / "tight")
    assert res.status == "GEOMETRY_FAILURE"
    assert "folded/degenerate local chart" in (res.reason or "")
    assert res.artifact_path is None


@pytest.mark.slow
def test_d_oversized_footprint_rejected_by_geometry_validator(
        manifests, tmp_path):
    doc = json.loads(Path(manifests["s0"]).read_text())
    policies, context, spacing = load_policy(str(POLICY))
    _, footprint = load_vehicle_config(
        str(CONFIG / "models" / "s0_route_model.json"))
    wide = dataclasses.replace(footprint, width_m=1.9)
    res, _ = _compile("wide", doc, tmp_path / "wide", footprint=wide)
    assert res.status == "FAIL"
    assert res.geometry is not None and res.geometry.status != "PASS"
    assert res.artifact_path is None
