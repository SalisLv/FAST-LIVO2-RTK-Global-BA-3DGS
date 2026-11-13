"""Record verified output paths and the final Visual BA pose status."""
import json
from pathlib import Path
import os
import sys

root = Path(sys.argv[1])
iteration = int(os.environ["TRAIN_ITERATIONS"])
base = "datasets/input/3DGS_V6"
files = {
    "rtk_trajectory": "frontend/TUM/enu_imu_after_rtk.txt",
    "rtk_map": "frontend/global_pcd/after_optimization.pcd",
    "lidar_ba_trajectory": f"{base}/densify/lidar_after_twi.txt",
    "camera_poses": f"{base}/sparse/0/images.txt",
    "lidar_ba_map": "maps/after_lidar_ba.pcd",
    "colored_lidar_map": f"{base}/colored_lidar_v6.pcd",
    "gaussian_model": f"3dgs/point_cloud/iteration_{iteration}/point_cloud.ply",
}
for name, relative in files.items():
    path = root / relative
    if not path.is_file() or path.stat().st_size == 0:
        raise FileNotFoundError(f"Missing {name}: {path}")

log = (root / "logs/global-lvba.log").read_text(errors="replace")
if "pose guard rejected solution" in log:
    visual_ba = "rejected_by_pose_guard"
elif "[optimizeCamPoses] done." in log:
    visual_ba = "accepted"
else:
    visual_ba = "kept_lidar_initialized_poses"
render = json.loads((root / "report/render_stats.json").read_text())
summary = {"outputs": files, "visual_ba": visual_ba, "render_metrics": render}
(root / "results.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps(summary, indent=2))
