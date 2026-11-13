#!/usr/bin/env bash
set -eo pipefail
source /gunda_ws/devel/setup.bash
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=2
read -r transport camera_topic <<< "$(python3 /pipeline/preflight.py)"
mapper= republisher= master=
cleanup() {
  for pid in "$mapper" "$republisher" "$master"; do
    if [ -n "$pid" ]; then kill -INT "$pid" 2>/dev/null || true; fi
  done
  wait || true
}
trap cleanup EXIT
roscore >/run-data/logs/roscore.log 2>&1 &
master=$!
for attempt in {1..30}; do
  if rosparam list >/dev/null 2>&1; then break; fi
  sleep 1
done
rosparam set /use_sim_time true
rosparam load /profile/frontend.yaml
rosparam load /profile/camera.yaml /laserMapping
rosparam set /laserMapping/outputfilepath /run-data/frontend
if [ "$transport" = compressed ]; then
  rosrun image_transport republish compressed "in:=$camera_topic" raw "out:=$camera_topic" >/run-data/logs/image-transport.log 2>&1 &
  republisher=$!
fi
fifo=$(mktemp -d)/trigger-offline
mkfifo "$fifo"
exec 9<>"$fifo"
stdbuf -oL -eL rosrun fast_livo_rtk fastlivo_mapping __name:=laserMapping <&9 9<&- >/run-data/logs/frontend.log 2>&1 &
mapper=$!
sleep 4
kill -0 "$mapper"
rosbag play --clock -r "$BAG_RATE" -d 2 /input.bag >/run-data/logs/rosbag.log 2>&1
sleep 8
kill -0 "$mapper"
printf '\n' >&9
for attempt in {1..300}; do
  if grep -Fq '[Offline Optimization] Finished.' /run-data/logs/frontend.log; then
    for path in frontend/TUM/{aligned_imu_before_rtk,enu_imu_after_rtk}.txt frontend/global_pcd/{before_optimization,after_optimization}.pcd raw/all_image/image_poses.txt raw/all_pcd_body/lidar_poses.txt; do
      test -s "/run-data/$path"
    done
    exit 0
  fi
  if ! kill -0 "$mapper" || grep -Fq 'RTK alignment failed' /run-data/logs/frontend.log; then
    tail -35 /run-data/logs/frontend.log >&2
    exit 1
  fi
  sleep 2
done
echo 'Offline RTK optimization did not complete within 10 minutes.' >&2
exit 1
