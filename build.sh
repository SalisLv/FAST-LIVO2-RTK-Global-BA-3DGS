#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
if (($#)); then echo 'Usage: ./build.sh' >&2; exit 2; fi
bash scripts/fetch-sources.sh
docker build -f docker/ros.Dockerfile -t bag-to-3dgs-ros:local .
docker build -f docker/ros-sophus.Dockerfile -t bag-to-3dgs-ros-dev:local docker
docker build -f docker/frontend.Dockerfile -t bag-to-3dgs-frontend:local src
docker build -f docker/lvba/Dockerfile -t bag-to-3dgs-lvba-base:local .
docker build -f docker/lvba/Dockerfile.program -t bag-to-3dgs-lvba:local src/Global-LVBA
docker build --build-arg "CUDA_ARCH_LIST=${CUDA_ARCH_LIST:-8.0;8.6;8.9;9.0;12.0}" -f docker/3dgs/Dockerfile -t bag-to-3dgs-cuda:local docker/3dgs
docker build -f docker/3dgs/Dockerfile.extensions -t bag-to-3dgs-train:local src/gaussian-splatting
docker build -f docker/analysis.Dockerfile -t bag-to-3dgs-analysis:local docker
