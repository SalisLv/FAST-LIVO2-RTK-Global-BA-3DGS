#!/usr/bin/env bash
# Loaded by run.sh after the frontend stage.
dataset="$run/datasets/input"

prepare() {
  analysis python /pipeline/prepare.py /run-data
}
match() {
  docker run "${docker_common[@]}" --memory 4g \
    --mount "type=bind,src=$dataset,dst=/dataset" \
    "$LVBA_IMAGE" bash /pipeline/run-matches.sh
  python3 - "$dataset/Colmap/colmap_sub5.db" <<'PY'
import sqlite3
import sys

with sqlite3.connect(sys.argv[1]) as connection:
    count, = connection.execute("SELECT count(*) FROM two_view_geometries WHERE rows > 0").fetchone()
    if count == 0:
        sys.exit("COLMAP produced no geometrically verified image pairs.")
    print(f"COLMAP verified image pairs: {count}")
PY
}
lvba() {
  docker run "${docker_common[@]}" "${ros_env[@]}" --memory 6g --memory-swap 7g \
    --mount "type=bind,src=$run/datasets,dst=/lvba_ws/src/Global-LVBA/dataset" \
    --mount "type=bind,src=$profile/lvba.generated.yaml,dst=/lvba_ws/src/Global-LVBA/config/config.yaml,readonly" \
    "$LVBA_IMAGE" bash /pipeline/run-lvba.sh
}
prepare_gs() {
  analysis python /pipeline/prepare_gs.py /run-data
}
train() {
  docker run "${docker_common[@]}" --gpus all --memory 5g --memory-swap 5632m \
    --mount "type=bind,src=$dataset/3DGS_train,dst=/dataset,readonly" \
    --mount "type=bind,src=$root/src/gaussian-splatting/scene/gaussian_model.py,dst=/opt/gaussian-splatting/scene/gaussian_model.py,readonly" \
    "$GS_IMAGE" bash /pipeline/run-3dgs.sh
}
verify() {
  mkdir -p "$run/maps" "$run/report/figures"
  analysis bash -e -c '
    python /pipeline/compare_maps.py /run-data rtk
    python /pipeline/compare_maps.py /run-data lvba
    python /pipeline/rviz_previews.py /run-data
    python /pipeline/compare_renders.py /run-data
    python /pipeline/summarize.py /run-data
  '
}
stage prepare prepare datasets frontend/TUM/image_before_rtk.txt frontend/TUM/image_after_rtk.txt frontend/TUM/lidar_before_rtk.txt frontend/TUM/lidar_after_rtk.txt report/preparation.json profile/lvba.generated.yaml
stage matches match datasets/input/Colmap/colmap_sub5.db datasets/input/Colmap/colmap_sub5.db-wal datasets/input/Colmap/colmap_sub5.db-shm
stage lvba lvba datasets/input/3DGS_V6 datasets/input/reproj
stage prepare-gs prepare_gs datasets/input/3DGS_train report/gs_preparation.json
stage train train 3dgs
stage verify verify maps report/figures report/rtk_map_stats.json report/lvba_map_stats.json report/render_stats.json results.json
printf 'Complete. Results: %s\n' "$run"
