#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
if (( $# != 2 )); then echo 'Usage: ./view-map.sh RUN_DIR {livo|rtk|pre-ba|ba|ba-rgb}' >&2; exit 2; fi
run=$(realpath -- "$1")
case "$2" in
  livo|rtk|ba-rgb) config=maps.rviz ;;
  pre-ba|ba) config=maps-intensity.rviz ;;
  *) echo "Unknown map: $2" >&2; exit 2 ;;
esac
pcd="$run/maps/rviz_preview/$2.pcd"
test -s "$pcd" || { echo "Missing preview: $pcd" >&2; exit 1; }
gpu=()
if [[ -e /dev/dxg && -d /usr/lib/wsl ]]; then
  gpu=(--device /dev/dxg -v /usr/lib/wsl:/usr/lib/wsl:ro
    -e LD_LIBRARY_PATH=/usr/lib/wsl/lib -e GALLIUM_DRIVER=d3d12)
fi
docker run --rm --network none --user "$(id -u):$(id -g)" \
  -e HOME=/tmp -e ROS_HOME=/tmp/.ros -e ROS_IP=127.0.0.1 -e ROS_MASTER_URI=http://127.0.0.1:11311 \
  -e "DISPLAY=${DISPLAY:-:0}" -e QT_X11_NO_MITSHM=1 "${gpu[@]}" \
  --mount type=bind,src=/tmp/.X11-unix,dst=/tmp/.X11-unix,readonly \
  --mount "type=bind,src=$root/scripts,dst=/pipeline,readonly" \
  --mount "type=bind,src=$pcd,dst=/map.pcd,readonly" \
  "${FRONTEND_IMAGE:-bag-to-3dgs-frontend:local}" bash -c \
    'source /opt/ros/noetic/setup.bash; exec roslaunch /pipeline/maps.launch pcd_file:=/map.pcd "config_file:=/pipeline/$1"' bash "$config"
