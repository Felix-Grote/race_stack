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
from demo_project_a.s5_stress import generator as s5gen  # noqa: E402
from demo_project_a import visualize as viz  # noqa: E402
from global_planner.route_artifact import ArtifactError, load_reference  # noqa: E402
from global_planner.route_compile import (  # noqa: E402
    compile_reference, load_policy, load_vehicle_config)
from global_planner.route_input import RouteError, validate_route  # noqa: E402

CONFIG = ROOT / "planner/global_planner/config/project_a"
POLICY = CONFIG / "policies" / "synthetic_policy.json"
S5_POLICY = CONFIG / "policies" / "s5_stress_policy.json"
S5_ROUTES = ["s5_p1", "s5_p2", "s5_p3", "s5_p4"]
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
             policy_path=POLICY, footprint=None):
    policies, context, spacing = load_policy(str(policy_path))
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

    On the logic PR alone there is intentionally no fixtures directory
    and the gate skips -- that is the only skip path. Once the fixtures
    directory exists (the combined stack) every missing, extra or
    differing file FAILS. Setting PROJECT_A_REQUIRE_FIXTURES=1 (the
    final stacked verification configuration) also turns a missing
    directory into a failure instead of a skip.
    """
    import os
    committed = sorted(COMMITTED_FIXTURES.glob("*.json"))
    if not committed:
        if os.environ.get("PROJECT_A_REQUIRE_FIXTURES") == "1":
            pytest.fail("committed fixtures required but none present")
        if COMMITTED_FIXTURES.is_dir():
            pytest.fail("fixtures directory present but empty")
        pytest.skip("no committed fixtures directory (logic PR alone)")
    assert {p.stem for p in committed} == set(manifests), (
        "committed fixture set must equal generator scenario set")
    for path in committed:
        assert path.read_bytes() == Path(manifests[path.stem]).read_bytes(), path.name


def test_all_manifests_validate(manifests):
    for name, path in manifests.items():
        route = validate_route(json.loads(Path(path).read_text()))
        assert [o.id for o in route.occurrences] == ["o0", "o1", "o2", "o3"], name
        assert len(route.portals) == 4


def test_s5_manifests_shape_via_generator(tmp_path):
    """S5 Grand Challenge: 24 occurrences, 24 portals, cyclic closure shape.

    Fast (no optimizer): builds all four route variants from the
    deterministic generator and checks validated route shape — occurrence
    and portal counts, gate sequence, closing finish and init origin.
    """
    out = s5gen.generate_all(str(tmp_path / "s5gen"))
    assert set(out) == set(S5_ROUTES) | {"world"}
    committed = (ROOT / "planner/global_planner/demo_project_a"
                 / "s5_stress" / "fixtures")
    for rid in S5_ROUTES:
        assert (committed / f"{rid}.json").read_bytes() == Path(out[rid]).read_bytes(), rid
    assert (committed / "s5_world.json").read_bytes() == Path(out["world"]).read_bytes()
    for rid in S5_ROUTES:
        doc = json.loads(Path(out[rid]).read_text())
        route = validate_route(doc)
        assert [o.id for o in route.occurrences] == [
            "o0", "o1", "o2", "o3", "o4", "o5", "o6", "o7", "o8", "o9",
            "o10", "o11", "o12", "o13", "o14", "o15", "o16a", "o16b",
            "o17", "o18", "o19", "o20", "o21", "o22"], rid
        assert len(route.portals) == 24, rid
        assert doc["gate_sequence"] == [f"p{i}" for i in range(24)], rid
        assert doc["finish"] == "p23", rid
        assert doc["initialization"]["occurrence_id"] == "o0", rid


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


def test_exact_occurrence_boundaries_refine_grid():
    class FakeRef:
        def sample(self, s):
            return SimpleNamespace(
                occurrence_id="o0" if s < 0.31 else "o1")
    samples = [SimpleNamespace(s=s, occurrence_id=o) for s, o in
               [(0.0, "o0"), (0.2, "o0"), (0.4, "o1"), (0.6, "o1")]]
    exact = viz.exact_occurrence_boundaries(FakeRef(), samples)
    assert exact == pytest.approx([0.31], abs=1e-9)


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


def _accepted_row(name):
    return {"scenario": name, "compile": "PASS", "reload": "PASS",
            "geo_reload": "PASS", "dyn_reload": "PASS",
            "cyclic_closure": True}


def test_suite_ok_exact_expected_set():
    good_adv = {c: {"ok": True} for c in runner.ADVERSARIAL_CASES}
    expected = ["s0", "s2"]
    rows = [_accepted_row("s0"), _accepted_row("s2")]
    assert runner.suite_ok(rows, good_adv, expected, True)
    assert runner.suite_ok(rows, {}, expected, False)
    # missing scenario result
    assert not runner.suite_ok(rows[:1], good_adv, expected, True)
    # empty suite
    assert not runner.suite_ok([], good_adv, expected, True)
    # duplicate scenario results
    assert not runner.suite_ok(rows + [_accepted_row("s0")], good_adv,
                               expected, True)
    # unexpected scenario result
    assert not runner.suite_ok(rows + [_accepted_row("s9")], good_adv,
                               expected, True)
    # compiled but never reloaded/validated
    unreloaded = [_accepted_row("s0"),
                  {"scenario": "s2", "compile": "PASS"}]
    assert not runner.suite_ok(unreloaded, good_adv, expected, True)
    # compile failure
    failed = [dict(_accepted_row("s0"), compile="FAIL"),
              _accepted_row("s2")]
    assert not runner.suite_ok(failed, good_adv, expected, True)
    # adversarial missing / wrong-accept / unexpected extra case
    assert not runner.suite_ok(rows, {}, expected, True)
    bad_adv = dict(good_adv, B_tampered_artifact={"ok": False})
    assert not runner.suite_ok(rows, bad_adv, expected, True)
    extra_adv = dict(good_adv, Z_extra={"ok": True})
    assert not runner.suite_ok(rows, extra_adv, expected, True)


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


def _seg_cross(o, a, b):
    return ((a[0] - o[0]) * (b[1] - o[1])
            - (a[1] - o[1]) * (b[0] - o[0]))


def _segment_intersection(p1, p2, p3, p4):
    """Proper intersection point of segments p1p2/p3p4, or None."""
    d1, d2 = _seg_cross(p3, p4, p1), _seg_cross(p3, p4, p2)
    d3, d4 = _seg_cross(p1, p2, p3), _seg_cross(p1, p2, p4)
    if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)):
        t = d1 / (d1 - d2)
        return (p1[0] + t * (p2[0] - p1[0]), p1[1] + t * (p2[1] - p1[1]))
    return None


@pytest.mark.slow
def test_s2_compile_ownership_at_crossing(manifests, tmp_path):
    doc = json.loads(Path(manifests["s2"]).read_text())
    res, context = _compile("s2", doc, tmp_path / "s2",
                            model_name="s3_surfaces_route_model.json")
    assert res.status == "PASS", res.reason
    ref = load_reference(res.artifact_path, expected_H=res.H,
                         validation_context=context)
    # Independent validators pass on the accepted reference itself.
    assert ref.geometry_report.status == "PASS"
    assert ref.dynamics_report.status == "PASS"
    # Dense evaluation of the accepted coefficients via the public
    # query API (not seed geometry, not plotting interpolation).
    samples = [s for s in ref.window(0.0, ref.length, 0.05)
               if s.s < ref.length - 1e-9]  # drop cyclic seam repeat
    # Route ordering: owners appear exactly in declared cycle order,
    # so the XY overlap creates no undeclared transition. The lap
    # seam lies inside o0 (finish gate p3 is the o3->o0 portal), so
    # the cyclic owner sequence starts and ends with o0.
    sequence = []
    for s in samples:
        if not sequence or sequence[-1] != s.occurrence_id:
            sequence.append(s.occurrence_id)
    assert sequence == ["o0", "o1", "o2", "o3", "o0"]
    # The optimized o0 and o2 sections genuinely intersect in XY.
    # Segments are consecutive sample pairs only, so the two disjoint
    # o0 chunks are never joined by a spurious cross-lap segment.
    def segments(occ):
        return [(a, b) for a, b in zip(samples, samples[1:])
                if a.occurrence_id == occ and b.occurrence_id == occ]
    hits = []
    for a, b in segments("o0"):
        for c, d in segments("o2"):
            hit = _segment_intersection(a.xy, b.xy, c.xy, d.xy)
            if hit:
                hits.append((hit, (a, b), (c, d)))
    assert hits, "optimized o0/o2 sections must intersect in XY"
    (hx, hy), (a, b), (c, d) = hits[0]
    # Intersection is the lemniscate crossing region (the optimized
    # line shifts it off the exact origin; 0.5 m bound vs ~0.3 m seen).
    assert abs(hx) < 0.5 and abs(hy) < 0.5
    # Both sides of the intersection retain occurrence AND surface
    # identity from the accepted reference.
    assert {a.occurrence_id, b.occurrence_id} == {"o0"}
    assert {a.surface_id, b.surface_id} == {"ground"}
    assert {c.occurrence_id, d.occurrence_id} == {"o2"}
    assert {c.surface_id, d.surface_id} == {"upper-deck"}
    # Upper-deck declared speed limit respected on the accepted ref.
    o2_speeds = [s.speed_mps for s in samples if s.occurrence_id == "o2"]
    assert o2_speeds and max(o2_speeds) <= 2.5 + 1e-9


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
@pytest.mark.parametrize("route_id", S5_ROUTES)
def test_s5_compile_reload_query(route_id, tmp_path):
    """S5 Grand Challenge: compile -> reload -> query for each route.

    Mirrors the S0/S2/S4 slow tests with the S5 policy and per-route
    model: PASS compile, PASS geometry/dynamics on the trusted reload,
    cyclic closure, and per-sample compliance with the declared
    occurrence caps (spotlighting the A1/A2 and B1/B2 discriminators).
    Requires the pinned environment; publication needs a namespace the
    publisher controls (see route_artifact publication rules).
    """
    ba, bb = s5gen.ROUTES[route_id]
    doc = s5gen.build_manifest(f"demo-s5-{route_id}", ba, bb)
    res, context = _compile(route_id, doc, tmp_path / route_id,
                            model_name=f"{route_id}_model.json",
                            policy_path=S5_POLICY)
    assert res.status == "PASS", res.reason
    ref = load_reference(res.artifact_path, expected_H=res.H,
                         validation_context=context)
    assert ref.geometry_report.status == "PASS"
    assert ref.dynamics_report.status == "PASS"
    a, b = ref.sample(0.0), ref.sample(ref.length)
    assert a.xy == pytest.approx(b.xy, abs=1e-6)  # cyclic closure
    caps = s5gen.caps_for(ba, bb)
    samples = ref.window(0.0, ref.length, 0.25)
    assert samples
    for s in samples:
        assert 0 < s.speed_mps <= caps[s.occurrence_id] + 1e-9, (
            route_id, s.occurrence_id, s.speed_mps)
    by_occ = {}
    for s in samples:
        by_occ.setdefault(s.occurrence_id, []).append(s.speed_mps)
    assert max(by_occ["o0"]) <= 7.0 + 1e-9
    o7_cap = 4.0 if ba == "A1" else 5.5
    o9_cap = 4.5 if bb == "B1" else 5.0
    assert max(by_occ["o7"]) <= o7_cap + 1e-9, (route_id, ba)
    assert max(by_occ["o9"]) <= o9_cap + 1e-9, (route_id, bb)


@pytest.mark.slow
def test_s5_cli_end_to_end(tmp_path):
    """Real runner subprocess: --scenario s5 compiles all four routes."""
    script = ROOT / "scripts" / "run_project_a_demo.py"
    out = tmp_path / "s5_run"
    # Measured serial compile total is 268.1 + 247.8 + 259.7 + 231.9 =
    # 1007.5 s on the pinned env, before figure rendering; 1500 s covers
    # that plus rendering/startup overhead and machine variance.
    proc = _run_cli(script, out, "s5", timeout=1500)
    assert proc.returncode == 0, proc.stdout[-2000:] + proc.stderr[-2000:]
    summary = json.loads((out / "summary.json").read_text())
    assert summary["suite_ok"] is True
    assert [r["scenario"] for r in summary["scenarios"]] == S5_ROUTES
    for row in summary["scenarios"]:
        assert row["compile"] == "PASS", row
        assert row["reload"] == "PASS", row
        assert row["geo_reload"] == "PASS", row
        assert row["dyn_reload"] == "PASS", row


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
    # Optimizer produced a candidate first (iterations recorded, the
    # optimization phase ran) and the geometry phase then executed.
    report = res.run_report
    assert report["solver_iteration_count"] >= 1
    assert {"optimization", "geometry"} <= set(report["phases"])
    # Rejection is specifically the footprint-containment check:
    # structured coverage + identified offending interval + reason.
    geo = res.geometry
    assert geo is not None and geo.status == "FAIL"
    assert "reference_aligned_rectangle" in geo.coverage
    assert geo.offending_interval
    assert "rectangle" in res.reason and "exit" in res.reason
    assert res.artifact_path is None


def _run_cli(script, out_dir, scenario, timeout=900):
    import os
    import subprocess
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "planner" / "global_planner")
    return subprocess.run(
        [sys.executable, str(script), "--scenario", scenario,
         "--out", str(out_dir)], capture_output=True, text=True,
        timeout=timeout, env=env)


def _run_s3_cli(script, out_dir):
    return _run_cli(script, out_dir, "s3")


@pytest.mark.slow
def test_s3_cli_end_to_end(tmp_path):
    """Real runner subprocess: S0 auto-compiled, all cases enforced."""
    script = ROOT / "scripts" / "run_project_a_demo.py"
    out = tmp_path / "s3_run"
    proc = _run_s3_cli(script, out)
    assert proc.returncode == 0, proc.stdout[-2000:] + proc.stderr[-2000:]
    summary = json.loads((out / "summary.json").read_text())
    assert summary["suite_ok"] is True
    # S0 prerequisite was compiled automatically and accepted.
    assert [r["scenario"] for r in summary["scenarios"]] == ["s0"]
    s0 = summary["scenarios"][0]
    assert s0["compile"] == "PASS" and s0["reload"] == "PASS"
    assert s0["geo_reload"] == "PASS" and s0["dyn_reload"] == "PASS"
    # All five adversarial cases executed and rejected as specified.
    adv = summary["adversarial"]
    assert set(adv) == set(runner.ADVERSARIAL_CASES)
    assert all(case["ok"] for case in adv.values())
    assert "RouteError: disconnected portal seeds" in (
        adv["A1_disconnected"]["observed"])
    assert "RouteError: invalid portal end caps" in (
        adv["A2_reversed_gate_endcaps"]["observed"])
    assert "ArtifactError" in adv["B_tampered_artifact"]["observed"]
    # No negative case published an accepted reference.
    assert adv["C_optimizer_geometry_failure"]["artifact"] is None
    assert adv["D_validator_geometry_rejection"]["artifact"] is None
    for sub in ("s3_tight", "s3_wide_footprint"):
        assert not list((out / sub).rglob("reference.json"))


@pytest.mark.slow
def test_s3_cli_failure_path_wrong_adversarial_expectation(tmp_path):
    """If an adversarial case does not reject *as specified*, CLI fails.

    Runs a copy of the real runner (real compiler, real CLI) whose A1
    expected-reason string is sabotaged, in a scratch tree holding a
    plain copy of the planner package (the trusted loader rejects
    symlinked directories). A1 still raises RouteError, but not with
    the expected reason, so the case must flip to not-ok and exit 1.
    """
    root = tmp_path / "tree"
    (root / "scripts").mkdir(parents=True)
    shutil.copytree(ROOT / "planner" / "global_planner",
                    root / "planner" / "global_planner",
                    ignore=shutil.ignore_patterns("output", "__pycache__"))
    source = (ROOT / "scripts" / "run_project_a_demo.py").read_text()
    sabotaged = source.replace('"disconnected portal seeds"',
                               '"nonexistent expected reason"', 1)
    assert sabotaged != source
    script = root / "scripts" / "run_project_a_demo.py"
    script.write_text(sabotaged)
    out = tmp_path / "s3_fail_run"
    proc = _run_s3_cli(script, out)
    assert proc.returncode == 1, proc.stdout[-2000:] + proc.stderr[-2000:]
    summary = json.loads((out / "summary.json").read_text())
    assert summary["suite_ok"] is False
    adv = summary["adversarial"]
    assert adv["A1_disconnected"]["ok"] is False
    assert "RouteError: disconnected portal seeds" in (
        adv["A1_disconnected"]["observed"])
    assert all(case["ok"] for name, case in adv.items()
               if name != "A1_disconnected")
