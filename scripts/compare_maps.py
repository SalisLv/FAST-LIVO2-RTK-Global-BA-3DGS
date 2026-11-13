import json
from pathlib import Path
import sys

import yaml

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import numpy as np
from scipy.interpolate import CubicSpline
from scipy.spatial.transform import Rotation

from prepare import load_poses, paired, read_pcd, stats

BLUE, ORANGE = "#2171a5", "#d55e00"
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})


def track_figure(before, after, figure):
    shift = paired(before, after)
    peak = int(shift.argmax())
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.2), layout="constrained")
    for ax in axes[:2]:
        for pose, color, title, pattern in [(before, BLUE, "LIVO, rigidly aligned", "-"),
                                            (after, ORANGE, "After offline RTK", "--")]:
            ax.plot(pose[:, 1], pose[:, 2], pattern, color=color, label=title, lw=1.7)
        ax.set_aspect("equal", adjustable="box")
        ax.set(xlabel="East (m)", ylabel="North (m)")
        ax.grid(alpha=0.25)
    axes[0].scatter(*before[peak, 1:3], facecolors="none", edgecolors="black", s=135, zorder=3)
    axes[0].legend(loc="best", fontsize=8)
    axes[0].set_title("Full trajectory in a common ENU frame")
    mid = (before[peak, 1:3] + after[peak, 1:3]) / 2
    radius = max(1.1, shift[peak] * 1.55)
    axes[1].set(xlim=(mid[0]-radius, mid[0]+radius), ylim=(mid[1]-radius, mid[1]+radius),
                title="Location of largest 3D correction")
    axes[1].annotate("", xy=after[peak, 1:3], xytext=before[peak, 1:3],
                     arrowprops=dict(arrowstyle="->", color="black", lw=1.2))
    t = before[:, 0] - before[0, 0]
    axes[2].plot(t, shift * 100, color=ORANGE, lw=1.2)
    axes[2].axhline(np.median(shift)*100, color=BLUE, ls=":", label="Median")
    axes[2].scatter(t[peak], shift[peak]*100, color=ORANGE, zorder=3)
    axes[2].set(xlabel="Time from first matched pose (s)", ylabel="3D position change (cm)",
                title=f"Per-pose correction | max {shift[peak]*100:.1f} cm")
    axes[2].legend(fontsize=8)
    axes[2].grid(alpha=0.25)
    fig.suptitle("Impact of offline GNSS/RTK factors", fontweight="bold")
    fig.savefig(figure, dpi=170)
    plt.close(fig)


def xyz(records):
    return np.column_stack([records[field] for field in ("x", "y", "z")])


def sample_regions(a, delta, cell=5.0):
    keys, ids = np.unique(np.floor(a[:, :2] / cell).astype(np.int32), axis=0, return_inverse=True)
    groups = np.argsort(ids)
    counts = np.bincount(ids)
    start = np.r_[0, np.cumsum(counts)]
    candidates = []
    for i, key in enumerate(keys):
        if counts[i] < max(140, len(a)//500):
            continue
        q = float(np.percentile(delta[groups[start[i]:start[i+1]]], 90))
        candidates.append(dict(e=float(key[0]*cell), n=float(key[1]*cell), width=cell,
                               points=int(counts[i]), p90_m=q))
    candidates.sort(key=lambda x: x["p90_m"], reverse=True)
    chosen = []
    for row in candidates:
        if all(np.hypot(row["e"]-p["e"], row["n"]-p["n"]) >= cell*1.7 for p in chosen):
            chosen.append(row)
        if len(chosen) == 2:
            break
    if not chosen:
        i = int(np.argmax(counts))
        q = float(np.percentile(delta[groups[start[i]:start[i + 1]]], 90))
        chosen.append(dict(e=float(keys[i, 0] * cell), n=float(keys[i, 1] * cell),
                           width=cell, points=int(counts[i]), p90_m=q))
    return chosen


def map_figure(a, b, labels, output, peak_pose=None):
    assert a.shape == b.shape
    valid = np.isfinite(a).all(axis=1) & np.isfinite(b).all(axis=1)
    a, b = a[valid], b[valid]
    d = np.linalg.norm(b-a, axis=1)
    regions = sample_regions(a, d)
    roi = regions[0]
    height = np.percentile(a[:, 2], [4, 96])
    xy_min = np.minimum(np.percentile(a[:, :2], 2.0, axis=0), np.percentile(b[:, :2], 2.0, axis=0)) - 3
    xy_max = np.maximum(np.percentile(a[:, :2], 98.0, axis=0), np.percentile(b[:, :2], 98.0, axis=0)) + 3
    for row in regions:
        xy_min = np.minimum(xy_min, [row["e"]-2, row["n"]-2])
        xy_max = np.maximum(xy_max, [row["e"]+row["width"]+2, row["n"]+row["width"]+2])
    fig, axes = plt.subplots(2, 2, figsize=(12, 10), layout="constrained")
    idx = slice(None, None, max(1, len(a)//190000))
    zoom = ((a[:, 0] >= roi["e"]-1) & (a[:, 0] <= roi["e"]+roi["width"]+1) &
            (a[:, 1] >= roi["n"]-1) & (a[:, 1] <= roi["n"]+roi["width"]+1))
    for j, values in enumerate((a, b)):
        p = values[idx]
        axes[0, j].scatter(p[:, 0], p[:, 1], c=p[:, 2], cmap="viridis", vmin=height[0], vmax=height[1],
                           s=0.55, linewidths=0, rasterized=True)
        axes[0, j].set(xlim=(xy_min[0], xy_max[0]), ylim=(xy_min[1], xy_max[1]), title=labels[j])
        p = values[zoom]
        axes[1, j].scatter(p[:, 0], p[:, 1], c=p[:, 2], cmap="viridis", vmin=height[0], vmax=height[1],
                           s=3, linewidths=0)
        axes[1, j].set(xlim=(roi["e"]-0.4, roi["e"]+roi["width"]+0.4),
                       ylim=(roi["n"]-0.4, roi["n"]+roi["width"]+0.4),
                       title=f"A zoom | paired point displacement p90: {100*roi['p90_m']:.2f} cm")
        for i, row in enumerate(regions):
            for ax in (axes[0, j], axes[1, j]) if i == 0 else (axes[0, j],):
                ax.add_patch(Rectangle((row["e"], row["n"]), row["width"], row["width"],
                                       fill=False, lw=1.8, ec=ORANGE, zorder=4))
                ax.text(row["e"], row["n"]+row["width"], chr(65+i), color=ORANGE,
                        fontweight="bold", fontsize=13, zorder=5, va="bottom")
    if peak_pose is not None:
        for j, ax in enumerate(axes[0]):
            x, y = peak_pose[j]
            ax.scatter(x, y, marker="x", color="#c51b8a", s=68, linewidths=2, zorder=8)
            ax.annotate("C | max pose shift", (x, y), xytext=(12, 15), textcoords="offset points",
                        color="#a50f74", fontweight="bold", fontsize=9,
                        arrowprops=dict(arrowstyle="-", color="#a50f74"), zorder=8)
    candidates = np.flatnonzero(zoom)
    strong = candidates[d[candidates] >= np.percentile(d[candidates], 75)]
    markers = strong[np.linspace(0, len(strong)-1, min(16, len(strong)), dtype=int)]
    if len(markers):
        gain = 5 if roi["p90_m"] < 0.25 else 1
        v = gain * (b[markers, :2] - a[markers, :2])
        axes[1, 1].quiver(a[markers, 0], a[markers, 1], v[:, 0], v[:, 1], color=ORANGE,
                          angles="xy", scale_units="xy", scale=1, width=0.004, zorder=6)
        axes[1, 1].text(0.02, 0.02, f"Displacement arrows x{gain}", transform=axes[1, 1].transAxes,
                        color=ORANGE, bbox=dict(facecolor="white", alpha=0.88, edgecolor="none"))
    for ax in axes.flat:
        ax.set_aspect("equal")
        ax.set(xlabel="East (m)", ylabel="North (m)")
    fig.suptitle("Same LiDAR samples, same coordinates | color indicates elevation", fontweight="bold")
    fig.savefig(output, dpi=160)
    plt.close(fig)
    return dict(stats_m=stats(d), sampled_points=len(d), regions=regions)


def save_lidar_pair(root):
    dataset = root / "datasets/input"
    poses = dataset / "3DGS_V6/densify"
    before = load_poses(poses / "lidar_before_twi.txt")
    after = load_poses(poses / "lidar_after_twi.txt")
    shift = paired(before, after)
    input_poses = load_poses(dataset / "all_pcd_body/lidar_poses.txt")
    assert input_poses.shape == before.shape
    max_time_error = float(np.max(abs(input_poses[:, 0] - before[:, 0])))
    assert max_time_error <= 6e-6, max_time_error
    assert np.max(abs(input_poses[:, 1:4] - before[:, 1:4])) < 1e-6
    files = [dataset / "all_pcd_body" / f"{t:.6f}.pcd" for t in input_poses[:, 0]]
    counts = [len(read_pcd(path)) for path in files]
    total = sum(counts)
    header = (
        "# .PCD v0.7\nVERSION 0.7\nFIELDS x y z intensity\nSIZE 4 4 4 4\nTYPE F F F F\nCOUNT 1 1 1 1\n"
        f"WIDTH {total}\nHEIGHT 1\nVIEWPOINT 0 0 0 1 0 0 0\nPOINTS {total}\nDATA binary\n"
    ).encode()
    step = max(1, total // 600000)
    clouds_before, clouds_after = [], []
    offset = 0
    with (root / "maps/rtk_before_lidar_ba.pcd").open("wb") as f0, (root / "maps/after_lidar_ba.pcd").open("wb") as f1:
        f0.write(header)
        f1.write(header)
        for a, b, path in zip(before, after, files):
            cloud = read_pcd(path)
            local = xyz(cloud)
            pa = (Rotation.from_quat(a[4:]).apply(local) + a[1:4]).astype("f4")
            pb = (Rotation.from_quat(b[4:]).apply(local) + b[1:4]).astype("f4")
            np.column_stack((pa, cloud["intensity"])).astype("<f4").tofile(f0)
            np.column_stack((pb, cloud["intensity"])).astype("<f4").tofile(f1)
            ind = slice((-offset) % step, None, step)
            clouds_before.append(pa[ind])
            clouds_after.append(pb[ind])
            offset += len(cloud)
    peak = int(shift.argmax())
    info = map_figure(np.concatenate(clouds_before), np.concatenate(clouds_after),
                      ("RTK-corrected poses before LiDAR BA", "After Global-LVBA LiDAR BA"),
                      root / "report/figures/03_global_ba_map.png", (before[peak, 1:3], after[peak, 1:3]))
    neighbor = peak + 1 if peak + 1 < len(before) else max(0, peak - 1)
    info.update(points=total, matched_lidar_poses=len(shift), lidar_pose_shift_m=stats(shift),
                max_time_error_us=max_time_error*1e6, peak_time_s=float(before[peak, 0]-before[0, 0]),
                count_over_1m=int((shift>1).sum()), count_over_2m=int((shift>2).sum()),
                near_peak_step_before_m=float(np.linalg.norm(before[neighbor,1:4]-before[peak,1:4])),
                near_peak_step_after_m=float(np.linalg.norm(after[neighbor,1:4]-after[peak,1:4])))
    return info


def main(root, stage):
    if stage == "rtk":
        before = load_poses(root / "frontend/TUM/aligned_imu_before_rtk.txt")
        after = load_poses(root / "frontend/TUM/enu_imu_after_rtk.txt")
        track_figure(before, after, root / "report/figures/01_rtk_trajectory.png")
        parent = root / "frontend/global_pcd"
        a = read_pcd(parent / "before_optimization.pcd")
        b = read_pcd(parent / "after_optimization.pcd")
        assert len(a) == len(b)
        stride = max(1, len(a)//600000)
        info = map_figure(xyz(a[::stride]), xyz(b[::stride]), ("Before RTK, aligned to ENU", "After RTK"),
                          root / "report/figures/02_rtk_map.png")
        gps = np.loadtxt(root / "frontend/TUM/opt_trajectory_before.txt")
        times, unique = np.unique(gps[:, 0], return_index=True)
        in_range = (before[:, 0] >= times[0]) & (before[:, 0] <= times[-1])
        info.update(points=len(a), gnss_overlap=int(in_range.sum()))
        if len(times) > 1 and in_range.any():
            config = yaml.safe_load((root / "profile/frontend.yaml").read_text())
            lever_arm = np.asarray(config["gps"]["extrinsic_T"], dtype=float)
            enu = CubicSpline(times - times[0], gps[unique, 1:4])(before[in_range, 0] - times[0])
            for name, poses in (("before", before[in_range]), ("after", after[in_range])):
                antenna = poses[:, 1:4] + Rotation.from_quat(poses[:, 4:]).apply(lever_arm)
                info[f"gnss_{name}_m"] = stats(np.linalg.norm(antenna - enu, axis=1))
    elif stage == "lvba":
        info = save_lidar_pair(root)
    else:
        raise ValueError(stage)
    (root / f"report/{stage}_map_stats.json").write_text(json.dumps(info, indent=2) + "\n")
    print(json.dumps(info, indent=2), flush=True)


if __name__ == "__main__":
    main(Path(sys.argv[1]), sys.argv[2])
