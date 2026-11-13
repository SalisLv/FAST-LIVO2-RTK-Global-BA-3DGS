from pathlib import Path
import json
import os
import sys

import cv2
import numpy as np
import yaml
from scipy.spatial.transform import Rotation, Slerp


def load_poses(path):
    rows = np.loadtxt(path, ndmin=2)
    if rows.shape[1] != 8 or not np.isfinite(rows).all() or not (np.diff(rows[:, 0]) > 0).all():
        raise ValueError(f"Invalid TUM poses in {path}")
    return rows


def save_poses(path, rows):
    np.savetxt(path, rows, fmt="%.9f")


def paired(a, b):
    if a.shape != b.shape or not np.array_equal(a[:, 0], b[:, 0]):
        raise ValueError("Trajectory timestamp mismatch")
    return np.linalg.norm(b[:, 1:4] - a[:, 1:4], axis=1)


def stats(d):
    return dict(max=float(d.max()), mean=float(d.mean()), median=float(np.median(d)),
                rmse=float(np.sqrt(np.mean(d ** 2))), std=float(d.std()), p95=float(np.percentile(d, 95)))


def read_pcd(path):
    fields = {}
    with path.open("rb") as fp:
        for line in fp:
            row = line.decode("ascii").split()
            if row and not row[0].startswith("#"):
                fields[row[0]] = row[1:]
                if row[0] == "DATA":
                    offset = fp.tell()
                    break
    if fields["DATA"] != ["binary"]:
        raise ValueError(f"Expected binary PCD: {path}")
    types = {"F": "f", "U": "u", "I": "i"}
    columns = []
    for name, size, code, count in zip(fields["FIELDS"], fields["SIZE"], fields["TYPE"],
                                        fields.get("COUNT", ["1"] * len(fields["FIELDS"]))):
        dtype = "<" + types[code] + size
        columns.append((name, dtype) if count == "1" else (name, dtype, (int(count),)))
    return np.memmap(path, dtype=np.dtype(columns), offset=offset, mode="r",
                     shape=(int(fields["POINTS"][0]),))


def write_pcd(path, values, last_field):
    if len(values) == 0:
        raise ValueError(f"Empty cloud: {path}")
    header = (
        f"# .PCD v0.7\nVERSION 0.7\nFIELDS x y z {last_field}\n"
        "SIZE 4 4 4 4\nTYPE F F F F\nCOUNT 1 1 1 1\n"
        f"WIDTH {len(values)}\nHEIGHT 1\nVIEWPOINT 0 0 0 1 0 0 0\nPOINTS {len(values)}\nDATA binary\n"
    )
    with path.open("wb") as file:
        file.write(header.encode("ascii"))
        np.asarray(values, dtype="<f4").tofile(file)


def nearest_indices(t, target):
    right = np.clip(np.searchsorted(t, target), 1, len(t) - 1)
    left = right - 1
    return np.where(abs(t[right] - target) < abs(t[left] - target), right, left)


def prepare(root):
    raw = root / "raw"
    trajectory = root / "frontend/TUM"
    before = load_poses(trajectory / "aligned_imu_before_rtk.txt")
    after = load_poses(trajectory / "enu_imu_after_rtk.txt")
    diff = paired(before, after)
    raw_images = load_poses(raw / "all_image/image_poses.txt")
    raw_lidar = load_poses(raw / "all_pcd_body/lidar_poses.txt")
    sample = raw_images[nearest_indices(raw_images[:, 0], before[:, 0])]
    synchronized = abs(sample[:, 0] - before[:, 0]) < 2e-5
    if synchronized.sum() < 0.9 * len(before):
        raise ValueError("Too few precisely synchronized VIO/RTK graph poses")
    origin_rot = (Rotation.from_quat(before[synchronized, 4:]) *
                  Rotation.from_quat(sample[synchronized, 4:]).inv()).mean()
    origin_pos = np.median(before[synchronized, 1:4] - origin_rot.apply(sample[synchronized, 1:4]), axis=0)
    residual = np.linalg.norm(origin_rot.apply(sample[synchronized, 1:4]) + origin_pos -
                              before[synchronized, 1:4], axis=1)
    if np.percentile(residual, 95) > 0.005:
        raise ValueError(f"Inconsistent ENU alignment, p95 residual={np.percentile(residual, 95):.6f} m")

    correction_rot = Rotation.from_quat(after[:, 4:]) * Rotation.from_quat(before[:, 4:]).inv()
    correction_pos = after[:, 1:4] - correction_rot.apply(before[:, 1:4])
    t0 = before[0, 0]
    knot_t = before[:, 0] - t0
    correction_interp = Slerp(knot_t, correction_rot)

    def transform(rows, label):
        rows = rows[(rows[:, 0] >= before[0, 0]) & (rows[:, 0] <= before[-1, 0])].copy()
        t = rows[:, 0] - t0
        baseline = rows.copy()
        baseline[:, 1:4] = origin_rot.apply(rows[:, 1:4]) + origin_pos
        baseline[:, 4:] = (origin_rot * Rotation.from_quat(rows[:, 4:])).as_quat()
        rotations = correction_interp(t)
        translations = np.column_stack([np.interp(t, knot_t, correction_pos[:, j]) for j in range(3)])
        adjusted = baseline.copy()
        adjusted[:, 1:4] = rotations.apply(baseline[:, 1:4]) + translations
        adjusted[:, 4:] = (rotations * Rotation.from_quat(baseline[:, 4:])).as_quat()
        save_poses(trajectory / f"{label}_before_rtk.txt", baseline)
        save_poses(trajectory / f"{label}_after_rtk.txt", adjusted)
        return adjusted

    images = transform(raw_images, "image")
    lidar = transform(raw_lidar, "lidar")
    dataset = root / "datasets/input"
    profile = root / "profile"
    cal = yaml.safe_load((profile / "camera.yaml").read_text())
    frontend_scale = float(cal["scale"])
    lvba_scale = float(os.environ["LVBA_IMAGE_SCALE"])
    source_size = (int(cal["cam_width"] * frontend_scale), int(cal["cam_height"] * frontend_scale))
    target_size = (int(cal["cam_width"] * lvba_scale), int(cal["cam_height"] * lvba_scale))
    for name in ("all_image", "all_pcd_body", "Colmap"):
        (dataset / name).mkdir(parents=True, exist_ok=True)

    image_step = int(os.environ["IMAGE_STRIDE"])
    lidar_step = int(os.environ["LIDAR_STRIDE"])
    leaf = float(os.environ["SCAN_VOXEL_M"])
    if image_step < 1 or lidar_step < 1 or leaf <= 0 or min(target_size) < 1:
        raise ValueError("Invalid image, LiDAR or voxel sampling settings")
    selected_images = images[::image_step]
    selected_lidar = lidar[::lidar_step]
    for row in selected_images:
        name = f"{row[0]:.6f}.png"
        img = cv2.imread(str(raw / "all_image" / name))
        if img is None or img.shape[1::-1] != source_size:
            raise ValueError(f"Unexpected image: {name}, {None if img is None else img.shape}")
        if not cv2.imwrite(str(dataset / "all_image" / name), cv2.resize(img, target_size, interpolation=cv2.INTER_AREA)):
            raise OSError(name)
    point_count = 0
    for row in selected_lidar:
        name = f"{row[0]:.6f}.pcd"
        cloud = read_pcd(raw / "all_pcd_body" / name)
        data = np.column_stack([cloud[field] for field in ("x", "y", "z", "intensity")])
        data = data[np.isfinite(data).all(axis=1)]
        cells = np.floor(data[:, :3] / leaf).astype(np.int32)
        _, ids = np.unique(cells, axis=0, return_index=True)
        points = data[ids]
        write_pcd(dataset / "all_pcd_body" / name, points, "intensity")
        point_count += len(points)
    # Global-LVBA's filenames use exactly six decimal places.
    np.savetxt(dataset / "all_image/image_poses.txt", selected_images, fmt=["%.6f"] + ["%.10f"] * 7)
    np.savetxt(dataset / "all_pcd_body/lidar_poses.txt", selected_lidar, fmt=["%.6f"] + ["%.10f"] * 7)
    (dataset / "Colmap/keyframes.txt").write_text("".join(f"{row[0]:.6f}.png\n" for row in selected_images))
    cfg = yaml.safe_load((profile / "lvba-template.yaml").read_text())
    cal.pop("cam_model", None)
    cal["scale"] = lvba_scale
    cfg["cam_model"] = cal
    cfg["extrin_calib"] = yaml.safe_load((profile / "frontend.yaml").read_text())["extrin_calib"]
    cfg["data_config"].update(data_path="dataset/input/", image_sample_step=1,
                              enable_lidar_ba=True, enable_visual_ba=True)
    cfg["window_ba"]["anchor_leaf_size"] = float(os.environ["BA_ANCHOR_LEAF_M"])
    cfg["gs_export"]["point_leaf_size"] = float(os.environ["BA_EXPORT_LEAF_M"])
    (root / "profile/lvba.generated.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
    opencv = [cal[key]*lvba_scale for key in ("cam_fx", "cam_fy", "cam_cx", "cam_cy")]
    opencv += [cal[f"cam_d{i}"] for i in range(4)]
    (dataset / "Colmap/camera_params.txt").write_text(",".join(map(str, opencv)) + "\n")

    data = dict(
        rtk_keyframes=len(diff), rtk_stats_m=stats(diff), rtk_peak_time=float(before[diff.argmax(), 0]),
        enu_fit_pairs=int(synchronized.sum()), enu_fit_p95_m=float(np.percentile(residual, 95)),
        raw_images=len(raw_images), raw_scans=len(raw_lidar), transferred_images=len(images),
        transferred_scans=len(lidar), lvba_images=len(selected_images), lvba_scans=len(selected_lidar),
        lvba_lidar_points=point_count, image_stride=image_step, lidar_stride=lidar_step, scan_voxel_m=leaf,
    )
    (root / "report/preparation.json").write_text(json.dumps(data, indent=2) + "\n")
    print(json.dumps(data, indent=2), flush=True)


if __name__ == "__main__":
    prepare(Path(sys.argv[1]))
