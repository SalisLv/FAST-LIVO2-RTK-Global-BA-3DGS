#!/bin/bash
set -eo pipefail
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=2
source /lvba_ws/devel/setup.bash
log=/run-data/logs/global-lvba.log
roslaunch Global-LVBA lvba.launch rviz:=false >"$log" 2>&1 &
launcher=$!
cleanup() {
  kill -INT "$launcher" 2>/dev/null || true
  wait "$launcher" || true
}
trap cleanup EXIT
for attempt in {1..1200}; do
  if grep -qF '[3DGSExport] done' "$log"; then
    exit 0
  fi
  if ! kill -0 "$launcher" 2>/dev/null || grep -qF 'process has died' "$log"; then
    tail -50 "$log" >&2
    exit 1
  fi
  sleep 2
done
echo 'Global-LVBA did not reach the export completion marker.' >&2
exit 1
