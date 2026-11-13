from pathlib import Path
import math
import sys
import numpy as np
from prepare import read_pcd, write_pcd

root = Path(sys.argv[1])
out = root / "maps/rviz_preview"
out.mkdir(exist_ok=True)
entries = {
    "livo": "frontend/global_pcd/before_optimization.pcd",
    "rtk": "frontend/global_pcd/after_optimization.pcd",
    "pre-ba": "maps/rtk_before_lidar_ba.pcd",
    "ba": "maps/after_lidar_ba.pcd",
    "ba-rgb": "datasets/input/3DGS_V6/colored_lidar_v6.pcd",
}
for key, path in entries.items():
    points = read_pcd(root / path)
    step = max(1, math.ceil(len(points)/500000))
    points = points[::step]
    f = "intensity" if "intensity" in points.dtype.names else "rgb"
    last = points[f] if f == "intensity" else points["rgb" if "rgb" in points.dtype.names else "rgba"].view("<f4")
    data = np.column_stack([points[x] for x in ("x","y","z")] + [last])
    write_pcd(out / f"{key}.pcd", data, f)
    print(key, len(data), flush=True)
