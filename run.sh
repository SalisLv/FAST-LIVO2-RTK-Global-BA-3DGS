#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
usage() {
  echo 'Usage: ./run.sh --bag FILE [--profile DIRECTORY] [--run-dir DIRECTORY] [--resume]'
}
bag= profile="$root/profiles/hh-lvgo" run= resume=false
while (($#)); do
  case "$1" in
    --bag|--profile|--run-dir)
      if (($# < 2)); then usage >&2; exit 2; fi
      case "$1" in
        --bag) bag=$2 ;;
        --profile) profile=$2 ;;
        --run-dir) run=$2 ;;
      esac
      shift 2 ;;
    --resume) resume=true; shift ;;
    --help|-h) usage; exit ;;
    *) usage >&2; exit 2 ;;
  esac
done
if [[ ! -f "$bag" || ! -s "$bag" || ! -r "$bag" ]]; then
  echo "Specify a readable, nonempty ROS 1 bag with --bag." >&2
  exit 2
fi
bag=$(realpath -- "$bag")
profile=$(realpath -- "$profile")
for f in frontend.yaml camera.yaml lvba-template.yaml pipeline.env; do
  test -s "$profile/$f" || { echo "Missing device profile file: $profile/$f" >&2; exit 2; }
done
if [[ -z "$run" ]]; then
  if "$resume"; then echo '--resume requires --run-dir.' >&2; exit 2; fi
  mkdir -p "$root/runs"
  run=$(mktemp -d -- "$root/runs/$(basename "$bag" .bag)-XXXXXXXX")
else
  run=$(realpath -m -- "$run")
  if "$resume"; then
    test -d "$run/.stages" || { echo "Unknown run: $run" >&2; exit 2; }
  else
    mkdir -p -- "$(dirname -- "$run")"
    mkdir -- "$run" || { echo 'Choose a new --run-dir or use --resume.' >&2; exit 2; }
  fi
fi
mkdir -p "$run"/{logs,report,.stages}
exec 8>"$run/.lock"
flock -n 8 || { echo "Run already active: $run" >&2; exit 1; }
bag_id=$(stat -Lc '%d:%i:%s:%Y' -- "$bag")
if "$resume"; then
  if [[ $(cat "$run/.bag-path") != "$bag" || $(cat "$run/.bag-id") != "$bag_id" ]]; then
    echo 'This run used a different bag. Choose a new run directory.' >&2
    exit 2
  fi
else
  printf '%s\n' "$bag" > "$run/.bag-path"
  printf '%s\n' "$bag_id" > "$run/.bag-id"
  mkdir "$run/profile"
  cp -- "$profile/"{frontend.yaml,camera.yaml,lvba-template.yaml,pipeline.env} "$run/profile/"
fi
profile=$run/profile
# shellcheck source=/dev/null
source "$profile/pipeline.env"
: "${FRONTEND_IMAGE:=bag-to-3dgs-frontend:local}"
: "${LVBA_IMAGE:=bag-to-3dgs-lvba:local}"
: "${GS_IMAGE:=bag-to-3dgs-train:local}"
: "${ANALYSIS_IMAGE:=bag-to-3dgs-analysis:local}"
source "$root/scripts/stages.sh"
printf 'Run directory: %s\n' "$run"
stage() {
  local name=$1
  local action=$2
  shift 2
  if [[ -f "$run/.stages/$name" ]]; then
    printf '[%s] already complete\n' "$name"
    return
  fi
  printf '[%s] starting\n' "$name"
  local path archived=
  for path in "$@"; do
    if [[ -e "$run/$path" ]]; then
      if [[ -z "$archived" ]]; then
        mkdir -p "$run/attempts"
        archived=$(mktemp -d -- "$run/attempts/$name-XXXXXXXX")
      fi
      mkdir -p "$archived/$(dirname -- "$path")"
      mv -- "$run/$path" "$archived/$path"
    fi
  done
  set +e
  ( set -e; "$action" ) >"$run/logs/stage-$name.log" 2>&1
  local status=$?
  set -e
  if ((status != 0)); then
    tail -35 "$run/logs/stage-$name.log" >&2
    printf '[%s] failed. See %s/logs/\n' "$name" "$run" >&2
    exit 1
  fi
  touch "$run/.stages/$name"
  printf '[%s] complete\n' "$name"
}
for img in "$FRONTEND_IMAGE" "$LVBA_IMAGE" "$GS_IMAGE" "$ANALYSIS_IMAGE"; do
  docker image inspect "$img" >/dev/null 2>&1 || { echo "Missing Docker image $img. Run ./build.sh first." >&2; exit 1; }
done
stage frontend frontend frontend raw
source "$root/scripts/downstream.sh"
