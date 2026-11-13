from pathlib import Path
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
from plyfile import PlyData
from scipy.spatial.transform import Rotation

from compare_maps import xyz
from prepare import read_pcd


def splat_points(cloud, pose, fx, fy, width, height):
    # The reference 3DGS renderer uses a symmetric frustum.
    rot = Rotation.from_quat([*map(float, pose[2:5]), float(pose[1])])
    trans = np.asarray(pose[5:8], dtype=float)
    best_depth = np.full(width * height, np.inf, dtype=np.float32)
    rgb = np.zeros((width * height, 3), dtype=np.uint8)
    chunk_size = 350000
    rgb_name = "rgb" if "rgb" in cloud.dtype.names else "rgba"
    for start in range(0, len(cloud), chunk_size):
        points = cloud[start:start+chunk_size]
        cam = rot.apply(xyz(points)) + trans
        mask = (cam[:, 2] > 0.2) & np.isfinite(cam).all(axis=1)
        cam = cam[mask]
        if not len(cam):
            continue
        z = cam[:, 2]
        u = np.floor(fx * cam[:, 0]/z + width/2).astype(int)
        v = np.floor(fy * cam[:, 1]/z + height/2).astype(int)
        visible = (u>=0) & (v>=0) & (u<width) & (v<height)
        px = v[visible]*width + u[visible]
        if not len(px):
            continue
        z = z[visible]
        order = np.lexsort((z, px))
        _, first = np.unique(px[order], return_index=True)
        chosen = order[first]
        chosen = chosen[z[chosen] < best_depth[px[chosen]]]
        new = px[chosen]
        best_depth[new] = z[chosen]
        colors = points[rgb_name].view("<u4")[mask][visible][chosen]
        rgb[new] = np.column_stack(((colors >> 16) & 255, (colors >> 8) & 255, colors & 255))
    return rgb.reshape(height, width, 3), float(np.isfinite(best_depth).mean())


def render_pairs(model, split, iteration):
    output = model / split / f"ours_{iteration}"
    files = sorted((output / "renders").glob("*.png"))
    gt = sorted((output / "gt").glob("*.png"))
    assert files and [p.name for p in files] == [p.name for p in gt]
    scores = []
    for real, synthetic in zip(gt, files):
        with Image.open(real) as reference, Image.open(synthetic) as image:
            assert reference.size == image.size
            a = np.asarray(reference.convert("RGB"), dtype=np.float32)/255
            b = np.asarray(image.convert("RGB"), dtype=np.float32)/255
            mse = np.mean((a-b)**2)
            assert np.isfinite(mse) and 0 <= mse <= 1
            scores.append(float(-10*np.log10(max(mse, np.finfo(np.float32).eps))))
    return gt, files, scores


def main(root):
    model = root / "3dgs"
    iteration = int(os.environ["TRAIN_ITERATIONS"])
    final = model / f"point_cloud/iteration_{iteration}/point_cloud.ply"
    points = PlyData.read(final, mmap="r")["vertex"].data
    assert len(points) > 1000 and {"opacity", "scale_0", "rot_0", "f_dc_0"} <= set(points.dtype.names)
    for name in ("x", "y", "z", "opacity"):
        assert np.isfinite(points[name]).all()
    gt, renders, scores = render_pairs(model, "test", iteration)
    _, train, train_scores = render_pairs(model, "train", iteration)
    cameras = json.loads((model / "cameras.json").read_text())
    # Scene serializes test cameras first and render.py disables shuffling.
    assert len(cameras) == len(gt) + len(train)
    sparse = root / "datasets/input/3DGS_train/sparse/0"
    rows = [line.split() for line in (sparse / "images.txt").read_text().splitlines()
            if line and not line.startswith("#")][::2]
    poses = {row[9]: row for row in rows}
    point_cloud = read_pcd(root / "frontend/global_pcd/after_optimization.pcd")
    picks = [len(gt)//4, len(gt)//2, len(gt)*3//4]
    fig, axes = plt.subplots(3, 3, figsize=(13, 11), layout="constrained")
    rows = []
    for col, idx in enumerate(picks):
        camera = cameras[idx]
        width, height = camera["width"], camera["height"]
        projection, coverage = splat_points(point_cloud, poses[camera["img_name"]], camera["fx"], camera["fy"], width, height)
        Image.fromarray(projection).save(root / f"report/figures/rtk_projection_{renders[idx].name}")
        for ax, im in zip(axes[:, col], (Image.open(gt[idx]), Image.open(renders[idx]), projection)):
            ax.imshow(im)
            ax.axis("off")
        axes[0, col].set_title(f"Camera | view {renders[idx].stem}")
        axes[1, col].set_title(f"3DGS | PSNR {scores[idx]:.2f} dB")
        axes[2, col].set_title(f"RTK color LiDAR | {100*coverage:.1f}% pixels with points")
        rows.append(dict(render=renders[idx].name, source=camera["img_name"],
                         psnr_db=scores[idx], lidar_pixel_coverage=coverage))
    fig.suptitle("Matched virtual camera views", fontsize=16, fontweight="bold")
    fig.savefig(root / "report/figures/04_camera_3dgs_rtk.png", dpi=155)
    plt.close(fig)
    metadata = dict(gaussians=len(points), test_views=len(gt), train_views=len(train),
                    test_psnr_db=float(np.mean(scores)), train_psnr_db=float(np.mean(train_scores)),
                    samples=rows, width=width, height=height)
    (root / "report/render_stats.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(metadata, indent=2), flush=True)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
