#!/bin/bash
set -euo pipefail
export QT_QPA_PLATFORM=offscreen OMP_NUM_THREADS=4
cd /dataset
test ! -e Colmap/colmap_sub5.db
colmap feature_extractor \
  --database_path Colmap/colmap_sub5.db --image_path all_image --image_list_path Colmap/keyframes.txt \
  --ImageReader.single_camera 1 --ImageReader.camera_model OPENCV \
  --ImageReader.camera_params "$(cat Colmap/camera_params.txt)" \
  --SiftExtraction.use_gpu 0 --SiftExtraction.num_threads 6 --SiftExtraction.max_num_features "$MATCH_FEATURES"
colmap sequential_matcher --database_path Colmap/colmap_sub5.db \
  --SiftMatching.use_gpu 0 --SiftMatching.num_threads 6 \
  --SequentialMatching.overlap "$MATCH_OVERLAP" --SequentialMatching.quadratic_overlap 0 --SequentialMatching.loop_detection 0
