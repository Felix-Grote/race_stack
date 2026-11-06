#!/usr/bin/env python3
"""Reproducible Project A (W1-W3) offline global-planner demonstration.

Usage (requires the pinned Python 3.10.12 environment, see DEMO_README.md):
  .venv-demo/bin/python scripts/run_project_a_demo.py --all
  .venv-demo/bin/python scripts/run_project_a_demo.py --scenario s2

Writes only into a NEW run-specific output directory (immutable artifacts
are never overwritten). No ROS node, vehicle, LiDAR or actuation is used.
"""
import argparse
import copy
import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "planner" / "global_planner"))

from demo_project_a import fixtures as fx  # noqa: E402
from demo_project_a import visualize as viz  # noqa: E402
from global_planner.route_artifact import load_reference  # noqa: E402
from global_planner.route_compile import (  # noqa: E402
    load_policy, load_vehicle_config, compile_reference)
from global_planner.route_input import RouteError, load_route, validate_route  # noqa: E402

CONFIG = ROOT / "planner/global_planner/config/project_a"
MODELS = {"s0": "s0_route_model.json", "s1_route_a": "s0_route_model.json",
          "s1_route_b": "s0_route_model.json", "s2": "s3_surfaces_route_model.json"}
TITLES = {"s0": "S0 conventional closed circuit (ellipse, varied curvature)",
          "s1_route_a": "S1 Route A (compact northern branch)",
          "s1_route_b": "S1 Route B (taller northern branch)",
          "s2": "S2 bridge / overlapping XY (lemniscate, o2 on upper-deck)"}


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
    row = {"scenario": name, "compile": res.status, "reason": res.reason,
           "geo": res.geometry.status if res.geometry else None,
           "dyn": res.dynamics.status if res.dynamics else None,
           "H": res.H, "runtime_s": round(wall, 2),
           "artifact_path": res.artifact_path}
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
    return row, ref, route


def adversarial(paths, out_dir, context, policies, spacing, good):
    """Three distinct rejection mechanisms; none may yield an accepted ref."""
    results = {}
    base = json.loads(Path(paths["s0"]).read_text())
    # Case A1: disconnected transition (shift o1 seed away from shared gate)
    bad = copy.deepcopy(base)
    for pt in bad["occurrences"][1]["seed"]:
        pt[0] += 5.0
    try:
        validate_route(bad)
        results["A1_disconnected"] = {"expected": "RouteError", "observed": "ACCEPTED!"}
    except RouteError as exc:
        results["A1_disconnected"] = {"expected": "RouteError", "observed": str(exc)}
    # Case A2: wrong directed portal (reverse gate point order)
    bad = copy.deepcopy(base)
    bad["transitions"][0]["gate"] = bad["transitions"][0]["gate"][::-1]
    try:
        validate_route(bad)
        results["A2_wrong_direction"] = {"expected": "RouteError", "observed": "ACCEPTED!"}
    except RouteError as exc:
        results["A2_wrong_direction"] = {"expected": "RouteError", "observed": str(exc)}
    # Case B: tampered artifact copy loaded under the original expected H
    src = Path(good.artifact_path)
    dst = out_dir / "tampered" / src.parent.name
    shutil.copytree(src.parent, dst)
    target = dst / "reference.json"
    target.chmod(0o644)
    data = target.read_text()
    target.write_text(data.replace('"speed_max_mps":3.0', '"speed_max_mps":9.0', 1)
                      if '"speed_max_mps":3.0' in data else data[:-20] + "0" + data[-19:])
    try:
        load_reference(str(dst), expected_H=good.H, validation_context=context)
        results["B_tampered_artifact"] = {"expected": "ArtifactError", "observed": "ACCEPTED!"}
    except Exception as exc:  # ArtifactError from trusted loading
        results["B_tampered_artifact"] = {"expected": "ArtifactError",
                                          "observed": f"{type(exc).__name__}: {exc}"[:200]}
    # Case C: genuine curvature-infeasible geometry reaches compiler, no artifact
    tight = fx.build_manifest("demo-s3", "s3-tight-hairpin",
                              fx.ellipse_points(a=3.0, b=1.1),
                              ["ground"] * 4)
    try:
        route = validate_route(tight)
        model, footprint = load_vehicle_config(
            str(CONFIG / "models" / "s0_route_model.json"))
        res = compile_reference(route, model, footprint, policies,
                                output_dir=str(out_dir / "s3_tight"),
                                retime_spacing_m=spacing,
                                validation_context=context)
        results["C_infeasible_geometry"] = {
            "expected": "non-PASS, no artifact", "observed": res.status,
            "reason": res.reason[:200], "artifact": res.artifact_path}
    except RouteError as exc:
        results["C_infeasible_geometry"] = {
            "expected": "non-PASS, no artifact", "observed": "RouteError",
            "reason": str(exc), "artifact": None}
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--scenario", choices=["s0", "s1", "s2", "s3"])
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

    wanted = (["s0", "s1_route_a", "s1_route_b", "s2"] if args.all or
              args.scenario in ("s0", "s1", "s2") else [])
    if args.scenario == "s0":
        wanted = ["s0"]
    elif args.scenario == "s2":
        wanted = ["s2"]
    elif args.scenario == "s1":
        wanted = ["s1_route_a", "s1_route_b"]

    rows, refs, routes = [], {}, {}
    for name in wanted:
        row, ref, route = compile_one(name, fixture_paths[name], out,
                                      policies, context, spacing)
        rows.append(row)
        routes[name] = route
        print(json.dumps(row))
        if ref is not None:
            refs[name] = ref
            manifest = json.loads(Path(fixture_paths[name]).read_text())
            (fig_dir / name).mkdir(exist_ok=True)
            figs = viz.plot_track(manifest, ref, str(fig_dir / name), TITLES[name])
            figs += viz.plot_velocity(
                ref, viz.model_limits_from_json(viz.load_json(
                    str(CONFIG / "models" / MODELS[name]))),
                str(fig_dir / name), f"Velocity — {name}")
            figs += viz.plot_curvature(route, ref, str(fig_dir / name),
                                       f"Curvature — {name}")
            row["figures"] = figs
    if "s1_route_a" in refs and "s1_route_b" in refs:
        (fig_dir / "s1").mkdir(exist_ok=True)
        a, b = refs["s1_route_a"], refs["s1_route_b"]
        stats = {"length_m": (round(a.length, 2), round(b.length, 2)),
                 "lap_s": (round(a.lap_time_s, 2), round(b.lap_time_s, 2)),
                 "runtime_s": (next(r["runtime_s"] for r in rows if r["scenario"] == "s1_route_a"),
                               next(r["runtime_s"] for r in rows if r["scenario"] == "s1_route_b")),
                 "validation": ("PASS/PASS", "PASS/PASS")}
        viz.plot_split(json.loads(Path(fixture_paths["s1_route_a"]).read_text()), a,
                       json.loads(Path(fixture_paths["s1_route_b"]).read_text()), b,
                       stats, str(fig_dir / "s1"))
    if "s2" in refs:
        viz.plot_bridge(json.loads(Path(fixture_paths["s2"]).read_text()),
                        refs["s2"], str(fig_dir / "s2"))
    adv = {}
    if (args.all or args.scenario == "s3") and "s0" in refs:
        good_row = next(r for r in rows if r["scenario"] == "s0")
        from dataclasses import dataclass

        @dataclass
        class _Good:
            artifact_path: str
            H: str
        adv = adversarial(fixture_paths, out, context, policies, spacing,
                          _Good(good_row["artifact_path"], good_row["H"]))
        print(json.dumps({"adversarial": adv}, indent=1))
    elif args.scenario == "s3":
        print("S3 requires a valid S0 artifact; run --all or --scenario s0 first")

    viz.plot_report(rows, str(fig_dir))
    summary = {"git_head": _git_head(), "python": sys.version.split()[0],
               "scenarios": rows, "adversarial": adv}
    (out / "summary.json").write_text(json.dumps(summary, indent=1, default=str))
    print(f"summary: {out / 'summary.json'}")
    ok = all(r["compile"] == "PASS" for r in rows) if rows else True
    return 0 if ok else 1


def _git_head():
    import subprocess
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True).stdout.strip()


if __name__ == "__main__":
    raise SystemExit(main())
