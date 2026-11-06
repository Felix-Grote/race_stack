#!/usr/bin/env python3
"""Reproducible Project A (W1-W3) offline global-planner demonstration.

Usage (requires the pinned Python 3.10.12 environment, see DEMO_README.md):
  .venv-demo/bin/python scripts/run_project_a_demo.py --all
  .venv-demo/bin/python scripts/run_project_a_demo.py --scenario s2
  .venv-demo/bin/python scripts/run_project_a_demo.py --scenario s3

Writes only into a NEW run-specific output directory (immutable artifacts
are never overwritten). No ROS node, vehicle, LiDAR or actuation is used.

Exit status is 0 only when every requested positive scenario compiles
PASS *and* (for --all / --scenario s3) every adversarial case rejects
exactly as specified -- exception class and reason, or non-PASS status
with no published artifact. An empty or partially-run suite is nonzero.
"""
import argparse
import copy
import dataclasses
import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "planner" / "global_planner"))

from demo_project_a import fixtures as fx  # noqa: E402
from demo_project_a import visualize as viz  # noqa: E402
from global_planner.route_artifact import ArtifactError, load_reference  # noqa: E402
from global_planner.route_compile import (  # noqa: E402
    load_policy, load_vehicle_config, compile_reference)
from global_planner.route_input import RouteError, load_route, validate_route  # noqa: E402

CONFIG = ROOT / "planner/global_planner/config/project_a"
MODELS = {"s0": "s0_route_model.json", "s1_route_a": "s0_route_model.json",
          "s1_route_b": "s0_route_model.json", "s2": "s3_surfaces_route_model.json",
          "s4": "s0_route_model.json"}
TITLES = {"s0": "S0 conventional closed circuit (ellipse, varied curvature)",
          "s1_route_a": "S1 Route A (compact northern branch)",
          "s1_route_b": "S1 Route B (taller northern branch)",
          "s2": "S2 bridge / overlapping XY (lemniscate, o2 on upper-deck)",
          "s4": "S4 braking/acceleration-rich circuit (eccentric ellipse, narrow corridor)"}
ALL_POSITIVE = ["s0", "s1_route_a", "s1_route_b", "s2", "s4"]
ADVERSARIAL_CASES = ["A1_disconnected", "A2_reversed_gate_endcaps",
                     "B_tampered_artifact", "C_optimizer_geometry_failure",
                     "D_validator_geometry_rejection"]


def summarize_run_report(run):
    """Trim CompileResult.run_report to JSON-safe diagnostics.

    Keeps phase timings, solver iteration count and per-iteration
    curvature energies, and retimer stats. Drops the bulk per-iteration
    coefficient/corridor tuples, which are neither small nor evidence
    a reader can check by eye.
    """
    if not isinstance(run, dict):
        return {}
    iterations = []
    for trace in run.get("solver_iterations") or []:
        if isinstance(trace, dict):
            iterations.append({
                "number": trace.get("number"),
                "source_curvature_energy": trace.get("source_curvature_energy"),
                "reference_curvature_energy": trace.get("reference_curvature_energy"),
                "shifted_curvature_energy": trace.get("shifted_curvature_energy"),
                "shifted_curvature_max": trace.get("shifted_curvature_max")})
    return {"phases": run.get("phases"),
            "wall_seconds": run.get("wall_seconds"),
            "cpu_seconds": run.get("cpu_seconds"),
            "solver_iteration_count": run.get("solver_iteration_count"),
            "solver_iterations": iterations,
            "retimer": run.get("retimer")}


def _energy_delta_pct(summary):
    its = summary.get("solver_iterations") or []
    if not its:
        return None
    src = its[0].get("source_curvature_energy")
    opt = its[-1].get("shifted_curvature_energy")
    if not src or opt is None:
        return None
    return round(100.0 * (opt - src) / src, 1)


def compile_one(name, manifest_path, out_dir, policies, context, spacing):
    model_doc_path = CONFIG / "models" / MODELS[name]
    model, footprint = load_vehicle_config(str(model_doc_path))
    route = load_route(str(manifest_path))
    began = time.monotonic()
    res = compile_reference(route, model, footprint, policies,
                            output_dir=str(out_dir / name),
                            retime_spacing_m=spacing,
                            validation_context=context)
    wall = time.monotonic() - began
    report = summarize_run_report(res.run_report)
    row = {"scenario": name, "compile": res.status, "reason": res.reason,
           "geo": res.geometry.status if res.geometry else None,
           "dyn": res.dynamics.status if res.dynamics else None,
           "H": res.H, "runtime_s": round(wall, 2),
           "artifact_path": res.artifact_path,
           "solver_iters": report.get("solver_iteration_count"),
           "curv_energy_delta_pct": _energy_delta_pct(report),
           "run_report": report}
    ref = None
    if res.status == "PASS":
        ref = load_reference(res.artifact_path, expected_H=res.H,
                             validation_context=context)
        row.update(length_m=round(ref.length, 3), lap_s=round(ref.lap_time_s, 3),
                   reload="PASS", geo_reload=ref.geometry_report.status,
                   dyn_reload=ref.dynamics_report.status)
        # cyclic continuity probe through the public query API
        a = ref.sample(0.0)
        b = ref.sample(ref.length)
        row["cyclic_closure"] = bool(
            abs(a.xy[0] - b.xy[0]) < 1e-6 and abs(a.xy[1] - b.xy[1]) < 1e-6)
        samples = ref.window(0.0, ref.length, 0.25)
        speeds = [s.speed_mps for s in samples]
        row["speed_min_mps"] = round(min(speeds), 3)
        row["speed_max_mps"] = round(max(speeds), 3)
        row["occurrence_transitions_s"] = [
            round(s_at, 4)
            for s_at in viz.refined_occurrence_boundaries(ref, samples)]
        row.update(_normalized_progress_position(route, ref))
    return row, ref, route


def _normalized_progress_position(route, ref, stations=256):
    """Initial-vs-optimized displacement at equal normalized progress.

    Method (exactly as reported): both the seed curve and the accepted
    reference are evaluated at `stations` equal fractions of their own
    total arclength; the metric is the RMS and maximum Euclidean
    distance between corresponding points. This measures how far the
    optimizer moved the line at comparable relative locations; it is
    not a closest-point (perpendicular) distance.
    """
    from global_planner.route_corridor import seed_curve
    seed = seed_curve(route).curve
    seed_samples = seed.window(0.0, seed.length, seed.length / 2048)
    dists = []
    for i in range(stations):
        frac = i / stations
        opt = ref.sample(frac * ref.length)
        j = round(frac * (len(seed_samples) - 1))
        ini = seed_samples[j]
        dists.append(((opt.xy[0] - ini.xy[0]) ** 2
                      + (opt.xy[1] - ini.xy[1]) ** 2) ** 0.5)
    rms = (sum(d * d for d in dists) / len(dists)) ** 0.5
    return {"normalized_progress_position_rms_m": round(rms, 4),
            "normalized_progress_position_max_m": round(max(dists), 4)}


def _expect_route_error(doc, reason_substring):
    try:
        validate_route(doc)
    except RouteError as exc:
        return reason_substring in str(exc), f"RouteError: {exc}"
    return False, "ACCEPTED!"


def adversarial(paths, out_dir, context, policies, spacing, good):
    """Five negative cases across four stages; each records its own ok flag.

    A1 input validation (portal continuity), A2 input validation (portal
    end caps), B trusted loading (artifact integrity), C optimizer-prep
    geometry failure, D independent geometry-validator rejection. None
    may yield an accepted reference; a wrong exception class, wrong
    reason, PASS status or published artifact flips that case's ok flag.
    """
    results = {}
    base = json.loads(Path(paths["s0"]).read_text())
    # Case A1: true disconnected transition. Translate the WHOLE o1
    # occurrence (seed and both corridors), so o1 stays internally valid
    # and only inter-occurrence portal continuity is broken.
    bad = copy.deepcopy(base)
    for key in ("seed", "left", "right"):
        for pt in bad["occurrences"][1][key]:
            pt[0] += 5.0
    ok, observed = _expect_route_error(bad, "disconnected portal seeds")
    results["A1_disconnected"] = {
        "expected": "RouteError: disconnected portal seeds",
        "observed": observed, "ok": ok}
    # Case A2: reversed portal gate. The validator checks end-cap
    # correspondence before gate direction, and with seeds confined to
    # their ribbons the travel vector's gate-normal component is forced
    # positive -- so the 'wrong directed gate' check is unreachable by
    # gate reversal (defence in depth). This case is named for the check
    # that actually fires.
    bad = copy.deepcopy(base)
    bad["transitions"][0]["gate"] = bad["transitions"][0]["gate"][::-1]
    ok, observed = _expect_route_error(bad, "invalid portal end caps")
    results["A2_reversed_gate_endcaps"] = {
        "expected": "RouteError: invalid portal end caps",
        "observed": observed, "ok": ok}
    # Case B: tampered artifact copy loaded under the original expected
    # H. The mutation is syntactically valid JSON (asserted), so the
    # rejection must come from the trusted-H check, not a parse error.
    src = Path(good["artifact_path"])
    dst = out_dir / "tampered" / src.parent.name
    shutil.copytree(src.parent, dst)
    target = dst / "reference.json"
    target.chmod(0o644)
    data = target.read_text()
    mutated = data.replace('"speed_max_mps":3.0', '"speed_max_mps":9.0', 1)
    mutation_valid = mutated != data
    if mutation_valid:
        json.loads(mutated)  # must stay parseable; raises if not
        target.write_text(mutated)
    try:
        load_reference(str(dst), expected_H=good["H"],
                       validation_context=context)
        results["B_tampered_artifact"] = {
            "expected": "ArtifactError: externally trusted artifact H mismatch",
            "observed": "ACCEPTED!", "ok": False}
    except ArtifactError as exc:
        results["B_tampered_artifact"] = {
            "expected": "ArtifactError: externally trusted artifact H mismatch",
            "observed": f"ArtifactError: {exc}"[:200],
            "ok": bool(mutation_valid
                       and "externally trusted artifact H mismatch" in str(exc))}
    except Exception as exc:  # wrong rejection mechanism: still a failure
        results["B_tampered_artifact"] = {
            "expected": "ArtifactError: externally trusted artifact H mismatch",
            "observed": f"{type(exc).__name__}: {exc}"[:200], "ok": False}
    model, footprint = load_vehicle_config(
        str(CONFIG / "models" / "s0_route_model.json"))
    # Case C: curvature-infeasible hairpin. Fails inside the optimizer's
    # corridor/geometry preparation (folded local chart), i.e. BEFORE the
    # independent geometry validator runs. Named accordingly.
    tight = fx.build_manifest("demo-s3", "s3-tight-hairpin",
                              fx.ellipse_points(a=3.0, b=1.1),
                              ["ground"] * 4)
    route = validate_route(tight)
    res = compile_reference(route, model, footprint, policies,
                            output_dir=str(out_dir / "s3_tight"),
                            retime_spacing_m=spacing,
                            validation_context=context)
    results["C_optimizer_geometry_failure"] = {
        "expected": "GEOMETRY_FAILURE (folded/degenerate local chart), no artifact",
        "observed": res.status, "reason": (res.reason or "")[:200],
        "artifact": res.artifact_path,
        "ok": bool(res.status == "GEOMETRY_FAILURE"
                   and "folded/degenerate local chart" in (res.reason or "")
                   and res.artifact_path is None)}
    # Case D: candidate that survives optimization but is rejected by the
    # independent geometry validator. The optimizer plans for the policy
    # vehicle width; compiling the valid S0 route against an oversized
    # footprint makes the validator's footprint-containment check fail.
    route = validate_route(base)
    wide = dataclasses.replace(footprint, width_m=1.9)
    res = compile_reference(route, model, wide, policies,
                            output_dir=str(out_dir / "s3_wide_footprint"),
                            retime_spacing_m=spacing,
                            validation_context=context)
    geo = res.geometry
    report = res.run_report if isinstance(res.run_report, dict) else {}
    phases = set((report.get("phases") or {}).keys())
    results["D_validator_geometry_rejection"] = {
        "expected": ("optimizer candidate produced, then FAIL at "
                     "independent geometry validation (footprint "
                     "rectangle containment), no artifact"),
        "observed": res.status, "reason": (res.reason or "")[:200],
        "geometry": geo.status if geo else None,
        "geometry_coverage": list(geo.coverage) if geo else None,
        "offending_interval": (list(geo.offending_interval)
                               if geo and geo.offending_interval else None),
        "solver_iterations": report.get("solver_iteration_count"),
        "phases": sorted(phases),
        "artifact": res.artifact_path,
        "ok": bool(
            res.status == "FAIL"
            and geo is not None and geo.status == "FAIL"
            # the intended violation: footprint (reference-aligned
            # rectangle) containment with an identified interval
            and "reference_aligned_rectangle" in geo.coverage
            and geo.offending_interval
            and "rectangle" in (res.reason or "")
            and "exit" in (res.reason or "")
            # optimizer produced a candidate before validation ran
            and (report.get("solver_iteration_count") or 0) >= 1
            and {"optimization", "geometry"} <= phases
            and res.artifact_path is None)}
    return results


def adversarial_ok(adv):
    """True only if exactly the specified cases ran and all rejected."""
    return (set(adv) == set(ADVERSARIAL_CASES)
            and all(adv[case].get("ok") for case in ADVERSARIAL_CASES))


def _row_accepted(row):
    """A positive scenario counts only if it compiled AND its published
    artifact independently reloaded with PASS geometry and dynamics."""
    return (row.get("compile") == "PASS"
            and row.get("reload") == "PASS"
            and row.get("geo_reload") == "PASS"
            and row.get("dyn_reload") == "PASS"
            and row.get("cyclic_closure") is True)


def suite_ok(rows, adv, expected_scenarios, need_adversarial):
    """Exit-status predicate for the whole requested suite.

    The actual scenario identifiers must match the expected set exactly
    (missing, duplicate or unexpected results fail), every expected
    scenario must be accepted per _row_accepted, and -- when required --
    every adversarial case must have rejected as specified. An empty
    or partially executed suite is therefore never ok.
    """
    if not expected_scenarios:
        return False  # empty expectation is never ok
    if len(expected_scenarios) != len(set(expected_scenarios)):
        return False  # duplicate expectations
    actual = [r.get("scenario") for r in rows]
    if len(actual) != len(set(actual)):
        return False  # duplicate scenario results
    if set(actual) != set(expected_scenarios):
        return False  # missing or unexpected scenarios (covers empty)
    if not all(_row_accepted(r) for r in rows):
        return False
    if need_adversarial and not adversarial_ok(adv):
        return False
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--scenario", choices=["s0", "s1", "s2", "s3", "s4"])
    parser.add_argument("--out", default=None,
                        help="output dir (default: new demo_project_a/output/run-*)")
    args = parser.parse_args(argv)
    if not args.all and not args.scenario:
        parser.error("pass --all or --scenario")
    stamp = time.strftime("%Y%m%d-%H%M%S")
    out = Path(args.out) if args.out else (
        ROOT / "planner/global_planner/demo_project_a/output" / f"run-{stamp}")
    if out.exists():
        parser.error(f"output directory already exists: {out}")
    fig_dir = out / "figures"
    fig_dir.mkdir(parents=True)
    print(f"python={sys.version.split()[0]} out={out}")

    fixture_paths = fx.generate_all(str(out / "fixtures"))
    policies, context, spacing = load_policy(
        str(CONFIG / "policies" / "synthetic_policy.json"))

    want_adversarial = bool(args.all or args.scenario == "s3")
    if args.all:
        wanted = list(ALL_POSITIVE)
    elif args.scenario == "s3":
        # S3 standalone: build its S0 prerequisite internally.
        wanted = ["s0"]
    elif args.scenario == "s1":
        wanted = ["s1_route_a", "s1_route_b"]
    else:
        wanted = [args.scenario]

    rows, refs, routes = [], {}, {}
    for name in wanted:
        row, ref, route = compile_one(name, fixture_paths[name], out,
                                      policies, context, spacing)
        rows.append(row)
        routes[name] = route
        print(json.dumps({k: v for k, v in row.items() if k != "run_report"}))
        if ref is not None:
            refs[name] = ref
            manifest = json.loads(Path(fixture_paths[name]).read_text())
            model_doc = viz.load_json(str(CONFIG / "models" / MODELS[name]))
            (fig_dir / name).mkdir(exist_ok=True)
            figs = viz.plot_track(manifest, ref, str(fig_dir / name), TITLES[name])
            figs += viz.plot_velocity(
                ref, viz.model_limits_from_json(model_doc),
                str(fig_dir / name), f"Velocity — {name}",
                ay_limits=viz.model_ay_from_json(model_doc))
            energies = None
            its = row["run_report"].get("solver_iterations") or []
            if its:
                energies = (its[0]["source_curvature_energy"],
                            its[-1]["shifted_curvature_energy"])
            figs += viz.plot_curvature(route, ref, str(fig_dir / name),
                                       f"Curvature — {name}", energies=energies)
            row["figures"] = figs
    if "s1_route_a" in refs and "s1_route_b" in refs:
        (fig_dir / "s1").mkdir(exist_ok=True)
        a, b = refs["s1_route_a"], refs["s1_route_b"]
        runtime = {r["scenario"]: r["runtime_s"] for r in rows}
        stats = {"length_m": (round(a.length, 2), round(b.length, 2)),
                 "lap_s": (round(a.lap_time_s, 2), round(b.lap_time_s, 2)),
                 "runtime_s": (runtime["s1_route_a"], runtime["s1_route_b"]),
                 "validation": ("PASS/PASS", "PASS/PASS")}
        viz.plot_split(json.loads(Path(fixture_paths["s1_route_a"]).read_text()), a,
                       json.loads(Path(fixture_paths["s1_route_b"]).read_text()), b,
                       stats, str(fig_dir / "s1"))
    if "s2" in refs:
        viz.plot_bridge(json.loads(Path(fixture_paths["s2"]).read_text()),
                        refs["s2"], str(fig_dir / "s2"))
    adv = {}
    if want_adversarial:
        good_row = next((r for r in rows
                         if r["scenario"] == "s0" and r["compile"] == "PASS"), None)
        if good_row is None:
            print("S3 cannot run: internal S0 prerequisite did not compile PASS")
        else:
            adv = adversarial(fixture_paths, out, context, policies, spacing,
                              {"artifact_path": good_row["artifact_path"],
                               "H": good_row["H"]})
            print(json.dumps({"adversarial": adv}, indent=1))

    viz.plot_report(rows, str(fig_dir))
    ok = suite_ok(rows, adv, expected_scenarios=wanted,
                  need_adversarial=want_adversarial)
    summary = {"git_head": _git_head(), "python": sys.version.split()[0],
               "scenarios": rows, "adversarial": adv, "suite_ok": ok}
    (out / "summary.json").write_text(json.dumps(summary, indent=1, default=str))
    print(f"summary: {out / 'summary.json'}")
    print(f"suite_ok={ok}")
    return 0 if ok else 1


def _git_head():
    import subprocess
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True).stdout.strip()


if __name__ == "__main__":
    raise SystemExit(main())
