#!/usr/bin/env bash
# Loaded by run.sh with the project, profile, run and bag paths resolved.
docker_common=(--rm --network none --user "$(id -u):$(id -g)" -e HOME=/tmp
  --mount "type=bind,src=$root/scripts,dst=/pipeline,readonly"
  --mount "type=bind,src=$run,dst=/run-data"
  --env-file "$profile/pipeline.env")
ros_env=(-e ROS_HOME=/tmp/.ros -e ROS_IP=127.0.0.1 -e ROS_MASTER_URI=http://127.0.0.1:11311)
analysis() {
  docker run "${docker_common[@]}" --memory 3g -e MPLCONFIGDIR=/tmp/mpl "$ANALYSIS_IMAGE" "$@"
}
frontend() {
  mkdir -p "$run/frontend/"{TUM,global_pcd,debug,vel,scan_pcd} "$run/raw"
  docker run "${docker_common[@]}" "${ros_env[@]}" --memory 5g --memory-swap 6g \
    --mount "type=bind,src=$bag,dst=/input.bag,readonly" \
    --mount "type=bind,src=$profile,dst=/profile,readonly" \
    --mount "type=bind,src=$run/raw,dst=/gunda_ws/src/FAST-LIVO2-RTK/Log/GlobalLVBA/pipeline" \
    "$FRONTEND_IMAGE" bash /pipeline/run-frontend.sh
}
