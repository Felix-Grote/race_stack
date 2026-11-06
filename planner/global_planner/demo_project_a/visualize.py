"""Matplotlib figures derived exclusively from accepted planner artifacts.

Optimized trajectories, speeds and curvatures are sampled through
global_planner.route_artifact.load_reference / Reference.window, i.e. the
same trusted metric-query API a consumer would use. Corridor boundaries and
seed centrelines come from the validated input manifest. Nothing here
fabricates or smooths a racing line for display.
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

COLORS = {"o0": "#1b9e77", "o1": "#d95f02", "o2": "#7570b3", "o3": "#e7298a"}
SURF_STYLE = {"ground": "-", "upper-deck": "--"}


def _save(fig, out, name):
    paths = []
    for ext in ("png", "svg"):
        p = Path(out) / f"{name}.{ext}"
        fig.savefig(p, dpi=160, bbox_inches="tight")
        paths.append(str(p))
    plt.close(fig)
    return paths


def _samples(ref, step=0.25):
    return ref.window(0.0, ref.length, step)


def _arrows(ax, xs, ys, every=24):
    for i in range(0, len(xs) - 1, every):
        ax.annotate("", xy=(xs[i + 1], ys[i + 1]), xytext=(xs[i], ys[i]),
                    arrowprops=dict(arrowstyle="->", color="black", lw=0.8))


def plot_track(manifest, ref, out, title):
    """Figure 1: corridor, seed, optimized trajectory, portals, start."""
    fig, ax = plt.subplots(figsize=(8, 7))
    for occ in manifest["occurrences"]:
        c = COLORS[occ["id"]]
        for key, ls in (("left", "-"), ("right", "-")):
            pts = np.array(occ[key])
            ax.plot(pts[:, 0], pts[:, 1], ls, color=c, lw=0.7, alpha=0.55)
        seed = np.array(occ["seed"])
        ax.plot(seed[:, 0], seed[:, 1], ":", color=c, lw=1.2,
                label=f"seed {occ['id']} ({occ['surface_id']})")
    samples = _samples(ref)
    xs = [s.xy[0] for s in samples]
    ys = [s.xy[1] for s in samples]
    ax.plot(xs, ys, "-", color="black", lw=1.8, label="optimized (accepted ref)")
    _arrows(ax, xs, ys)
    for tr in manifest["transitions"]:
        g = np.array(tr["gate"])
        ax.plot(g[:, 0], g[:, 1], "r-", lw=2.0)
        ax.plot(g[:, 0].mean(), g[:, 1].mean(), "r|", ms=10)
    ax.plot(xs[0], ys[0], "go", ms=9, label="start/finish (s=0)")
    ax.set_aspect("equal")
    ax.set_xlabel("x [m]")
    ax.set_ylabel("y [m]")
    ax.set_title(title)
    ax.legend(fontsize=7, loc="best")
    ax.grid(alpha=0.3)
    return _save(fig, out, "fig1_track")


def plot_split(man_a, ref_a, man_b, ref_b, stats, out):
    """Figure 2: two manually selected routes overlaid; no branch selection."""
    fig, ax = plt.subplots(figsize=(8, 7))
    for man, ref, color, name in ((man_a, ref_a, "#08519c", "Route A"),
                                  (man_b, ref_b, "#a50f15", "Route B")):
        for occ in man["occurrences"]:
            seed = np.array(occ["seed"])
            ax.plot(seed[:, 0], seed[:, 1], "--", color=color, lw=0.9, alpha=0.6)
        samples = _samples(ref)
        ax.plot([s.xy[0] for s in samples], [s.xy[1] for s in samples],
                "-", color=color, lw=1.8, label=f"{name} optimized")
    ax.set_aspect("equal")
    ax.set_xlabel("x [m]")
    ax.set_ylabel("y [m]")
    ax.set_title("S1 split/remerge: two independently compiled, manually\n"
                 "selected whole-lap routes (planner does not select branches)")
    txt = "\n".join(
        f"{k}: A={v[0]}  B={v[1]}" for k, v in stats.items())
    ax.text(0.02, 0.02, txt, transform=ax.transAxes, fontsize=7,
            family="monospace", bbox=dict(facecolor="white", alpha=0.85))
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    return _save(fig, out, "fig2_split_comparison")


def plot_bridge(manifest, ref, out):
    """Figure 3: overlapping XY with distinct surfaces + occurrence/s diagram."""
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(11, 5),
                                  gridspec_kw={"width_ratios": [1.4, 1]})
    for occ in manifest["occurrences"]:
        seed = np.array(occ["seed"])
        ls = SURF_STYLE.get(occ["surface_id"], "-")
        ax.plot(seed[:, 0], seed[:, 1], ls, color=COLORS[occ["id"]], lw=2,
                label=f"{occ['id']} on {occ['surface_id']}")
    samples = _samples(ref)
    ax.plot([s.xy[0] for s in samples], [s.xy[1] for s in samples],
            "k-", lw=0.8, alpha=0.7, label="optimized")
    ax.set_aspect("equal")
    ax.set_xlabel("x [m]")
    ax.set_ylabel("y [m]")
    ax.set_title("S2 XY projection (overlap != connection;\nno 3D clearance claimed)")
    ax.legend(fontsize=7)
    ax.grid(alpha=0.3)
    keep = [s for s in samples if s.s < ref.length - 1e-9]
    ss = [s.s for s in keep]
    owners = [s.occurrence_id for s in keep]
    ax2.step(ss, [int(o[1:]) for o in owners], "k-", lw=1.2, where="post")
    ax2.set_yticks([0, 1, 2, 3])
    ax2.set_yticklabels(["o0\nground", "o1\nground", "o2\nupper-deck", "o3\nground"])
    ax2.set_xlabel("true arclength s [m]")
    ax2.set_title("Ordered occurrence ownership vs progress")
    ax2.grid(alpha=0.3)
    return _save(fig, out, "fig3_bridge_topology")


def plot_velocity(ref, model_limits, out, title="Velocity profile"):
    """Figure 4: v(s), static limits, transitions, accel/braking shading."""
    samples = _samples(ref, 0.2)
    ss = np.array([s.s for s in samples])
    vs = np.array([s.speed_mps for s in samples])
    acc = np.array([s.acceleration_mps2 for s in samples])
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.fill_between(ss, 0, vs.max() * 1.1, where=acc > 0.05,
                    color="green", alpha=0.12, label="acceleration")
    ax.fill_between(ss, 0, vs.max() * 1.1, where=acc < -0.05,
                    color="red", alpha=0.12, label="braking")
    ax.plot(ss, vs, "k-", lw=1.4, label="v(s) accepted ref")
    limits = [model_limits[s.occurrence_id] for s in samples]
    ax.plot(ss, limits, "b--", lw=1.0, label="static speed_max (model)")
    seen = set()
    for s in samples:
        if s.occurrence_id not in seen and s.s > 0:
            seen.add(s.occurrence_id)
            ax.axvline(s.s, color="gray", ls=":", lw=0.8)
    ax.axvline(ref.length, color="purple", ls="-", lw=1.0,
               label="lap seam (cyclic)")
    ax.set_xlabel("true metric arclength s [m]")
    ax.set_ylabel("speed [m/s]")
    ax.set_title(title)
    ax.legend(fontsize=7)
    ax.grid(alpha=0.3)
    return _save(fig, out, "fig4_velocity")


def plot_curvature(manifest_route, ref, out, title="Curvature profile"):
    """Figure 5: optimized kappa(s) vs seed kappa over the full lap."""
    from global_planner.route_corridor import seed_curve
    samples = _samples(ref, 0.2)
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot([s.s for s in samples], [s.curvature for s in samples],
            "k-", lw=1.2, label="optimized kappa(s)")
    seed = seed_curve(manifest_route)
    ssamples = seed.curve.window(0.0, seed.curve.length, 0.2)
    ax.plot([s.s for s in ssamples], [s.curvature for s in ssamples],
            color="gray", ls="--", lw=0.9, label="seed kappa(s)")
    ax.axvline(ref.length, color="purple", lw=1.0, label="lap seam")
    ax.set_xlabel("true metric arclength s [m]")
    ax.set_ylabel("curvature kappa [1/m]")
    ax.set_title(title)
    ax.legend(fontsize=7)
    ax.grid(alpha=0.3)
    return _save(fig, out, "fig5_curvature")


def plot_report(rows, out):
    """Figure 6: validation/performance table rendered as a figure."""
    fig, ax = plt.subplots(figsize=(10, 0.6 + 0.45 * len(rows)))
    ax.axis("off")
    cols = ["scenario", "compile", "geo", "dyn", "length_m", "lap_s",
            "runtime_s", "H (short)"]
    table = [[str(r.get(c, "-")) for c in cols] for r in rows]
    tbl = ax.table(cellText=table, colLabels=cols, loc="center")
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(7)
    tbl.scale(1, 1.4)
    ax.set_title("Validation and performance report (measured, not invented)",
                 fontsize=9)
    return _save(fig, out, "fig6_validation_report")


def model_limits_from_json(model_doc):
    return {r["occurrence_id"]: r["limits"]["speed_max_mps"]
            for r in model_doc["model"]["regions"]}


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))
