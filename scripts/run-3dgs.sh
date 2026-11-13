#!/usr/bin/env bash
set -euo pipefail
cd /opt/gaussian-splatting
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=2
python -u train.py -s /dataset -m /run-data/3dgs \
  --iterations "$TRAIN_ITERATIONS" --save_iterations 3000 7500 "$TRAIN_ITERATIONS" \
  --test_iterations 3000 7500 "$TRAIN_ITERATIONS" --checkpoint_iterations 3000 7500 12000 \
  --densify_grad_threshold "$DENSIFY_GRAD" --densify_until_iter "$DENSIFY_UNTIL" \
  --eval --resolution 1 --data_device cpu --disable_viewer > /run-data/logs/3dgs-train.log 2>&1
python -u render.py -m /run-data/3dgs --iteration "$TRAIN_ITERATIONS" > /run-data/logs/3dgs-render.log 2>&1
test -s "/run-data/3dgs/point_cloud/iteration_$TRAIN_ITERATIONS/point_cloud.ply"
