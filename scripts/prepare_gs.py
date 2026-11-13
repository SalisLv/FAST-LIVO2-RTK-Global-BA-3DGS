import json
import os
from pathlib import Path
import shutil
import sys
import numpy as np
from plyfile import PlyData, PlyElement

root = Path(sys.argv[1])
dataset = root / "datasets/input/3DGS_V6"
sparse = dataset / "sparse/0"
train = dataset.parent / "3DGS_train"
train_sparse = train / "sparse/0"
train_sparse.mkdir(parents=True)
shutil.copytree(dataset / "images", train / "images", copy_function=os.link)
for name in ("images.txt", "cameras.txt"):
    shutil.copyfile(sparse / name, train_sparse / name)
files = sorted((train / "images").glob("*.png"))
poses = (train_sparse / "images.txt").read_text().splitlines()
poses = [line.split() for line in poses if line.strip() and not line.startswith("#")][::2]
assert {p[9] for p in poses} == {path.name for path in files} and len(poses) == len(files) >= 2
data = np.loadtxt(sparse / "points3D.txt", usecols=(1, 2, 3, 4, 5, 6), dtype=np.float32, ndmin=2)
assert len(data) > 10000 and np.isfinite(data).all()
point_limit = int(os.environ["TRAIN_POINT_LIMIT"])
if point_limit < 1:
    raise ValueError("TRAIN_POINT_LIMIT must be positive")
leaf = 0.0
while True:
    if leaf == 0 and len(data) <= point_limit:
        reduced = data
        break
    leaf = leaf * 1.25 if leaf else 0.12
    cells = np.floor(data[:, :3] / leaf).astype(np.int32)
    _, ids, count = np.unique(cells, axis=0, return_inverse=True, return_counts=True)
    if len(count) <= point_limit:
        reduced = np.column_stack([np.bincount(ids.reshape(-1), weights=data[:, j]) / count for j in range(6)])
        break
records = np.zeros(len(reduced), dtype=[(x, "f4") for x in ("x","y","z","nx","ny","nz")] +
                                      [(x, "u1") for x in ("red","green","blue")])
for j, name in enumerate(("x", "y", "z", "red", "green", "blue")):
    records[name] = reduced[:, j] if j < 3 else np.rint(reduced[:, j])
PlyData([PlyElement.describe(records, "vertex")]).write(train_sparse / "points3D.ply")
summary = dict(images=len(files), initial_points=int(len(data)), training_points=int(len(reduced)), additional_voxel_m=leaf)
(root / "report/gs_preparation.json").write_text(json.dumps(summary, indent=2) + "\n")
print(summary, flush=True)
